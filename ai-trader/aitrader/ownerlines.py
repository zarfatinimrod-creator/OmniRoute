"""Every Hebrew line the supervisor work sends the owner, in one table (supervisor spec, section 8).

Standard library only: the parent process, the engine, the watcher and the slots all render from here, so a line is
written once and one test checks all of them: each ends with "כסף נייר" and stays under supervisor.max_line_bytes.
The numbers (the byte limit, the names in {held}, the length of a free text) come from config.json through the caller.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

# id -> (priority, template). The templates are the table of spec section 8, character for character. A spec
# placeholder keeps its name, except the times: the first {HH:MM} or {HH:MM:SS} of a line is {time}, a second one is
# {time2}, and {DD.MM} is {date}. DM1 and DM2 are "urgent or high" in the spec: priority() decides.
LINES: dict[str, tuple[str, str]] = {
    "R1": ("high", "מנוע החדשות נפל ב-{time} ({cause}) וחזר אחרי {down_s} שניות{falls}. סטופים לא נבדקו {blind_s} שניות."
                   " פתוח: {held}.{sold}{code} הפעלה מחדש מספר {n} היום. שעון ישראל. כסף נייר"),
    "R2": ("high", "מנוע החדשות נתקע: {s} שניות בלי פעימה. נהרג והופעל מחדש ב-{time}. סטופים לא נבדקו {blind_s} שניות. פתוח:"
                   " {held}. שעון ישראל. כסף נייר"),
    "R3": ("urgent", "מנוע החדשות נפל {k} פעמים ב-{m} דקות. המפקח הפסיק להפעיל אותו. סטופים לא נבדקים עכשיו. פתוח: {held}. סשן"
                     " הסוחר מנסה שוב פעם אחת. כסף נייר"),
    "R3c": ("urgent", "מנוע החדשות לא עולה: משיכה מ-git לא הסתיימה בתיקייה שלו. סטופים לא נבדקים. פתוח: {held}. סשן הסוחר מטפל"
                      " בזה עכשיו. כסף נייר"),
    "R3b": ("urgent", "מנוע החדשות נפל שוב אחרי הניסיון החוזר. סטופים לא נבדקים. פתוח: {held}. ניסיון נוסף רק בבדיקה המתוזמנת"
                      " הבאה (עד חצי שעה). היום לא אשלח על זה עוד שורות, רק סיכום בסגירה. כסף נייר"),
    "R4": ("high", "המכונה של הבוט לא רצה מ-{time} עד {time2}: {m} דקות בשעות המסחר. סטופים לא נבדקו בזמן הזה. פתוח: {held}."
                   " המנוע רץ שוב. שעון ישראל. כסף נייר"),
    "R4b": ("high", "המפקח נעצר ב-{time} ({why}) ולא הופעל מחדש עד {time2}: {m} דקות בשעות המסחר בלי בדיקת סטופים. פתוח:"
                    " {held}. המנוע רץ שוב. שעון ישראל. כסף נייר"),
    "R4c": ("high", "היום המנוע לא רץ מ-{time} עד סוף המסחר: {m} דקות בלי בדיקת סטופים. פתוח: {held}. שעון ישראל. כסף נייר"),
    "R5a": ("urgent", "יומן מנוע החדשות פגום. המנוע נעצר ולא יופעל עד שהיומן ייבדק. סטופים לא נבדקים. פתוח: {held}. כסף נייר"),
    "R5b": ("urgent", "לוח החגים בהגדרות לא מכסה את השנה. מנוע החדשות נעצר. סטופים לא נבדקים. פתוח: {held}. כסף נייר"),
    "R5c": ("urgent", "מנוע חדשות אחר, שאינו בפיקוח, מחזיק את התיק כבר {s} שניות. המפקח לא מפעיל מנוע שני, ולא ידוע אם האחר"
                      " בודק סטופים. סשן הסוחר מטפל בזה עכשיו. כסף נייר"),
    "R5d": ("urgent", "קובץ התיק של מנוע החדשות חסר או לא קריא, ויש עסקאות ביומן. המנוע לא עולה, כדי לא לדרוס את התיק. סטופים"
                      " לא נבדקים. כסף נייר"),
    "R5e": ("urgent", "מנוע החדשות עדיין עצור מאז {date} ({why}). סטופים לא נבדקים. פתוח: {held}. כסף נייר"),
    "R6": ("urgent", "מנוע החדשות חי, אבל הסטופים לא נבדקו כבר {s} שניות ({names}). כנראה המחירים מ-Yahoo מגיעים לאט. פתוח:"
                     " {held}. כסף נייר"),
    "R6b": ("high", "הסטופים נבדקים שוב, אחרי {s} שניות. כסף נייר"),
    "R7": ("default", "מפקח: {n} שורות נוספות לא נשלחו בשעה האחרונה (הגג הוא {cap} בשעה). הפעלות מחדש היום: {r}. הכל ביומן"
                      " הזמינות. כסף נייר"),
    "R8": ("high", "המפקח נעצר אחרי שעתיים למרות ההגדרה של 9 שעות. חוזרים להחלפה מתוכננת 4 פעמים ביום. כסף נייר"),
    "R9": ("default", 'ייתכן שתקבל בקרוב אזעקת "דממה" מ-ntfy. היא שגויה: יום המסחר נגמר כרגיל, והביטול לא הגיע ל-ntfy. כסף נייר'),
    "R10": ("high", "מכסת ההודעות היומית ב-ntfy נגמרה או כמעט נגמרה. האזעקה מבחוץ כבויה עד {time}. המנוע עצמו עובד. שעון"
                    " ישראל. כסף נייר"),
    "R11": ("default", "סיכום יום: המנוע נפל {r} פעמים, המפקח עצר {t} פעמים, {m} דקות בשעות המסחר בלי בדיקת סטופים. כסף נייר"),
    "R12": ("high", "המפקח עצמו קרס (תקלה בקוד שלו). הפעלתי אותו מחדש פעם אחת. כסף נייר"),
    "E1": ("urgent", "ביומן העסקאות יש {side} של {sym} שהתיק לא מכיר (כנראה עצירה באמצע כתיבה). המנוע בודק סטופים על מה שבתיק"
                     " ולא פותח פוזיציות חדשות. סשן הסוחר צריך ליישב את זה. כסף נייר"),
    "E2": ("urgent", "מנוע החדשות רץ בלי נעילה (הנעילה לא עבדה). סטופים נבדקים. סשן הסוחר צריך לוודא שרץ רק מנוע אחד. כסף נייר"),
    "DM1": ("high", "לא התקבלה פעימה ממנוע החדשות מאז {time} (יותר מ-6 דקות). המכונה נרדמה או נפלה, המנוע נתקע, או שאין קשר"
                    " ל-ntfy. בשעות המסחר סטופים לא נבדקים עד שהמנוע חוזר. פתוח: {held}. הבדיקה המתוזמנת הבאה מפעילה מחדש."
                    " שעון ישראל. כסף נייר"),
    "DM2": ("high", "המפקח נעצר ב-{time} ולא הופעל מחדש כבר 10 דקות. סטופים לא נבדקים. פתוח: {held}. הבדיקה המתוזמנת הבאה"
                    " מפעילה מחדש. שעון ישראל. כסף נייר"),
    "DM3": ("low", "סוף יום המסחר. האזעקה של המנוע לא בוטלה בזמן ב-ntfy. זו לא תקלה. כסף נייר"),
    "DM4": ("default", "מכסת ההודעות היומית ב-ntfy כמעט נגמרה. האזעקה מבחוץ כבויה עד {time}. המנוע עצמו עובד. שעון ישראל. כסף"
                       " נייר"),
    "W0": ("high", "משגיח: הבדיקה עצמה נכשלה ({what}). כרגע אני לא רואה את המנוע ואת המשבצות. כסף נייר"),
    "W1": ("urgent", "משגיח: מנוע החדשות שותק מאז {time}. הפעלתי את בדיקת המנוע לפני {m} דקות והוא עדיין שותק. שעון ישראל. כסף"
                     " נייר"),
    "W2": ("default", 'משגיח: "{he}" של {time} לא רצה. הפעלתי אותה שוב. שעון ישראל. כסף נייר'),
    "W2b": ("default", 'משגיח: "{he}" של {time} לא רצה. היא לא מופעלת שוב לבד. שעון ישראל. כסף נייר'),
    "W3": ("high", 'משגיח: "{he}" של {time} לא רצה גם אחרי הפעלה חוזרת. כדאי לפתוח את סשן הסוחר ולראות מה תקוע שם. שעון'
                   " ישראל. כסף נייר"),
    "W4": ("high", 'משגיח: "{he}" של {time} רצה ונכשלה: {note}. שעון ישראל. כסף נייר'),
    "W4b": ("high", 'משגיח: "{he}" של {time} התחילה ולא הסתיימה כבר {m} דקות. שעון ישראל. כסף נייר'),
    "W6": ("high", "התרגיל השבועי נכשל: המשגיח לא תפס משבצת חסרה. עד שזה מתוקן אי אפשר לסמוך עליו. כסף נייר"),
    "W7": ("high", "המשגיח לא רץ כבר {m} דקות, או שהוא מחכה לאישור. בדיקת המשבצות לא פועלת. כסף נייר"),
    "S1": ("default", "המשימות המתוזמנות לא תואמות להגדרות: {what}. כסף נייר"),
    "S2": ("high", "משיכה מ-git נעצרה על התנגשות בקובץ {file}. לא מחקתי כלום, והמנוע ממשיך לרוץ על מה שיש. כסף נייר"),
}

# The pieces a line is built with. R1's {falls}, {sold} and {code} are passed to render already built ("" when they do
# not apply); R2.off is R2 with the hang-kill switch off; R4.cold goes in after a restore from git.
PARTS: dict[str, str] = {
    "R1.falls": " ({k} נפילות ברצף)",
    "R1.sold": " נמכר בהפעלה: {sym} בסטופ {stop}, במחיר {fill}.",
    "R1.code": " נטען קוד חדש ({commit}).",
    "R2.off": "מנוע החדשות נתקע: {s} שניות בלי פעימה. לא נהרג, המתג כבוי. פתוח: {held}. כסף נייר",
    "R4.cold": " המצב שוחזר מ-git של {cold_time}; מה שקרה אחריו ולא נשמר אבד.",
}

# The owner's word for an internal code. The spec gives no words for E1's {side}; these two were decided with the table.
WORDS: dict[str, dict] = {
    "cause": {"crash": "קרס", "killed": "נהרג", "stopped": "נעצר"},
    "R4b.why": {"handover": "החלפה מתוכננת", "crash_loop": "נפילות חוזרות", "signal": "אות עצירה", "orphaned": "אות עצירה"},
    "R5e.why": {4: "יומן פגום", 5: "לוח חגים", 6: "קובץ התיק"},
    "W0.what": {"sync": "אין גישה לקוד", "crash": "הפקודה קרסה", "ntfy": "אין קריאה מ-ntfy", "fire": "אי אפשר להפעיל משימה"},
    "E1.side": {"BUY": "קנייה", "SELL": "מכירה"},
}

FREE = ("note", "what", "file", "names")  # fields whose text comes from outside this table: render cuts them


def held_text(held: dict[str, float], max_names: int) -> str:
    """{held} from {symbol: stop}: "MU (סטופ 708.97)" for each name, at most max_names of them and then "ועוד {n}"."""
    if not held:
        return "אין פוזיציות"
    more = len(held) - max_names
    names = ", ".join(f"{sym} (סטופ {stop:.2f})" for sym, stop in list(held.items())[:max_names])
    return names + (f" ועוד {more}" if more > 0 else "")


def sold_text(sales: list[dict], max_names: int) -> str:
    """R1's {sold}: PARTS["R1.sold"] for each sale {sym, stop, fill}, at most max_names of them and then " ועוד {n}.".
    The tail has its own full stop, as every sale has: R1 goes on with its next sentence right after {sold}."""
    more = len(sales) - max_names
    text = "".join(PARTS["R1.sold"].format(sym=s["sym"], stop=f"{s['stop']:.2f}", fill=f"{s['fill']:.2f}")
                   for s in sales[:max_names])
    return text + (f" ועוד {more}." if more > 0 else "")


def hhmm(t: datetime, tz: str, seconds: bool = False) -> str:
    """t on the owner's clock (supervisor.owner_tz), as HH:MM or HH:MM:SS."""
    return t.astimezone(ZoneInfo(tz)).strftime("%H:%M:%S" if seconds else "%H:%M")


