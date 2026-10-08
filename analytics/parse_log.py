#!/usr/bin/env python3
"""Parse Caddy JSON access log for www.161808.xyz into Hugo data + report.

Reads new lines since last run (tracked in state.json), aggregates:
  - per-path all-time human pageviews  -> data/analytics.json (Hugo)
  - weekly top pages (with titles)      -> data/analytics.json (Hugo)
  - per-day views / unique IPs, top referrers, bot share, 404s -> analytics/report.json
"""
import json, re, os, sys
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(BASE)
LOG = os.path.join(BASE, "161808-access.log")
STATE = os.path.join(BASE, "state.json")
DATA_OUT = os.path.join(SITE, "data", "analytics.json")
REPORT_OUT = os.path.join(BASE, "report.json")
CONTENT_DIR = os.path.join(SITE, "content", "tutorials")

SGT = timezone(timedelta(hours=8))
STATIC_EXT = re.compile(r"\.(css|js|png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|eot|map|xml|txt|json)$", re.I)
BOT_RE = re.compile(r"bot|crawl|spider|slurp|mediapartners|baidu|yandex|sogou|exabot|facebot|ia_archiver|gptbot|ccbot|anthropic-ai|claudebot|oai-searchbot|chatgpt-user|googlebot|bingbot|applebot|bytespider|semrush|ahrefs|mj12bot|dotbot|petalbot|aspiegelbot", re.I)
OWN_HOST = "161808.xyz"


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"offset": 0, "pages": {}, "daily": {}, "referrers": {},
            "bots": 0, "humans": 0, "not_found": {}}


def save_state(s):
    with open(STATE, "w") as f:
        json.dump(s, f)


def page_title(path):
    """Resolve a URL path to a display title via tutorial front matter."""
    if path in ("/", ""):
        return "Home"
    slug = path.strip("/").split("/")[0]
    md = os.path.join(CONTENT_DIR, slug + ".md")
    if os.path.exists(md):
        with open(md, encoding="utf-8") as f:
            head = f.read(2000)
        m = re.search(r'^title:\s*"(.*)"', head, re.M)
        if m:
            return m.group(1)
        m = re.search(r"^title:\s*(.+)$", head, re.M)
        if m:
            return m.group(1).strip().strip('"')
    return path


def main():
    st = load_state()
    offset = st.get("offset", 0)
    new_lines = 0
    if os.path.exists(LOG):
        size = os.path.getsize(LOG)
        if size < offset:  # log rotated
            offset = 0
        with open(LOG, "rb") as f:
            f.seek(offset)
            for raw in f:
                new_lines += 1
                try:
                    d = json.loads(raw)
                except Exception:
                    continue
                req = d.get("request", {})
                if req.get("method") != "GET":
                    continue
                status = d.get("status", 0)
                uri = req.get("uri", "")
                path = uri.split("?", 1)[0]
                headers = req.get("headers", {}) or {}
                ua = (headers.get("User-Agent") or [""])[0]
                is_bot = bool(BOT_RE.search(ua))
                day = datetime.fromtimestamp(d.get("ts", 0), SGT).strftime("%Y-%m-%d")
                ip = req.get("remote_ip", "")

                if status == 404:
                    st["not_found"][path] = st["not_found"].get(path, 0) + 1
                    continue
                if status != 200 or STATIC_EXT.search(path):
                    continue
                if path in ("/404.html",):
                    continue

                dayrec = st["daily"].setdefault(day, {"views": 0, "humans": 0, "bots": 0, "ips": []})
                dayrec["views"] += 1
                if ip and ip not in dayrec["ips"]:
                    dayrec["ips"].append(ip)

                if is_bot:
                    st["bots"] += 1
                    dayrec["bots"] += 1
                    continue
                st["humans"] += 1
                dayrec["humans"] += 1
                st["pages"][path] = st["pages"].get(path, 0) + 1

                ref = (headers.get("Referer") or [""])[0]
                if ref:
                    host = urlparse(ref).netloc.lower().replace("www.", "")
                    if host and OWN_HOST not in host:
                        st["referrers"][host] = st["referrers"].get(host, 0) + 1
            offset = f.tell()
    st["offset"] = offset

    # weekly top pages (last 7 days incl. today)
    today = datetime.now(SGT).date()
    week_days = {(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)}
    # rebuild weekly from daily is not per-path; use all-time ranking as proxy,
    # but weight by recent days when we have per-day path data (future). For now: top by all-time.
    ranked = sorted(st["pages"].items(), key=lambda kv: kv[1], reverse=True)[:5]
    weekly = [{"path": p, "title": page_title(p), "views": v} for p, v in ranked]

    total_views = sum(st["pages"].values())
    data = {
        "pages": st["pages"],
        "weekly": weekly,
        "total_views": total_views,
        "humans": st["humans"],
        "bots": st["bots"],
        "updated": datetime.now(SGT).isoformat(timespec="seconds"),
    }
    os.makedirs(os.path.dirname(DATA_OUT), exist_ok=True)
    with open(DATA_OUT, "w") as f:
        json.dump(data, f, ensure_ascii=False)

    top_refs = sorted(st["referrers"].items(), key=lambda kv: kv[1], reverse=True)[:10]
    top_404 = sorted(st["not_found"].items(), key=lambda kv: kv[1], reverse=True)[:10]
    daily_summary = {d: {"views": r["views"], "humans": r["humans"],
                         "unique_ips": len(r["ips"])} for d, r in sorted(st["daily"].items())[-7:]}
    report = {
        "generated_at": datetime.now(SGT).isoformat(timespec="seconds"),
        "new_lines": new_lines,
        "total_views": total_views,
        "humans": st["humans"],
        "bots": st["bots"],
        "top_pages": [{"path": p, "title": page_title(p), "views": v} for p, v in ranked],
        "top_referrers": [{"domain": h, "views": v} for h, v in top_refs],
        "daily": daily_summary,
        "top_404": [{"path": p, "count": c} for p, c in top_404],
    }
    with open(REPORT_OUT, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    save_state(st)
    print(json.dumps({"new_lines": new_lines, "total_views": total_views,
                      "humans": st["humans"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
