"""
MBH Facebook Group Auto-Poster
────────────────────────────────
מריץ כל שעה ע"י LaunchAgent.
כל ריצה = 4 קבוצות בלבד.
מקסימום 20 קבוצות ביום.

Usage:
  python main.py                    # post to up to 4 groups (hourly run)
  python main.py --scan             # re-scan group list first
  python main.py --dry-run          # simulate without posting
  python main.py --limit 2          # override session limit
  python main.py --post-id mbh_main # specific post template
"""

import argparse
import json
import os
import random
import sys
import time
import requests
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import db
import human
import groups_scraper
import poster
import stealth
import warmup as warmup_mod
import behavior
import personalizer

CONFIG_PATH = os.path.join(BASE, 'config.json')


def load_config() -> dict:
    with open(CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


def rp(cfg, key):
    return os.path.join(BASE, cfg[key])


def ntfy(url, title, body, priority="default"):
    if not url:
        return
    try:
        requests.post(url, data=body.encode('utf-8'),
                      headers={"Title": title, "Priority": priority}, timeout=10)
    except Exception:
        pass


def within_hours(start, end):
    return start <= datetime.now().hour < end


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan',     action='store_true')
    parser.add_argument('--dry-run',  action='store_true')
    parser.add_argument('--limit',    type=int, default=None)
    parser.add_argument('--post-id',  type=str, default=None)
    parser.add_argument('--headless', type=lambda x: x.lower() != 'false', default=True)
    args = parser.parse_args()

    cfg        = load_config()
    session_f  = rp(cfg, 'session_file')
    groups_f   = rp(cfg, 'groups_file')
    db_f       = rp(cfg, 'db_file')
    screens    = os.path.join(BASE, 'screenshots')
    ntfy_url   = cfg.get('ntfy_url', '')
    timing     = cfg['timing']

    # ── בדוק אם מושהה ──
    if cfg.get('paused') and not args.dry_run:
        print("[⏸️] הפוסטר מושהה. הפעל דרך הדשבורד.")
        return

    # ── שעות פרסום ──
    start_h, end_h = timing['post_only_between_hours']
    if not within_hours(start_h, end_h):
        print(f"[⏰] מחוץ לשעות פרסום ({start_h}:00–{end_h}:00). יציאה.")
        return

    # ── בחר פוסט ──
    posts = cfg['posts']
    post  = next((p for p in posts if p['id'] == args.post_id), None) if args.post_id else None
    if not post:
        post = random.choice(posts)
    text  = human.vary_text(post)
    image = post.get('image')
    if image:
        image = os.path.join(BASE, image)

    con = db.init(db_f)

    # ── מכסה יומית ──
    posted_today = db.posted_today_count(con)
    daily_max    = timing['max_posts_per_day']
    if posted_today >= daily_max and not args.dry_run:
        print(f"[🔒] מכסה יומית: {posted_today}/{daily_max}. יציאה.")
        return

    # ── מכסה לריצה ──
    session_max = args.limit or timing['max_posts_per_session']
    can_post    = min(session_max, daily_max - posted_today)

    # ── בדיקות התנהגות — לפני הכל ──
    ok, reason = behavior.should_run(dry_run=args.dry_run)
    if not ok:
        print(f"[⏭️] {reason}")
        return

    # ── בדיקת IP — פייסבוק יזהו שינוי כמכשיר חדש ──
    ip_ok, ip_msg = behavior.check_ip_consistency()
    print(f"[🌐] {ip_msg}")
    if not ip_ok:
        ntfy(ntfy_url, "⚠️ MBH Poster — IP שינוי", ip_msg, "high")
        # ממשיך אבל מדווח — לא עוצרים כי זה יכול להיות שינוי לגיטימי
        print("     ממשיך — שים לב לסיכון מוגבר")

    # ג'יטר — לא תמיד מתחילים בדיוק ב-:00
    behavior.startup_jitter(max_minutes=12, dry_run=args.dry_run)

    # מספר פוסטים משתנה לריצה זו
    if not args.limit:
        session_max = behavior.session_post_count(base=timing['max_posts_per_session'])

    ts = datetime.now().strftime('%d/%m/%Y %H:%M')
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}MBH Facebook Poster — {ts}")
    print(f"פוסט: {post['id']} | {len(text)} תווים")
    print(f"היום: {posted_today}/{daily_max} | ריצה זו: עד {can_post} קבוצות\n")

    try:
        try:
            from rebrowser_playwright.sync_api import sync_playwright
        except ImportError:
            from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            proxy = cfg.get('proxy') or None
            browser, context = stealth.make_context(pw, session_f, headless=args.headless, proxy=proxy)

            try:
                from playwright_stealth import stealth_sync
                _stealth = stealth_sync
            except ImportError:
                _stealth = None

            page = context.new_page()
            if _stealth:
                _stealth(page)

            # ── בדוק session ──
            print("[1/4] בודק session...")
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=20000)
            human.delay(2000, 4000)
            if '/login' in page.url:
                print("[!] Session פגה — הרץ ./setup.sh תחילה.")
                browser.close()
                return
            print("    ✓ מחובר\n")

            # ── חימום — גלוש בפיד לפני הכל ──
            if not args.dry_run:
                warmup_mod.warmup_session(page, cfg)

            # ── טען קבוצות ──
            print("[2/4] טוען קבוצות...")
            blacklist   = set(cfg.get('blacklist_groups', []))
            repost_days = timing.get('re_post_same_group_after_days', 4)
            cutoff      = datetime.now() - timedelta(days=repost_days)

            all_groups = groups_scraper.load_or_scrape(page, groups_f, force_rescan=args.scan)

            eligible = []
            for g in all_groups:
                if g['id'] in blacklist:
                    continue
                last = db.last_posted(con, g['id'])
                if last and last > cutoff:
                    continue
                eligible.append(g)

            # ── הגבל לקבוצות שנבחרו בדשבורד (אם יש בחירה) ──
            sel_file = os.path.join(BASE, 'logs', 'selected_groups.json')
            if os.path.exists(sel_file):
                try:
                    with open(sel_file, encoding='utf-8') as f:
                        selected_ids = set(json.load(f))
                    if selected_ids:
                        eligible = [g for g in eligible if g['id'] in selected_ids]
                except Exception:
                    pass

            random.shuffle(eligible)
            eligible = eligible[:can_post]
            print(f"    {len(all_groups)} קבוצות | {len(eligible)} לריצה זו\n")

            if not eligible:
                print("[✓] אין קבוצות חדשות לפרסם כעת.")
                browser.close()
                return

            # ── פרסם ──
            print("[3/4] מפרסם...\n")
            ok_count = failed_count = 0
            delay_lo = timing['delay_between_posts_min_sec']
            delay_hi = timing['delay_between_posts_max_sec']

            for i, group in enumerate(eligible):
                gname = group.get('name', group['id'])[:55]
                print(f"  [{i+1}/{len(eligible)}] {gname}")

                if args.dry_run:
                    print("         → [DRY RUN] דילוג")
                    db.log_post(con, group, 'skipped', 'dry-run')
                    continue

                # פרסונליזציה — טקסט ייחודי לכל קבוצה
                group_text = personalizer.personalize(post, group.get('name', ''))
                success, reason = poster.post_to_group(page, group, group_text, image, screens)

                if success:
                    ok_count += 1
                    db.log_post(con, group, 'ok')
                    print(f"         ✓ פורסם")
                else:
                    failed_count += 1
                    db.log_post(con, group, 'failed', reason)
                    print(f"         ✗ נכשל — {reason}")

                    if any(x in reason for x in ['checkpoint', 'חסמו', 'limit', 'login']):
                        print("\n  [🛑] חסימה זוהתה — עוצרים.")
                        ntfy(ntfy_url, "🛑 MBH Poster חסימה!", f"סיבה: {reason}", "urgent")
                        break

                # בין פוסטים: גלוש בפיד + המתנה
                if i < len(eligible) - 1:
                    warmup_mod.inter_post_activity(page, cfg)
                    wait = random.uniform(delay_lo, delay_hi)
                    m, s = divmod(int(wait), 60)
                    print(f"         ⏳ המתנה {m}:{s:02d}...\n")
                    time.sleep(wait)

            # ── שמור session מחודש ──
            if not args.dry_run:
                context.storage_state(path=session_f)
                print("\n[4/4] Session נשמר ✓")

            browser.close()

    except Exception as e:
        print(f"\n[!] שגיאה: {e}")
        ntfy(ntfy_url, "⚠️ MBH Poster שגיאה", str(e), "high")
        raise

    # ── סיכום ──
    summary      = db.session_summary(con)
    today_total  = db.posted_today_count(con)
    ok_names     = ', '.join(summary['ok'][:5]) + ('...' if len(summary['ok']) > 5 else '')
    fail_names   = ', '.join(summary['failed'][:3]) if summary['failed'] else 'אין'

    print(f"""
╔══════════════════════════════════════╗
║      MBH Poster — סיכום ריצה        ║
╠══════════════════════════════════════╣
║  ✓ הצליחו  : {ok_count:<24}║
║  ✗ נכשלו   : {failed_count:<24}║
║  📅 סה"כ היום: {today_total}/{daily_max:<20}║
╚══════════════════════════════════════╝""")

    behavior.log_session(ok_count, failed_count)

    # שמור דוח יומי לסיכום הלילי
    try:
        import json as _json
        poster_report_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', 'agents', 'reports', 'poster_daily.json'
        )
        poster_report_path = os.path.normpath(poster_report_path)
        _all = db.session_summary(con)
        _report = {
            "date": datetime.now().strftime("%d/%m/%Y"),
            "posts_ok": today_total,
            "posts_failed": len(_all['failed']),
            "max_per_day": daily_max,
            "groups_ok": _all['ok'],
            "groups_failed": _all['failed'],
            "last_updated": datetime.now().isoformat(),
        }
        with open(poster_report_path, 'w', encoding='utf-8') as _f:
            _json.dump(_report, _f, ensure_ascii=False, indent=2)
    except Exception as _e:
        print(f"[poster-report] שגיאה: {_e}")

    # עדכן דשבורד
    try:
        import poster_export
        poster_export.export()
    except Exception:
        pass

    if not args.dry_run:
        ntfy(ntfy_url,
             f"📣 MBH Poster — {ok_count} פוסטים ({today_total}/{daily_max} היום)",
             f"✓ {ok_names}\n✗ נכשלו: {fail_names}",
             "default")


if __name__ == '__main__':
    main()