def priority(line_id: str, held: bool = False) -> str:
    """The line's priority. The dead-man's DM1 and DM2 are urgent when a name is held, else high (spec 6)."""
    return "urgent" if held and line_id in ("DM1", "DM2") else LINES[line_id][0]


def render(line_id: str, *, max_bytes: int, free_chars: int, off: bool = False, cold_time: str | None = None,
           **fields) -> str:
    """The line as the owner reads it. off=True takes the line's ".off" form in place of its template; cold_time adds
    its ".cold" part right before " שעון ישראל". Every FREE field is cut to free_chars characters first, so a long note,
    file name or difference list shortens the line and never fails it.
    KeyError: an unknown id or form, or a field the template names is missing. ValueError: still over max_bytes."""
    template = PARTS[f"{line_id}.off"] if off else LINES[line_id][1]
    if cold_time is not None:
        head, israel_time, tail = template.rpartition(" שעון ישראל")
        template = head + PARTS[f"{line_id}.cold"] + israel_time + tail
    cut = {k: str(v)[:free_chars] if k in FREE else v for k, v in fields.items()}
    line = template.format(cold_time=cold_time, **cut)
    size = len(line.encode())
    if size > max_bytes:
        raise ValueError(f"owner line {line_id} is {size} bytes, over the limit of {max_bytes}")
    return line
