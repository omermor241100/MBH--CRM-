"""
Agent 1: Paid Marketing Researcher for Construction Business
Researches paid marketing strategies and saves findings to research/paid-marketing.md
"""

import anthropic
import os
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PROMPT = """
אתה חוקר שיווק דיגיטלי מומחה לתחום הבניה והשיפוצים בישראל.
המשימה שלך: לכתוב דוח מחקר מקיף ומעשי על שיווק ממומן לעסק שיפוצים ובניה בישראל.

שם העסק: MBH - Mor Building Holdings
תחומי פעילות: גבס, צבע, שיפוצים כלליים, אינסטלציה, חשמל, תוספות בנייה, אחזקת מבנים
קהל יעד: בעלי בתים, דיירים, עסקים, קיבוצים ומושבים
ניסיון: 25 שנה, 300+ פרויקטים

כתוב דוח מפורט הכולל:

## 1. ערוצי פרסום ממומן מומלצים
- Facebook Ads — למה, איך, כמה לשלם
- Google Ads (Search + Display) — מילות מפתח, תקציב
- Instagram Ads — פורמטים, קהלים
- YouTube Ads — מתי כדאי
- Waze Ads — לעסק מקומי

## 2. טרגוט מדויק
- פילוח גיאוגרפי — אזורים לטרגט
- פילוח דמוגרפי — גיל, הכנסה, סטטוס נכס
- Lookalike audiences
- Retargeting — איך לשלב

## 3. תקציבים ו-ROI
- מה תקציב סביר להתחיל בשיווק ממומן
- עלות ממוצעת לליד בתחום הבניה
- כיצד למדוד תשואה
- חלוקת תקציב מומלצת בין ערוצים

## 4. מסרים ותוכן שממיר
- כותרות שעובדות בפרסומות בניה
- Call-to-action יעיל
- מה להבליט (ניסיון, מחיר, אחריות)

## 5. עונתיות ותזמון
- מתי לפרסם יותר (עונות שיא)
- ימים ושעות אופטימליים

## 6. טעויות נפוצות שצריך להימנע

## 7. תוכנית פעולה ל-30 הימים הראשונים
- שבוע 1-2: מה לעשות
- שבוע 3-4: מה לעשות
- KPIs למעקב

כתוב בעברית, בצורה מעשית ומפורטת. כל המלצה עם נימוק ומספרים ריאליים.
"""

print("Agent 1: Starting paid marketing research...")

message = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4000,
    messages=[{"role": "user", "content": PROMPT}]
)

research = message.content[0].text
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

output = f"""# מחקר שיווק ממומן — MBH Building Holdings
*נוצר אוטומטית על ידי Agent 1 | {timestamp}*

---

{research}
"""

os.makedirs("research", exist_ok=True)
with open("research/paid-marketing.md", "w", encoding="utf-8") as f:
    f.write(output)

print("Agent 1: Research complete → research/paid-marketing.md")
