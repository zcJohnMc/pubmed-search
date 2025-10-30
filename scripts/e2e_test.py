import json
import time
import random
import requests

BASE = "http://127.0.0.1:5000"

TOPICS = [
    "肠道微生物群与抑郁症的关系",
    "CRISPR 基因编辑在癌症治疗中的应用与安全性",
    "间歇性禁食对代谢综合征的影响",
]

random.shuffle(TOPICS)

SUMMARY = []

for idx, topic in enumerate(TOPICS, 1):
    sess = requests.Session()
    print(f"\n=== Case {idx}: {topic} ===")

    # 1) AI 生成查询
    query = None
    try:
        r = sess.post(f"{BASE}/api/generate_query", json={"topic": topic}, timeout=60)
        data = r.json()
        if data.get("success"):
            query = data.get("query")
            print("AI生成查询: ", query[:120].replace("\n"," ") + ("..." if len(query) > 120 else ""))
        else:
            print("AI生成失败: ", data.get("error"))
    except Exception as e:
        print("AI生成异常:", e)

    # Fallback: 简易查询（限制年份与类型，避免结果过多）
    if not query:
        query = f"{topic} AND review[Publication Type] AND (2024:2025[dp])"
        print("使用回退查询:", query)

    # 2) 发起搜索
    payload = {
        "query": query,
        "user_topic": topic,
        "ai_generated_query": query,
        "journal_filter": "Nature, Science, Cell",
        "min_year": "2024",
        "max_year": "2025",
        "min_score": 5,
        "article_types": ["Review"],
    }

    try:
        r = sess.post(f"{BASE}/api/search", json=payload, timeout=30)
        sdata = r.json()
        if not sdata.get("success"):
            print("启动搜索失败:", sdata.get("error"))
            SUMMARY.append({"topic": topic, "status": "failed_to_start", "error": sdata.get("error")})
            continue
        sid = sdata["search_session_id"]
        print("搜索会话:", sid)
    except Exception as e:
        print("启动搜索异常:", e)
        SUMMARY.append({"topic": topic, "status": "failed_to_start", "error": str(e)})
        continue

    # 3) 轮询进度（最多 90 秒）
    status = "unknown"
    search_id = None
    message = None
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            r = sess.get(f"{BASE}/api/search_progress/{sid}", timeout=30)
            pdata = r.json()
            if pdata.get("success"):
                prog = pdata.get("progress", {})
                status = prog.get("status")
                pct = prog.get("progress")
                message = prog.get("message")
                print(f"  进度: {pct}% | 状态: {status} | {message}")
                if status == "completed":
                    search_id = prog.get("search_id")
                    break
                if status == "error":
                    break
            else:
                print("  进度获取失败")
        except Exception as e:
            print("  进度异常:", e)
        time.sleep(2)

    # 4) 导出结果（使用历史导出，避免依赖会话）
    if status == "completed" and search_id:
        try:
            r = sess.get(f"{BASE}/api/export_history/{search_id}/json", timeout=60)
            edata = r.json()
            if edata.get("success"):
                articles = edata["data"].get("articles", [])
                print(f"完成：共 {len(articles)} 篇")
                SUMMARY.append({"topic": topic, "status": "ok", "count": len(articles)})
            else:
                print("导出失败:", edata.get("error"))
                SUMMARY.append({"topic": topic, "status": "export_failed", "error": edata.get("error")})
        except Exception as e:
            print("导出异常:", e)
            SUMMARY.append({"topic": topic, "status": "export_exception", "error": str(e)})
    else:
        print("未完成：", message)
        SUMMARY.append({"topic": topic, "status": status or "unknown", "message": message})

print("\n==== 汇总 ====")
print(json.dumps(SUMMARY, ensure_ascii=False, indent=2))

