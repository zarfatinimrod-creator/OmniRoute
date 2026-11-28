"""The mutants, for snapshot 2 of DEV (mutlens2/work2, sha list in mutlens2/snapshot2.sha). Every edit is anchored on
text of the pristine file, so the list survives a line shift; an anchor that is not found exactly once is an error."""
from pathlib import Path

PRISTINE = Path(__file__).resolve().parent.parent / "work5"
NL, PM, MN, JN, CJ = "aitrader/news_live.py", "aitrader/postmortem.py", "aitrader/__main__.py", "aitrader/journal.py", "config.json"
MUTANTS = []
_lines = {}


def at(file, anchor, k=None):
    if file not in _lines:
        _lines[file] = (PRISTINE / file).read_text(encoding="utf-8").split("\n")
    hits = [i + 1 for i, l in enumerate(_lines[file]) if anchor in l]
    if k is None:
        if len(hits) != 1:
            raise ValueError(f"{file}: anchor {anchor!r} found {len(hits)} times {hits[:6]}")
        return hits[0]
    return hits[k - 1]


class F:
    def __init__(self, file):
        self.file = file

    def m(self, id, note, *edits):
        MUTANTS.append({"id": id, "file": self.file, "note": note, "edits": list(edits)})

    def s(self, anchor, old, new, k=None):          # replace old by new in the one line that holds anchor
        return ("sub", at(self.file, anchor, k), old, new)

    def u(self, old, new):                          # old is its own anchor
        return ("sub", at(self.file, old), old, new)

    def r(self, anchor, n, new, k=None, off=0):     # replace n lines starting off lines after the anchor line
        a = at(self.file, anchor, k) + off
        return ("rep", a, a + n - 1, new)

    def mv(self, anchor, n, dest_anchor, k=None, dk=None):
        a = at(self.file, anchor, k)
        return ("move", a, a + n - 1, at(self.file, dest_anchor, dk))

    def t(self, old, new):
        return ("txt", 0, old, new)


N, P, M, J, C = F(NL), F(PM), F(MN), F(JN), F(CJ)

# ================================================================== news_live.py
# ---- DEFAULTS / TRIAL_GUARDS / words in config
DEF1 = '"require_known_move": True, "max_day_move_pct_to_buy": 3.0'
DEF2 = '"verify_buys": True, "verify_calls": 2'
DEF3 = '"stop_catchup": "alert", "stop_catchup_gap_seconds": 90,'
N.m("D01", "default: block_buys_until_loss_reviewed True->False", N.s('    "block_buys_until_loss_reviewed": True,', "True", "False"))
N.m("D02", "default: require_known_move True->False", N.s(DEF1, '"require_known_move": True', '"require_known_move": False'))
N.m("D03", "default: max_day_move_pct_to_buy 3.0->0 (off)", N.s(DEF1, '"max_day_move_pct_to_buy": 3.0', '"max_day_move_pct_to_buy": 0'))
N.m("D04", "default: rebuy_cooldown_sessions 1->0 (off)", N.s(DEF1, '"rebuy_cooldown_sessions": 1', '"rebuy_cooldown_sessions": 0'))
N.m("D05", "default: verify_buys True->False", N.s(DEF2, '"verify_buys": True', '"verify_buys": False'))
N.m("D06", "default: verify_calls 2->1", N.s(DEF2, '"verify_calls": 2', '"verify_calls": 1'))
N.m("D07", "default: verify_rescore True->False", N.s(DEF2, '"verify_rescore": True', '"verify_rescore": False'))
N.m("D08", "default: stop_catchup alert->sell", N.s(DEF3, '"stop_catchup": "alert"', '"stop_catchup": "sell"'))
N.m("D09", "default: stop_catchup_gap_seconds 90->86400", N.s(DEF3, '"stop_catchup_gap_seconds": 90', '"stop_catchup_gap_seconds": 86400'))
N.m("D10", "default: guards log->enforce", N.s('    "guards": "log",', '"log"', '"enforce"'))
TG = 'TRIAL_GUARDS = ("no_chase", "second_check", "stop_cooldown")'
N.m("D11", "TRIAL_GUARDS gains unknown_move (a repair becomes a trial)", N.s(TG, '"stop_cooldown")', '"stop_cooldown", "unknown_move")'))
N.m("D12", "TRIAL_GUARDS gains loss_review and hold", N.s(TG, '"stop_cooldown")', '"stop_cooldown", "loss_review", "hold")'))
N.m("D13", "TRIAL_GUARDS loses no_chase (enforced in log mode)", N.s(TG, '("no_chase", "second_check", "stop_cooldown")', '("second_check", "stop_cooldown")'))
N.m("D14", "default verify_allow_kinds gains third_party_report",
    N.s('    "verify_allow_kinds": ["company_announcement", "regulator_or_counterparty"],', '"regulator_or_counterparty"]', '"regulator_or_counterparty", "third_party_report"]'))
N.m("D15", "ncfg: defaults override config", N.u('{**DEFAULTS, **cfg.get("news", {})}', '{**cfg.get("news", {}), **DEFAULTS}'))
N.m("D16", "TRIAL_GUARDS loses stop_cooldown (enforced in log mode)", N.s(TG, '("no_chase", "second_check", "stop_cooldown")', '("no_chase", "second_check")'))
N.m("D17", "TRIAL_GUARDS loses second_check", N.s(TG, '("no_chase", "second_check", "stop_cooldown")', '("no_chase", "stop_cooldown")'))
WORDS = 'for key, known, safe in (("stop_catchup", ("alert", "sell", "off"), "alert"), ("guards", ("log", "enforce"), "log")):'
N.m("D18", "unknown stop_catchup word reads as sell", N.s(WORDS, '("alert", "sell", "off"), "alert")', '("alert", "sell", "off"), "sell")'))
N.m("D19", "unknown guards word reads as enforce", N.s(WORDS, '("log", "enforce"), "log")', '("log", "enforce"), "enforce")'))
N.m("D20", "unknown words in config are kept as they are", N.u("if self.n[key] not in known:", "if False:"))
N.m("D21", "unknown word: safe side taken silently", N.r("if self.n[key] not in known:", 2, "                pass", off=1))
N.m("D22", "unknown word: said but not replaced", N.r("self.n = {**self.n, key: safe}", 1, "                pass"))
N.m("D23", "default: trade_outside_hours False->True", N.u('"trade_outside_hours": False', '"trade_outside_hours": True'))

# ---- _buys_blocked
N.m("B01", "_buys_blocked: switch inverted", N.s('        if self.n["block_buys_until_loss_reviewed"]:  # Basic law', "if self.n[", "if not self.n["))
N.m("B02", "_buys_blocked: any book's loss blocks news", N.s('                if postmortem.pending("news"):', 'pending("news")', "pending()"))
N.m("B03", "_buys_blocked: pending inverted", N.s('                if postmortem.pending("news"):', "if postmortem", "if not postmortem"))
N.m("B04", "_buys_blocked: unreadable ledger fails OPEN", N.r('return ("loss_review", "אי אפשר לקרוא את קובץ התחקירים', 2, "                return None"))
N.m("B05", "_buys_blocked: log flag inverted", N.u("                    if log:", "                    if not log:"))
N.m("B06", "_buys_blocked: hold never acted on", N.s("        if hold:", "if hold:", "if False:"))
N.m("B07", "_buys_blocked: hold labelled loss_review", N.u('return ("hold",', 'return ("loss_review",'))
N.m("B08", "_buys_blocked: unreadable ledger raises instead of blocking",
    N.s("except Exception as e:  # noqa: BLE001 - a ledger that cannot be read must not open a position", "except Exception as e:", "except KeyError as e:"))
N.m("B09", "_buys_blocked: failure to journal the error escapes",
    N.r("try:  # and a failure to write that down must not leave this check either", 6,
        '                if log:\n                    journal.append("news_errors.jsonl", {"at": journal.now_utc(), "error": type(e).__name__,\n'
        '                                                         "detail": str(e)[:300], "where": "postmortem"})'))
N.m("B10", "_buys_blocked: a pending loss labelled hold", N.s('return ("loss_review", "יש הפסד', '("loss_review",', '("hold",'))
N.m("B11", "_buys_blocked: hold only asked while the loss-review switch is on",
    N.r("        hold = buy_hold()", 3, "            hold = buy_hold()\n            if hold:\n"
        "                return (\"hold\", f\"קניות חדשות עצורות: {hold['reason']}. סטופים ומכירות עובדים כרגיל\")"))

# ---- _note_check / _refuse
N.m("N01", "_note_check: write failure escapes",
    N.r('            journal.append("news_checks.jsonl", {"at": journal.now_utc(), **row})', 8,
        '        journal.append("news_checks.jsonl", {"at": journal.now_utc(), **row})', off=-1))
N.m("N02", "_note_check: write failure not put in news_errors",
    N.r('            journal.append("news_checks.jsonl", {"at": journal.now_utc(), **row})', 5, "            pass", off=2))
