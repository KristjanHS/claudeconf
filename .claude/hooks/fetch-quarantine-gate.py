#!/usr/bin/env python3
# Consumer: upstream-exec-gate.py reuses Ctx, unwrap, _cd, _subshells, REDIRECT, UNRESOLVED, MAX_DEPTH, _load_parser.
"""
fetch-quarantine-gate — global PreToolUse hook on Bash.

Denies (exit 2) fetching foreign code into a trusted tree (a dir listed in
~/.claude/safe-hashes/trusted-dirs.txt, or below one): `git clone`, `git submodule
add`, `gh repo clone`, a downloader piped into tar/unzip/bsdtar, a downloader saving
an archive, `pip download`, `npm pack <spec>`. Foreign code goes to the quarantine
root instead: `repo-fetch OWNER/REPO SHA` → ~/quarantine/<name>/src.

Parsing reuses destructive-bash-gate's quote-aware splitter, so commit messages
and heredoc bodies that MENTION `git clone` pass. Wrappers (sudo, env, timeout,
nice, xargs, …) are stripped; `sh -c STRING` / `eval ARGS` are re-analysed.
`cd DIR` / `git -C DIR` / `env -C DIR` move the cwd (a `cd` inside `( … )` stays
there). A destination that can't be resolved (`$VAR`, `$(...)`, xargs input)
blocks only when the effective cwd is trusted. An unparseable command — or a shell
fed a heredoc — falls back to a raw-text match: a fetch verb plus a trusted cwd or
a trusted path in the text blocks. No in-band bypass; playbook:
~/.claude/hooks/README.md.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path

SUSPICION = re.compile(r"\b(git|gh|curl|wget|pip[0-9.]*|npm)\b")
RAW_FETCH = re.compile(
    r"\bgit\b[^\n;&|]*\b(clone|submodule[ \t]+add)\b"
    r"|\bgh[ \t]+repo[ \t]+clone\b"
    r"|\bpip[0-9.]*\b[^\n;&|]*\bdownload\b"
    r"|\bnpm\b[^\n;&|]*\bpack\b"
    r"|\b(curl|wget)\b"
)
ARCHIVE = re.compile(
    r"\.(tar(\.[a-z0-9]+)?|tgz|tbz2?|txz|zip|whl|7z|jar|gem|crate|nupkg)$", re.I
)
URLISH = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://|[^/\s:@]+@[^/\s:]+:")
OWNER_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
REDIRECT = re.compile(r"(\d*|&)(>>?|>\||<<<|<>|<|>&|<&)(.*)")
EXTRACTORS = {"tar", "bsdtar", "unzip"}
DOWNLOADER = r"\b(curl|wget)\b"
DOWNLOAD_PIPE = DOWNLOADER + r"[^;&\n]*(^|[^|])\|[ \t]*$"
DOWNLOADERS = {"curl", "wget"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# Option-value tables: (short opts taking a value, long opts taking a value).
CLONE_OPTS = ("bocju", {
    "--branch", "--origin", "--config", "--depth", "--jobs", "--reference",
    "--reference-if-able", "--separate-git-dir", "--filter", "--template",
    "--upload-pack", "--shallow-since", "--shallow-exclude", "--server-option",
    "--bundle-uri", "--revision", "--ref-format",
})  # fmt: skip
SUBMODULE_OPTS = ("b", {"--branch", "--name", "--reference", "--depth"})
GH_CLONE_OPTS = ("u", {"--upstream-remote-name"})
CURL_OPTS = ("AbcCdDeEFHKmoPQrtTuUwxXyYz", {
    "--output", "--output-dir", "--data", "--header", "--user", "--user-agent",
    "--referer", "--proxy", "--request", "--form", "--cookie", "--cookie-jar",
    "--max-time", "--config", "--upload-file", "--write-out", "--range",
})  # fmt: skip
WGET_OPTS = ("OPoaeiBtTwQUlARDIX", {
    "--output-document", "--directory-prefix", "--output-file", "--append-output",
    "--execute", "--input-file", "--base", "--tries", "--timeout", "--wait",
    "--quota", "--user-agent", "--level", "--accept", "--reject", "--domains",
    "--include-directories", "--exclude-directories", "--header",
})  # fmt: skip
TAR_OPTS = ("fCTXbHKNgVL", {"--file", "--directory", "--files-from", "--exclude-from"})
PIP_OPTS = ("dcreif", {
    "--dest", "--destination-dir", "--constraint", "--requirement", "--editable",
    "--index-url", "--extra-index-url", "--find-links", "--platform",
    "--python-version", "--implementation", "--abi", "--no-binary", "--only-binary",
})  # fmt: skip
NPM_OPTS = (
    "Cw",
    {
        "--prefix",
        "--pack-destination",
        "--workspace",
        "--registry",
        "--userconfig",
        "--cache",
    },
)
# Wrapper → (short opts taking a value, long opts taking a value, leading positionals).
WRAPPER_OPTS: dict[str, tuple[str, set[str], int]] = {
    "sudo": ("ugCDpRrTtU", {"--user", "--group", "--chdir", "--prompt", "--role",
             "--type", "--other-user", "--close-from", "--command-timeout", "--chroot"}, 0),
    "doas": ("uC", set(), 0),
    "env": ("uCS", {"--unset", "--chdir", "--split-string"}, 0),
    "nice": ("n", {"--adjustment"}, 0),
    "ionice": ("cnpPu", {"--class", "--classdata", "--pid", "--pgid", "--uid"}, 0),
    "timeout": ("sk", {"--signal", "--kill-after"}, 1),
    "stdbuf": ("ioe", {"--input", "--output", "--error"}, 0),
    "nohup": ("", set(), 0),
    "command": ("", set(), 0),
    "exec": ("a", set(), 0),
    "time": ("fo", {"--format", "--output"}, 0),
    "xargs": ("adEILnPs", {"--arg-file", "--delimiter", "--eof", "--replace",
              "--max-lines", "--max-args", "--max-procs", "--max-chars",
              "--process-slot-var"}, 0),
}  # fmt: skip
MAX_DEPTH = 25
UNRESOLVED = "<unresolved>"


def _load_parser():
    spec = importlib.util.spec_from_file_location(
        "dbg", Path(__file__).with_name("destructive-bash-gate.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def trusted_dirs() -> tuple[list[str], list[str]]:
    """(realpath'd roots, spellings to look for in raw text)."""
    f = Path.home() / ".claude" / "safe-hashes" / "trusted-dirs.txt"
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], []
    listed = [ln.strip() for ln in lines if ln.startswith("/")]
    roots = sorted({os.path.realpath(ln) for ln in listed})
    home = os.path.expanduser("~").rstrip("/")
    forms = set()
    for r in {ln.rstrip("/") or "/" for ln in listed} | set(roots):
        forms.add(r)
        if home and r.startswith(home + "/"):
            rest = r[len(home) :]
            forms |= {"~" + rest, "$HOME" + rest, "${HOME}" + rest}
    return roots, sorted(forms)


