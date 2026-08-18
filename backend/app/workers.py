"""进程内任务队列 worker：轮询 tasks 表，执行入库/增量任务。

单机场景无需 Redis/Celery；生产如需横向扩展可替换为 Celery。
"""
from __future__ import annotations

import logging
import threading
import time

from .config import get_settings
from .database import SessionLocal
from .models import Task
from .services.pipeline import process_document, reembed_chunk

logger = logging.getLogger("kb.worker")

_STOP = threading.Event()
_THREAD: threading.Thread | None = None


def _run_task(task: Task) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        ttype = task.type
        if ttype == "process_document":
            stats = process_document(db, int(task.params.get("doc_id")), settings)
            task.result = {"stats": stats}
            task.status = "done"
            task.progress = 100.0
        elif ttype == "reembed_chunk":
            reembed_chunk(db, int(task.params.get("chunk_id")), settings)
            task.status = "done"
            task.progress = 100.0
        else:
            task.status = "error"
            task.error_msg = f"未知任务类型: {ttype}"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        try:
            task = db.get(Task, task.id)
            task.status = "error"
            task.error_msg = str(exc)
            doc_id = task.params.get("doc_id")
            if doc_id:
                from .models import Document
                doc = db.get(Document, int(doc_id))
                if doc:
                    doc.status = "失败"
                    doc.error_msg = str(exc)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        logger.exception("任务 %s 执行失败: %s", task.id, exc)
    finally:
        db.close()


def _loop() -> None:
    while not _STOP.is_set():
        db = SessionLocal()
        try:
            task = (db.query(Task)
                    .filter(Task.status == "pending")
                    .order_by(Task.id)
                    .first())
            if task is not None:
                task.status = "running"
                db.commit()
                db.refresh(task)
                _run_task(task)
        except Exception:  # noqa: BLE001
            logger.exception("worker 轮询异常")
        finally:
            db.close()
        time.sleep(1.0)


def start_worker() -> None:
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, name="kb-worker", daemon=True)
    _THREAD.start()
    logger.info("任务 worker 已启动")


def stop_worker() -> None:
    _STOP.set()
    if _THREAD is not None:
        _THREAD.join(timeout=3)
