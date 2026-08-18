"""格式演示：展示各文件类型经流水线后"做成什么样子"（临时知识库，演示后自动清理）。

用法：python scripts/demo_formats.py [base_url]
默认 base_url = http://127.0.0.1:8002
"""
from __future__ import annotations

import io
import json
import sys
import time

import httpx
import openpyxl

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8002"


def main() -> None:
    c = httpx.Client(timeout=120)
    tok = c.post(f"{BASE}/api/admin/login",
                 json={"username": "admin", "password": "admin123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    kb = c.post(f"{BASE}/api/admin/kbs",
                json={"name": "格式演示(临时)", "description": "演示后自动删除"}, headers=h).json()["id"]

    # 规整 Excel：有表头、一行为一条记录
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "设备台账"
    ws.append(["设备编号", "名称", "维护周期", "责任人"])
    ws.append(["EQ-001", "空压机", "每周", "张三"])
    ws.append(["EQ-002", "冷水机组", "每月", "李四"])
    buf = io.BytesIO()
    wb.save(buf)
    d1 = c.post(f"{BASE}/api/admin/kbs/{kb}/documents", headers=h,
                files={"file": ("设备台账.xlsx", buf.getvalue(),
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                ).json()["id"]

    # 规整 Markdown：标题层级清晰
    md = "# 巡检规程\n\n## 巡检频率\n\n每日一次，记录温度与压力。\n\n## 异常处理\n\n温度超过80度需停机检修。"
    d2 = c.post(f"{BASE}/api/admin/kbs/{kb}/documents", headers=h,
                files={"file": ("巡检规程.md", md.encode("utf-8"), "text/markdown")}).json()["id"]

    def wait(doc: int) -> str:
        for _ in range(120):
            s = c.get(f"{BASE}/api/admin/documents/{doc}", headers=h).json()["status"]
            if s in ("完成", "失败"):
                return s
            time.sleep(0.5)
        return "超时"

    print(f"xlsx 处理: {wait(d1)} | md 处理: {wait(d2)}")

    for doc, name in [(d1, "Excel「设备台账.xlsx」"), (d2, "MD「巡检规程.md」")]:
        chunks = c.get(f"{BASE}/api/admin/kbs/{kb}/chunks", headers=h,
                       params={"doc_id": doc}).json()
        print(f"\n--- {name} => 切分块 {len(chunks)} 个 ---")
        for ch in chunks[:5]:
            meta = json.dumps(ch["metadata"], ensure_ascii=False)
            print(f"  seq#{ch['seq']}  元数据: {meta}")
            print(f"           内容: {ch['content'][:70].replace(chr(10), ' / ')}")

    ents = c.get(f"{BASE}/api/admin/kbs/{kb}/entities", headers=h).json()["total"]
    rels = c.get(f"{BASE}/api/admin/kbs/{kb}/relations", headers=h).json()["total"]
    print(f"\n图谱: 实体={ents} 关系={rels}（当前实例未配置云端大模型，抽取为空）")

    c.delete(f"{BASE}/api/admin/kbs/{kb}", headers=h)
    print("临时知识库已清理")


if __name__ == "__main__":
    main()