def trusted_root(dest: str, roots: list[str]) -> str | None:
    for r in roots:
        if dest == r or dest.startswith(r.rstrip("/") + "/"):
            return r
    return None


class Ctx:
    def __init__(self, raw: str, cwd: str, roots: list[str], forms: list[str], p):
        self.raw, self.origin, self.roots, self.forms, self.p = (
            raw,
            cwd,
            roots,
            forms,
            p,
        )
        self.home_overridden = bool(re.search(r"\bHOME=", raw))


def resolve(path: str, cwd: str, ctx: Ctx) -> str:
    """Absolute realpath, or UNRESOLVED. Only `~` and $HOME/${HOME} expand."""
    if ctx.p.CMDSUB_TOKEN in path:
        return UNRESOLVED
    if path.startswith("~") or re.match(r"\$(HOME|\{HOME\})(/|$)", path):
        if ctx.home_overridden:
            return UNRESOLVED
        path = os.path.expanduser(re.sub(r"^\$(HOME|\{HOME\})", "~", path))
        if path.startswith("~"):
            return UNRESOLVED
    if "$" in path:
        return UNRESOLVED
    if not os.path.isabs(path):
        if cwd == UNRESOLVED:
            return UNRESOLVED
        path = os.path.join(cwd, path)
    return os.path.realpath(path)


