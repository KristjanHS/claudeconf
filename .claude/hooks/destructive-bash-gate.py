#!/usr/bin/env python3
"""
destructive-bash-gate — global PreToolUse hook on Bash.

Blocks (exit 2) the destructive-command class that settings.json prefix-match
deny rules cannot catch:

  D1: recursive rm against /, /*, ~, $HOME/${HOME}, bare-variable roots
      ($VAR/ or $VAR/* — empty expansion => /), or top-level system dirs;
      any rm with --no-preserve-root
  D2: downloader piped into a shell (curl|wget ... | sh/bash/...), or a shell
      fed a downloader via command/process substitution (bash -c "$(curl ...)")
  D3: write-actions into a .ssh dir (redirect, tee, sed -i, cp/mv/install/
      rsync/ln dest, dd of=, truncate, rm)
  D4 (asks, never blocks): the same write-actions into a path an `Edit(...)` ask rule in
      ~/.claude/settings.json or managed-settings guards — resolved via ~/$HOME, cwd, realpath.

Analysis is token-level, not substring: commands are split quote-aware into
pipelines/stages (comments and <<'EOF' bodies dropped; $(...)/`...`/<(...) and
`bash -c`/`eval` strings analyzed, even inside an unquoted <<EOF body), so commit messages and heredoc text that MENTION
"rm -rf /" pass. Reads of .ssh paths pass (write-actions only).

Fail-open on unexpected errors (outer wrapper) and on parse failures (incl. nesting
too deep to recurse), EXCEPT an unparseable command whose raw text matches RAW_DANGER —
that blocks as "unparseable".

No in-band bypass: Claude authors the commands this gate inspects, so an
escape hatch Claude could add itself would be no gate at all. If a blocked
command is genuinely intended, the USER runs it manually or temporarily
removes the hook from settings.json (hooks hot-reload; no restart needed).

Every block is logged to ~/.claude/state/destructive-bash-blocks.log (JSONL).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
try:
    import ask_paths
except ImportError:  # lib absent (partial install) => D4 inert, D1–D3 unaffected
    ask_paths = None

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LOG_PATH = Path.home() / ".claude" / "state" / "destructive-bash-blocks.log"
ASK_SETTINGS = (
    Path.home() / ".claude" / "settings.json",
    Path("/etc/claude-code/managed-settings.json"),
)

# Cheap stage-1 scan; anything not matching is allowed without parsing.
SUSPICION = re.compile(
    r"\brm\b|\.ssh|\bcurl\b|\bwget\b|>"
    r"|\b(?:tee|sed|cp|mv|install|rsync|ln|dd|truncate)\b"
)
REDIRECT = re.compile(r"(?:\d*|&)>[>|]?")
GLUED_REDIRECT = re.compile(r"(?:\d*|&)>[>|]?(\S+)")
COPY_VERBS = ("cp", "mv", "install", "rsync", "ln")
TARGET_DIR_VERBS = ("cp", "mv", "install", "ln")  # GNU -t DIR / --target-directory=DIR

KEYWORDS = {"!", "{", "}", "if", "then", "elif", "else", "while", "until", "do"}
# Words after which a `(` still sits at command position (subshell), not inside a word.
CMD_POS_WORDS = KEYWORDS | {"time", "coproc"}
CASE_WORD = re.compile(r"(case|esac|in)(?=[\s;&|()<>]|$)")
FUNC_PARENS = re.compile(r"\([ \t]*\)")
WRAPPERS = {
    "sudo",
    "command",
    "env",
    "nice",
    "ionice",
    "nohup",
    "time",
    "xargs",
    "doas",
}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
DOWNLOADERS = {"curl", "wget"}
SYSTEM_ROOTS = {
    "/bin",
    "/boot",
    "/etc",
    "/home",
    "/lib",
    "/lib64",
    "/opt",
    "/root",
    "/sbin",
    "/srv",
    "/usr",
    "/var",
}
SSH_PATH = re.compile(r"(^|/)\.ssh(/|$)")
CMDSUB_TOKEN = "__CMDSUB__"

# Raw-text danger shapes: the fail-closed fallback when the parser gives up.
# Arguments stay inside one stage, so `rm -rf x && mkdir y/.claude` does not match.
_ROOTS = "|".join(sorted(r.lstrip("/") for r in SYSTEM_ROOTS))
_TARGET = (
    r"[\"']?(/[*/]*|~/?\**|\$\{?HOME\}?(/+\**)*|\$\{?[A-Za-z_]\w*\}?/+\**|/("
    + _ROOTS
    + r")/*\**)"
    r"[\"']?(?=[ \t\n]|$|[;&|)])"
)
_ARGS = r"([^\s;&|]+[ \t]+)*?"
RAW_DANGER = re.compile(
    r"--no-preserve-root"
    r"|\brm[ \t]+"
    + _ARGS
    + r"(-[A-Za-z]*[rR][A-Za-z]*|--recursive)[ \t]+"
    + _ARGS
    + _TARGET
    + r"|\b(curl|wget)\b[^\n;]*\|[ \t]*(\S*/)?(sudo([ \t]+-\S+)*[ \t]+)?(\S*/)?(ba|z|da|k)?sh\b"
    r"|\b(ba|z|da|k)?sh\b[^\n]*(\$\(|<\(|`)[ \t]*(\S*/)?(curl|wget)\b"
    r"|(>>?|\btee\b|\bsed[ \t]+-i|\b(cp|mv|install|rsync|truncate|rm)\b|\bof=)[^\n;|&]*\.ssh(/|\b)"
)


class ParseFailure(Exception):
    def __init__(self, msg: str, pos: int | None = None) -> None:
        super().__init__(msg)
        self.pos = pos  # index into the scanned top-level text, when known


def split_pipelines(text: str) -> tuple[list[list[str]], list[str]]:
    """Quote-aware split into pipelines (lists of stage strings) + captured
    command-substitution texts. Heredoc bodies and # comments are dropped.
    Raises ParseFailure on unbalanced quotes/parens."""
    pipelines, subs, _ = _scan(text, 0, closer=False)
    return pipelines, subs


def _scan(text: str, i: int, closer: bool) -> tuple[list[list[str]], list[str], int]:
    """Scan from i; with closer, stop after the unmatched `)` that ends a $( )/<( )
    group. Returns (pipelines, subs, index after the scanned text)."""
    pipelines: list[list[str]] = []
    subs: list[str] = []
    stage: list[str] = []
    stages: list[str] = []
    n = len(text)
    start = i
    quote = ""  # '', "'", '"'
    quote_at = i
    depth = 0  # subshell ( ) nesting inside this scan
    # Word-internal ( ) nesting: arr=(…), [[ =~ (…) ]], ${x:-(…)}. Blanks inside are
    # kept escaped so the group stays ONE token — `x=( rm -rf / )` is an assignment.
    wdepth = 0
    cases: list[str] = []  # per open `case`: "word" (before `in`), "pat", "body"
    pending_heredocs: list[
        tuple[str, bool, bool]
    ] = []  # (delimiter, strip_tabs, expands)

    def end_stage() -> None:
        nonlocal wdepth
        if wdepth:  # a separator ends an unclosed group: `${x:-(}; rm -rf /` splits
            stage[:] = [e[1:] if e in ("\\ ", "\\\t") else e for e in stage]
            wdepth = 0
        s = "".join(stage).strip()
        stage.clear()
        if s:
            stages.append(s)

    def end_pipeline() -> None:
        end_stage()
        if stages:
            pipelines.append(list(stages))
            stages.clear()

    def at_cmd_pos() -> bool:
        """Only keywords so far: a `(` / `case` here is at command position."""
        return all(w in CMD_POS_WORDS for w in "".join(stage).split())

    def word_paren() -> bool:
        """A `(` glued to a word (`x=(`, `${x:-(`, `@(`) or inside `[[ … ]]` runs
        nothing; any other `(` — `time -p (`, `coproc NAME (` — opens a subshell
        (fail closed)."""
        if at_cmd_pos():
            return False
        if stage[-1] not in (" ", "\t"):
            return True
        words = "".join(stage).split()
        for k, w in enumerate(words):
            if w == "[[":
                return "]]" not in words[k + 1 :]
            if w not in CMD_POS_WORDS:
                return False
        return False

    def substitution(open_idx: int) -> int:
        """Recurse into the group opened at open_idx; return index after its `)`."""
        _, _, end = _scan(text, open_idx + 1, closer=True)
        subs.append(text[open_idx + 1 : end - 1])
        stage.append(CMDSUB_TOKEN)
        return end

    def body_subs(body: str) -> None:
        """Capture $( )/backticks of an expanding heredoc body, scanned on its own so
        nothing can match past the delimiter; an unterminated one consumes the rest of
        the body (bash), so scanning stops there — also keeps this linear."""
        body = re.sub(
            r"\\(\\|\n)", lambda m: "\\\\" if m.group(1) == "\\" else "", body
        )
        k = 0
        while k < len(body):
            if body[k] == "\\":
                k += 2
                continue
            if not (body.startswith("$(", k) or body[k] == "`"):
                k += 1
                continue
            try:
                if body[k] == "$":
                    end = _scan(body, k + 2, closer=True)[2]
                    subs.append(body[k + 2 : end - 1])
                else:
                    end = body.index("`", k + 1) + 1
                    subs.append(body[k + 1 : end - 1])
            except (ParseFailure, ValueError):
                break
            # Own word: D2 sees `bash <<EOF` fed $(curl …); `> ~/.bashrc` stays resolvable.
            stage.append(" " + CMDSUB_TOKEN)
            k = end

    def backtick(start: int) -> int:
        end = text.find("`", start + 1)
        if end < 0:
            raise ParseFailure("unbalanced backtick", start)
        subs.append(text[start + 1 : end])
        stage.append(CMDSUB_TOKEN)
        return end + 1

    while i < n:
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = ""
            stage.append(c)
            i += 1
            continue
        if c == "\\":
            if text[i + 1 : i + 2] != "\n":  # bash deletes \<newline> before tokenising
                stage.append(text[i : i + 2])
            i += 2
            continue
        if quote == '"':
            if c == '"':
                quote = ""
                stage.append(c)
                i += 1
            elif text[i : i + 2] == "$(":
                i = substitution(i + 1)
            elif c == "`":
                i = backtick(i)
            else:
                stage.append(c)
                i += 1
            continue
        # unquoted
        # Word start per the stage buffer: escapes are 2-char elements, so `a\;#` is no comment.
        if c == "#" and (not stage or stage[-1] in (" ", "\t", "(")):
            eol = text.find("\n", i)
            i = n if eol < 0 else eol
            continue
        if c in ("'", '"'):
            quote, quote_at = c, i
            stage.append(c)
            i += 1
            continue
        if text[i : i + 2] in ("$(", "<(", ">("):
            i = substitution(i + 1)
            continue
        if c == "`":
            i = backtick(i)
            continue
        if text[i : i + 2] == "<<" and text[i : i + 3] != "<<<":
            j = i + 2
            strip_tabs = j < n and text[j] == "-"
            if strip_tabs:
                j += 1
            while j < n and text[j] in " \t":
                j += 1
            m = re.match(r"""(['"]?)([A-Za-z0-9_]+)\1""", text[j:])
            if m:
                pending_heredocs.append((m.group(2), strip_tabs, not m.group(1)))
                i = j + m.end()
                continue
            stage.append(text[i : i + 2])
            i += 2
            continue
        if c == "\n":
            if pending_heredocs:
                # Drop heredoc bodies up to each delimiter; an unquoted delimiter's
                # body still runs its $( ) and backticks, so those are captured.
                j = i + 1
                for delim, strip_tabs, expands in pending_heredocs:
                    body_start = j
                    while j < n:
                        eol = text.find("\n", j)
                        if eol < 0:
                            eol = n
                        line = text[j:eol]
                        if (line.lstrip("\t") if strip_tabs else line) == delim:
                            if expands:
                                body_subs(text[body_start:j])
                            j = eol + 1
                            break
                        j = eol + 1
                    else:
                        if expands:
                            body_subs(text[body_start:])
                pending_heredocs.clear()
                end_pipeline()
                i = j
                continue
            end_pipeline()
            i += 1
            continue
        if c == "(":
            if not word_paren():  # subshell, or the optional `(` of a case pattern
                if not (cases and cases[-1] == "pat"):
                    depth += 1
                end_pipeline()
                i += 1
                continue
            m = FUNC_PARENS.match(text, i)
            if m:  # name() function definition: the body follows as commands
                end_pipeline()
                i = m.end()
                continue
            wdepth += 1  # inside a word: the group runs nothing
            stage.append(c)
            i += 1
            continue
        if c == ")":
            if wdepth:
                wdepth -= 1
                stage.append(c)
                i += 1
                continue
            if cases and cases[-1] == "pat":  # case pattern ends; its commands follow
                cases[-1] = "body"
                end_pipeline()
                i += 1
                continue
            if closer and depth == 0:
                end_pipeline()
                return pipelines, subs, i + 1
            depth = max(depth - 1, 0)
            end_pipeline()
            i += 1
            continue
        if c == ";":
            if cases and cases[-1] == "body" and text[i + 1 : i + 2] in (";", "&"):
                cases[-1] = "pat"  # ;; ;& ;;& end a case branch
                end_pipeline()
                i += 3 if text[i : i + 3] == ";;&" else 2
                continue
            end_pipeline()
            i += 1
            continue
        if c == "&":
            if text[i - 1 : i] == ">":  # 2>&1, >&2
                stage.append(c)
                i += 1
                continue
            if text[i : i + 2] in ("&>", "&&"):
                if text[i + 1] == ">":
                    stage.append(text[i : i + 2])
                    i += 2
                    continue
                end_pipeline()
                i += 2
                continue
            end_pipeline()
            i += 1
            continue
        if c == "|":
            if text[i : i + 2] == "||":
                end_pipeline()
                i += 2
                continue
            if stage and stage[-1] == ">":  # `>|` noclobber-override redirect
                stage.append(c)
                i += 1
                continue
            if text[i : i + 2] == "|&":
                i += 2
            else:
                i += 1
            end_stage()
            continue
        if c == ">" and not wdepth:
            # `x>f` redirects to f: split it off its word, unless that word is an fd (`2>`, `&>`).
            words = "".join(stage).split()
            if words and stage[-1] not in (" ", "\t"):
                if not re.fullmatch(r"\d*&?|.*>", words[-1]):
                    stage.append(" ")
        if wdepth and c in " \t":
            stage.append("\\" + c)
            i += 1
            continue
        if c in "cei" and (not stage or stage[-1] in (" ", "\t")):
            m = CASE_WORD.match(text, i)
            if m and m.group(1) == "in" and cases and cases[-1] == "word":
                cases[-1] = "pat"
                stage.append("in")
                end_pipeline()
                i = m.end()
                continue
            if m and m.group(1) != "in" and at_cmd_pos():
                if m.group(1) == "case" and not (cases and cases[-1] == "pat"):
                    cases.append("word")
                elif m.group(1) == "esac" and cases:
                    cases.pop()
        stage.append(c)
        i += 1
    if quote:
        raise ParseFailure("unbalanced quote", quote_at)
    if closer:
        raise ParseFailure("unbalanced (", start - 1)
    end_pipeline()
    return pipelines, subs, n


def tokens(stage: str) -> list[str]:
    try:
        toks = shlex.split(stage, posix=True)
    except ValueError as e:
        raise ParseFailure(str(e)) from e
    # Strip wrappers and VAR=VAL; leading redirects move to the end; argv0 is basenamed.
    moved: list[str] = []
    while toks:
        t = toks[0]
        if REDIRECT.fullmatch(t):  # `2>/dev/null rm -rf /` runs rm
            moved += toks[:2]
            del toks[:2]
        elif GLUED_REDIRECT.fullmatch(t):
            moved.append(toks.pop(0))
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
            toks.pop(0)
        elif t in KEYWORDS:
            toks.pop(0)
        elif t in ("coproc", "function"):  # `coproc [NAME] {`, `function NAME {`
            toks.pop(0)
            if toks and (t == "function" or toks[1:2] == ["{"]):
                toks.pop(0)
        elif os.path.basename(t) in WRAPPERS:
            toks.pop(0)
            while toks and toks[0].startswith("-"):
                toks.pop(0)
        else:
            break
    if toks and "/" in toks[0]:  # /bin/rm, /usr/bin/curl, ./x/sh
        toks[0] = os.path.basename(toks[0]) or toks[0]
    return toks + moved


def is_protected_rm_target(t: str) -> bool:
    if re.fullmatch(r"/+[*/]*", t):  # /, //, /*, /*/*
        return True
    if re.fullmatch(r"~(/\**)?", t):  # ~, ~/, ~/*
        return True
    if re.fullmatch(r"\$\{?HOME\}?(/+\**)*", t):  # $HOME, ${HOME}/, $HOME/*
        return True
    if re.fullmatch(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/+\**", t):  # $VAR/ => / when unset
        return True
    norm = re.sub(r"[*/]+$", "", t) or "/"
    if norm in SYSTEM_ROOTS:
        return True
    home = os.path.expanduser("~")
    if norm == home.rstrip("/"):
        return True
    return False


def check_stage(argv: list[str]) -> str | None:
    """Return block reason or None for one pipeline stage."""
    if not argv:
        return None
    cmd = argv[0]
    args = argv[1:]
    flags = [a for a in args if a.startswith("-")]
    positional = [a for a in args if not a.startswith("-") and a != CMDSUB_TOKEN]

    if cmd == "rm":
        if "--no-preserve-root" in flags:
            return "rm --no-preserve-root"
        recursive = "--recursive" in flags or any(
            re.fullmatch(r"-[A-Za-z]+", f) and ("r" in f or "R" in f) for f in flags
        )
        if recursive:
            for t in positional:
                if is_protected_rm_target(t):
                    return f"recursive rm against protected path {t!r}"

    # D3 write-actions into .ssh
    for t in write_targets(argv)[0]:
        if SSH_PATH.search(t):
            return f"{cmd} writes .ssh path {t!r}"
    return None


def write_targets(argv: list[str]) -> tuple[list[str], list[str]]:
    """(paths one stage writes, copy-verb sources). A real redirect is its own `>`/`>>`
    token or a glued `>>path` token; a quoted mention stays inside one message arg."""
    targets: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if REDIRECT.fullmatch(tok):
            targets.extend(argv[i + 1 : i + 2])
            i += 2
            continue
        m = GLUED_REDIRECT.fullmatch(tok)
        if m:
            if not m.group(1).startswith("&"):  # 2>&1 duplicates an fd
                targets.append(m.group(1))
        else:
            rest.append(tok)
        i += 1
    if not rest:
        return targets, []
    cmd, args = rest[0], rest[1:]
    flags = [a for a in args if a.startswith("-")]
    pos = [a for a in args if not a.startswith("-") and a != CMDSUB_TOKEN]
    if cmd in TARGET_DIR_VERBS:
        tdir = _target_dir(args)
        if tdir is not None:
            return targets + [tdir], [a for a in pos if a != tdir]
    if cmd in ("rm", "tee", "truncate") or (cmd == "sed" and any(map(_sed_i, flags))):
        targets += pos
    elif cmd in COPY_VERBS and pos:
        return targets + pos[-1:], pos[:-1]
    elif cmd == "dd":
        targets += [a[3:] for a in args if a.startswith("of=")]
    return targets, []


def _target_dir(args: list[str]) -> str | None:
    """DIR of `-t DIR`, `-rtDIR`, `--target-directory[=]DIR`, else None."""
    for k, a in enumerate(args):
        if a.startswith("--target-directory="):
            return a.split("=", 1)[1]
        if a == "--target-directory" or re.fullmatch(r"-[A-Za-z]*t", a):
            return args[k + 1] if k + 1 < len(args) else None
        m = re.fullmatch(r"-[A-Za-z]*?t(.+)", a)
        if m and not a.startswith("--"):
            return m.group(1)
    return None


def _sed_i(flag: str) -> bool:
    """sed in-place: --in-place[=SUF], or an `i` in a short cluster (-i, -Ei, -ni.bak)."""
    if flag.startswith("--"):
        return flag == "--in-place" or flag.startswith("--in-place=")
    for ch in flag[1:]:
        if ch == "i":
            return True
        if ch in "efl" or not ch.isalpha():  # -e/-f/-l take an argument
            return False
    return False


def resolve_target(tok: str, cwd: str, home: str) -> str | None:
    """Absolute path for a written token; None when another variable or substitution remains."""
    if tok == "~" or tok.startswith("~/"):
        tok = home + tok[1:]
    else:
        tok = re.sub(r"\A\$(?:HOME\b|\{HOME\})", lambda _: home, tok)
    if not tok or "$" in tok or "`" in tok or CMDSUB_TOKEN in tok:
        return None
    return os.path.normpath(os.path.join(cwd, tok))


def make_asker(
    globs: list[str], cwd: str, home: str, settings_dir: str
) -> Callable[[list[str]], str | None]:
    """D4: ask reason when a stage writes a path an Edit ask glob guards."""
    assert ask_paths is not None

    def ask(argv: list[str]) -> str | None:
        targets, sources = write_targets(argv)
        for t in targets:
            p = resolve_target(t, cwd, home)
            if p is None:
                continue
            cands = {p, os.path.realpath(p)}
            if os.path.isdir(p):  # written path is a child: the copied name, or any
                kids = [os.path.basename(s.rstrip("/")) for s in sources] + ["_"]
                cands |= {os.path.join(c, k) for c in list(cands) for k in kids}
            for c in sorted(cands):
                g = ask_paths.matching_glob(c, globs, cwd, home, settings_dir)
                if g:
                    return f"{argv[0]} writes {t!r} (ask rule Edit({g}))"
        return None

    return ask


def shell_string(argv: list[str]) -> str | None:
    """The command text a `bash -c '…'` / `eval …` stage runs, else None."""
    if not argv:
        return None
    cmd = argv[0]
    if cmd == "eval":
        return " ".join(argv[1:]) or None
    if cmd in SHELLS:
        for k, a in enumerate(argv[1:], 1):
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a):
                rest = [x for x in argv[k + 1 :] if not x.startswith("-")]
                return rest[0] if rest else None
    return None


def analyze(
    command: str, asker: Callable[[list[str]], str | None] | None = None
) -> tuple[str | None, str | None]:
    """(block reason, ask reason); a block anywhere wins over an ask. Raises ParseFailure."""
    ask_reason = None
    queue = [(command, False)]  # (text, is a `bash -c`/`eval` string)
    while queue:
        text, inner_str = queue.pop()
        try:
            pipelines, subs = split_pipelines(text)
            queue.extend((sub, inner_str) for sub in subs)
            sub_argv0s = set()
            for sub in subs:
                try:
                    sub_pipes, _ = split_pipelines(sub)
                    for sp in sub_pipes:
                        tk = tokens(sp[0])
                        if tk:
                            sub_argv0s.add(tk[0])
                except ParseFailure:
                    pass
            for pipeline in pipelines:
                argvs = []
                for stage_text in pipeline:
                    argv = tokens(stage_text)
                    argvs.append(argv)
                    reason = check_stage(argv)
                    if reason:
                        return reason, None
                    if asker and argv and ask_reason is None:
                        try:  # a D4 error must never abort D1–D3 on later stages
                            ask_reason = asker(argv)
                        except Exception:
                            pass
                    inner = shell_string(argv)
                    if inner is not None:
                        queue.append((inner, True))
                # D2: downloader piped into shell
                for idx, argv in enumerate(argvs):
                    if argv and argv[0] in DOWNLOADERS:
                        for later in argvs[idx + 1 :]:
                            if later and later[0] in SHELLS:
                                return f"{argv[0]} piped into {later[0]}", None
                # D2: shell fed a downloader via $( ) / <( ) / backticks
                for argv in argvs:
                    if argv and argv[0] in SHELLS and CMDSUB_TOKEN in argv:
                        if sub_argv0s & DOWNLOADERS:
                            return (
                                "shell executing downloader output (substitution)",
                                None,
                            )
        except ParseFailure:
            if not inner_str:
                raise
            # Unparseable -c/eval string: block on a raw danger shape, else skip it alone.
            if RAW_DANGER.search(re.sub(r"[\"']|\\\n", "", text)):
                return "unparseable shell -c/eval string with a destructive shape", None
    return None, ask_reason


class Verdict(NamedTuple):
    reason: str
    parse_error: str | None = None  # set when the block is the unparseable fallback
    line: int | None = None  # 1-based line of the parse failure, when known
    ask: bool = False  # D4: prompt the user instead of blocking


def verdict(
    command: str, asker: Callable[[list[str]], str | None] | None = None
) -> Verdict | None:
    """Block/ask verdict or None; an unparseable command blocks only on a raw danger shape."""
    try:
        block, ask = analyze(command, asker)
        if block:
            return Verdict(block)
        return Verdict(ask, ask=True) if ask else None
    except (ParseFailure, RecursionError) as e:
        # Quotes and \<newline> are stripped so `"$HOME"/` and continued lines still match.
        if not RAW_DANGER.search(re.sub(r"[\"']|\\\n", "", command)):
            return None
        pos = e.pos if isinstance(e, ParseFailure) else None
        msg = "nesting too deep" if isinstance(e, RecursionError) else str(e)
        line = None if pos is None else command.count("\n", 0, pos) + 1
        return Verdict(
            f"suspicious command could not be safely parsed ({msg})", msg, line
        )


def log_block(payload: dict, command: str, v: Verdict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        session = re.sub(r"[^A-Za-z0-9_.-]", "", str(payload.get("session_id", "")))
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": session,
            "test": not UUID.fullmatch(session),
            "decision": "ask" if v.ask else "block",
            "reason": v.reason,
            "line": v.line,
            "len": len(command),
            "command": command[:4000],
        }
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def build_asker(payload: dict) -> Callable[[list[str]], str | None] | None:
    if ask_paths is None:
        return None
    globs = list(
        dict.fromkeys(g for p in ASK_SETTINGS for g in ask_paths.edit_ask_globs(p))
    )
    if not globs:
        return None
    home = os.path.expanduser("~")
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and os.path.isabs(cwd) else os.getcwd()
    return make_asker(globs, cwd, home, os.path.join(home, ".claude"))


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not SUSPICION.search(command):
        return 0
    v = verdict(command, build_asker(payload))
    if v is None:
        return 0
    log_block(payload, command, v)
    if v.ask and payload.get("permission_mode") != "bypassPermissions":
        out = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"destructive-bash-gate D4: {v.reason}",
        }
        print(json.dumps({"hookSpecificOutput": out}))
        return 0
    if v.ask:  # bypassPermissions: no prompt is guaranteed, so never pass silently
        sys.stderr.write(
            f"destructive-bash-gate BLOCKED (D4 under bypassPermissions): {v.reason}. "
            "Nothing ran. Use Edit/Write (ask-ruled) or ask the user to run it. "
            "Playbook: ~/.claude/hooks/README.md\n"
        )
        return 2
    if v.parse_error:
        where = f"near line {v.line}" if v.line else "in one stage"
        sys.stderr.write(
            f"destructive-bash-gate BLOCKED: could not parse {where} ({v.parse_error}), and "
            "the raw text carries a destructive shape. Nothing ran. Split the command so "
            "the dangerous part stands alone, or use Edit/Write for file edits — the "
            "rewrite is re-checked by this same gate. Playbook: ~/.claude/hooks/README.md\n"
        )
        return 2
    sys.stderr.write(
        f"destructive-bash-gate BLOCKED: {v.reason}. Nothing ran (PreToolUse blocks the "
        "whole compound command). Do NOT retry variants to slip past the gate. If this "
        "is genuinely intended, ask the user to run it manually in their own terminal, "
        "or to temporarily remove this hook from settings.json. "
        "Playbook: ~/.claude/hooks/README.md\n"
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
