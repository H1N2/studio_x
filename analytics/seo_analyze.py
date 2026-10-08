#!/usr/bin/env python3
"""ToolPilot SEO 分析器：技术健康检查 + 长尾机会挖掘。
输出 analytics/seo-report.json，并在 stdout 打印中文简报。
对网络抖动容忍：单项检查失败记为 unknown，不中断整体。
"""
import json, re, sys, glob, os
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET
import yaml

BASE = "https://www.161808.xyz"
SITE_DIR = os.path.expanduser("~/workspace/sites/161808.xyz")
GOAL_DIR = os.path.expanduser("~/workspace/goals/www-161808-xyz-adsense")
SGT = timezone(timedelta(hours=8))
TIMEOUT = 15

report = {
    "generated_at": datetime.now(SGT).isoformat(timespec="seconds"),
    "checks": {},
    "crawlers": {},
    "content_gaps": [],
    "orphans": [],
    "backlog_top5": [],
    "health_score": None,
}

def fetch(path):
    try:
        req = Request(BASE + path, headers={"User-Agent": "ToolPilot-SEO-Analyzer/1.0"})
        with urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)

def check(name, ok, detail=""):
    report["checks"][name] = {"ok": ok, "detail": detail}

# ---- 1. sitemap ----
st, body = fetch("/sitemap.xml")
if st == 200:
    try:
        root = ET.fromstring(body)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [u.find("s:loc", ns).text for u in root.findall("s:url", ns)]
        check("sitemap", True, "%d 个 URL" % len(urls))
    except Exception as e:
        check("sitemap", False, "解析失败: %s" % e)
else:
    check("sitemap", None if st is None else False, "HTTP %s" % st)

# ---- 2. robots.txt ----
st, body = fetch("/robots.txt")
if st == 200:
    bots_want = ["OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Claude-SearchBot"]
    missing = [b for b in bots_want if b not in body]
    check("robots_ai_bots", len(missing) == 0,
          "AI 检索爬虫全部放行" if not missing else "缺: %s" % ",".join(missing))
else:
    check("robots_ai_bots", None if st is None else False, "HTTP %s" % st)

# ---- 3. 首页 on-page ----
st, body = fetch("/")
if st == 200:
    def has(p):
        return re.search(p, body, re.I) is not None
    items = {
        "title": has(r"<title>[^<]{10,120}</title>"),
        "meta_description": has(r'<meta[^>]+name=["\']?description'),
        "canonical": has(r'<link[^>]+rel=["\']?canonical'),
        "og_tags": has(r'og:title') and has(r'og:description'),
        "jsonld": has(r'application/ld\+json'),
        "msvalidate": has(r'msvalidate\.01'),
    }
    bad = [k for k, v in items.items() if not v]
    check("homepage_onpage", len(bad) == 0, "全部通过" if not bad else "缺: %s" % ",".join(bad))
else:
    check("homepage_onpage", None if st is None else False, "HTTP %s" % st)

# ---- 4. 验证文件 + llms.txt ----
for name, path in [("google_verify", "/google8d50a1cf2d776ccd.html"),
                   ("bing_verify", "/BingSiteAuth.xml"),
                   ("llms_txt", "/llms.txt")]:
    st, _ = fetch(path)
    check(name, True if st == 200 else (None if st is None else False), "HTTP %s" % st)

# ---- 5. 日志：爬虫活跃度 + 404 内容缺口 ----
log_path = os.path.join(SITE_DIR, "analytics", "161808-access.log")
crawler_re = re.compile(r"Googlebot|Bingbot|OAI-SearchBot|ChatGPT-User|PerplexityBot|Claude-SearchBot|ClaudeBot|GPTBot|CCBot|Bytespider|Diffbot", re.I)
bots, paths_404 = {}, {}
if os.path.exists(log_path):
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            req = e.get("request", {})
            ua = " ".join(req.get("headers", {}).get("User-Agent", []))
            m = crawler_re.search(ua)
            if m:
                b = m.group(0)
                bots[b] = bots.get(b, 0) + 1
            if e.get("status") == 404:
                uri = req.get("uri", "").split("?")[0]
                if not re.search(r"\.(env|git|php|asp|bak|sql|zip)$|wp-|xmlrpc|\.well-known", uri, re.I):
                    paths_404[uri] = paths_404.get(uri, 0) + 1