def parse_opts(
    args: list[str], shorts: str, longs: set[str], first_pos: bool = False
) -> tuple[list[tuple[str, str | None]], list[str]]:
    """getopt-style split → ([(flag, value)], positionals). Short clusters (`-qb V`,
    `-bV`) and `--long V` / `--long=V`. first_pos: stop at the first positional."""
    opts: list[tuple[str, str | None]] = []
    pos: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos += args[i + 1 :]
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            if eq:
                opts.append((name, val))
            elif name in longs and i + 1 < len(args):
                i += 1
                opts.append((name, args[i]))
            else:
                opts.append((name, None))
        elif a.startswith("-") and len(a) > 1:
            for j in range(1, len(a)):
                ch = a[j]
                if ch in shorts:
                    if j + 1 < len(a):
                        opts.append(("-" + ch, a[j + 1 :]))
                    elif i + 1 < len(args):
                        i += 1
                        opts.append(("-" + ch, args[i]))
                    else:
                        opts.append(("-" + ch, None))
                    break
                opts.append(("-" + ch, None))
        else:
            pos.append(a)
            if first_pos:
                pos += args[i + 1 :]
                break
        i += 1
    return opts, pos


def _last(opts: list[tuple[str, str | None]], *names: str) -> str | None:
    vals = [v for f, v in opts if f in names and v is not None]
    return vals[-1] if vals else None


def _has(opts: list[tuple[str, str | None]], *names: str) -> bool:
    return any(f in names for f, _ in opts)


def _repo_basename(url: str) -> str:
    name = re.sub(r"(\.git)?/*$", "", url).rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return name or "."


def _tokens(stage: str, p) -> tuple[list[str], list[str]]:
    """(argv, stdout-redirect targets) of one pipeline stage."""
    try:
        toks = shlex.split(stage, posix=True)
    except ValueError as e:
        raise p.ParseFailure(str(e)) from e
    argv, outs = [], []
    i = 0
    while i < len(toks):
        m = REDIRECT.fullmatch(toks[i])
        if m:
            target = m.group(3)
            if not target and m.group(2) not in (">&", "<&") and i + 1 < len(toks):
                i += 1
                target = toks[i]
            if ">" in m.group(2) and m.group(1) in ("", "1", "&") and target:
                outs.append(target)
        else:
            argv.append(toks[i])
        i += 1
    return argv, outs


class Stage:
    def __init__(self, argv, cwd, xargs=False, nested=(), heredoc=False, outs=()):
        self.argv, self.cwd, self.xargs = argv, cwd, xargs
        self.nested, self.heredoc, self.outs = list(nested), heredoc, list(outs)
        self.name = os.path.basename(argv[0]) if argv else ""


def unwrap(argv: list[str], cwd: str, ctx: Ctx, outs: list[str]) -> Stage:
    """Strip assignments, keywords and wrappers; surface `sh -c` / `eval` text."""
    xargs = False
    wrappers = set(WRAPPER_OPTS) | set(ctx.p.WRAPPERS)
    while argv:
        a, name = argv[0], os.path.basename(argv[0])
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", a) or a in ctx.p.KEYWORDS:
            argv = argv[1:]
            continue
        if name not in wrappers:
            break
        shorts, longs, lead = WRAPPER_OPTS.get(name, ("", set(), 0))
        opts, rest = parse_opts(argv[1:], shorts, longs, first_pos=True)
        for flag, val in opts:
            if val is None:
                continue
            if (name, flag) in {("env", "-C"), ("env", "--chdir"), ("sudo", "-D"), ("sudo", "--chdir")}:  # fmt: skip
                cwd = resolve(val, cwd, ctx)
            if name == "env" and flag in ("-S", "--split-string"):
                return Stage([], cwd, xargs, [" ".join([val, *map(shlex.quote, rest)])])
        xargs = xargs or name == "xargs"
        argv = rest[lead:]
    name = os.path.basename(argv[0]) if argv else ""
    if name == "eval":
        return Stage([], cwd, xargs, [" ".join(argv[1:])])
    if name in SHELLS:
        args, i, has_c = argv[1:], 0, False
        while i < len(args):
            a = args[i]
            if a in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file"):
                i += 2
                continue
            if a == "--":
                i += 1
                break
            if re.fullmatch(r"[-+][A-Za-z]+", a):
                has_c = has_c or (a[0] == "-" and "c" in a)
            elif not a.startswith("--"):
                break
            i += 1
        script = args[i:]
        if has_c:
            return Stage([], cwd, xargs, script[:1])
        heredoc = not script and "<<" in ctx.raw
        return Stage(argv, cwd, xargs, heredoc=heredoc)
    return Stage(argv, cwd, xargs, outs=outs)