TR = 'trial = guard in TRIAL_GUARDS and self.n["guards"] != "enforce"'
N.m("R01", "_refuse: enforce/log swapped", N.s(TR, '!= "enforce"', '== "enforce"'))
N.m("R02", "_refuse: every guard is a trial in log mode", N.s(TR, "guard in TRIAL_GUARDS and ", ""))
N.m("R03", "_refuse: a trial refuses (log mode changes a trade)", N.r("        if trial:", 1, "            return True", off=1))
N.m("R04", "_refuse: enforce does not refuse", N.r('        events.append(f"{sym} ציון {score}: לא קונים. {text}")', 1, "        return False", off=1))
N.m("R05", "_refuse: verdict words swapped", N.u('"would_refuse" if trial else "refused"', '"refused" if trial else "would_refuse"'))
N.m("R06", "_refuse: owner not told", N.r('        events.append(f"{sym} ציון {score}: לא קונים. {text}")', 1, "        pass"))
N.m("R07", "_refuse: no row in news_checks", N.r('        self._note_check({"symbol": sym, "score": score, "verdict": "would_refuse"', 2, "        pass"))
N.m("R08", "_refuse: and->or", N.s(TR, "in TRIAL_GUARDS and", "in TRIAL_GUARDS or"))
N.m("R09", "_refuse: trial only when the word is exactly log", N.s(TR, '!= "enforce"', '== "log"'))

# ---- _buy
N.m("Y01", "_buy: cooldown switch inverted", N.s('        if stops and self.n["rebuy_cooldown_sessions"]:', "and self.n[", "and not self.n["))
N.m("Y02", "_buy: cooldown off by one (< -> <=)", N.u('cooling = since < self.n["rebuy_cooldown_sessions"]', 'cooling = since <= self.n["rebuy_cooldown_sessions"]'))
N.m("Y03", "_buy: cooldown counts the stop day itself", N.s("pd.bdate_range(max(stops), today)[1:]", "[1:]", ""))
N.m("Y04", "_buy: any sale starts the cooldown", N.s("        stops = [str(t.get(\"date\")) for t in mine", ' and str(t.get("reason")).startswith("stop")', ""))
N.m("Y05", "_buy: cooldown measured from the OLDEST stop", N.s("pd.bdate_range(max(stops), today)[1:]", "max(stops)", "min(stops)"))
N.m("Y06", "_buy: move checks only when there is no move", N.u("        if move is not _NO_MOVE:", "        if move is _NO_MOVE:"))
N.m("Y07", "_buy: require_known_move inverted", N.s('                if self.n["require_known_move"]:', "if self.n[", "if not self.n["))
N.m("Y08", "_buy: unknown move refusal is a no-op (buys)", N.r('self._refuse(sym, score, events, "unknown_move"', 1, "                    pass", off=1))
NC = "chase, said = bool(limit) and move >= limit, "
N.m("Y09", "_buy: no_chase limit exclusive", N.s(NC, "move >= limit", "move > limit"))
N.m("Y10", "_buy: no_chase on abs(move)", N.s(NC, "move >= limit", "abs(move) >= limit"))
N.m("Y11", "_buy: block/hold refusal is a no-op (BUYS THROUGH A BLOCK)", N.r("        blocked = self._buys_blocked()", 1, "            pass", off=4))
N.m("Y12", "_buy: block never asked", N.s("        blocked = self._buys_blocked()", "self._buys_blocked()", "None"))
N.m("Y13", "_buy: block judged before the guards", N.mv("        blocked = self._buys_blocked()", 5, "        stops = [str(t.get(\"date\")) for t in mine"))
N.m("Y14", "_buy: other names' trades count", N.s('        mine = [t for t in journal.read("news_trades.jsonl")', ' if t.get("symbol") == sym', ""))
N.m("Y15", "_buy: operator exit of another day keeps the name out", N.s("        if sym in exit_requests()[0] or any(", 't.get("date") == today', 't.get("date") != today'))
N.m("Y16", "_buy: block only asked when there is a move (outside-hours buys skip block and hold)",
    N.r("        blocked = self._buys_blocked()", 5,
        "            blocked = self._buys_blocked()\n            if blocked:\n                self._refuse(sym, score, events, blocked[0], blocked[1], price=px,\n"
        "                             day_move_pct=None if move is _NO_MOVE else move, id=ref)\n                return None"))
N.m("Y17", "_buy: stop_cooldown refusal is a no-op", N.r('sym, score, events, "stop_cooldown"', 1, "                pass", off=2))
N.m("Y18", "_buy: no_chase refusal is a no-op", N.r("day_move_pct=move, limit=limit, price=px, id=ref):", 1, "                    pass", off=1))
N.m("Y20", "_buy: limit 0 no longer switches no_chase off", N.s(NC, "bool(limit) and move >= limit", "move >= limit"))
N.m("Y22", "_buy: a waiting owner exit request no longer stops the buy", N.u("        if sym in exit_requests()[0] or any(", "        if any("))
N.m("Y30", "_buy: a buy writes no row of its own", N.r('        self._note_check({"symbol": sym, "score": score, "verdict": "bought"', 2, "        pass"))
N.m("Y31", "_buy: full book refused silently", N.r('"no_room", "התיק מלא', 1, "            pass"))
N.m("Y32", "_buy: too-dear share refused silently", N.r('"no_room", "המחיר של מניה אחת', 1, "            pass"))
N.m("Y33", "_buy: the block's row has no price", N.s("            self._refuse(sym, score, events, blocked[0], blocked[1], price=px,", "price=px,", ""))

# ---- _sell / check_stops
SELL = 'f.update({"reason": reason, "quote": px, "quote_at": QUOTE_TIME.get(sym), "stop": stop})'
N.m("S01", "_sell: quote, quote_at, stop not on the row", N.s(SELL, ', "quote": px, "quote_at": QUOTE_TIME.get(sym), "stop": stop', ""))
N.m("S02", "_sell: quote_at always None", N.s(SELL, '"quote_at": QUOTE_TIME.get(sym)', '"quote_at": None'))
N.m("S03", "_sell: stop always None", N.s(SELL, '"stop": stop', '"stop": None'))
N.m("S04", "_sell: a hold holds back EVERY sale", N.r('        stop = pos.get("stop_price")', 1, "        if buy_hold():\n            return None\n        stop = pos.get(\"stop_price\")"))
N.m("S05", "check_stops: sales held back while buys are blocked", N.s("            if reason:", "if reason:", "if reason and not self._buys_blocked(log=False):"))
BAD = '            elif s["score"] <= self.n["sell_on_score_at_most"] and x["symbol"] in self.book.positions and px and live:'
N.m("S06", "handle_scored: bad-news sale held back by a hold", N.s(BAD, "and px and live:", "and px and live and not buy_hold():"))
N.m("S07", "handle_scored: bad-news sale held back while buys are blocked", N.s(BAD, "and px and live:", "and px and live and not self._buys_blocked(log=False):"))
N.m("S08", "check_stops: owner's exit held back by a hold",
    N.s("            if sym in exits and self._quote_is_live(QUOTE_TIME.get(sym), None, now):", "if sym in exits and self._quote_is_live", "if sym in exits and not buy_hold() and self._quote_is_live"))
MH = '            elif self.n.get("max_hold_days"):'
N.m("S09", "check_stops: time exit held back by a hold", N.s(MH, 'elif self.n.get("max_hold_days"):', 'elif self.n.get("max_hold_days") and not buy_hold():'))
BR = '            elif (self.n["stop_catchup"] == "sell" and pos.get("stop_breach")'
N.m("S10", "check_stops: breach sale (sell mode) held back by a hold", N.s(BR, 'and pos.get("stop_breach")', 'and pos.get("stop_breach") and not buy_hold()'))
N.m("S11", "check_stops: time exit held back while a loss waits", N.s(MH, 'elif self.n.get("max_hold_days"):', 'elif self.n.get("max_hold_days") and not self._buys_blocked(log=False):'))
N.m("S12", "check_stops: the price stop held back by a hold",
    N.s("            elif px <= pos.get(\"stop_price\", pos[\"avg_cost\"] * (1 - self.n[\"stop_loss_pct\"])):", "elif px <= pos.get(", "elif not buy_hold() and px <= pos.get("))
N.m("C01", "check_stops: breach sold in every mode but sell", N.s(BR, '== "sell"', '!= "sell"'))
N.m("C02", "check_stops: breach sold without a live quote", N.r("                  and self._quote_is_live(QUOTE_TIME.get(sym), None, now)):", 1, "                  ):"))
N.m("C03", "check_stops: sell mode sells with no breach", N.s(BR, ' and pos.get("stop_breach")', ' and (pos.get("stop_breach") or {"found_at": journal.now_utc(), "low": 0.0, "at": "x"})')
    , N.r("                b = pos[\"stop_breach\"]", 1, '                b = pos.get("stop_breach") or {"found_at": journal.now_utc(), "low": 0.0, "at": "x"}')
    , N.s('                  and str(pos["stop_breach"].get("found_at", ""))[:10] == journal.now_utc()[:10]', 'str(pos["stop_breach"].get("found_at", ""))[:10] == journal.now_utc()[:10]', "True"))
N.m("C04", "check_stops: the clock of the last look is never set", N.r("        self._stops_checked_at = now.astimezone(timezone.utc)", 1, "        self._stops_checked_at = getattr(self, '_stops_checked_at', None)"))
N.m("C05", "check_stops: alert mode sells on the memory of a breach", N.s(BR, '== "sell"', 'in ("sell", "alert")'))
N.m("C06", "check_stops: a mark from an earlier day sells after a later switch",
    N.s('                  and str(pos["stop_breach"].get("found_at", ""))[:10] == journal.now_utc()[:10]', 'str(pos["stop_breach"].get("found_at", ""))[:10] == journal.now_utc()[:10]', "True"))
