#!/usr/bin/env python3
"""
docs-bloat-gate — PreToolUse hook on Write/Edit/Bash.

Why it saves context: docs and rules that grow unchecked get read into context
on every future session. This gate blocks the bloat at write time. Three signals
on .md writes (any blocks):
  S2: AI-slop stoplist phrase in net-added text         UNBYPASSABLE, always-on
  S3: lexical density < 0.45 on >100-char addition      UNBYPASSABLE, always-on
  S1: char-delta exceeds tier cap (rule<50ln=150,
      doc=800, spec=2000)                               bypassable, opt-in per project

W1.1: new docs/*.md root file with audit/analysis/report/research keywords
      (Write only, requires project's docs/ dir to exist)               bypassable

S1 bypasses: brand-new L2 heading (<=30 lines / 1500 chars exempt) or
override sentinel (hard cap N=1 per session, reason >=30 chars, no
anti-stopwords).

Override sentinel: <!-- docs-bloat-gate-override: <reason >=30 chars> -->

Per-project opt-in: S1/W1.1 fire when CLAUDE_PROJECT_DIR surfaces
auto-discovered convention paths (docs/spec.md, .claude/rules/, docs/).
Override with .claude/docs-bloat-gate.json (keys: gated_docs,
gated_rule_prefixes, audit_root_check, log_path, claude_md_gated).

Memory paths (**/.claude/projects/*/memory/*.md) are exempt from all signals.

Self-contained: the S2 slop wordlist + S3 density tokenizer are inlined below
(no external imports) so this file can be dropped into ~/.claude/hooks/ as-is.

Fail-open: any uncaught exception exits 0 so a hook bug never blocks an edit.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# === Inlined docs-quality rules (S2 slop + S3 density) ===================
# Single source for the slop stoplist and the lexical-density tokenizer.
SLOP_WORDS = {
    # transition adverbs
    "furthermore", "moreover", "additionally", "consequently",
    "subsequently", "accordingly", "nevertheless", "notwithstanding",
    # hedge adverbs
    "fundamentally", "essentially", "ultimately",
    # AI tells (single-word)
    "comprehensive", "robust", "seamless", "leverage", "utilize",
}
SLOP_PHRASES = (
    # hedges (multi-word)
    "it's worth noting", "it should be noted", "it is important to",
    "that said", "having said that", "in essence", "at its core",
    "while this may vary", "in the context of",
    # AI tells (multi-word)
    "delve into", "navigate the", "landscape of", "realm of", "tapestry of",
)

# ~150 English function words for the S3 lexical-density stoplist.
FUNCTION_WORDS = {
    # articles
    "a", "an", "the",
    # pronouns
    "i", "me", "my", "mine", "we", "us", "our", "ours",
    "you", "your", "yours", "he", "him", "his",
    "she", "her", "hers", "it", "its",
    "they", "them", "their", "theirs",
    "this", "that", "these", "those",
    "who", "whom", "whose", "which", "what",
    # conjunctions / subordinators
    "and", "or", "but", "nor", "so", "yet", "for",
    "if", "then", "than", "while", "although", "though",
    "because", "since", "unless", "until", "when",
    "where", "whether", "how", "why", "as",
    # prepositions
    "in", "on", "at", "to", "of", "by", "with",
    "from", "into", "onto", "upon", "about", "above",
    "across", "after", "against", "along", "among",
    "around", "before", "behind", "below", "beneath",
    "beside", "between", "beyond", "during", "except",
    "inside", "near", "outside", "over", "through",
    "throughout", "toward", "towards", "under", "underneath",
    "up", "down", "off", "out",
    # auxiliaries / be / have / do / modals
    "be", "am", "is", "are", "was", "were", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "shall", "should", "can", "could",
    "may", "might", "must", "ought",
    # determiners / quantifiers
    "no", "not", "all", "any", "some", "none", "both",
    "each", "every", "much", "many", "more", "most",
    "less", "least", "few", "several", "such", "same",
    "other", "another", "own",
    # discourse / fillers
    "only", "just", "very", "too", "also", "even", "again",
    "here", "there", "now", "well", "like", "yes", "ok",
    # contraction stubs (after \w+ tokenization)
    "s", "t", "re", "ve", "ll", "d", "m",
}

DENSITY_THRESHOLD = 0.45

_SLOP_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(SLOP_WORDS)) + r")\b",
    re.IGNORECASE,
)


def slop_hit_counts(text: str) -> Counter[str]:
    """Return a Counter of slop-pattern occurrences in ``text``.

    Counts (not just presence) so net-added detection can catch the
    "added one more occurrence" case — set-difference would miss the second
    instance when the first already appears in prior text.
    """
    counts: Counter[str] = Counter()
    if not text:
        return counts
    for m in _SLOP_WORD_RE.finditer(text):
        counts[m.group(1).lower()] += 1
    lower = text.lower()
    for ph in SLOP_PHRASES:
        n, start = 0, 0
        while (idx := lower.find(ph, start)) != -1:
            n += 1
            start = idx + len(ph)
        if n:
            counts[ph] += n
    return counts


def lexical_density(text: str) -> float:
    """Content-word ratio. Returns 0.0–1.0; 1.0 if ``text`` has no tokens."""
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return 1.0
    content = sum(1 for t in tokens if t not in FUNCTION_WORDS)
    return content / len(tokens)


# === Convention defaults =================================================
DEFAULT_GATED_DOCS = ("docs/spec.md",)
DEFAULT_GATED_RULES_PREFIX = ".claude/rules/"
DEFAULT_LOG_REL = "docs/analysis/bloat-overrides.log"
CONFIG_REL = ".claude/docs-bloat-gate.json"

# --- Memory-path exemption ----------------------------------------------
MEMORY_PATH_RE = re.compile(r"/\.claude/projects/[^/]+/memory/[^/]+\.md$")

# --- Audit-keyword + sentinel regexes -----------------------------------
AUDIT_KEYWORDS_RE = re.compile(r"\b(audit|analysis|report|research)\b", re.IGNORECASE)
OVERRIDE_RE = re.compile(r"<!--\s*docs-bloat-gate-override:\s*(.+?)\s*-->", re.DOTALL)
ANTI_STOPWORDS = {"update", "rewrite", "improvement", "cleanup", "fix"}
SENTINEL_CAP = 1
SENTINEL_REASON_MIN = 30
STATE_DIR = Path.home() / ".claude" / "state"

# --- Tier thresholds -----------------------------------------------------
TIER_CAPS = {"rule": 150, "doc": 800, "spec": 2000}

# --- L2 heading exemption ------------------------------------------------
NEW_SECTION_LINE_EXEMPT = 30
NEW_SECTION_CHAR_EXEMPT = 1500

# --- S3 char-delta gate (when density check applies) ---------------------
DENSITY_DELTA_GUARD = 100


# --- Config loading ------------------------------------------------------
def project_dir_or_none() -> Path | None:
    """Return CLAUDE_PROJECT_DIR resolved, or None if unset/invalid."""
    raw = os.environ.get("CLAUDE_PROJECT_DIR")
    if not raw:
        return None
    try:
        p = Path(raw).resolve()
        return p if p.is_dir() else None
    except OSError:
        return None


def load_config(proj: Path | None) -> dict:
    """Resolve convention defaults + JSON overrides for the given project.

    Returns a dict with: gated_docs (set[str], project-relative),
    gated_rule_prefixes (list[str]), audit_root_check (bool),
    log_path (Path | None), claude_md_gated (bool).

    With proj=None: all opt-in checks disabled; S2/S3 still fire from caller.
    """
    if proj is None:
        return {
            "gated_docs": set(),
            "gated_rule_prefixes": [],
            "audit_root_check": False,
            "log_path": None,
            "claude_md_gated": False,
        }

    cfg = {
        "gated_docs": (
            {DEFAULT_GATED_DOCS[0]} if (proj / DEFAULT_GATED_DOCS[0]).exists() else set()
        ),
        "gated_rule_prefixes": (
            [DEFAULT_GATED_RULES_PREFIX]
            if (proj / DEFAULT_GATED_RULES_PREFIX.rstrip("/")).is_dir()
            else []
        ),
        "audit_root_check": (proj / "docs").is_dir(),
        "log_path": (
            (proj / DEFAULT_LOG_REL)
            if (proj / "docs" / "analysis").is_dir()
            else None
        ),
        "claude_md_gated": os.environ.get("DOCS_BLOAT_GATE_CLAUDE_MD") == "1",
    }

    cfg_file = proj / CONFIG_REL
    if cfg_file.exists():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = None
        if isinstance(data, dict):
            if "gated_docs" in data:
                cfg["gated_docs"] = set(data["gated_docs"])
            if "gated_rule_prefixes" in data:
                cfg["gated_rule_prefixes"] = list(data["gated_rule_prefixes"])
            if "audit_root_check" in data:
                cfg["audit_root_check"] = bool(data["audit_root_check"])
            if "log_path" in data:
                # log_path comes from project-local config (untrusted on a
                # cloned repo). Resolve and require containment so an absolute
                # or ../ value can't steer append_log writes outside the project.
                # A malformed value (embedded null, etc.) drops to None rather
                # than raising out and disabling the whole config load.
                if data["log_path"]:
                    try:
                        cand = (proj / data["log_path"]).resolve()
                        cfg["log_path"] = cand if cand.is_relative_to(proj) else None
                    except (OSError, ValueError):
                        cfg["log_path"] = None
                else:
                    cfg["log_path"] = None
            if "claude_md_gated" in data:
                cfg["claude_md_gated"] = bool(data["claude_md_gated"])

    return cfg


# --- Helpers -------------------------------------------------------------
def relpath_in(proj: Path, file_path: str) -> str | None:
    try:
        return str(Path(file_path).resolve().relative_to(proj))
    except (ValueError, OSError):
        return None


def is_memory_path(abs_path: str) -> bool:
    return bool(MEMORY_PATH_RE.search(abs_path))


def is_gated_path(rel: str, cfg: dict) -> bool:
    if rel in cfg["gated_docs"]:
        return True
    for prefix in cfg["gated_rule_prefixes"]:
        if rel.startswith(prefix) and rel.endswith(".md"):
            return True
    if rel == "CLAUDE.md" and cfg["claude_md_gated"]:
        return True
    return False


def build_bash_patterns(cfg: dict) -> list[re.Pattern[str]]:
    """Build Bash write-pattern regexes from gated paths. Empty if nothing gated."""
    docs = sorted(re.escape(p) for p in cfg["gated_docs"])
    rule_alts = []
    for prefix in cfg["gated_rule_prefixes"]:
        rule_alts.append(re.escape(prefix) + r"\S+\.md")
    alts = docs + rule_alts
    if not alts:
        return []
    path_re = r"(?:" + "|".join(alts) + r")"
    return [
        re.compile(r">>?\s*['\"]?" + path_re),
        re.compile(r"\btee\b[^|;&]*?\s" + path_re),
        re.compile(r"\bsed\b[^|;&]*?(?:-i|--in-place)\b[^|;&]*?\s" + path_re),
    ]


def line_count(s: str) -> int:
    if not s:
        return 0
    return s.count("\n") + (0 if s.endswith("\n") else 1)


def file_tier(current_lines: int) -> str:
    if current_lines < 50:
        return "rule"
    if current_lines < 500:
        return "doc"
    return "spec"


def _safe_sid(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)[:64] or "default"


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return _safe_sid(sid)
    transcript = os.environ.get("CLAUDE_TRANSCRIPT_PATH")
    if transcript:
        return hashlib.md5(transcript.encode(), usedforsecurity=False).hexdigest()[:12]
    seed = f"{os.environ.get('CLAUDE_PROJECT_DIR', '')}|{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    return hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest()[:12]


def sentinel_counter_path() -> Path:
    return STATE_DIR / f"docs-bloat-gate-sentinels-{session_id()}.txt"


def read_sentinel_count() -> int:
    p = sentinel_counter_path()
    try:
        return int(p.read_text().strip() or "0")
    except (OSError, ValueError):
        return 0


def increment_sentinel_count() -> int:
    p = sentinel_counter_path()
    new = read_sentinel_count() + 1
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(new))
    except OSError:
        pass
    return new


# --- L2-heading carve-out ------------------------------------------------
def l2_headings(text: str) -> set[str]:
    return {ln[3:].rstrip() for ln in text.splitlines() if ln.startswith("## ")}


def carved_char_delta(added: str, removed: str, current: str) -> int:
    """Char-delta with brand-new L2 sections exempted (<=30 lines / 1500 chars)."""
    delta = len(added) - len(removed)
    new_h = l2_headings(added) - l2_headings(current)
    if not new_h:
        return delta

    in_exempt = False
    exempt_lines = 0
    exempt_chars = 0
    for line in added.splitlines(keepends=True):
        if line.startswith("## "):
            head_text = line[3:].rstrip("\r\n")
            if head_text in new_h:
                in_exempt = True
                exempt_lines = 0
                exempt_chars = 0
            else:
                in_exempt = False
        if in_exempt:
            if (
                exempt_lines < NEW_SECTION_LINE_EXEMPT
                and exempt_chars + len(line) <= NEW_SECTION_CHAR_EXEMPT
            ):
                exempt_lines += 1
                exempt_chars += len(line)
                delta -= len(line)
            else:
                in_exempt = False
    return delta


# --- Override log --------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_schema_header(log: Path, fields: str) -> None:
    if log.exists() and log.stat().st_size > 0:
        return
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"# JSONL fields: {fields}\n")
    except OSError:
        pass


def append_log(entry: dict, log_path: Path | None) -> None:
    if log_path is None:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _write_schema_header(
            log_path,
            "ts, file, signal, bypass_type, char_delta, [reason], [carved_delta], "
            "[headings], session_id, tool, regression_test",
        )
        entry["regression_test"] = os.environ.get("HOOK_REGRESSION_TEST") == "1"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def validate_reason(reason: str) -> str | None:
    r = reason.strip()
    if len(r) < SENTINEL_REASON_MIN:
        return f"reason too short ({len(r)} < {SENTINEL_REASON_MIN} chars)"
    lower = r.lower()
    for sw in ANTI_STOPWORDS:
        if re.search(rf"\b{sw}\b", lower):
            return f"anti-stopword in reason: {sw!r}"
    return None


# --- Signal checks -------------------------------------------------------
def check_s2(added: str, removed: str) -> int:
    """S2 — net-added slop phrases. Returns 0 (pass) or 2 (block)."""
    added_counts = slop_hit_counts(added)
    removed_counts = slop_hit_counts(removed)
    new_hits = sorted(
        p for p, n in added_counts.items() if n > removed_counts.get(p, 0)
    )
    if not new_hits:
        return 0
    sys.stderr.write(
        f"docs-bloat-gate: AI-slop phrases detected: {', '.join(new_hits)}. "
        "UNBYPASSABLE.\nRemove these phrases - they signal LLM-generated "
        "bloat regardless of edit size.\n"
    )
    return 2


def check_s3(added: str, removed: str) -> int:
    """S3 — lexical density on >100-char additions. Returns 0 or 2."""
    char_delta = len(added) - len(removed)
    if char_delta <= DENSITY_DELTA_GUARD:
        return 0
    density = lexical_density(added)
    if density >= DENSITY_THRESHOLD:
        return 0
    sys.stderr.write(
        f"docs-bloat-gate: lexical density {density:.2f} below "
        f"{DENSITY_THRESHOLD} on {char_delta}-char addition. "
        "Function-word ratio too high - prose is filler-dense. "
        "UNBYPASSABLE.\nTighten by removing hedges, articles, and "
        "transition phrases.\n"
    )
    return 2


def gate_s1(
    rel: str, added: str, removed: str, current: str, tool: str, cfg: dict
) -> int:
    """S1 tier-cap gate. Returns 0 (pass) or 2 (block)."""
    char_delta = len(added) - len(removed)
    tier = file_tier(line_count(current))
    cap = TIER_CAPS[tier]

    if char_delta <= cap:
        return 0

    # L2-heading carve-out.
    new_h = l2_headings(added) - l2_headings(current)
    if new_h:
        carved = carved_char_delta(added, removed, current)
        if carved <= cap:
            append_log({
                "ts": now_iso(),
                "file": rel,
                "signal": "S1",
                "bypass_type": "l2_heading",
                "char_delta": char_delta,
                "carved_delta": carved,
                "headings": sorted(new_h),
                "session_id": session_id(),
                "tool": tool,
            }, cfg["log_path"])
            return 0

    # Sentinel bypass (cap-gated).
    used = read_sentinel_count()
    m = OVERRIDE_RE.search(added)
    if m:
        if used >= SENTINEL_CAP:
            sys.stderr.write(
                f"docs-bloat-gate: session sentinel cap exhausted "
                f"({used}/{SENTINEL_CAP} used).\n"
                "All gated-doc edits hard-block until next session.\n"
            )
            return 2
        reason = m.group(1).strip()
        err = validate_reason(reason)
        if err:
            sys.stderr.write(
                f"docs-bloat-gate: override sentinel rejected ({err}). "
                f"Reason must be >={SENTINEL_REASON_MIN} chars and contain no "
                f"anti-stopwords ({', '.join(sorted(ANTI_STOPWORDS))}).\n"
            )
            return 2
        new_count = increment_sentinel_count()
        append_log({
            "ts": now_iso(),
            "file": rel,
            "signal": "S1",
            "bypass_type": "sentinel",
            "reason": reason,
            "char_delta": char_delta,
            "session_id": session_id(),
            "tool": tool,
        }, cfg["log_path"])
        sys.stderr.write(
            f"docs-bloat-gate: sentinel burned ({new_count}/{SENTINEL_CAP} "
            "this session). Edit allowed.\n"
        )
        return 0

    sys.stderr.write(
        f"docs-bloat-gate: char_delta={char_delta} exceeds cap={cap} "
        f"({tier} tier, file={rel}).\nOptions:\n"
        "  1. Revise edit to fit within budget\n"
        "  2. Add L2 heading if introducing genuinely new section "
        f"(<={NEW_SECTION_LINE_EXEMPT} lines / "
        f"{NEW_SECTION_CHAR_EXEMPT} chars exempt)\n"
        "  3. Override: <!-- docs-bloat-gate-override: "
        f"<reason >={SENTINEL_REASON_MIN} chars, no stopwords> -->\n"
        f"     WARNING: {SENTINEL_CAP} sentinel per session. After use, all "
        "further edits\n"
        "     to gated docs hard-block until next session.\n"
        f"Sentinels used this session: {used}/{SENTINEL_CAP}.\n"
    )
    return 2


# --- Tool handlers -------------------------------------------------------
def handle_write_edit(payload: dict, tool: str) -> int:
    ti = payload.get("tool_input", {})
    file_path = ti.get("file_path", "")
    if not file_path:
        return 0

    # Memory exempt — skip all signals.
    if is_memory_path(file_path):
        return 0

    # All signals apply only to .md writes.
    if not file_path.endswith(".md"):
        return 0

    # Extract added/removed text.
    if tool == "Edit":
        added = ti.get("new_string", "")
        removed = ti.get("old_string", "")
    else:  # Write
        added = ti.get("content", "")
        try:
            removed = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            removed = ""

    # S2 + S3 always run on .md writes regardless of project.
    rc = check_s2(added, removed)
    if rc:
        return rc
    rc = check_s3(added, removed)
    if rc:
        return rc

    # Below: opt-in checks (S1, W1.1) — require project_dir.
    proj = project_dir_or_none()
    if proj is None:
        return 0

    rel = relpath_in(proj, file_path)
    if rel is None:
        return 0

    cfg = load_config(proj)

    # W1.1 — block new audit-style files at docs/ root (depth=1, not gated).
    if (
        tool == "Write"
        and cfg["audit_root_check"]
        and rel.startswith("docs/")
        and rel.count("/") == 1
        and rel.endswith(".md")
        and rel not in cfg["gated_docs"]
    ):
        content = ti.get("content", "")
        if AUDIT_KEYWORDS_RE.search(content) and not OVERRIDE_RE.search(content):
            sys.stderr.write(
                "docs-bloat-gate: new docs/*.md root file with "
                "audit/analysis/report/research keywords. Move to "
                "docs/analysis/ (gitignored), use a docs/ subdir, or add "
                f"<!-- docs-bloat-gate-override: <reason >={SENTINEL_REASON_MIN} "
                "chars> -->.\n"
            )
            return 2

    if not is_gated_path(rel, cfg):
        return 0

    try:
        current = (proj / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        current = ""

    return gate_s1(rel, added, removed, current, tool, cfg)


def handle_bash(payload: dict) -> int:
    cmd = payload.get("tool_input", {}).get("command", "")
    if not cmd:
        return 0

    proj = project_dir_or_none()
    if proj is None:
        return 0

    cfg = load_config(proj)
    patterns = build_bash_patterns(cfg)
    if not patterns:
        return 0

    matches = [m for pat in patterns for m in pat.findall(cmd)]
    if not matches:
        return 0

    used = read_sentinel_count()
    m = OVERRIDE_RE.search(cmd)
    if m:
        if used >= SENTINEL_CAP:
            sys.stderr.write(
                f"docs-bloat-gate: session sentinel cap exhausted "
                f"({used}/{SENTINEL_CAP} used). Bash write blocked.\n"
            )
            return 2
        reason = m.group(1).strip()
        err = validate_reason(reason)
        if err:
            sys.stderr.write(
                f"docs-bloat-gate: override sentinel rejected ({err}).\n"
            )
            return 2
        new_count = increment_sentinel_count()
        append_log({
            "ts": now_iso(),
            "file": "|".join(sorted(set(matches))),
            "signal": "S1",
            "bypass_type": "sentinel",
            "reason": reason,
            "char_delta": 0,
            "session_id": session_id(),
            "tool": "Bash",
        }, cfg["log_path"])
        sys.stderr.write(
            f"docs-bloat-gate: sentinel burned ({new_count}/{SENTINEL_CAP} "
            "this session). Bash write allowed.\n"
        )
        return 0

    sys.stderr.write(
        "docs-bloat-gate: Bash command writes to a gated doc/rule path "
        f"({', '.join(sorted(set(matches)))}). Use Write/Edit (gate "
        "computes delta + density), or include "
        f"<!-- docs-bloat-gate-override: <reason >={SENTINEL_REASON_MIN} "
        "chars> --> in the command. "
        f"Sentinels used: {used}/{SENTINEL_CAP}.\n"
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    tool = payload.get("tool_name", "")
    if tool in ("Write", "Edit"):
        return handle_write_edit(payload, tool)
    if tool == "Bash":
        return handle_bash(payload)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
