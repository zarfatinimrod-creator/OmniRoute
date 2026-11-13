### Task 2: The owner's lines in one table

**Kind:** BUILD. **Spec:** 8, 6 ("Size"), 11.1 (the 20-names test).

**Files:** Create `aitrader/ownerlines.py`, `tests/helpers/__init__.py` (empty), `tests/helpers/no_phone.py`, `tests/test_ownerlines.py`.

**Interfaces:** Consumes nothing. Produces:

```python
# tests/helpers/no_phone.py
PHONE_VARS = ("AITRADER_NTFY_TOPIC", "AITRADER_TELEGRAM_TOKEN", "AITRADER_TELEGRAM_CHAT")  # popped from os.environ at import
def clean_env(**extra: str) -> dict[str, str]  # PATH, HOME, PYTHONPATH=<ai-trader>, NO_PROXY=127.0.0.1, then extra; no AITRADER_*, no *_proxy / *_PROXY

# aitrader/ownerlines.py (standard library only)
LINES: dict[str, tuple[str, str]]   # id -> (priority, template); priority is "urgent" | "high" | "default" | "low"
PARTS: dict[str, str]               # "R1.falls", "R1.sold", "R1.code", "R2.off", "R4.cold"
WORDS: dict[str, dict]              # "cause", "R4b.why", "R5e.why", "W0.what", "E1.side"
FREE = ("note", "what", "file", "names")                          # fields whose text comes from outside this table
def held_text(held: dict[str, float], max_names: int) -> str
def sold_text(sales: list[dict], max_names: int) -> str           # PARTS["R1.sold"] per sale {sym, stop, fill}; after max_names: " ועוד {n}"
def hhmm(t: datetime, tz: str, seconds: bool = False) -> str      # the owner's clock
def priority(line_id: str, held: bool = False) -> str             # DM1 and DM2: "urgent" when a name is held, else "high"
def render(line_id: str, *, max_bytes: int, free_chars: int, off: bool = False, cold_time: str | None = None, **fields) -> str
    # KeyError: unknown id or missing field; ValueError: still over max_bytes after the FREE fields were cut
```