N.m("C07", "check_stops: a stale quote counts as a look at the name", N.s("                    if live:  # only a live quote counts as a look", "if live:", "if True:"))
N.m("C08", "check_stops: a live quote does not count as a look at the name", N.s("                    if live:  # only a live quote counts as a look", "if live:", "if False:"))

# ---- _last_stop_check
N.m("L01", "_last_stop_check: own clock ignored", N.s('        at = getattr(self, "_stops_checked_at", None)', 'getattr(self, "_stops_checked_at", None)', "None"))
N.m("L02", "_last_stop_check: heartbeat's own time, not the stops'", N.u('["stops_checked_at"])', '["at"])'))
N.m("L03", "_last_stop_check: first equity point, not last", N.s('at = datetime.fromisoformat(journal.read("news_equity.jsonl")[-1]["at"])', "[-1]", "[0]"))
N.m("L04", "_last_stop_check: equity curve before heartbeat",
    N.mv("        if at is None:", 5, "        if at is None:", k=2, dk=1))
N.m("L05", "_last_stop_check: a naive time stays naive", N.r("        if at is not None and at.tzinfo is None:", 2, ""))
N.m("L06", "_last_stop_check: no equity fallback", N.r('at = datetime.fromisoformat(journal.read("news_equity.jsonl")[-1]["at"])', 5, "", off=-2))

# ---- catch_up_stops
GAP = 'if looked is not None and (now - looked).total_seconds() <= self.n["stop_catchup_gap_seconds"]:'
N.m("U01", "catch_up: alert mode does not look", N.u('if mode not in ("alert", "sell") or not self.book.positions:', 'if mode not in ("sell",) or not self.book.positions:'))
N.m("U02", "catch_up: gap test inverted", N.s(GAP, "<=", ">"))
N.m("U03", "catch_up: any gap is a gap", N.s(GAP, 'self.n["stop_catchup_gap_seconds"]', "0"))
N.m("U04", "catch_up: a known breach is looked for again (alert every gap)", N.r('            if str((pos.get("stop_breach") or {}).get("found_at", ""))[:10] == journal.now_utc()[:10]:', 2, ""))
N.m("U05", "catch_up: the entry minute's own bar is read", N.u(" + timedelta(minutes=1))", ")"))
N.m("U06", "catch_up: no wait for a completed minute", N.r('                if (now - since).total_seconds() < self.n["stop_catchup_min_seconds"]:', 2, ""))
N.m("U07", "catch_up: low AT the stop is not under", N.s("under.extend(b for b in", "lo <= stop", "lo < stop"))
N.m("U08", "catch_up: close AT the stop is not under", N.s("closed_under = [(t, lo) for t, lo, c in bars if c <= stop]", "c <= stop", "c < stop"))
TWO = '                if closed_under or len(under) >= self.n["stop_catchup_min_lows"]:'
N.m("U09", "catch_up: one low is enough", N.s(TWO, '>= self.n["stop_catchup_min_lows"]', ">= 1"))
N.m("U10", "catch_up: three lows needed", N.s(TWO, '>= self.n["stop_catchup_min_lows"]', ">= 3"))
N.m("U11", "catch_up: close AND two lows", N.s(TWO, "closed_under or", "closed_under and"))
N.m("U12", "catch_up: reports the highest low under the stop", N.u("t, lo = min(under or closed_under", "t, lo = max(under or closed_under"))
N.m("U13", "catch_up: sell/alert wording swapped", N.s('what = ("המניה נמכרת במחיר החי הראשון"', 'if mode == "sell" else', 'if mode != "sell" else'))
N.m("U14", "catch_up: no urgent alert", N.r('notify.send("AI Trader - סטופ שלא נבדק", text, self.cfg, "urgent")', 1, "                    pass"))
N.m("U15", "catch_up: no event line", N.r("                    events.append(text)", 1, "                    pass"))
N.m("U16", "catch_up: unreadable bars alert every time", N.u('        if sym in getattr(self, "_catchup_blind", set()):', "        if False:"))
N.m("U17", "catch_up: window starts at the earlier of open and last look", N.u("max(opened, looked.astimezone(NY))", "min(opened, looked.astimezone(NY))"))
N.m("U18", "catch_up: whole session every time", N.u("since = opened if looked is None else max(opened, looked.astimezone(NY))", "since = opened"))
N.m("U20", "catch_up: a failure inside escapes", N.s("except Exception as e:  # noqa: BLE001 - a failure here must never cost the normal stop check its turn", "except Exception as e:", "except KeyError as e:"))
N.m("U21", "catch_up: window opens at midnight", N.u("hour=hours[0][0], minute=hours[0][1]", "hour=0, minute=0"))
N.m("U22", "catch_up: today's entry not cut out", N.u('if pos.get("entry_date") == now.date().isoformat():', "if False:"))
N.m("U23", "catch_up: bars None treated as no bars (silently)", N.r("                if bars is None:", 4, "                bars = bars or []"))
N.m("U24", "catch_up: the per-name look is ignored", N.u("looked = seen.get(sym, last)", "looked = last"))
N.m("U25", "catch_up: a read stretch is not marked as covered", N.r('                    self._covered[sym] = max(b[0] for b in bars) + timedelta(seconds=60)', 1, "                    pass"))
N.m("U26", "catch_up: lone prints are forgotten between reads", N.u("under = self._unseen_lows.setdefault(sym, [])", "under = []"))
N.m("U27", "catch_up: a print read twice counts twice", N.u(" if b not in under)", ")"))
N.m("U28", "catch_up: 'unwatched' / 'not known' wording swapped", N.s('when = ("בזמן שהסטופ לא נבדק" if looked is not None else', "is not None", "is None"))
N.m("U29", "catch_up: a failure inside is not told to the owner", N.r("                self._note_error(e, \"catch_up_stops\")", 5, "", off=1))
N.m("U30", "catch_up: a failure inside is not put on record", N.r("                self._note_error(e, \"catch_up_stops\")", 1, "                pass"))

# ---- _look_at_stops
N.m("LS1", "_look_at_stops: minute bars before the live quote", N.mv("            self.catch_up_stops(events, last=last, seen=seen)", 6, "            self.check_stops(events)", k=None, dk=1)
    if False else N.r("            self._prev_look = self._last_stop_check()", 1,
                      "            self._prev_look = self._last_stop_check()\n"
                      "        try:\n            self.catch_up_stops(events, now, last=self._prev_look, seen=seen)\n        except Exception as e:  # noqa: BLE001\n"
                      "            self._note_error(e, \"catch_up_stops\")"))
N.m("LS2", "_look_at_stops: gap measured after its own live look", N.u("self.catch_up_stops(events, now, last=self._prev_look, seen=seen)", "self.catch_up_stops(events, now)"))
N.m("LS3", "_look_at_stops: nothing saved at once", N.r("        if len(events) > n:", 2, ""))
N.m("LS4", "_look_at_stops: guarded inverted", N.u("            if not guarded:", "            if guarded:"))
N.m("LS5", "_look_at_stops: a failed live look reported as done", N.r("            looked = False", 1, "            looked = True"))
N.m("LS6", "_look_at_stops: a breach just found waits for the next look", N.r('            if self.n["stop_catchup"] == "sell" and any(p.get("stop_breach")', 2, ""))
N.m("LS7", "_look_at_stops: a broken catch-up costs the look", N.s("except Exception as e:  # noqa: BLE001 - the catch-up is an extra: it never costs the step", "except Exception as e:", "except KeyError as e:"))
N.m("LS8", "_look_at_stops: a failed live look not put on record", N.r('            self._note_error(e, "early_stops")', 1, "            pass"))
N.m("LS9", "_look_at_stops: only last passed on, the per-name looks are read after the live look", N.u("self.catch_up_stops(events, now, last=self._prev_look, seen=seen)", "self.catch_up_stops(events, now, last=self._prev_look)"))
N.m("LS10", "_look_at_stops: alert mode also re-checks (no behaviour) / sell re-check in alert mode", N.s('            if self.n["stop_catchup"] == "sell" and any(p.get("stop_breach")', '== "sell"', '!= "sell"'))

# ---- _log_trade
PAUSE = '        if f["side"] == "SELL" and f.get("realized_pnl", 0) < 0 and self.n["block_buys_until_loss_reviewed"]:'
N.m("P01", "pause line on a break-even sale", N.s(PAUSE, "< 0", "<= 0"))
N.m("P02", "pause line on a winning sale only", N.s(PAUSE, "< 0", "> 0"))
N.m("P03", "pause line with the switch off", N.s(PAUSE, ' and self.n["block_buys_until_loss_reviewed"]', ""))
N.m("P04", "no pause line", N.r(PAUSE, 2, "            pass", off=2))
N.m("P05", "_log_trade: the book is not saved with the trade", N.r("        try:  # the book goes to disk with the journal row", 4, ""))
N.m("P06", "_log_trade: a failing save loses the trade's report", N.s("except Exception as e:  # noqa: BLE001 - the save at the end of the step tries again", "except Exception as e:", "except KeyError as e:"))

