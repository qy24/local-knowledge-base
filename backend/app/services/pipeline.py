"""入库流水线：解析 → 切分 → 向量化 → 图谱抽取。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Chunk, Document, KnowledgeBase, Task
from ..stores import get_graph_store, get_vector_store
from . import chunking, llm as llm_svc, parsing
from .embedding import get_embedder


def _doc_status(doc: Document, status: str) -> None:
    doc.status = status


def process_document(db: Session, doc_id: int, settings: Settings) -> dict:
    """处理单个文档的完整流水线。返回统计信息。"""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: {doc_id}")
    kb = db.get(KnowledgeBase, doc.kb_id)
    if kb is None:
        raise ValueError(f"知识库不存在: {doc.kb_id}")

    embedder = get_embedder(settings, kb.embedding_model)
    vstore = get_vector_store(settings)
    gstore = get_graph_store(settings)

    chunk_size = kb.chunk_size or settings.default_chunk_size
    chunk_overlap = kb.chunk_overlap or settings.default_chunk_overlap

    stats = {"blocks": 0, "chunks": 0, "entities": 0, "relations": 0}

    # ① 解析
    _doc_status(doc, "解析中")
    db.commit()
    blocks = parsing.extract_blocks(doc.file_path)
    stats["blocks"] = len(blocks)
    doc.page_count = len(blocks)

    # ② 切分
    _doc_status(doc, "切分中")
    db.commit()
    pieces = chunking.split_blocks(blocks, chunk_size, chunk_overlap)
    # 清理旧的 chunks/向量/图谱（重解析场景）
    old_chunks = db.query(Chunk).filter(Chunk.doc_id == doc.id).all()
    old_ids = [c.id for c in old_chunks]
    for c in old_chunks:
        db.delete(c)
    db.commit()
    if old_ids:
        try:
            vstore.delete_by_doc(doc.id)
            gstore.delete_by_doc(doc.id)
        except Exception:
            pass
    chunk_rows: list[Chunk] = []
    for i, (content, meta) in enumerate(pieces):
        chunk_rows.append(Chunk(
            kb_id=doc.kb_id, doc_id=doc.id, seq=i, content=content,
            meta=meta, embedding_status="pending",
        ))
    db.add_all(chunk_rows)
    db.commit()
    stats["chunks"] = len(chunk_rows)
    for cr in chunk_rows:
        db.refresh(cr)

    # ③ 向量化（批量）
    _doc_status(doc, "向量化中")
    db.commit()
    texts = [c.content for c in chunk_rows]
    vectors = []
    for i in range(0, len(texts), settings.embedding_batch_size):
        batch = texts[i:i + settings.embedding_batch_size]
        vectors.extend(embedder.embed_documents(batch))
        doc.status = "向量化中"
        db.commit()
    for cr, vec in zip(chunk_rows, vectors):
        page = cr.meta.get("page", 1)
        vstore.upsert(
            kb_id=doc.kb_id, doc_id=doc.id, chunk_id=cr.id, seq=cr.seq,
            vector=vec, doc_name=doc.filename, page=page,
        )
        cr.embedding_status = "done"
    db.commit()

    # ④ 图谱抽取（LLM，按批）
    if kb.graph_extraction_enabled and settings.graph_extraction_enabled:
        _doc_status(doc, "图谱抽取中")
        db.commit()
        llm = llm_svc.resolve_llm(settings, kb)
        if llm.configured():
            batch = settings.graph_batch_chunks
            seen_entities: dict[tuple[int, str], str] = {}
            for i in range(0, len(chunk_rows), batch):
                group = chunk_rows[i:i + batch]
                result = llm_svc.extract_graph(llm, [c.content for c in group])
                for ent in result.get("entities", []):
                    name = str(ent.get("name", "")).strip()
                    if not name:
                        continue
                    eid = gstore.upsert_entity(
                        kb_id=doc.kb_id, name=name,
                        etype=str(ent.get("type", "术语")),
                        properties={}, source_doc_id=doc.id,
                        source_chunk_id=group[0].id,
                    )
                    seen_entities[(doc.kb_id, name)] = eid
                    stats["entities"] += 1
                for rel in result.get("relations", []):
                    src = str(rel.get("source", "")).strip()
                    tgt = str(rel.get("target", "")).strip()
                    rtype = str(rel.get("type", "")).strip()
                    if not src or not tgt or not rtype:
                        continue
                    if (doc.kb_id, src) not in seen_entities:
                        gstore.upsert_entity(kb_id=doc.kb_id, name=src, etype="术语",
                                             properties={}, source_doc_id=doc.id,
                                             source_chunk_id=group[0].id)
                    if (doc.kb_id, tgt) not in seen_entities:
                        gstore.upsert_entity(kb_id=doc.kb_id, name=tgt, etype="术语",
                                             properties={}, source_doc_id=doc.id,
                                             source_chunk_id=group[0].id)
                    try:
                        gstore.upsert_relation(
                            kb_id=doc.kb_id, src_name=src, tgt_name=tgt,
                            rel_type=rtype, properties={},
                            source_doc_id=doc.id, source_chunk_id=group[0].id,
                        )
                        stats["relations"] += 1
                    except ValueError:
                        pass
        # 实体名去重统计修正（upsert 合并同名）
        entities, _ = gstore.count()  # noqa: F841
    else:
        _doc_status(doc, "图谱抽取中")
        db.commit()

    _doc_status(doc, "完成")
    doc.error_msg = ""
    db.commit()
    return stats


def reembed_chunk(db: Session, chunk_id: int, settings: Settings) -> None:
    """编辑切分块后重新向量化（增量更新）。"""
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        raise ValueError(f"切分块不存在: {chunk_id}")
    kb = db.get(KnowledgeBase, chunk.kb_id)
    embedder = get_embedder(settings, kb.embedding_model if kb else "")
    vstore = get_vector_store(settings)
    vec = embedder.embed_documents([chunk.content])[0]
    doc = db.get(Document, chunk.doc_id)
    page = chunk.meta.get("page", 1)
    vstore.upsert(
        kb_id=chunk.kb_id, doc_id=chunk.doc_id, chunk_id=chunk.id, seq=chunk.seq,
        vector=vec, doc_name=doc.filename if doc else "", page=page,
    )
    chunk.embedding_status = "done"
    db.commit()
