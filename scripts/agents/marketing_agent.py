"""
MBH Marketing Agent — רץ כל 30 דקות.
מנתח נתונים, מזהה בעיות, מבצע פעולות אוטומטיות, מעביר ממצאים ל-Researcher.
"""

import requests, json, subprocess, os
from datetime import datetime, timedelta

BASE_DIR    = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, '..', 'marketing', 'config.json')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
KNOWLEDGE   = os.path.join(BASE_DIR, 'campaign_knowledge.json')
LIVE_LOG    = os.path.join(REPORTS_DIR, 'live.json')
NTFY        = "https://ntfy.sh/mbh-crm-leads-7x4k9"
META        = "https://graph.facebook.com/v25.0"

with open(CONFIG_PATH) as f:
    TOKEN = json.load(f)['access_token']
with open(KNOWLEDGE, encoding='utf-8') as f:
    KN = json.load(f)

CAMPAIGN_ID = KN['campaign']['id']
ADSET_ID    = KN['campaign']['adset_id']
AD_IDS      = list(KN['campaign']['ads'].keys())
AD_NAMES    = KN['campaign']['ads']
BENCH       = KN['benchmarks']

os.makedirs(REPORTS_DIR, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = {"time": ts, "agent": "📊 Marketing", "msg": msg}
    print(f"[{ts}] {msg}")
    hist = []
    if os.path.exists(LIVE_LOG):
        try:
            with open(LIVE_LOG, encoding='utf-8') as f:
                hist = json.load(f)
        except: pass
    hist.insert(0, entry)
    with open(LIVE_LOG, 'w', encoding='utf-8') as f:
        json.dump(hist[:100], f, ensure_ascii=False)


def meta_get(ep, params={}):
    params['access_token'] = TOKEN
    return requests.get(f"{META}/{ep}", params=params, timeout=15).json()


def meta_post(ep, data={}):
    data['access_token'] = TOKEN
    return requests.post(f"{META}/{ep}", data=data, timeout=15).json()


def ntfy(title, body, priority="default"):
    try:
        requests.post(NTFY, data=body.encode('utf-8'),
                      headers={"Title": title, "Priority": priority}, timeout=10)
    except: pass


def get_stats(preset="today"):
    fields = (
        "spend,impressions,clicks,reach,cpm,ctr,actions,"
        "video_play_actions,video_p25_watched_actions,"
        "video_p50_watched_actions,video_p75_watched_actions,"
        "video_p100_watched_actions"
    )
    d = meta_get(f"{CAMPAIGN_ID}/insights", {"fields": fields, "date_preset": preset})
    return d.get("data", [{}])[0] if d.get("data") else {}


def get_video_retention(data):
    def vv(field):
        val = data.get(field, [])
        return int(float(val[0]['value'])) if val else 0
    return {
        "p0":   vv("video_play_actions"),
        "p25":  vv("video_p25_watched_actions"),
        "p50":  vv("video_p50_watched_actions"),
        "p75":  vv("video_p75_watched_actions"),
        "p100": vv("video_p100_watched_actions"),
    }


def get_ad_stats(aid, preset="today"):
    d = meta_get(f"{aid}/insights", {"fields": "spend,impressions,clicks,ctr", "date_preset": preset})
    return d.get("data", [{}])[0] if d.get("data") else {}


def get_leads(actions):
    for a in (actions or []):
        if a['action_type'] in ('lead','onsite_web_lead','offsite_conversion.fb_pixel_lead'):
            return int(a['value'])
    return 0


def get_landing_views(actions):
    for a in (actions or []):
        if a['action_type'] == 'landing_page_view':
            return int(a['value'])
    return 0


def get_weekly_stats():
    fields = "spend,impressions,clicks,reach,ctr,cpm,actions"
    d = meta_get(f"{CAMPAIGN_ID}/insights", {
        "fields": fields, "date_preset": "maximum", "time_increment": "1"
    })
    return d.get("data", [])


def save_weekly(now, api_data):
    """Merge API data into persistent daily_history.json, then rebuild marketing_weekly.json."""
    hist_file = os.path.join(REPORTS_DIR, "daily_history.json")

    # Load existing history
    hist = {}
    if os.path.exists(hist_file):
        try:
            with open(hist_file, encoding='utf-8') as f:
                hist = json.load(f).get("days", {})
        except: pass

    # Merge API data (overwrites existing day entries with fresh data)
    for day in api_data:
        s  = float(day.get("spend", 0))
        im = int(day.get("impressions", 0))
        cl = int(day.get("clicks", 0))
        le = get_leads(day.get("actions", []))
        lp = get_landing_views(day.get("actions", []))
        ct = float(day.get("ctr", 0))
        cp = float(day.get("cpm", 0))
        ds = day.get("date_start", "")
        try:
            dl = datetime.strptime(ds, "%Y-%m-%d").strftime("%d/%m")
        except:
            dl = ds
        entry = {"date_start": ds, "date_label": dl,
                 "spend": s, "impressions": im, "clicks": cl,
                 "ctr": ct, "cpm": cp, "leads": le, "lp_views": lp}
        if ds in hist:
            entry["note"] = hist[ds].get("note", "")
        hist[ds] = entry

    # Save updated history
    with open(hist_file, 'w', encoding='utf-8') as f:
        json.dump({"days": hist}, f, ensure_ascii=False, indent=2)

    # Build sorted list for dashboard
    days = sorted(hist.values(), key=lambda d: d["date_start"])
    ts = sum(d["spend"] for d in days)
    ti = sum(d["impressions"] for d in days)
    tc = sum(d["clicks"] for d in days)
    tl = sum(d["leads"] for d in days)
    tlp = sum(d["lp_views"] for d in days)

    report = {
        "generated_at": now.isoformat(),
        "days": days,
        "totals": {
            "spend": round(ts, 2), "impressions": ti,
            "clicks": tc, "leads": tl, "lp_views": tlp,
            "active_days": sum(1 for d in days if d["spend"] > 0)
        }
    }
    with open(os.path.join(REPORTS_DIR, "marketing_weekly.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def save_hourly_snap(now, spend, impressions, clicks, leads, lp_views):
    snap_file = os.path.join(REPORTS_DIR, "hourly_snapshots.json")
    today = now.strftime("%d/%m/%Y")
    data = {"date": today, "snapshots": []}
    if os.path.exists(snap_file):
        try:
            with open(snap_file, encoding='utf-8') as f:
                data = json.load(f)
        except: pass
    if data.get("date") != today:
        data = {"date": today, "snapshots": []}
    data["snapshots"].append({
        "time": now.strftime("%H:%M"), "hour": now.strftime("%H"),
        "spend": spend, "impressions": impressions,
        "clicks": clicks, "leads": leads, "lp_views": lp_views
    })
    with open(snap_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ask_claude(prompt):
    try:
        r = subprocess.run(["/Users/owner/.local/bin/claude", "-p", prompt], capture_output=True, text=True, timeout=90)
        return r.stdout.strip()
    except Exception as e:
        return f"שגיאה: {e}"


def auto_pause_ad(aid, reason):
    r = meta_post(aid, {"status": "PAUSED"})
    if 'id' in r or 'success' in r:
        log(f"⏸ השהיה אוטומטית: {AD_NAMES.get(aid,aid)} — {reason}")
        ntfy("⏸ MBH: מודעה הושהתה", f"{AD_NAMES.get(aid,aid)}\nסיבה: {reason}", "high")
    else:
        log(f"שגיאה בהשהיה: {r}")


def main():
    now = datetime.now()
    log(f"מתחיל ריצה — {now.strftime('%H:%M')}")

    # שלוף נתונים עכשיו
    log("שולף נתוני קמפיין מ-Meta...")
    stats = get_stats("today")
    ad_stats = {aid: get_ad_stats(aid, "today") for aid in AD_IDS}

    # שיפוצים campaign
    spend       = float(stats.get("spend", 0))
    impressions = int(stats.get("impressions", 0))
    clicks      = int(stats.get("clicks", 0))
    reach       = int(stats.get("reach", 0))
    leads       = get_leads(stats.get("actions", []))
    lp_views    = get_landing_views(stats.get("actions", []))
    video_ret   = get_video_retention(stats)

    # לידים campaign — add to totals
    leads_stats = meta_get(f"{KN['leads_campaign']['id']}/insights",
                           {"fields": "spend,impressions,clicks,actions", "date_preset": "today"})
    leads_day   = leads_stats.get("data", [{}])[0] if leads_stats.get("data") else {}
    leads_spend      = float(leads_day.get("spend", 0))
    leads_impressions = int(leads_day.get("impressions", 0))
    leads_clicks     = int(leads_day.get("clicks", 0))
    leads_leads      = get_leads(leads_day.get("actions", []))

    spend       = round(spend + leads_spend, 2)
    impressions = impressions + leads_impressions
    clicks      = clicks + leads_clicks
    leads       = leads + leads_leads
    ctr         = round((clicks / impressions * 100) if impressions > 0 else 0, 6)
    cpm         = round((spend / impressions * 1000) if impressions > 0 else 0, 6)

    log(f"נתונים: {spend:.2f}₪ | {impressions} חשיפות | {clicks} קליקים | CTR {ctr:.2f}% | {leads} לידים")

    # ──── פעולות אוטומטיות ────
    actions_taken = []

    for aid in AD_IDS:
        s = ad_stats[aid]
        ad_imp = int(s.get("impressions", 0))
        ad_ctr = float(s.get("ctr", 0))
        if ad_imp >= BENCH["min_impressions_before_pause"] and ad_ctr < BENCH["ctr_bad"] * 0.5:
            auto_pause_ad(aid, f"CTR {ad_ctr:.2f}% אחרי {ad_imp} חשיפות")
            actions_taken.append(f"הושהתה מודעה: {AD_NAMES[aid]} (CTR {ad_ctr:.2f}%)")

    if cpm > BENCH["cpm_bad"]:
        log(f"⚠️ CPM גבוה מדי: {cpm:.0f}₪ (יעד: {BENCH['cpm_ok']}₪) — שלב לימוד")
        ntfy("⚠️ MBH: CPM גבוה", f"CPM: {cpm:.0f}₪ — גבוה מהיעד. שלב לימוד עדיין פעיל.", "default")
        actions_taken.append(f"התראה: CPM {cpm:.0f}₪")

    if clicks >= 30 and leads == 0:
        msg = f"🚨 {clicks} קליקים ו-0 לידים — בעיית דף נחיתה"
        log(msg)
        ntfy("🚨 MBH: בעיית המרה", f"{clicks} קליקים, {lp_views} כניסות לדף, 0 לידים\nהדף לא ממיר!", "urgent")
        actions_taken.append("התראה: בעיית המרה בדף נחיתה")

    if clicks > 0 and lp_views < clicks * 0.3:
        drop = round((1 - lp_views/clicks) * 100)
        log(f"⚠️ Drop-off גבוה: {drop}% לא הגיעו לדף אחרי קליק")
        actions_taken.append(f"Drop-off {drop}% — קליקים לא הגיעים לדף")

    # ──── עדכן ממצאים לשיתוף עם Researcher ────
    current_problems = []
    if ctr < BENCH["ctr_bad"]:
        current_problems.append("CTR נמוך — המודעות לא מספיק מושכות")
    if cpm > BENCH["cpm_bad"]:
        current_problems.append(f"CPM גבוה ({cpm:.0f}₪) — שלב לימוד או קהל צר")
    if clicks > 10 and leads == 0:
        current_problems.append(f"דף נחיתה לא ממיר — {clicks} קליקים, 0 לידים")
    if lp_views < clicks * 0.4 and clicks > 5:
        current_problems.append(f"Drop-off גבוה אחרי קליק — {lp_views}/{clicks} הגיעו לדף")

    # ──── ניתוח Claude ────
    log("שולח לClaude לניתוח...")
    ad_summary = "\n".join([
        f"- {AD_NAMES[aid]}: {ad_stats[aid].get('spend','0')}₪ | {ad_stats[aid].get('impressions','0')} חשיפות | CTR {float(ad_stats[aid].get('ctr',0)):.2f}%"
        for aid in AD_IDS
    ])

    prompt = f"""אתה מנהל שיווק דיגיטלי אוטונומי של קמפיין שיפוצים ישראלי (MBH).

נתוני היום ({now.strftime('%d/%m/%Y %H:%M')}):
- הוצאה: {spend:.2f}₪ / 30₪
- חשיפות: {impressions} | הגעה: {reach}
- קליקים: {clicks} | כניסות לדף: {lp_views} | לידים: {leads}
- CTR: {ctr:.2f}% | CPM: {cpm:.2f}₪

מודעות:
{ad_summary}

בעיות שזוהו:
{chr(10).join(['- ' + p for p in current_problems]) if current_problems else '- לא זוהו בעיות קריטיות'}

פעולות שבוצעו אוטומטית:
{chr(10).join(['- ' + a for a in actions_taken]) if actions_taken else '- לא בוצעו פעולות'}

כתוב ניתוח קצר (3-4 משפטים) + המלצה אחת שאפשר לבצע עכשיו. עברית בלבד, ישיר ומעשי."""

    analysis = ask_claude(prompt)
    log("ניתוח הושלם ✓")

    # ──── שמור דוח ────
    report = {
        "date": now.strftime("%d/%m/%Y"),
        "generated_at": now.isoformat(),
        "stats": {
            "spend": spend, "impressions": impressions, "clicks": clicks,
            "reach": reach, "ctr": ctr, "cpm": cpm, "leads": leads,
            "lp_views": lp_views, "budget": 30,
            "budget_used_pct": round(spend / 30 * 100, 1),
        },
        "ads": {
            AD_NAMES[aid]: {
                "spend": float(ad_stats[aid].get("spend", 0)),
                "impressions": int(ad_stats[aid].get("impressions", 0)),
                "clicks": int(ad_stats[aid].get("clicks", 0)),
                "ctr": float(ad_stats[aid].get("ctr", 0)),
            } for aid in AD_IDS
        },
        "problems": current_problems,
        "actions_taken": actions_taken,
        "analysis": analysis,
        "video_retention": video_ret,
    }

    with open(os.path.join(REPORTS_DIR, "marketing_latest.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    save_hourly_snap(now, spend, impressions, clicks, leads, lp_views)
    log("שולף נתוני היסטוריה שבועית...")
    save_weekly(now, get_weekly_stats())

    # שמור בעיות עבור Researcher
    shared = {"updated_at": now.isoformat(), "current_problems": current_problems, "stats_summary": {
        "spend": spend, "clicks": clicks, "leads": leads, "ctr": ctr, "cpm": cpm, "lp_views": lp_views
    }}
    with open(os.path.join(REPORTS_DIR, "shared_findings.json"), "w", encoding="utf-8") as f:
        json.dump(shared, f, ensure_ascii=False, indent=2)

    ntfy_body = f"📊 {now.strftime('%H:%M')} | {spend:.2f}₪ | {impressions} חשיפות | {clicks} קליקים | {leads} לידים\n{analysis[:200]}"
    ntfy("📊 MBH עדכון", ntfy_body)
    log(f"סיים ריצה — הבא בעוד 30 דקות")


def git_push_reports():
    """Push report JSONs to GitHub so the daily summary workflow can read them."""
    repo = os.path.join(BASE_DIR, '..', '..')
    files = [
        "scripts/agents/reports/marketing_latest.json",
        "scripts/agents/reports/marketing_today.json",
        "scripts/agents/reports/shared_findings.json",
        "scripts/agents/reports/research_latest.json",
        "scripts/agents/reports/poster_daily.json",
        "scripts/agents/campaign_knowledge.json",
    ]
    try:
        subprocess.run(["git", "add"] + files, cwd=repo, timeout=15)
        result = subprocess.run(
            ["git", "diff", "--staged", "--quiet"], cwd=repo, timeout=10
        )
        if result.returncode != 0:  # changes exist
            subprocess.run(
                ["git", "commit", "-m", f"agents: update reports {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                cwd=repo, timeout=15
            )
            subprocess.run(["git", "push"], cwd=repo, timeout=30)
    except Exception as e:
        log(f"[git-push] שגיאה: {e}")


if __name__ == "__main__":
    main()
    git_push_reports()