# ---- handle_scored
N.m("H01", "handle_scored: enforce/log swapped", N.u('enforce = self.n["guards"] == "enforce"', 'enforce = self.n["guards"] != "enforce"'))
N.m("H02", "handle_scored: check asked before the buy in log mode too", N.u('                    if enforce and self.n["verify_buys"]:', '                    if self.n["verify_buys"]:'))
N.m("H03", "handle_scored: log mode never asks the second check", N.r('                    if not enforce and self.n["verify_buys"]:', 4, ""))
N.m("H04", "handle_scored: LOG MODE RE-QUOTES before the buy (changes price/move of a trade)", N.u('                        if checked and "price_at" in x:', '                        if "price_at" in x:'))
N.m("H05", "handle_scored: move not refreshed after the check", N.u("                            move = fresh if is_open else move", "                            move = move"))
N.m("H06", "handle_scored: no liveness test after the check", N.r("if not (buy_px and self._quote_is_live(QUOTE_TIME.get(sym), x.get(\"published\"))):", 3, ""))
N.m("H07", "handle_scored: buys at the quote from before the check", N.u("                            buy_px, fresh = live_price(sym)", "                            _, fresh = live_price(sym)"))
MOVE = '                        move = x.get("day_move_pct") if is_open else _NO_MOVE'
N.m("H08", "handle_scored: missing move treated as flat", N.s(MOVE, 'x.get("day_move_pct")', 'x.get("day_move_pct", 0.0)'))
N.m("H09", "handle_scored: UNKNOWN MOVE TREATED AS FLAT", N.s(MOVE, 'x.get("day_move_pct")', '(x.get("day_move_pct") or 0.0)'))
N.m("H10", "handle_scored: in session there is 'no move to check'", N.s(MOVE, "if is_open else _NO_MOVE", "if not is_open else _NO_MOVE"))
CHK = '                        checked = "refused" if self._second_check(x, s, events) else "passed"'
N.m("H11", "handle_scored: enforce buys what the check refused", N.s(CHK, '"refused" if self._second_check(x, s, events) else "passed"', '"passed" if self._second_check(x, s, events) else "refused"'))
N.m("H12", "handle_scored: a refusal by the check is ignored", N.u('                    if checked == "refused":', '                    if checked == "never":'))
N.m("H13", "score row: no model/prompt/context", N.u('"model": self.n["model"], "prompt": PROMPT_ID, "context": context_id(),', ""))
N.m("H14", "score row: no link", N.u('"link": x.get("link") or None', '"link": None'))
N.m("H16", "handle_scored: unknown fresh move replaced by the older one", N.u("                            move = fresh if is_open else move", "                            move = fresh if (is_open and fresh is not None) else move"))
N.m("H17", "score row: no description", N.u('"description": x.get("description") or None', '"description": None'))
N.m("H18", "handle_scored: no look at the stops after the enforced check", N.r("                        if is_open:  # the check took seconds", 2, ""))
N.m("H19", "handle_scored: the look after the check is unguarded", N.s("                            self._look_at_stops(events, guarded=True)", "guarded=True", "guarded=False"))
N.m("H20", "handle_scored: a queued name is always marked as passed", N.u('"id": x["key"], "second_check": checked})', '"id": x["key"], "second_check": "passed"})'))
N.m("H21", "handle_scored: on trial the check is asked in the loop (not in the background)",
    N.u("                        self._ask_later(x, s)", "                        self._judge_second(x, s, *self._ask_second(x), [])"))
N.m("H22", "handle_scored: the buy's rows have no headline id", N.u('events, move, ref=x["key"])', "events, move)"))
N.m("H23", "handle_scored: log mode asks even with verify_buys off", N.u('                    if not enforce and self.n["verify_buys"]:', "                    if not enforce:"))
N.m("H24", "handle_scored: enforce asks/requotes even with verify_buys off", N.u('                    if enforce and self.n["verify_buys"]:', "                    if enforce:"))
N.m("H25", "handle_scored: the check is asked for held names too", N.u("                if (buy_px or to_queue) and sym not in self.book.positions:", "                if (buy_px or to_queue):"))
N.m("H26", "handle_scored: the look after the check also when closed", N.u("                        if is_open:  # the check took seconds", "                        if True:  # the check took seconds"))

# ---- second check
N.m("K02", "second check: one call", N.u('calls = max(1, int(self.n["verify_calls"]))', "calls = 1"))
N.m("K03", "second check: verify_model ignored", N.s('        model = self.n.get("verify_model") or self.n["model"]', 'self.n.get("verify_model") or self.n["model"]', 'self.n["model"]'))
ANS = '            if not isinstance(a, dict) or a.get("error") or not {"kind", "confirmed"} <= set(a):'
N.m("K04", "second check: answer with parts missing not caught", N.s(ANS, ' or not {"kind", "confirmed"} <= set(a)', ""))
N.m("K05", "second check: allow list inverted", N.s('            elif a["kind"] not in self.n["verify_allow_kinds"]:', "not in", "in"))
N.m("K06", "second check: truthy counts as confirmed", N.u('a["confirmed"] is not True', 'not a["confirmed"]'))
N.m("K07", "second check: only the first answer counts", N.u("        for a in answers:", "        for a in answers[:1]:"))
N.m("K08", "second check: rescore ignored", N.u("        if not why and again is not _UNSET:", "        if False:"))
N.m("K09", "second check: rescore AT the line passes", N.u('            elif again <= self.n["buy_min_score"]:', '            elif again < self.n["buy_min_score"]:'))
N.m("K10", "second check: a raising checker passes", N.u('                answers[i] = {"error": type(e).__name__}', "                answers[i] = dict(kind=self.n['verify_allow_kinds'][0], confirmed=True)"))
N.m("K11", "second check: refusal not returned", N.u("            return why if self._refuse(", "            return None if self._refuse("))
N.m("K12", "second check: rescore switch ignored", N.u('        if self.n["verify_rescore"]:', "        if True:"), N.u('(second[0] if self.n["verify_rescore"] else _UNSET)', "second[0]"))
N.m("K13", "second check: a pass leaves no row", N.r('        self._note_check({"symbol": x["symbol"], "score": s["score"], "verdict": "passed"', 2, "        pass"))
N.m("K14", "second check: error key not looked at", N.s(ANS, 'a.get("error") or ', ""))
N.m("K17", "second check: rescore asked of verify_model, not the scorer", N.u('second[0] = rescore_headline(x, self.n["model"], timeout)', "second[0] = rescore_headline(x, model, timeout)"))
N.m("K19", "second check: any known kind allowed", N.s('            elif a["kind"] not in self.n["verify_allow_kinds"]:', 'self.n["verify_allow_kinds"]', "VERIFY_KINDS"))
N.m("K20", "second check: checker timeout from config not passed", N.u("verify_headline(x, model, timeout)", "verify_headline(x, model)"))
N.m("K21", "second check: rescore timeout from config not passed", N.u('second[0] = rescore_headline(x, self.n["model"], timeout)', 'second[0] = rescore_headline(x, self.n["model"])'))
N.m("K22", "second check: _second_check ignores its switch", N.r('        if not self.n["verify_buys"]:', 2, "", k=None))
N.m("K23", "drain_trial: a record that fails escapes", N.s("except Exception as e:  # noqa: BLE001 - a record that fails costs nothing but itself", "except Exception as e:", "except KeyError as e:"))
N.m("K24", "drain_trial: answers that are back are never written by a step", N.r("        self.drain_trial()", 1, "        pass"))
N.m("K25", "_run: trial answers still out at the end are dropped", N.r('    nt.drain_trial(wait=0 if market_open_now() else nt.n["verify_timeout_seconds"])', 1, "    pass"))
N.m("K26", "drain_trial: answers not yet back are dropped", N.r("                left.append((box, x, s))", 1, "                pass"))
N.m("K27", "drain_trial: the trial answer is told to the owner as a refusal (events not thrown away)",
    N.u("                self._judge_second(x, s, answers, again, [])", "                self._judge_second(x, s, answers, again, None)"))
N.m("K28", "second check: the timeout is not the configured one", N.u('        timeout = self.n["verify_timeout_seconds"]', "        timeout = 3600"))

# ---- run_queue_at_open
QM = 'live_price(q["symbol"])[1], ref=q.get("id"))'
N.m("Q01", "queue: no move check at the open", N.s(QM, 'live_price(q["symbol"])[1],', "_NO_MOVE,"))
N.m("Q02", "queue: move at the open taken as flat", N.s(QM, 'live_price(q["symbol"])[1],', "0.0,"))
N.m("Q03", "queue: unknown move at the open taken as flat", N.s(QM, 'live_price(q["symbol"])[1],', '(live_price(q["symbol"])[1] or 0.0),'))
N.m("Q04", "queue: move at the open always unknown", N.s(QM, 'live_price(q["symbol"])[1],', "None,"))
QE = '                if self.n["guards"] == "enforce" and self.n["verify_buys"] and q.get("second_check") != "passed":'
N.m("Q05", "queue: the passed/unpassed test inverted", N.s(QE, '!= "passed"', '== "passed"'))
N.m("Q06", "queue: a name queued on trial is bought once enforced", N.s(QE, 'if self.n["guards"] == "enforce" and', 'if False and self.n["guards"] == "enforce" and'))
N.m("Q07", "queue: a failed buy stays queued", N.r("            finally:  # bought or turned down once", 1, "            except Exception:\n                raise\n            else:"))
N.m("Q08", "queue: in LOG mode an unchecked queued name is refused", N.s(QE, 'self.n["guards"] == "enforce" and ', ""))
N.m("Q09", "queue: enforced refusal even with verify_buys off", N.s(QE, ' and self.n["verify_buys"]', ""))

