"""
MBH Daily Summary — GitHub Actions version.
Reads agent reports from the repo and sends to ntfy. No API key needed.
"""
import json, os, requests
from datetime import datetime, timezone, timedelta

NTFY_URL = "https://ntfy.sh/mbh-sikkum-yomi"
REPORTS  = "scripts/agents/reports"
ISRAEL   = timezone(timedelta(hours=3))


def load(filename):
    path = os.path.join(REPORTS, filename)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def send_ntfy(title, body):
    requests.post(
        NTFY_URL,
        data=body.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Priority": "high",
            "Tags": "bar_chart,moon",
        },
        timeout=10,
    )


def main():
    now      = datetime.now(ISRAEL)
    date_str = now.strftime("%d/%m/%Y")

    today    = load("marketing_today.json")
    mkt      = load("marketing_latest.json")
    research = load("research_latest.json")
    shared   = load("shared_findings.json")
    poster   = load("poster_daily.json")

    spend       = today.get("spend", 0)
    budget      = today.get("budget", 35)
    budget_pct  = today.get("budget_used_pct", 0)
    impressions = today.get("impressions", 0)
    clicks      = today.get("clicks", 0)
    leads       = today.get("leads", 0)
    ctr         = today.get("ctr", 0)
    cpm         = today.get("cpm", 0)

    ads         = today.get("ads", {})
    problems    = shared.get("current_problems", [])
    actions     = mkt.get("actions_taken", [])
    analysis    = mkt.get("analysis", "")
    research_f  = research.get("findings", "")
    research_t  = research.get("topic", "")

    # Build ad breakdown
    ads_lines = []
    for name, d in ads.items():
        ad_leads = f" | {d['leads']} לידים" if d.get("leads") is not None else ""
        ads_lines.append(f"  • {name}: {float(d.get('spend',0)):.0f}₪ | {int(d.get('impressions',0)):,} חשיפות{ad_leads}")

    # Poster stats
    poster_ok     = poster.get("posts_ok", 0)
    poster_failed = poster.get("posts_failed", 0)
    poster_max    = poster.get("max_per_day", 15)
    poster_groups = poster.get("groups_ok", [])
    poster_line   = f"{poster_ok}/{poster_max} פוסטים הצליחו"
    if poster_failed:
        poster_line += f" | {poster_failed} נכשלו"
    if poster_groups:
        poster_line += f"\n  קבוצות: {', '.join(poster_groups[:5])}" + ("..." if len(poster_groups) > 5 else "")

    # Build problems/actions
    prob_lines = ["  • " + p for p in problems] if problems else ["  • לא זוהו בעיות"]
    act_lines  = ["  • " + a for a in actions]  if actions  else ["  • לא בוצעו פעולות"]

    # Truncate analysis to 300 chars
    analysis_short   = (analysis[:300]   + "...") if len(analysis)   > 300 else analysis
    research_short   = (research_f[:200] + "...") if len(research_f) > 200 else research_f

    body = f"""📅 {date_str}

💰 הוצאה: {spend:.1f}₪ / {budget}₪ ({budget_pct:.0f}%)
👁 חשיפות: {impressions:,} | 🖱 קליקים: {clicks} | 🎯 לידים: {leads}
📈 CTR: {ctr:.2f}% | CPM: {cpm:.1f}₪

📊 לפי מודעה:
{chr(10).join(ads_lines)}

⚠️ בעיות שזוהו:
{chr(10).join(prob_lines)}

🤖 פעולות אוטומטיות:
{chr(10).join(act_lines)}

🧠 ניתוח סוכן השיווק:
{analysis_short or 'אין'}

📣 פרסום קבוצות:
  {poster_line if poster else '  אין נתונים עדיין'}

🔬 מחקר ({research_t}):
{research_short or 'אין'}"""

    title = f"📊 MBH {date_str} | {spend:.0f}₪ | {leads} לידים"
    send_ntfy(title, body)
    print(f"✓ נשלח: {title}")


if __name__ == "__main__":
    main()
