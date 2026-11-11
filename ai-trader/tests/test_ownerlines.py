"""The owner's lines (supervisor spec, section 8): one table, and every line fits the phone and says paper money."""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import os
import string
import unittest
from datetime import datetime, timezone

from aitrader import ownerlines

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
        self.assertEqual(ownerlines.held_text({"A": 1.0, "B": 2.5, "C": 3.0}, 2),   # past the cap a name is counted, not listed
                         "A (סטופ 1.00), B (סטופ 2.50) ועוד 1")
        sales = [{"sym": f"S{i}", "stop": 48.5, "fill": 48.0} for i in range(8)]
        self.assertEqual((ownerlines.sold_text([], 6), ownerlines.sold_text(sales, 6).count("נמכר בהפעלה"), ownerlines.sold_text(sales, 6).endswith("ועוד 2.")), ("", 6, True))

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
            ownerlines.render("W4", max_bytes=80, free_chars=200, he="x", time="12:34", note="y")   # the line is 87 bytes
        self.assertFalse([v for v in no_phone.PHONE_VARS if v in os.environ])
        self.assertEqual(no_phone.clean_env()["NO_PROXY"], "127.0.0.1")

    def test_the_owners_clock_the_dead_man_priority_and_the_three_key_errors(self):   # what no test above calls
        winter, summer = (datetime(2026, month, 10, 15, 2, 11, tzinfo=timezone.utc) for month in (11, 7))
        self.assertEqual((ownerlines.hhmm(winter, "Asia/Jerusalem"), ownerlines.hhmm(winter, "Asia/Jerusalem", seconds=True),
                          ownerlines.hhmm(summer, "Asia/Jerusalem")), ("17:02", "17:02:11", "18:02"))
        self.assertEqual([ownerlines.priority(i, held) for i in ("DM1", "DM2", "R1", "DM3") for held in (True, False)],
                         ["urgent", "high", "urgent", "high", "high", "high", "low", "low"])
        self.assertTrue(ownerlines.render("R6b", **LIM, s=5).endswith("כסף נייר"))   # R6b needs {s} and nothing else
        for bad in ({"line_id": "R99"},                               # no such id
                    {"line_id": "R6b"},                               # a field the template names is missing
                    {"line_id": "R6b", "s": 5, "off": True},          # a form the line does not have
                    {"line_id": "R6b", "s": 5, "cold_time": "07:42"}):
            with self.assertRaises(KeyError, msg=bad):
                ownerlines.render(**bad, **LIM)