def _clone(what, args, cwd, ctx, opts_spec, is_src, skip_extra=None) -> list:
    """Dest of a clone-shaped command, plus every other non-source positional — an
    unknown option's value shifts positionals, so any of them may be the real dest."""
    _, pos = parse_opts(args, *opts_spec)
    if not pos:
        return []
    src_i = next((i for i, a in enumerate(pos) if is_src(a)), 0)
    rest = pos[src_i + 1 :]
    dest = rest[0] if rest else _repo_basename(pos[src_i])
    hits = [(what, resolve(dest, cwd, ctx))]
    for a in pos[:src_i] + rest[1:]:
        if URLISH.match(a) or (skip_extra and skip_extra.fullmatch(a)):
            continue
        d = resolve(a, cwd, ctx)
        if d != UNRESOLVED:
            hits.append((what, d))
    return hits


def stage_dests(st: Stage, ctx: Ctx) -> list[tuple[str, str, str]]:
    """(what, destination, effective cwd) for each place this stage fetches into."""
    if not st.argv:
        return []
    cwd, args = st.cwd, st.argv[1:] + ([ctx.p.CMDSUB_TOKEN] if st.xargs else [])
    hits: list[tuple[str, str]] = []
    cmd = st.name
    if cmd == "git":
        while args and args[0].startswith("-"):
            a = args.pop(0)
            if a == "-C" and args:
                cwd = resolve(args.pop(0), cwd, ctx)
            elif a in ("-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix") and args:  # fmt: skip
                args.pop(0)
        if args[:1] == ["clone"]:
            hits = _clone("git clone", args[1:], cwd, ctx, CLONE_OPTS, URLISH.match)
        elif args[:2] == ["submodule", "add"]:
            hits = _clone("git submodule add", args[2:], cwd, ctx, SUBMODULE_OPTS, URLISH.match)  # fmt: skip
    elif cmd == "gh" and args[:2] == ["repo", "clone"]:
        rest = args[2:]
        rest = rest[: rest.index("--")] if "--" in rest else rest
        is_src = lambda a: URLISH.match(a) or OWNER_REPO.fullmatch(a)  # noqa: E731
        hits = _clone(
            "gh repo clone", rest, cwd, ctx, GH_CLONE_OPTS, is_src, OWNER_REPO
        )
    elif pip_args := _pip_args(cmd, args):
        opts, pos = parse_opts(pip_args, *PIP_OPTS)
        if pos[:1] == ["download"]:
            d = _last(opts, "-d", "--dest", "--destination-dir")
            hits = [("pip download", resolve(d, cwd, ctx) if d else cwd)]
    elif cmd == "npm":
        opts, pos = parse_opts(args, *NPM_OPTS)
        specs = [a for a in pos[1:] if not re.match(r"(\.|/|~|file:)", a)]
        if pos[:1] == ["pack"] and specs:
            d = _last(opts, "--pack-destination")
            hits = [("npm pack", resolve(d, cwd, ctx) if d else cwd)]
            if prefix := _last(opts, "--prefix", "-C"):
                hits.append(("npm pack", resolve(prefix, cwd, ctx)))
    elif cmd in DOWNLOADERS:
        hits = _download_dests(cmd, args, st.outs, cwd, ctx)
    return [(w, d, cwd) for w, d in hits]


def _pip_args(cmd: str, args: list[str]) -> list[str] | None:
    """pip's own argv for `pip[3.X] …` / `python[3.X] [-I …] -m pip …`, else None."""
    if re.fullmatch(r"pip[0-9.]*", cmd):
        return args
    if not re.fullmatch(r"python[0-9.]*", cmd):
        return None
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a in ("-W", "-X"):
            i += 2
            continue
        m = re.fullmatch(r"-[A-Za-z]*?m(.*)", a)
        if m and m.group(1):
            return args[i + 1 :] if m.group(1) == "pip" else None
        if m:
            return args[i + 2 :] if args[i + 1 : i + 2] == ["pip"] else None
        if "c" in a:
            return None
        i += 1
    return None