- Every template is copied character for character from the table of spec 8. A spec placeholder keeps its name, except the times: the first `{HH:MM}` or `{HH:MM:SS}` of a line is `{time}`, a second one `{time2}`, `{DD.MM}` is `{date}`.
- `WORDS`: `cause` = {"crash": "קרס", "killed": "נהרג", "stopped": "נעצר"}; `R4b.why` = {"handover": "החלפה מתוכננת", "crash_loop": "נפילות חוזרות", "signal": "אות עצירה", "orphaned": "אות עצירה"}; `R5e.why` = {4: "יומן פגום", 5: "לוח חגים", 6: "קובץ התיק"}; `W0.what` = {"sync": "אין גישה לקוד", "crash": "הפקודה קרסה", "ntfy": "אין קריאה מ-ntfy", "fire": "אי אפשר להפעיל משימה"}; `E1.side` = {"BUY": "קנייה", "SELL": "מכירה"} (the spec gives no words for `{side}`; these two are decided here).
- `render` cuts each `FREE` field to `free_chars` characters (`supervisor.free_text_max_chars`, 200) before it fills the template: a note the trader wrote, a file name or a difference list must never make a line fail. `render("R2", off=True, ...)` uses `PARTS["R2.off"]` in place of the R2 template (the spec's "switch off" form). `render("R4", cold_time="07:42", ...)` puts `PARTS["R4.cold"]` (its own time placeholder is `{cold_time}`) right before ` שעון ישראל`. `R1`'s `{falls}`, `{sold}` and `{code}` are passed in already built (`""` when they do not apply), `{sold}` by `sold_text(sales, supervisor.held_names_in_line)`.

- [ ] Write `tests/test_ownerlines.py`:

```python
IDS = ("R1 R2 R3 R3c R3b R4 R4b R4c R5a R5b R5c R5d R5e R6 R6b R7 R8 R9 R10 R11 R12 E1 E2 DM1 DM2 DM3 DM4"
       " W0 W1 W2 W2b W3 W4 W4b W6 W7 S1 S2").split()
LIM = {"max_bytes": 1200, "free_chars": 200}

def fill(template, held):   # a long value for every field the template names
    names = {n for _, n, _, _ in string.Formatter().parse(template) if n}
    return {n: held if n == "held" else "12:34:56" if n.startswith("time") else "א" * 700 if n in ownerlines.FREE else 99999 for n in names}

class Lines(unittest.TestCase):
    def test_the_table_has_exactly_the_ids_of_spec_section_8(self):
        self.assertEqual(sorted(ownerlines.LINES), sorted(IDS))

    def test_every_line_with_20_held_names_and_700_letter_free_text_fits_and_ends_with_paper_money(self):   # Review Focus 4
        held = ownerlines.held_text({f"SYM{i:02d}": 1234.56 for i in range(20)}, 6)
        for i in IDS:
            line = ownerlines.render(i, **LIM, **fill(ownerlines.LINES[i][1], held))
            self.assertTrue(line.endswith("כסף נייר") and len(line.encode()) <= 1200, i)
        for kw in ({"off": True}, {}):
            self.assertTrue(ownerlines.render("R2", **LIM, **kw, **fill(ownerlines.LINES["R2"][1] + ownerlines.PARTS["R2.off"], held)).endswith("כסף נייר"))

    def test_held_text_and_sold_text(self):
        self.assertEqual(ownerlines.held_text({}, 6), "אין פוזיציות")
        self.assertEqual(ownerlines.held_text({"MU": 708.97}, 6), "MU (סטופ 708.97)")
        self.assertTrue(ownerlines.held_text({f"S{i:02d}": 1.0 for i in range(20)}, 6).endswith("ועוד 14"))
        sales = [{"sym": f"S{i}", "stop": 48.5, "fill": 48.0} for i in range(8)]
        self.assertEqual((ownerlines.sold_text([], 6), ownerlines.sold_text(sales, 6).count("נמכר בהפעלה"), ownerlines.sold_text(sales, 6).endswith("ועוד 2")), ("", 6, True))

    def test_r1_and_the_two_forms_read_as_the_spec_writes_them(self):
        self.assertEqual(
            ownerlines.render("R1", **LIM, time="17:02:11", cause="קרס", down_s=1, falls="", blind_s=0,
                              held="אין פוזיציות", sold="", code="", n=1),
            "מנוע החדשות נפל ב-17:02:11 (קרס) וחזר אחרי 1 שניות. סטופים לא נבדקו 0 שניות. פתוח: אין פוזיציות."
            " הפעלה מחדש מספר 1 היום. שעון ישראל. כסף נייר")
        self.assertIn("לא נהרג, המתג כבוי", ownerlines.render("R2", **LIM, off=True, s=200, held="אין פוזיציות"))
        r4 = ownerlines.render("R4", **LIM, cold_time="07:42", time="16:00", time2="16:20", m=20, held="אין פוזיציות")
        self.assertIn("המצב שוחזר מ-git של 07:42; מה שקרה אחריו ולא נשמר אבד. שעון ישראל. כסף נייר", r4)

    def test_a_template_over_the_limit_is_refused_and_the_import_leaves_no_phone_variable(self):
        with self.assertRaises(ValueError):
            ownerlines.render("W4", max_bytes=100, free_chars=200, he="x", time="12:34", note="y")
        self.assertFalse([v for v in no_phone.PHONE_VARS if v in os.environ])
        self.assertEqual(no_phone.clean_env()["NO_PROXY"], "127.0.0.1")
```

- [ ] Run `python3 -m unittest discover -s tests -p 'test_ownerlines.py' -v`. Expected: `ModuleNotFoundError: No module named 'helpers'`.
- [ ] Create `tests/helpers/__init__.py` and `tests/helpers/no_phone.py`, then `aitrader/ownerlines.py` with the signatures above.
- [ ] Run the file again: 5 tests, `OK`. Then the whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/ownerlines.py ai-trader/tests/helpers/__init__.py ai-trader/tests/helpers/no_phone.py ai-trader/tests/test_ownerlines.py`; message `feat(ai-trader): one table for every line the supervisor work sends the owner`.

