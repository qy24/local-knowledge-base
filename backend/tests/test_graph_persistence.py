"""回归测试：本地图存储必须增量持久化（修复：之前仅 close() 时保存，强杀进程会丢数据）。

模拟"重启"：对同一数据目录创建新的 LocalGraphStore 实例，验证数据已落盘可恢复。
"""
from __future__ import annotations

import os
import shutil

os.environ["DATA_DIR"] = "./test_graph_data"
os.environ["GRAPH_BACKEND"] = "local"

for _p in ("test_graph_data",):
    if os.path.isdir(_p):
        shutil.rmtree(_p, ignore_errors=True)
    elif os.path.exists(_p):
        os.remove(_p)

from app.config import get_settings  # noqa: E402
from app.stores.graph import LocalGraphStore  # noqa: E402


def test_local_graph_store_incremental_persistence():
    settings = get_settings()
    path = settings.data_dir_path / "graph.json"

    # 实例 A：写入实体/关系/编辑/删除 后必须立即落盘
    a = LocalGraphStore(settings)
    e1 = a.upsert_entity(kb_id=1, name="设备A", etype="设备", properties={},
                         source_doc_id=None, source_chunk_id=None)
    e2 = a.upsert_entity(kb_id=1, name="维护周期", etype="术语", properties={},
                         source_doc_id=None, source_chunk_id=None)
    a.upsert_relation(kb_id=1, src_name="设备A", tgt_name="维护周期", rel_type="具有",
                      properties={}, source_doc_id=None, source_chunk_id=None)
    a.update_entity(e1, {"verified": True})

    # 立即检查文件已写盘（不等 close）
    assert path.exists(), "增删改后应立即写盘"
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["entities"]) == 2, data
    assert len(data["relations"]) == 1, data

    # 实例 B：模拟进程重启，重新加载同一目录
    b = LocalGraphStore(settings)
    ents, total = b.list_entities(1, 100, 0)
    assert total == 2, f"重启后实体丢失: {total}"
    assert any(e["name"] == "设备A" and e["verified"] for e in ents)
    rels, rtotal = b.list_relations(1, 100, 0)
    assert rtotal == 1, f"重启后关系丢失: {rtotal}"

    # 覆盖语义：同一对实体改关系类型，只保留一条（不新增重复边）
    b.upsert_relation(kb_id=1, src_name="设备A", tgt_name="维护周期", rel_type="需要",
                      properties={}, source_doc_id=None, source_chunk_id=None)
    rels2, rtotal2 = b.list_relations(1, 100, 0)
    assert rtotal2 == 1, f"改类型后不应新增重复关系: {rtotal2}"
    assert rels2[0]["relation_type"] == "需要", rels2

    # 删除与合并也要立即落盘
    b.delete_relation(rels2[0]["id"])
    b.delete_entity(e2)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["entities"]) == 1 and len(data["relations"]) == 0

    a.close()
    b.close()

    # 清理
    shutil.rmtree("test_graph_data", ignore_errors=True)