report["crawlers"] = dict(sorted(bots.items(), key=lambda x: -x[1]))
gaps = sorted(paths_404.items(), key=lambda x: -x[1])[:10]
report["content_gaps"] = [{"path": p, "count": c} for p, c in gaps]

# ---- 6. 内链孤儿检查 ----
tut_files = glob.glob(os.path.join(SITE_DIR, "content", "tutorials", "*.md"))
inbound = {}
for fp in tut_files:
    slug = os.path.basename(fp)[:-3]
    if slug == "_index":
        continue
    inbound[slug] = 0
link_re = re.compile(r"\]\((/[a-z0-9\-/]+/)\)")
for fp in tut_files:
    with open(fp, encoding="utf-8") as f:
        md = f.read()
    src = os.path.basename(fp)[:-3]
    for m in link_re.finditer(md):
        tgt = m.group(1).strip("/")
        if tgt in inbound and tgt != src:
            inbound[tgt] += 1
report["orphans"] = sorted([s for s in inbound if inbound[s] == 0])

# ---- 7. backlog 评分排行 ----
backlog_path = os.path.join(GOAL_DIR, "hidden_files", "seo-backlog.yaml")
top5 = []
if os.path.exists(backlog_path):
    with open(backlog_path, encoding="utf-8") as f:
        bl = yaml.safe_load(f)
    ranked = []
    for t in bl.get("topics", []) + bl.get("candidates", []):
        if t.get("status") != "planned":
            continue
        score = (0.30 * t.get("demand", 3) + 0.25 * (6 - t.get("competition", 3))
                 + 0.25 * t.get("ai_resistance", 3) + 0.20 * t.get("freshness", 3))
        ranked.append((round(score, 2), t))
    ranked.sort(key=lambda x: x[0], reverse=True)
    top5 = [{"keyword": t["keyword"], "slug": t.get("slug"), "score": s,
             "monthly_searches": t.get("monthly_searches")} for s, t in ranked[:5]]
    published = sum(1 for t in bl.get("topics", []) if t.get("status") == "published")
    report["backlog"] = {"published": published, "planned": len(ranked)}
report["backlog_top5"] = top5

# ---- 8. 健康分 ----
vals = [c["ok"] for c in report["checks"].values()]
known = [v for v in vals if v is not None]
report["health_score"] = round(100 * sum(1 for v in known if v) / len(known)) if known else None

out = os.path.join(SITE_DIR, "analytics", "seo-report.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)

print("【SEO 分析】%s" % report["generated_at"])
hs = report["health_score"]
print("技术健康分：%s" % (hs if hs is not None else "未知（网络抖动）"))
for name, c in report["checks"].items():
    mark = "OK" if c["ok"] is True else ("?" if c["ok"] is None else "FAIL")
    print("  [%s] %s: %s" % (mark, name, c["detail"]))
if bots:
    print("爬虫活跃：" + "、".join("%s %d次" % (k, v) for k, v in list(bots.items())[:6]))
else:
    print("爬虫活跃：日志中无记录（或日志未同步）")
if gaps:
    print("404 缺口（潜在选题）：")
    for p, c in gaps[:5]:
        print("  - %s（%d次）" % (p, c))
if report["orphans"]:
    print("正文无内链导入（主题已有相关推荐，可选加编辑内链）：" + "、".join(report["orphans"]))
if top5:
    print("本周推荐长尾选题 TOP5：")
    for t in top5:
        print("  - %s（%.2f分，月搜约%s）" % (t["keyword"], t["score"], t["monthly_searches"]))