# ---- step / heartbeat
N.m("T01", "step: no early stops", N.u("        if market_open_now():  # stops come first", "        if False:  # stops come first"))
N.m("T05", "step: no stops between batches", N.r('            if i + self.n["batch_max"] < len(new) and market_open_now():', 4, ""))
N.m("T06", "step: a failing early look aborts the step", N.u("            self._early_look = self._look_at_stops(events, guarded=True)", "            self._early_look = self._look_at_stops(events)"))
N.m("T07", "heartbeat: stops_checked_at None", N.u("checked.isoformat() if checked else None", "None"))
N.m("T08", "heartbeat: buys_blocked None", N.u("blocked[0] if blocked else None", "None"))
N.m("T09", "heartbeat's look fills the error journal", N.u("blocked = self._buys_blocked(log=False)", "blocked = self._buys_blocked(log=True)"))
N.m("T10", "heartbeat: code None", N.u('"code": getattr(self, "code", None)})', '"code": None})'))
N.m("T11", "step: no look at the end", N.r("        if market_open_now():\n            self._look_at_stops(events)\n        self.drain_trial()".split("\n")[2], 2, "", off=-2))
N.m("T12", "step: between-batch look only when closed", N.s('            if i + self.n["batch_max"] < len(new) and market_open_now():', "and market_open_now()", "and not market_open_now()"))
N.m("T13", "step: the early look's result is not kept (the alert cannot tell the truth)", N.u("            self._early_look = self._look_at_stops(events, guarded=True)", "            self._look_at_stops(events, guarded=True)"))
N.m("T14", "step: unknown move in session scored as flat", N.u('            x["day_move_pct"] = move if is_open else None', '            x["day_move_pct"] = (move or 0.0) if is_open else None'))
N.m("T15", "_run: the failing-engine alert always says the stops are looked at", N.s('כותרות וקניות לא עובדות" if getattr(nt, "_early_look", None)', 'if getattr(nt, "_early_look", None)', "if True"))

# ---- run() lock
N.m("RL1", "run: starts although another engine holds the book", N.r("        except BlockingIOError:", 2, "            pass", off=1))
N.m("RL2", "run: shared lock (two engines can both hold it)", N.u("fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)", "fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)"))
N.m("RL3", "run: no lock taken", N.u("            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)", "            pass"))
N.m("RL4", "run: a lock file per process", N.u('with open(journal._path("news_engine.lock"), "w") as lock:', 'with open(journal._path(f"news_engine.{os.getpid()}.lock"), "w") as lock:'))
N.m("RL5", "run: 'did not start' reported as a run (0)", N.u("            return 3", "            return 0"))
N.m("RL6", "run: a lock that does not work stops the engine", N.r("        except OSError as e:  # the lock itself does not work here", 1, "            return 3", off=1))
N.m("RL7", "run: blocking lock (a second engine waits and then trades)", N.u("fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)", "fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB) if False else None"))
N.m("RN1", "_run: no code stamp", N.r("    nt.code = code_stamp()", 3, ""))

# ---- buy_hold / set_hold
N.m("BH1", "buy_hold: unreadable file is no hold", N.r("    except Exception:  # noqa: BLE001 - whatever is wrong with the file, the answer is the same: no buys", 1, "        return None", off=1))
N.m("BH2", "buy_hold: any falsy content is no hold", N.u("    if h in (None, {}):", "    if not h:"))
N.m("BH3", "buy_hold: a malformed file is no hold", N.r('    return {"reason": "קובץ העצירה (news_hold.json) לא תקין"', 1, "    return None"))
N.m("BH4", "buy_hold: a dict without a reason is returned as it is", N.u(' and str(h.get("reason") or "").strip():', ":"))
N.m("BH5", "buy_hold: bad JSON escapes", N.s("    except Exception:  # noqa: BLE001 - whatever is wrong with the file, the answer is the same: no buys", "except Exception:", "except OSError:"))
N.m("BH6", "buy_hold: only OSError and ValueError are a hold (too-deep nesting escapes)", N.s("    except Exception:  # noqa: BLE001 - whatever is wrong with the file, the answer is the same: no buys", "except Exception:", "except (OSError, ValueError):"))
N.m("SH1", "set_hold: no reason needed", N.r("    if not reason:", 2, ""))
N.m("SH2", "set_hold: release sets, hold releases", N.u("    h = {} if release else", "    h = {} if not release else"))
N.m("SH3", "set_hold: file not written", N.r('    journal.save_json("news_hold.json", h)', 1, "    pass"))
N.m("SH4", "set_hold: change not journaled", N.r('    journal.append("news_holds.jsonl"', 2, "    pass"))
N.m("SH5", "set_hold: action words swapped", N.u('"release" if release else "hold"', '"hold" if release else "release"'))
N.m("SH6", "set_hold: blank reason accepted", N.u('    reason = _clean(reason or "", 300)', '    reason = (reason or "")'))

# ---- bars_since
BARF = "           if int(t) % 60 == 0 and t0 <= int(t) and int(t) + 60 <= t1 and lo and c]"
N.m("A01", "bars_since: arrays of different length accepted", N.r("    if not (len(stamps) == len(lows) == len(closes)):", 2, ""))
N.m("A02", "bars_since: rows off the minute accepted", N.s(BARF, "int(t) % 60 == 0 and ", ""))
N.m("A03", "bars_since: window start exclusive", N.s(BARF, "t0 <= int(t)", "t0 < int(t)"))
N.m("A04", "bars_since: the unfinished minute is read", N.s(BARF, "int(t) + 60 <= t1", "int(t) <= t1"))
N.m("A05", "bars_since: empty minutes not skipped", N.s(BARF, " and lo and c", ""))
HOLES = '                if bars is not None and minutes >= self.n["stop_catchup_min_minutes"] and ('
N.m("A06", "catch_up: bars with holes are believed", N.r(HOLES, 3, ""))
N.m("A07", "catch_up: a quarter of the minutes is enough", N.u('len(bars) < minutes * self.n["stop_catchup_min_bar_share"]):', "len(bars) < minutes * 0.25):"))
N.m("A08", "catch_up: holes rule only for long stretches", N.s(HOLES, 'minutes >= self.n["stop_catchup_min_minutes"]', "minutes >= 40"))
N.m("A09", "bars_since: a failing chart call escapes", N.r('        lows, closes = q.get("low") or [], q.get("close") or []', 1, "    except KeyError:", off=1))
N.m("A10", "bars_since: low and close swapped", N.u("float(lo), float(c))", "float(c), float(lo))"))

# ---- checker / rescore / day move / stamps
N.m("AC1", "_ask_checker: non-bool confirmed accepted", N.u(" or not isinstance(confirmed, bool):", ":"))
N.m("AC2", "_ask_checker: tools not switched off", N.u('"--tools", "", "--",', ""))
N.m("AC3", "_ask_checker: runs in the project directory", N.u(", cwd=_scorer_dir())", ")"))
N.m("AC4", "_ask_checker: kind not normalised", N.u('str(row["kind"]).strip().lower()', 'str(row["kind"])'))
N.m("AC5", "_ask_checker: unknown kind accepted", N.u("    if kind not in VERIFY_KINDS or ", "    if "))
N.m("AC6", "_rescore: no answer reads as 10", N.s("return (score_batch([item], model, timeout)", '.get("score")', '.get("score", 10)'))
N.m("AC7", "_rescore: the caller's timeout is not passed on", N.u("score_batch([item], model, timeout)", "score_batch([item], model)"))
N.m("DM1", "_day_move_pct: a missing day gives a two-day move", N.r("    if prev[-1][0] != before:", 2, ""))
N.m("DM2", "_day_move_pct: no walk back over closed days", N.r("    for _ in range(10):", 4, ""))
N.m("DM3", "_day_move_pct: holidays not skipped", N.u("        if journal.session_hours(before):", "        if before.weekday() < 5:"))
N.m("DM4", "live_price: a move that cannot be worked out reads as flat", N.r("    except Exception:  # noqa: BLE001\n        return px, None".split("\n")[1], 1, "        return px, 0.0", k=None))
N.m("CS1", "code_stamp: dirty inverted", N.u('out["dirty"] = bool(', 'out["dirty"] = not bool('))