def _download_dests(cmd, args, outs, cwd, ctx) -> list[tuple[str, str]]:
    """Archive files a downloader writes (`-o x.tgz`, `-O` remote name, `> x.tgz`)."""
    if cmd == "curl":
        opts, pos = parse_opts(args, *CURL_OPTS)
        out = _last(opts, "-o", "--output")
        odir = _last(opts, "--output-dir")
        remote = _has(opts, "-O", "--remote-name", "--remote-name-all")
        unknown = remote and _has(opts, "-J", "--remote-header-name")
    else:
        opts, pos = parse_opts(args, *WGET_OPTS)
        if _has(opts, "--spider"):
            return []
        out = _last(opts, "-O", "--output-document")
        odir = _last(opts, "-P", "--directory-prefix")
        remote = out is None
        unknown = remote and _has(opts, "-r", "--recursive", "-m", "--mirror")
    base = resolve(odir, cwd, ctx) if odir else cwd
    urls = [a for a in pos if re.match(r"[a-z]+://", a)]
    names = [out] if out and out != "-" else []
    if remote:
        names += [u.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1] for u in urls]
        unknown = unknown or ctx.p.CMDSUB_TOKEN in pos
    hits = [(f"{cmd} download into", base)] if unknown else []
    for n in names:
        if ARCHIVE.search(n):
            hits.append((f"{cmd} archive download", resolve(n, base, ctx)))
    for n in outs:
        if ARCHIVE.search(n):
            hits.append((f"{cmd} archive download (redirect)", resolve(n, cwd, ctx)))
    return hits


def extract_dest(st: Stage, ctx: Ctx) -> str | None:
    """Where an extractor stage writes, or None when it does not extract."""
    args = st.argv[1:]
    if st.name == "unzip":
        opts, _ = parse_opts(args, "dxX", set())
        if _has(opts, "-l", "-t", "-v", "-Z", "-p"):
            return None
        d = _last(opts, "-d")
    else:
        if args and re.fullmatch(r"[A-Za-z]+", args[0]):  # old-style `tar xzf -`
            args = ["-" + args[0], *args[1:]]
        opts, _ = parse_opts(args, *TAR_OPTS)
        if _has(opts, "-t", "--list"):
            return None
        d = _last(opts, "-C", "--directory")
    return resolve(d, st.cwd, ctx) if d else st.cwd


