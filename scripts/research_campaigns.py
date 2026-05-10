"""
Agent 2: Campaign Strategy Researcher for Construction Business
Researches campaign ideas that convert customers and saves to research/campaigns.md
"""

import anthropic
import os
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PROMPT = """
אתה אסטרטג שיווקי מומחה לתחום הבניה והשיפוצים בישראל.
המשימה שלך: לכתוב תוכנית קמפיינים שיווקיים מלאה שתביא לקוחות אמיתיים.

שם העסק: MBH - Mor Building Holdings
תחומי פעילות: גבס, צבע, שיפוצים כלליים, אינסטלציה, חשמל, תוספות בנייה, אחזקת מבנים
יתרון תחרותי: 25 שנות ניסיון, 300+ פרויקטים, אמינות ומקצועיות
ערוצי תקשורת: אתר, אינסטגרם, פייסבוק, וואטסאפ
מספרי קשר: 050-646-0099, 050-538-6460

כתוב תוכנית קמפיינים מפורטת:

## 1. קמפיין Before & After
- מבנה הקמפיין
- סוגי תוכן (תמונות, ריל, סטורי)
- טקסטים לדוגמה
- תדירות פרסום
- מדדי הצלחה

## 2. קמפיין אמון ומוניטין
- סרטוני עדויות לקוחות — איך לצלם ולפרסם
- הצגת ניסיון 25 שנה בצורה ויזואלית
- Behind the scenes מהעבודה
- טקסטים לפוסטים

## 3. קמפיין לידים ישירים
- מבצע "שיחת ייעוץ חינם"
- הנחה על הצעת מחיר
- ערבות תוצאה
- דוגמאות לטקסטים ממירים

## 4. קמפיין עונתי
- כניסה לדירה חדשה (ספטמבר-נובמבר)
- שיפוץ קיץ (יוני-אוגוסט)
- פסח — שיפוץ לפני החג (פברואר-מרץ)
- חורף — פתרונות רטיבות ותחזוקה

## 5. קמפיין אינסטגרם ספציפי
- 30 רעיונות לפוסטים (נושאים + טקסטים קצרים)
- הגשטגים מומלצים בעברית ובאנגלית
- תדירות מומלצת
- שעות פרסום אופטימליות

## 6. קמפיין וואטסאפ
- הודעות שיווקיות למאגר קיים
- תסריט שיחה עם לקוח מתעניין
- Follow-up אוטומטי

## 7. לוח שנה שיווקי — 3 חודשים
- פירוט יומי/שבועי של פעולות
- חלוקת עבודה ומשאבים

## 8. KPIs ומדדים
- מה למדוד
- יעדים ריאליים לחודש 1, 3, 6

כתוב בעברית, מעשי, עם דוגמאות טקסט אמיתיות שאפשר להשתמש בהן ישר.
"""

print("Agent 2: Starting campaign strategy research...")

message = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4000,
    messages=[{"role": "user", "content": PROMPT}]
)

research = message.content[0].text
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

output = f"""# אסטרטגיית קמפיינים — MBH Building Holdings
*נוצר אוטומטית על ידי Agent 2 | {timestamp}*

---

{research}
"""

os.makedirs("research", exist_ok=True)
with open("research/campaigns.md", "w", encoding="utf-8") as f:
    f.write(output)

print("Agent 2: Research complete → research/campaigns.md")