# ================================================================== postmortem.py
LOSS = '            if r.get("side") == "SELL" and pnl - fee < 0:'
P.m("PM01", "losses: fee ignored", P.s(LOSS, "pnl - fee < 0", "pnl < 0"))
P.m("PM02", "losses: break-even is a loss", P.s(LOSS, "pnl - fee < 0", "pnl - fee <= 0"))
P.m("PM03", "losses: buys counted", P.s(LOSS, 'r.get("side") == "SELL" and ', ""))
P.m("PM04", "losses: book filter ignored", P.u("BOOKS if book is None else (book,)", "BOOKS"))
P.m("PM05", "_fills: journals swapped", P.u('"news_trades.jsonl" if book == "news" else "trades.jsonl"', '"trades.jsonl" if book == "news" else "news_trades.jsonl"'))
REV = '    return [r for r in rows if isinstance(r, dict) and r.get("verdict") in VERDICTS and isinstance(r.get("keys"), list)'
P.m("PM06", "reviews: any verdict counts", P.s(REV, 'r.get("verdict") in VERDICTS and ', ""))
P.m("PM07", "reviews: keys need not be a list", P.s(REV, ' and isinstance(r.get("keys"), list)', ""))
REV2 = '            and all(isinstance(r.get(k), str) and r[k].strip() for k in ("what", "lesson", "fix")) and _causes(r)]'
P.m("PM08", "reviews: answers need not be there", P.s(REV2, 'and all(isinstance(r.get(k), str) and r[k].strip() for k in ("what", "lesson", "fix")) and _causes(r)]', "and _causes(r)]"))
P.m("PM09", "reviews: causes need not be there", P.s(REV2, " and _causes(r)]", "]"))
P.m("PM10", "pending inverted", P.u('if x["key"] not in done]', 'if x["key"] in done]'))
P.m("PM11", "repeated: planned losses counted", P.r('        if r["verdict"] == "planned_loss":', 2, ""))
P.m("PM12", "repeated: one loss is a repeat", P.u("if len(k) > 1}", "if len(k) > 0}"))
P.m("PM13", "repeated: needs three", P.u("if len(k) > 1}", "if len(k) > 2}"))
P.m("PM14", "_resolve: an ambiguous key takes the first fill", P.u("        if len(hits) != 1:", "        if len(hits) < 1:"))
P.m("PM15", "_resolve: a fragment of the hash is enough", P.u('x["key"].split(":", 1)[1].startswith(h)', 'h in x["key"].split(":", 1)[1]'))
P.m("PM16", "_resolve: a fill named twice is covered twice", P.u("        if hits[0] not in out:", "        if True:"))
P.m("PM17", "_resolve: a review may name no fill", P.r("    if not out:", 2, ""))
P.m("PM18", "record: any verdict word", P.r("    if verdict not in VERDICTS:", 2, ""))
P.m("PM19", "record: a loss can be reviewed twice", P.r("    if again:  # a second review of one loss", 2, ""))
P.m("PM20", "record: tags not lower-cased", P.u('t.strip().lower().replace(" ", "_")', 't.strip().replace(" ", "_")'))
SHORT = 'if len(text[k]) < mins[k]]'
P.m("PM21", "record: the minimum itself is too short", P.u(SHORT, "if len(text[k]) <= mins[k]]"))
P.m("PM22", "record: one character under the minimum passes", P.u(SHORT, "if len(text[k]) < mins[k] - 1]"))
P.m("PM23", "record: short text OR no tags passes", P.u("    if short or not tags:", "    if short and not tags:"))
P.m("PM24", "record: padding counts as text (what)", P.u('"what": " ".join((what or "").split())', '"what": (what or "")'))
P.m("PM25", "record: planned_loss needs only one yes", P.u("not (inside_rules and data_ok)", "not (inside_rules or data_ok)"))
P.m("PM26", "record: bad_data with data_ok yes", P.r('    if verdict == "bad_data" and data_ok:', 2, ""))
P.m("PM27", "record: rule_broken inside the rules", P.r('    if verdict == "rule_broken" and inside_rules:', 2, ""))
FIXREF = '    if verdict != "planned_loss" and len(ref) < mins["fix_ref"]:'
P.m("PM28", "record: no fix_ref needed", P.r(FIXREF, 3, ""))
P.m("PM29", "record: padding counts in fix_ref", P.u('    ref = " ".join((fix_ref or "").split())', '    ref = (fix_ref or "")'))
P.m("PM30", "record: ledger written in the active book's directory", P.r('    with journal.use_book("stocks"):\n        journal.append(LEDGER, rec)'.split("\n")[1], 2, "    journal.append(LEDGER, rec)", off=-1))
P.m("PM31", "_min_chars: fields config does not name have no minimum", P.u("{**MIN_CHARS, **(", "{**("))
P.m("PM32", "_min_chars: unreadable config means no minimum", P.u("        return dict(MIN_CHARS)", "        return {k: 0 for k in MIN_CHARS}"))
P.m("PM33", "MIN_CHARS what 40->4", P.u('MIN_CHARS = {"what": 40,', 'MIN_CHARS = {"what": 4,'))
P.m("PM34", "record: 'already reviewed' inverted", P.u('if f["key"] in _covered())', 'if f["key"] not in _covered())'))
P.m("PM35", "record: planned_loss rule applied to the others", P.u('    if verdict == "planned_loss" and not', '    if verdict != "planned_loss" and not'))
P.m("PM36", "record: fix_ref asked of planned losses only", P.s(FIXREF, 'verdict != "planned_loss"', 'verdict == "planned_loss"'))
P.m("PM38", "repeated: counts reviews, not fills", P.u('update(k for k in r["keys"] if isinstance(k, str))', 'add(json.dumps(r["keys"]))'))
P.m("PM40", "_crypto_dir: creates the directory to look into it", P.u("d.is_dir()", "(d.mkdir(parents=True, exist_ok=True) or True)"))
P.m("PM42", "record: loss_usd 0", P.u('round(sum(f["loss"] for f in fills), 2)', "0.0"))
P.m("PM43", "summary: pending_usd is the whole loss", P.u('"pending_usd": round(sum(x["loss"] for x in pend), 2)', '"pending_usd": round(sum(x["loss"] for x in all_losses), 2)'))
P.m("PM44", "reviews: only 'what' must be there", P.s(REV2, '("what", "lesson", "fix"))', '("what",))'))
P.m("PM49", "record: keys stored as typed (prefixes)", P.u('"keys": [f["key"] for f in fills]', '"keys": [k.strip() for k in keys]'))
P.m("PM50", "record: bad_data rule inverted", P.u('    if verdict == "bad_data" and data_ok:', '    if verdict == "bad_data" and not data_ok:'))
P.m("PM51", "record: rule_broken rule inverted", P.u('    if verdict == "rule_broken" and inside_rules:', '    if verdict == "rule_broken" and not inside_rules:'))
P.m("PM52", "_covered: a review covers every loss of its book",
    P.u('    return {k for r in reviews() for k in r["keys"] if isinstance(k, str)}',
        '    return {x["key"] for r in reviews() for k in r["keys"] if isinstance(k, str) for x in losses(k.split(":")[0])}'))
P.m("PM53", "record: lesson padding counts", P.u('"lesson": " ".join((lesson or "").split())', '"lesson": (lesson or "")'))
P.m("PM54", "record: fix padding counts", P.u('"fix": " ".join((fix or "").split())}', '"fix": (fix or "")}'))
KEYR = "        if len(h) < least or (book and book not in BOOKS):"
P.m("PM60", "_resolve: a key of any length", P.s(KEYR, "len(h) < least or ", ""))
P.m("PM61", "_resolve: MIN_KEY characters are not enough", P.s(KEYR, "len(h) < least", "len(h) <= least"))
P.m("PM62", "MIN_KEY 8->1", P.u("MIN_KEY = 8", "MIN_KEY = 1"))
P.m("PM63", "_resolve: the book in the key is not checked against the fill", P.u(' and (not book or x["book"] == book)]', "]"))
P.m("PM64", "_resolve: an unknown book word is ignored", P.s(KEYR, " or (book and book not in BOOKS)", ""))
P.m("PM65", "_resolve: one review may cover several books", P.r('    if len({f["book"] for f in out}) > 1:', 2, ""))
P.m("PM66", "record: fix_ref of exactly the minimum refused", P.s(FIXREF, 'len(ref) < mins["fix_ref"]', 'len(ref) <= mins["fix_ref"]'))
P.m("PM67", "record: fix_ref one under the minimum passes", P.s(FIXREF, 'len(ref) < mins["fix_ref"]', 'len(ref) < mins["fix_ref"] - 1'))
P.m("PM68", "MIN_CHARS fix_ref 7->1", P.u('"fix_ref": 7}', '"fix_ref": 1}'))
P.m("PM69", "reviews: read from the active book's directory", P.r('    with journal.use_book("stocks"):\n        rows = journal.read(LEDGER)'.split("\n")[1], 2, "    rows = journal.read(LEDGER)", off=-1))
P.m("PM70", "record: inside_rules always stored as yes", P.u('"inside_rules": bool(inside_rules)', '"inside_rules": True'))
P.m("PM71", "losses: a row that is not an object breaks the list", P.r("            if not isinstance(r, dict):", 2, ""))
P.m("PM72", "_key: the hash prefix in a key is 4 characters", P.u('return f"{book}:{h[:16]}"', 'return f"{book}:{h[:4]}"'))
P.m("PM73", "record: an empty review of planned_loss needs no data_ok (only inside_rules)", P.u("not (inside_rules and data_ok)", "not inside_rules"))