def _subshells(text: str) -> list[tuple[bool, str, str]] | None:
    """Split top-level `( … )` subshell groups out of text: [(is_subshell, chunk,
    piped)], so a `cd` inside one does not leak. piped: "all" = a downloader pipes into
    this group, "first" = a downloader group pipes into this chunk's first pipeline.
    None when a heredoc/case/backtick or unbalanced quoting is beyond this light scan."""
    if "<<" in text or "`" in text or re.search(r"\bcase\b", text):
        return None
    chunks: list[tuple[bool, str, str]] = []
    start, depth, open_at, is_sub, quote, i, piped = 0, 0, 0, False, "", 0, ""
    while i < len(text):
        c = text[i]
        if quote == "'":
            quote = "" if c == "'" else quote
        elif c == "\\":
            i += 1
        elif quote == '"':
            quote = "" if c == '"' else quote
        elif c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n;&|("):
            eol = text.find("\n", i)
            i = len(text) if eol < 0 else eol
            continue
        elif c == "(":
            if depth == 0:
                open_at, is_sub = i, i == 0 or text[i - 1] in " \t\n;&|("
            depth += 1
        elif c == ")":
            if depth == 0:
                return None
            depth -= 1
            if depth == 0 and is_sub:
                before, group = text[start:open_at], text[open_at + 1 : i]
                into = re.search(DOWNLOAD_PIPE, before)
                chunks += [(False, before, piped), (True, group, "all" if into else "")]
                out = re.search(DOWNLOADER, group) and re.match(
                    r"[ \t]*\|(?!\|)", text[i + 1 :]
                )
                piped, start = "first" if out else "", i + 1
        i += 1
    if quote or depth:
        return None
    return chunks + [(False, text[start:], piped)]


def _verdict(pairs: list[tuple[str, str, str]], ctx: Ctx) -> str | None:
    for what, dest, eff in pairs:
        if dest == UNRESOLVED:
            root = trusted_root(eff if eff != UNRESOLVED else ctx.origin, ctx.roots)
            if root:
                return (
                    f"{what} with an unresolvable destination from trusted tree {root}"
                )
            continue
        root = trusted_root(dest, ctx.roots)
        if root:
            return f"{what} into {dest} (trusted tree {root})"
    return None


def raw_reason(ctx: Ctx, cwd: str) -> str | None:
    """Fallback when the parser can't see the command: fetch verb + trusted tree in play."""
    if not RAW_FETCH.search(ctx.raw):
        return None
    root = trusted_root(cwd, ctx.roots) if cwd != UNRESOLVED else None
    root = root or trusted_root(ctx.origin, ctx.roots)
    root = root or next((f for f in ctx.forms if f in ctx.raw), None)
    if root:
        return (
            f"fetch command the parser can't follow, with trusted tree {root} in play"
        )
    return None


def walk(text: str, cwd: str, ctx: Ctx, depth: int = 0, piped: str = "") -> str | None:
    """Block reason or None. Raises ParseFailure. piped: see _subshells."""
    if depth > MAX_DEPTH:
        raise ctx.p.ParseFailure("nesting too deep")
    for is_sub, chunk, how in _subshells(text) or [(False, text, "")]:
        how = how or (piped if piped == "all" else "")  # stdin reaches the whole group
        if is_sub:
            reason = walk(chunk, cwd, ctx, depth + 1, how)
        else:
            reason, cwd = _walk_flat(chunk, cwd, ctx, depth, how)
        if reason:
            return reason
    return None


def _walk_flat(
    text: str, cwd: str, ctx: Ctx, depth: int, piped: str = ""
) -> tuple[str | None, str]:
    p = ctx.p
    pipelines, subs = p.split_pipelines(text)
    seen = {cwd}
    for n, pipeline in enumerate(pipelines):
        stages = []
        for stage_text in pipeline:
            argv, outs = _tokens(stage_text, p)
            stages.append(unwrap(argv, cwd, ctx, outs))
        for st in stages:
            for nested in st.nested:
                reason = walk(nested, st.cwd, ctx, depth + 1)
                if reason:
                    return reason, cwd
            if st.heredoc:
                reason = raw_reason(ctx, st.cwd)
                if reason:
                    return reason, cwd
        if len(stages) == 1 and stages[0].name in ("cd", "pushd", "popd"):
            cwd = _cd(stages[0], ctx)
            seen.add(cwd)
            continue
        pairs = [pr for st in stages for pr in stage_dests(st, ctx)]
        if piped == "all" or (piped == "first" and n == 0):
            pairs += [
                (f"download | ( {st.name} )", d, st.cwd)
                for st in stages
                if st.name in EXTRACTORS and (d := extract_dest(st, ctx)) is not None
            ]
        for idx, st in enumerate(stages):
            if st.name not in DOWNLOADERS:
                continue
            for later in stages[idx + 1 :]:
                if later.name in EXTRACTORS:
                    d = extract_dest(later, ctx)
                    if d is not None:
                        pairs.append((f"{st.name} | {later.name}", d, later.cwd))
        reason = _verdict(pairs, ctx)
        if reason:
            return reason, cwd
    for sub in subs:
        for c in seen:
            reason = walk(sub, c, ctx, depth + 1)
            if reason:
                return reason, cwd
    return None, cwd


def _cd(st: Stage, ctx: Ctx) -> str:
    args = st.argv[1:]
    if st.name == "popd":
        return UNRESOLVED
    while args and args[0].startswith("-") and args[0] != "-":
        if args.pop(0) == "--":
            break
    if args[:1] == ["-"]:
        return UNRESOLVED
    return resolve(args[0] if args else "~", st.cwd, ctx)


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not SUSPICION.search(command):
        return 0
    roots, forms = trusted_dirs()
    if not roots:
        return 0
    cwd = os.path.realpath(payload.get("cwd") or os.getcwd())
    p = _load_parser()
    ctx = Ctx(command, cwd, roots, forms, p)
    try:
        reason = walk(command, cwd, ctx)
    except (p.ParseFailure, RecursionError):
        reason = raw_reason(ctx, cwd)
    if not reason:
        return 0
    sys.stderr.write(
        f"fetch-quarantine-gate BLOCKED: {reason}. Nothing ran. Foreign code never lands in a "
        "trusted tree — fetch it into quarantine instead: `repo-fetch OWNER/REPO SHA` "
        "(→ ~/quarantine/<name>/src), then review there and copy in with the adoption flow. "
        "Do NOT retry variants to slip past the gate. Playbook: ~/.claude/hooks/README.md\n"
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
