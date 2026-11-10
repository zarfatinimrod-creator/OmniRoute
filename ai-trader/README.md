# AI Trader - סוחר AI שלומד (כסף נייר)

> **כסף נייר בלבד.** זו לא המלצת השקעה. אף מודל לא חוזה את השוק בוודאות - גם מערכות טובות צודקות
> ב-51-58% מהמקרים. המטרה: להוכיח (או להפריך) יתרון על כסף מדומה לפני שנוגעים בכסף אמיתי.

## מה זה

בוט מסחר במניות ו-ETF אמריקאיות, שרץ ברצף בענן ונשלט על ידי Claude כ"מנהל תיקים":

1. **נתונים** - Yahoo Finance (מחירים, חדשות), SEC EDGAR (דיווחי בעלי עניין). אופציונלי: Quiver Quant
   (מסחר של חברי קונגרס, לובינג, חוזים ממשלתיים), Liquid (ביצוע/נייר דרך MCP).
2. **8 אותות מבוססי מחקר** - מומנטום (סדרתי וחתך-רוחב), מגמה, קרבה לשיא 52 שבועות, תנודתיות נמוכה,
   פריצה, היפוך קצר, משיכה-לאחור ב-RSI(2). כל אות מנורמל ל-[-1, 1].
3. **אנסמבל לומד** - משקל כל אות נקבע לפי ה-IC (מתאם דירוג בין האות לתשואה שהגיעה בפועל), עם
   כיווץ לפריור, רצפה/תקרה ומגבלת צעד - כדי שהבוט ילמד מטעויות בלי לרדוף אחרי רעש.
4. **ניהול סיכונים** - יעד תנודתיות 12%, מקסימום 10% למניה / 30% לסקטור, סטופ ATR נגרר, מסנן
   משטר (SPY מתחת לממוצע 200 = חצי חשיפה), מפסק ירידה (-10% חצי, -20% מזומן).
5. **Claude כמנהל** - קורא חדשות, יכול **רק להקטין** סיכון (וטו/הקטנה), רושם תחזיות משלו שנבדקות
   אחר כך, וכותב לקחים.
6. **מכונת הזמן** - שחזור היסטוריה יום-יום עם אותו קוד בדיוק (`skills/strategy-time-machine/SKILL.md`).
7. **יומן** - כל תחזית, החלטה, עסקה ולקח נשמרים ב-`state/` (גיט = הזיכרון).

## הרצה

```bash
cd ai-trader
pip install -r requirements.txt
python3 -m aitrader cycle            # מחזור אחד (מבצע רק כשהשוק פתוח)
python3 -m aitrader cycle --dry-run  # רק הצעה, בלי ביצוע
python3 -m aitrader status           # מצב אחרון
python3 -m aitrader backtest --start 2018-01-01 --sweep   # מכונת הזמן
python3 -m aitrader predict NVDA up --horizon 20 --note "..."   # תחזית של Claude לבדיקה
python3 -m aitrader scorecard        # כרטיס ציונים
python3 -m aitrader brief NVDA       # חבילת נתונים לדסק המסחר
python3 -m aitrader desk NVDA Hold --prob 0.52 --thesis "..." --invalidation "..."
python3 -m unittest discover -s tests -v
```

## קבצים

| נתיב | מה |
|---|---|
| `config.json` | כל ההנחות (יקום, עלויות, סיכון, למידה). משנים רק כאן. |
| `aitrader/` | הקוד: data, signals, strategy, broker, learn, backtest, journal, cycle, report, notify |
| `state/` | הזיכרון: תיק, משקלות, תחזיות, החלטות, עסקאות, לקחים |
| `reports/` | דוח יומי בעברית |
| `logs/` | לוג סשן עם 8 כותרות (הבקשה · מה נעשה · קבצים ששונו · החלטות · כשלים בדרך · אימות · עבודה ידנית חוזרת → לאוטומציה · בזבוז טוקנים) |
| `skills/` | `trader`, `strategy-time-machine`, `trading-desk` (תפקידי TradingAgents על סוכני Claude) |
| `vendor/` | ה-Trader skill וה-Time Machine של Jake Schincariol (MIT, קומיט נעול; `trader-broker` לא מותקן) |
| `agents/` | `web-researcher`, `quant-critic` |

## התראות לטלפון

הכי פשוט: אפליקציית **ntfy** (חינם, בלי חשבון). בוחרים שם נושא אקראי ומגדירים
`AITRADER_NTFY_TOPIC` בסביבה. אפשר גם טלגרם (`AITRADER_TELEGRAM_TOKEN` + `AITRADER_TELEGRAM_CHAT`).
בנוסף, משימות מתוזמנות של Claude שולחות push כשיש פעולה.

## When a hash chain breaks

`python3 -m aitrader verify` prints `BROKEN at record N` and exits 1. When that happens, `cycle` (for the main
book's logs) or `news-live` (for the `news_*` logs) stops trading and sends an urgent alert. Stops on open positions are
**not** checked until the chain is repaired. A single crash in the middle of a write repairs itself: the torn fragment
is named in the next record (`after_torn`). Anything else needs a person:

1. `git log -p -- state/<file>` - find the last commit in which `verify` passed (state is committed every slot).
2. Compare that commit with the current file. Records that were added since and are intact stay. A damaged or edited
   record means the history was changed: write down what changed in `logs/` and tell Nimrod.
3. Restore the file from that commit (`git checkout <sha> -- state/<file>`), re-append the intact newer records in
   order with `journal.append`, and run `verify` again. Never edit hashes by hand, and never use `git stash`.
   A repaired chain gives its records new hashes, and a loss review names its sale by that hash: run
   `python3 -m aitrader postmortem` afterwards and record again the reviews of the sales that show up as pending.
   The second record repeats the first one's cause tag, so `verify` then lists it under REPEATED CAUSES although it
   is one loss: say so in the session log.