# ================================================================== __main__.py
M.m("M01", "verify: only news losses shown", M.u("            waiting = postmortem.pending()", '            waiting = postmortem.pending("news")'))
M.m("M02", "verify: line inverted", M.u("            if waiting:", "            if not waiting:"))
M.m("M03", "verify: sum is the first loss only", M.u("abs(sum(x['loss'] for x in waiting))", "abs(waiting[0]['loss'])"))
M.m("M04", "verify: a postmortem failure is fatal", M.r('            print(f"postmortem check failed: {type(e).__name__}")', 1, "        except KeyError as e:  # noqa: BLE001", off=-1))
M.m("M05", "verify: repeated causes never shown", M.u("            if again:", "            if False:"))
M.m("M06", "verify: hold shown for the other book only", M.s('        if journal.BOOK == "stocks":', '== "stocks"', '!= "stocks"'))
M.m("M07", "verify: hold line inverted", M.u("                if hold:", "                if not hold:"))
M.m("M08", "verify: a hold-check failure is fatal", M.r('                print(f"news hold check failed: {type(e).__name__}")', 1, "            except KeyError as e:  # noqa: BLE001", off=-1))
M.m("M09", "news-status: every book's losses", M.u('            waiting = postmortem.pending("news")', "            waiting = postmortem.pending()"))
M.m("M10", "news-status: unreadable ledger is a traceback", M.r('            waiting = f"unreadable ({type(e).__name__}): buys are blocked"', 1, "        except KeyError as e:  # noqa: BLE001", off=-1))
M.m("M11", "news-status: no losses field", M.u('"losses_awaiting_review": waiting, ', ""))
M.m("M12", "news-status: buy_hold always null", M.u('"buy_hold": buy_hold(),', '"buy_hold": None,'))
M.m("M13", "news-hold: --release ignored", M.u("release=a.release)", "release=False)"))
M.m("M14", "news-hold: refused but exit 0", M.r('            print(f"news-hold: {e}", file=sys.stderr)', 1, "            return 0", off=1))
M.m("M15", "news-hold: released word not echoed", M.u("a.reason.strip() if a.release else None", "None"))
M.m("M16", "postmortem: one answer is enough", M.u("is None or a.data_ok is None or a.verdict is None", "is None and a.data_ok is None and a.verdict is None"))
M.m("M17", "postmortem: inside-rules answer inverted", M.u('a.inside_rules == "yes"', 'a.inside_rules == "no"'))
M.m("M18", "postmortem: data-ok answer inverted", M.u('a.data_ok == "yes"', 'a.data_ok == "no"'))
M.m("M19", "postmortem: refused review exits 0", M.r('                print(f"postmortem: {e}", file=sys.stderr)', 1, "                return 0", off=1))
M.m("M20", "postmortem: unreadable list exits 0", M.r('" and the trade journals. Until it can be read the news engine opens no position.", file=sys.stderr)', 1, "            return 0", off=1))
M.m("M21", "postmortem: missing answers exit 0", M.r('print("postmortem --record needs --inside-rules, --data-ok and --verdict", file=sys.stderr)', 1, "                return 0", off=1))
M.m("M22", "postmortem: fix_ref dropped", M.s('a.verdict, a.causes.split(","), a.what, a.lesson, a.fix, a.fix_ref)', "a.fix, a.fix_ref)", 'a.fix, "")'))
M.m("M24", "verify: a waiting review is fatal", M.r("        if bad:\n            sys.exit(1)".split("\n")[1], 2, '        if bad or locals().get("waiting"):\n            sys.exit(1)', off=-1, k=None)
    if False else M.s("                    print(f\"NEWS BUYS ON HOLD since {hold.get('since')}: {hold['reason']}\")", "print(f", "sys.exit(1) if locals().get('waiting') else print(f"))
M.m("M26", "postmortem: answers without --record fall through to the list (exit 0)", M.r("        if not a.record and any((a.keys,", 3, ""))
M.m("M27", "postmortem: a ledger that cannot be written exits 0", M.r('                      f" state/{postmortem.LEDGER} and the trade journals", file=sys.stderr)', 1, "                return 0", off=1))
M.m("M28", "news-hold: a write failure exits 0", M.r('                  " state/news_holds.jsonl", file=sys.stderr)', 1, "            return 0", off=1))
M.m("M29", "news-hold: after a write failure the state is said the wrong way round", M.u('(f"SET ({now[\'reason\']})" if now else "NOT set")', '(f"SET ({now})" if not now else "NOT set")'))
M.m("M30", "news-live: the engine's 'did not start' is not passed on", M.u("        return run(a.until, a.minutes) or 0", "        run(a.until, a.minutes)"))
M.m("M31", "postmortem: --inside-rules filled in as yes when not given", M.u('pm.add_argument("--inside-rules", choices=["yes", "no"], default=None)', 'pm.add_argument("--inside-rules", choices=["yes", "no"], default="yes")'))
M.m("M32", "postmortem: --data-ok filled in as yes when not given", M.u('pm.add_argument("--data-ok", choices=["yes", "no"], default=None)', 'pm.add_argument("--data-ok", choices=["yes", "no"], default="yes")'))

# ================================================================== journal.py / config.json
J.m("J01", "news_checks.jsonl is hash-chained (a broken chain stops the engine)", J.u('"news_grades.jsonl"}', '"news_grades.jsonl", "news_checks.jsonl"}'))
C.m("CJ01", "config: guards log->enforce", C.t('"guards": "log"', '"guards": "enforce"'))
C.m("CJ02", "config: stop_catchup alert->sell", C.t('"stop_catchup": "alert"', '"stop_catchup": "sell"'))
C.m("CJ03", "config: block switch off", C.t('"block_buys_until_loss_reviewed": true', '"block_buys_until_loss_reviewed": false'))
C.m("CJ04", "config: require_known_move off", C.t('"require_known_move": true', '"require_known_move": false'))
C.m("CJ05", "config: no_chase limit 3->30", C.t('"max_day_move_pct_to_buy": 3.0', '"max_day_move_pct_to_buy": 30.0'))
C.m("CJ06", "config: cooldown off", C.t('"rebuy_cooldown_sessions": 1', '"rebuy_cooldown_sessions": 0'))
C.m("CJ07", "config: verify_buys off", C.t('"verify_buys": true', '"verify_buys": false'))
C.m("CJ08", "config: review minimum what 40->4", C.t('"min_chars": {"what": 40,', '"min_chars": {"what": 4,'))
C.m("CJ09", "config: catch-up gap 90->86400", C.t('"stop_catchup_gap_seconds": 90', '"stop_catchup_gap_seconds": 86400'))
C.m("CJ10", "config: verify_calls 2->1", C.t('"verify_calls": 2', '"verify_calls": 1'))
C.m("CJ11", "config: verify_rescore off", C.t('"verify_rescore": true', '"verify_rescore": false'))
C.m("CJ12", "config: commentary allowed", C.t('"regulator_or_counterparty"],', '"regulator_or_counterparty", "analyst_or_commentary"],'))
C.m("CJ13", "config: trade_outside_hours on", C.t('"trade_outside_hours": false', '"trade_outside_hours": true'))
C.m("CJ14", "config: fix_ref minimum 7->1", C.t('"fix_ref": 7}', '"fix_ref": 1}'))

# ================================================================== batch 3 (after reading snapshot 2's new paths)
N.m("K29", "step: waits for every trial check before it goes on (the background check stands in front of the next look)",
    N.u("        self.drain_trial()", '        self.drain_trial(wait=self.n["verify_timeout_seconds"])'))
N.m("K30", "step: gives every trial check one second before it goes on", N.u("        self.drain_trial()", "        self.drain_trial(wait=1.0)"))
N.m("X02", "check_stops: lone prints of a name that was sold are kept for its next position",
    N.r("        self._unseen_lows = {s_: v for s_, v in self._unseen_lows.items() if s_ in self.book.positions}", 1, "        pass"))
N.m("X03", "check_stops: the last look at a name that was sold is kept for its next position",
    N.r("        self._covered = {s_: t for s_, t in self._covered.items() if s_ in self.book.positions}", 1, "        pass"))
N.m("X18", "handle_scored: the stops are looked at before the enforced check, not after",
    N.mv("                        if is_open:  # the check took seconds", 2, CHK))
N.m("X19", "step: a failing look at the END of the step is swallowed (the step never fails, the owner is never alerted)",
    N.u("            self._look_at_stops(events)", "            self._look_at_stops(events, guarded=True)"))
N.m("X20", "step: a failing look between batches fails the step (the batches still to be scored are lost)",
    N.s("                self._look_at_stops(events, guarded=True)", "self._look_at_stops(events, guarded=True)", "self._look_at_stops(events)", k=2))
N.m("X21", "step: _early_look is not reset when the market is closed", N.r("        self._early_look = None  # None = the market is closed", 1, "        pass"))
N.m("X22", "_ask_later: asked and waited for at once (not in the background)",
    N.u('            threading.Thread(target=work, daemon=True, name="trial-check").start()', "            work()"))
N.m("X23", "run_queue_at_open: a name queued on trial is refused without a row or a word (silent drop)",
    N.r('                    self._refuse(q["symbol"], q["score"], events, "second_check", "נכנסה לתור לפני שהבדיקה השנייה נכנסה לתוקף",', 2, "                    pass"))
N.m("X24", "handle_scored: on trial the check is asked only when the buy was made (a held-back buy leaves no second-check record)",
    N.u('                    if not enforce and self.n["verify_buys"]:', '                    if not enforce and self.n["verify_buys"] and (sym in self.book.positions or to_queue):'))
N.m("X25", "__init__: an unknown guards word is said to the owner but the engine runs enforce",
    N.s(WORDS, '("guards", ("log", "enforce"), "log")', '("guards", ("log",), "enforce")'))
P.m("PM74", "summary: reviews counted from the raw ledger lines", P.u('"reviews": len(revs)', '"reviews": len(journal.read(LEDGER))'))
P.m("PM75", "pending: a review of any book's fill with the same hash prefix covers",
    P.u('    return [x for x in losses(book) if x["key"] not in done]', '    return [x for x in losses(book) if x["key"].split(":")[1] not in {d.split(":")[1] for d in done}]'))
M.m("M33", "verify: a hold is fatal (exit 1)", M.s("                    print(f\"NEWS BUYS ON HOLD since {hold.get('since')}: {hold['reason']}\")", "print(f", "bad.append('hold') or print(f"))


