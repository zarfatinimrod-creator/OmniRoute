"""Loss reviews. Basic law, item 3: every realized loss is studied, none is left unexamined.

A realized loss is a SELL fill with realized_pnl < 0 in a book's trade journal (stocks: trades.jsonl, news:
news_trades.jsonl, crypto: <state_subdir>/trades.jsonl). A review is one record in postmortems.jsonl, kept in the
stock state directory for every book, that names the fills it covers. pending() lists the losing fills that no
review covers. While a news loss is pending the news engine opens no new position
(config news.block_buys_until_loss_reviewed).

The review itself is written by the trader session (skills/trader/SKILL.md, section 3א), never by an engine: this
module only keeps the list honest. One review may cover several fills (for example the losing trims of one
rebalance); a fill is reviewed once. A cause tag named by the reviews of two different losses is a repeated
mistake, which the Basic law forbids: repeated() names those tags (planned losses are left out, a stop doing its
job twice is not a mistake made twice).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from . import journal

LEDGER = "postmortems.jsonl"
BOOKS = ("stocks", "news", "crypto")
# bad_data: the decision was made on wrong or missing data. bad_rule: the data was right and the rule itself
# is the problem. rule_broken: the trade or its exit was outside the rules. ops_defect: the system did not
# do what the rules say (an engine down, a stop not checked). planned_loss: inside the rules, on good data,
# a small loss the rules accept (the stop did its job).
VERDICTS = ("bad_data", "bad_rule", "rule_broken", "ops_defect", "planned_loss")
# config.json postmortem.min_chars: a review is more than a word (fix_ref: a short commit hash is 7 characters)
MIN_CHARS = {"what": 40, "lesson": 20, "fix": 10, "fix_ref": 7}
MIN_KEY = 8  # config.json postmortem.min_key_chars: "n" or "news:" must never be enough to clear a loss


def _base():
    """The stock state directory, whichever book is active (the ledger and the news journals live there)."""
    return journal.STATE if journal._BASE is None else journal._BASE


def _crypto_dir():
    """The crypto book's state directory, or None while that book has never traded here. A config that cannot be
    read is an error the caller sees (crypto losses must not vanish from the list without a word)."""
    from .data import load_config

    sub = (load_config("crypto").get("market") or {}).get("state_subdir")
    d = _base() / sub if sub else None
    return d if d is not None and d.is_dir() else None  # never create the directory just to look into it


def _min_key() -> int:
    try:
        from .data import load_config

        return max(1, int(load_config("stocks").get("postmortem", {}).get("min_key_chars", MIN_KEY)))
    except Exception:  # noqa: BLE001
        return MIN_KEY


def _min_chars() -> dict:
    try:
        from .data import load_config

        return {**MIN_CHARS, **(load_config("stocks").get("postmortem", {}).get("min_chars", {}))}
    except Exception:  # noqa: BLE001
        return dict(MIN_CHARS)


def _fills(book: str) -> list[dict]:
    if book == "crypto":
        if _crypto_dir() is None:
            return []
        with journal.use_book("crypto"):
            return journal.read("trades.jsonl")
    with journal.use_book("stocks"):
        return journal.read("news_trades.jsonl" if book == "news" else "trades.jsonl")


def _key(book: str, rec: dict) -> str:
    h = rec.get("hash") or hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()
    return f"{book}:{h[:16]}"


def losses(book: str | None = None) -> list[dict]:
    """Every losing SELL fill, oldest first. A BUY can carry a negative realized_pnl too (a crypto fee): that is
    a cost of entering, not a realized loss, and is not listed. Where fills pay a fee (crypto) the entry fee sits
    on the BUY and is missing from the SELL's realized_pnl, so a sale counts as a loss when its realized_pnl does
    not even cover one more fee of its own size (the round trip lost money); stock and news fills carry no fee."""
    out = []
    for b in BOOKS if book is None else (book,):
        for r in _fills(b):
            if not isinstance(r, dict):
                continue
            try:
                pnl = float(r.get("realized_pnl") or 0.0)
                fee = float(r.get("fee") or 0.0)
            except (TypeError, ValueError):
                continue
            if r.get("side") == "SELL" and pnl - fee < 0:
                # loss: what the sale lost. Without a fee it is the realized P&L; with one, the P&L less one more fee
                # of the sale's own size (the entry fee, which sits on the BUY row): an estimate, and never a gain
                out.append({"key": _key(b, r), "book": b, "date": r.get("date"), "symbol": r.get("symbol"),
                            "qty": r.get("qty"), "price": r.get("price"), "realized_pnl": round(pnl, 2),
                            "loss": round(pnl - fee, 2),
                            "reason": r.get("reason", ""), "logged_at": r.get("logged_at")})
    return out


def reviews() -> list[dict]:
    """The reviews on record. A line that is not a review (not an object, no verdict, an answer missing) reviews
    nothing: its fills stay on the list, and the tool that lists them keeps working."""
    with journal.use_book("stocks"):
        rows = journal.read(LEDGER)
    return [r for r in rows if isinstance(r, dict) and r.get("verdict") in VERDICTS and isinstance(r.get("keys"), list)
            and all(isinstance(r.get(k), str) and r[k].strip() for k in ("what", "lesson", "fix")) and _causes(r)]


def _covered() -> set[str]:
    return {k for r in reviews() for k in r["keys"] if isinstance(k, str)}


def pending(book: str | None = None) -> list[dict]:
    """Losing fills that no review covers yet."""
    done = _covered()
    return [x for x in losses(book) if x["key"] not in done]


def _causes(r: dict) -> set[str]:
    return {t for t in r["causes"] if isinstance(t, str)} if isinstance(r.get("causes"), list) else set()


def repeated() -> dict[str, int]:
    """Cause tags named by the reviews of more than one loss: the same mistake happened again. The number is how
    many different fills carry the tag. Planned losses are left out."""
    seen: dict[str, set] = {}
    for r in reviews():
        if r["verdict"] == "planned_loss":
            continue
        for t in _causes(r):
            seen.setdefault(t, set()).update(k for k in r["keys"] if isinstance(k, str))
    return {t: len(k) for t, k in sorted(seen.items()) if len(k) > 1}


def _resolve(keys: list[str]) -> list[dict]:
    """Each key is 'book:hashprefix' or a bare hash prefix, with at least MIN_KEY characters of the hash, and must
    name exactly one losing fill. All the fills of one review are in one book: a review is of one event."""
    known, least = losses(), _min_key()
    out = []
    for k in keys:
        k = k.strip()
        if not k:
            continue
        book, _, h = k.rpartition(":")
        if len(h) < least or (book and book not in BOOKS):
            raise ValueError(f"{k!r} is not a key: write it as the list shows it, book:hash, with at least {least}"
                             " characters of the hash (see `postmortem`)")
        hits = [x for x in known if x["key"].split(":", 1)[1].startswith(h) and (not book or x["book"] == book)]
        if len(hits) != 1:
            raise ValueError(f"{k!r} names {len(hits)} losing fills; it must name exactly one (see `postmortem`)")
        if hits[0] not in out:
            out.append(hits[0])
    if not out:
        raise ValueError("a review must name at least one losing fill")
    if len({f["book"] for f in out}) > 1:
        raise ValueError("one review, one book: losses in different books are different events and get a review each")
    return out


def record(keys: list[str], inside_rules: bool, data_ok: bool, verdict: str, causes: list[str], what: str,
           lesson: str, fix: str, fix_ref: str = "") -> dict:
    """Write one review. `what` is what happened and why (with the evidence), `lesson` is what was learned, `fix`
    is what changed so it does not happen again - or, for a planned loss, why nothing does. The answers must agree
    with the verdict, and every verdict but a planned loss names where its fix lives (fix_ref: a commit or a
    backlog item)."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    fills = _resolve(keys)
    again = sorted(f["key"] for f in fills if f["key"] in _covered())
    if again:  # a second review of one loss would make its cause look like a repeated mistake
        raise ValueError("already reviewed: " + ", ".join(again))
    tags = sorted({t.strip().lower().replace(" ", "_") for t in causes if t.strip()})
    text = {"what": " ".join((what or "").split()), "lesson": " ".join((lesson or "").split()),
            "fix": " ".join((fix or "").split())}
    ref = " ".join((fix_ref or "").split())
    mins = _min_chars()
    short = [f"{k} (at least {mins[k]} characters)" for k in ("what", "lesson", "fix") if len(text[k]) < mins[k]]
    if short or not tags:
        raise ValueError("a review needs: " + ", ".join(short + ([] if tags else ["causes"])))
    if verdict == "planned_loss" and not (inside_rules and data_ok):
        raise ValueError("planned_loss means inside the rules and on good data: --inside-rules yes --data-ok yes")
    if verdict == "bad_data" and data_ok:
        raise ValueError("bad_data needs --data-ok no")
    if verdict == "rule_broken" and inside_rules:
        raise ValueError("rule_broken needs --inside-rules no")
    if verdict != "planned_loss" and len(ref) < mins["fix_ref"]:
        raise ValueError("this verdict needs --fix-ref: the commit or the backlog item that carries the fix"
                         f" (at least {mins['fix_ref']} characters)")
    rec = {"at": journal.now_utc(), "keys": [f["key"] for f in fills], "fills": fills,
           "loss_usd": round(sum(f["loss"] for f in fills), 2), "inside_rules": bool(inside_rules),
           "data_ok": bool(data_ok), "verdict": verdict, "causes": tags, **text, "fix_ref": ref}
    with journal.use_book("stocks"):
        journal.append(LEDGER, rec)
    return rec


def summary() -> dict:
    all_losses, revs, pend = losses(), reviews(), pending()
    return {"pending": pend, "pending_usd": round(sum(x["loss"] for x in pend), 2),
            "losing_fills": len(all_losses), "realized_loss_usd": round(sum(x["loss"] for x in all_losses), 2),
            "reviews": len(revs), "by_verdict": dict(Counter(r["verdict"] for r in revs)),
            "causes_used": dict(sorted(Counter(t for r in revs for t in _causes(r)).items())),
            "repeated_causes": repeated()}