# ================================================================== batch 4: what is new in snapshot 3
DEF4 = '"stop_catchup": "alert", "stop_catchup_gap_seconds": 90, "stop_catchup_min_seconds": 120,'
DEF5 = '"stop_catchup_min_lows": 2, "stop_catchup_min_minutes": 4, "stop_catchup_min_bar_share": 0.5, "verify_parallel": 1,'
N.m("D30", "default: stop_catchup_min_seconds 120->0", N.s(DEF4, '"stop_catchup_min_seconds": 120', '"stop_catchup_min_seconds": 0'))
N.m("D31", "default: stop_catchup_min_lows 2->1 (one print is a breach)", N.s(DEF5, '"stop_catchup_min_lows": 2', '"stop_catchup_min_lows": 1'))
N.m("D32", "default: stop_catchup_min_minutes 4->400 (holes rule off)", N.s(DEF5, '"stop_catchup_min_minutes": 4', '"stop_catchup_min_minutes": 400'))
N.m("D33", "default: stop_catchup_min_bar_share 0.5->0.0 (holes believed)", N.s(DEF5, '"stop_catchup_min_bar_share": 0.5', '"stop_catchup_min_bar_share": 0.0'))
N.m("D34", "default: verify_parallel 1->8", N.s(DEF5, '"verify_parallel": 1', '"verify_parallel": 8'))
C.m("CJ15", "config: a review key of 1 character", C.t('"min_key_chars": 8', '"min_key_chars": 1'))
C.m("CJ16", "config: one print under the stop is a breach", C.t('"stop_catchup_min_lows": 2', '"stop_catchup_min_lows": 1'))
C.m("CJ17", "config: bars with holes are believed", C.t('"stop_catchup_min_bar_share": 0.5', '"stop_catchup_min_bar_share": 0.0'))
C.m("CJ18", "config: no wait for a completed minute", C.t('"stop_catchup_min_seconds": 120', '"stop_catchup_min_seconds": 0'))
C.m("CJ19", "config: holes rule only for very long stretches", C.t('"stop_catchup_min_minutes": 4', '"stop_catchup_min_minutes": 400'))
C.m("CJ20", "config: verify_parallel 1->4", C.t('"verify_parallel": 1', '"verify_parallel": 4'))
N.m("Y41", "_buy: enforced, a cooldown that cannot be worked out does not refuse", N.r('                self._note_error(e, "stop_cooldown")', 1, "                cooling = False", off=1))
N.m("Y42", "_buy: enforced, a move that cannot be compared does not refuse",
    N.u('chase, said = enforced, "אי אפשר לחשב כמה המניה עלתה היום"', 'chase, said = False, "אי אפשר לחשב כמה המניה עלתה היום"'))
N.m("Y43", "_buy: on trial, a cooldown that cannot be worked out refuses... (would_refuse row only) / enforced flag inverted",
    N.u('        enforced = self.n["guards"] == "enforce"', '        enforced = self.n["guards"] != "enforce"'))
N.m("Y44", "_buy: a cooldown that cannot be worked out is not put on record", N.r('                self._note_error(e, "stop_cooldown")', 1, "                pass"))
N.m("ST1", "step: what the step did is only said when the step did not fail",
    N.r("        finally:  # whatever fails further down, what the step already did is said", 1, "        except BaseException:\n            raise\n        else:"))
N.m("ST2", "step: last_events is not kept for the loop", N.r("        self.last_events = events", 1, "        pass"))
N.m("ST3", "step: an alert that cannot be sent hides the step's own error", N.s("except Exception as e:  # noqa: BLE001 - the alert must not hide the error of the step itself", "except Exception as e:", "except KeyError as e:"))
N.m("ST4", "_run: after a failed step what it did is not printed", N.r('            if getattr(nt, "last_events", None):', 2, ""))
N.m("HB1", "heartbeat: the newest look among the held names, not the oldest", N.u("checked = None if any(m is None for m in marks) else min(marks)", "checked = None if any(m is None for m in marks) else max(marks)"))
N.m("HB2", "heartbeat: the loop's own clock, whatever each name saw", N.r("        if self.book.positions and checked is not None:", 4, ""))
N.m("HB3", "heartbeat: a name never looked at still gets a stamp", N.u("checked = None if any(m is None for m in marks) else min(marks)", "checked = min(m for m in marks if m is not None) if any(m is not None for m in marks) else None"))
N.m("DT1", "drain_trial: waits for ever for an answer that is still out", N.u('if not box["done"].wait(max(0.0, until - time.time())):', 'if not box["done"].wait():'))
N.m("DT2", "drain_trial: the wait is per answer, not in total", N.u('if not box["done"].wait(max(0.0, until - time.time())):', 'if not box["done"].wait(float(wait)):'))
N.m("DT3", "_ask_later: a check that raised leaves a row that reads as a pass", N.u('box["out"] = ([{"error": type(e).__name__}], None)', 'box["out"] = ([], _UNSET)'))
N.m("DT4", "_run: the end of a run in session waits a whole call for trial answers (the lock is kept, no stop is looked at)",
    N.u('nt.drain_trial(wait=0 if market_open_now() else nt.n["verify_timeout_seconds"])', 'nt.drain_trial(wait=nt.n["verify_timeout_seconds"])'))
N.m("DT5", "_ask_second: no belt over the calls' own timeout (a call that hangs keeps its check out for ever)", N.u("            t.join(max(0.0, until - time.time()))", "            t.join()"))
N.m("SV1", "a save in the middle of a step writes the seen marks (headlines polled but not scored are lost by a kill)", N.u("        if seen:", "        if True:"))
N.m("SV2", "_log_trade: the save with the trade writes the seen marks", N.s("            self.save(seen=False)  # trade the book does not know", "self.save(seen=False)", "self.save()"))
N.m("BY1", "_buy: what was kept for an earlier position of the name is kept for the new one", N.r("        self._covered.pop(sym, None)\n        self._unseen_lows.pop(sym, None)\n        pos = self.book.positions[sym]".split("\n")[2], 2, "", off=-2))
N.m("SL1", "_sell: what was kept for the sold position is kept", N.r("        self._covered.pop(sym, None)  # what was kept for this position goes with it", 2, ""))
N.m("CU1", "catch_up: the stretch is read from the second of the last look, not from the start of its minute", N.r("                since = since.replace(second=0, microsecond=0)", 1, "                pass"))
N.m("CU2", "catch_up: an empty answer marks the stretch as looked at", N.u("                if bars:  # looked at up to the end of the last bar that was really read", "                if True:  # looked at up to the end of the last bar that was really read")
    , N.u("self._covered[sym] = max(b[0] for b in bars) + timedelta(seconds=60)", "self._covered[sym] = (max(b[0] for b in bars) + timedelta(seconds=60)) if bars else now.astimezone(timezone.utc)"))
N.m("CU3", "catch_up: a mark of an earlier day stops the look for good", N.u('            if str((pos.get("stop_breach") or {}).get("found_at", ""))[:10] == journal.now_utc()[:10]:', '            if pos.get("stop_breach"):'))
N.m("ED4", "catch_up: a run that reached the bell is told as a missed stretch", N.u("looked + timedelta(seconds=self.n[\"stop_catchup_gap_seconds\"]) < looked.replace(", "looked < looked.replace("))
N.m("ED1", "catch_up: an unread stretch of an earlier day is not told", N.r("                    self._earlier_days_unread(sym, looked.astimezone(NY), opened)", 1, "                    pass"))
N.m("ED2", "catch_up: the earlier-day alert is repeated at every look", N.u("        if unread is None or sym in told:", "        if unread is None:"))
N.m("ED3", "catch_up: the earlier-day alert also when no session was missed", N.u("        if unread is None or sym in told:", "        if sym in told:"))
N.m("SB1", "score_batch: a row with a null score aborts the batch", N.s("        except Exception:  # noqa: BLE001 - whatever is wrong with one row", "except Exception:", "except (KeyError, IndexError):"))
N.m("SB2", "score_batch: the scorer can answer for another ticker", N.r('            if str(row.get("symbol", "")).upper() != x["symbol"]:', 2, ""))
N.m("SB3", "score_batch: an envelope that is not an object aborts the step", N.u("    except (subprocess.SubprocessError, ValueError, OSError, AttributeError, TypeError) as e:", "    except (subprocess.SubprocessError, ValueError, OSError) as e:"))
N.m("VP1", "_ask_later: the trial pool ignores verify_parallel", N.u('threading.BoundedSemaphore(max(1, int(self.n["verify_parallel"])))', "threading.BoundedSemaphore(8)"))
P.m("PM80", "_min_key: config ignored, one character names a fill", P.u('return max(1, int(load_config("stocks").get("postmortem", {}).get("min_key_chars", MIN_KEY)))', "return 1"))
P.m("PM81", "_min_key: an unreadable config means one character is enough", P.r("def _min_key() -> int:", 1, "        return 1", off=6))
P.m("PM82", "losses: the loss shown ignores the fee", P.u('"loss": round(pnl - fee, 2),', '"loss": round(pnl, 2),'))
P.m("PM83", "_min_key: a config of 0 or less means no minimum", P.u('return max(1, int(load_config("stocks").get("postmortem", {}).get("min_key_chars", MIN_KEY)))', 'return int(load_config("stocks").get("postmortem", {}).get("min_key_chars", MIN_KEY))'))
P.m("PM84", "summary: realized_loss_usd is the pending loss only", P.u('"realized_loss_usd": round(sum(x["loss"] for x in all_losses), 2)', '"realized_loss_usd": round(sum(x["loss"] for x in pend), 2)'))
