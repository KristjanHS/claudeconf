#!/usr/bin/env python3
"""upstream-exec-gate — PreToolUse(Bash): deny running code under an external-sources marker dir outside its sandbox.
Playbook + per-project `.claude/upstream-exec.json` format: ~/.claude/hooks/README.md."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path

# The ONE marker list = rules/external-sources.md `paths:`; bats asserts each glob.
MARKERS = ("vendor", "third_party", "external", "upstream", "quarantine", "*-src")
_LITERAL = [re.escape(m) for m in MARKERS if m[0] != "*"]
_SUFFIX = [re.escape(m[1:]) for m in MARKERS if m[0] == "*"]
MARKER = rf"({'|'.join(_LITERAL + [rf'[\w.-]+{s}' for s in _SUFFIX])})"
MARKER_PART = re.compile(MARKER)
MARKER_WORD = re.compile(rf"(?<![\w.-]){MARKER}(?![\w.-])")
CODE_MARKER = re.compile(rf"(?:\A|[\s/'\"=:(,]){MARKER}(?:/|['\"])")
PREFILTER = re.compile("|".join(_LITERAL + [rf"{s}\b" for s in _SUFFIX]))
MARKER_LIST = ", ".join(f"{m}/" for m in MARKERS[:-1]) + f" or {MARKERS[-1]}/"
PY = r"(?:i?python|pypy)[0-9.]*"
PYTHON = re.compile(PY)
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "source", "."}
RUNNERS = {
    "make", "gmake", "cmake", "ninja", "meson", "just", "npm", "npx", "pnpm", "yarn", "cargo", "go",
    "pip", "pip3", "pytest", "py.test", "tox", "nox", "uv", "uvx", "poetry", "pdm", "hatch", "coverage",
    "gradle", "mvn", "bundle", "rake", "composer", "node", "deno", "bun", "ruby", "perl", "php", "Rscript",
}  # fmt: skip
CODE_FLAGS = {
    "node": {"-e", "--eval", "-p", "--print"}, "bun": {"-e", "--eval", "-p", "--print"}, "deno": {"eval"},
    "perl": {"-e", "-E"}, "ruby": {"-e"}, "php": {"-r"}, "Rscript": {"-e"},
}  # fmt: skip
STDIN_ARGS = {"-", "/dev/stdin", "run"}
ENV_PATHS = {
    "PYTHONPATH",
    "NODE_PATH",
    "PATH",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "PERL5LIB",
    "RUBYLIB",
}
SKIP_FLAG = re.compile(
    r"--(?:ignore|exclude|out)[\w-]*|--deselect|--target-dir|-o|-mod"
)
ASSIGN = re.compile(r"([A-Za-z_]\w*)=(.*)", re.S)
LOAD = re.compile(
    r"sys\.path|PYTHONPATH|NODE_PATH|\brunpy\b|\bexec(?:file)?\s*\(|\beval\s*\(|\bsubprocess\b|__import__"
    r"|\bos\.(?:system|exec\w*|spawn\w*|popen)|child_process|\b(?:execSync|spawnSync|execFileSync)\b|importlib"
    r"|\bimport\s*[('\"]|\bfrom\s*['\"]|\bCDLL\b|cdll\.|dlopen"
    r"|(?<![.\w])(?:require|require_relative|require_once|include|include_once|load|do|system)\s*[('\"]"
)
PY_IMPORT = re.compile(rf"^\s*(?:from|import)\s+{MARKER}\b", re.M)
PY_LOADER = re.compile(
    r"sys\.path\b|\b(?:exec|eval|execfile|__import__)$|runpy|subprocess|\bos\.(?:system|exec\w*|spawn\w*|popen)"
    r"|importlib|load_source|CDLL|cdll|dlopen|environ|addsitedir|^(?:run|call|check_call|check_output|Popen|system)$"
)
PATH_STR = re.compile(rf"(?:\A|[\s/'\"=:(,]){MARKER}(?:/|\Z)")
HDOC = re.compile(r"<<(-?)[ \t]*(['\"]?)([A-Za-z0-9_]+)\2")
HDOC_TOKEN = re.compile(r"__HDOC(\d+)__")
PATHISH = re.compile(r"[\w.~*?\[\]/-]+")
VARREF = re.compile(r"\$\{?([A-Za-z_]\w*|[0-9@*#])")
GREPS = {"grep", "egrep", "fgrep", "rg"}
UV_VALUE_FLAGS = {
    "--project", "--directory", "--with", "--with-requirements", "--python", "-p", "--group", "-w",
    "--extra", "--package", "--env-file", "--index", "--only-group", "--no-group",
}  # fmt: skip
RUNNER_RAW = re.compile(
    rf"(?<![\w.-])({PY}|"
    + "|".join(map(re.escape, sorted((SHELLS - {"source", "."}) | RUNNERS)))
    + r")(?![\w.-])"
)
SOURCE_RAW = re.compile(
    r"(?:^|[;&|({]|\b(?:then|do|else)\b)[ \t]*(?:source|\.)[ \t]", re.M
)
MAX_READ = 1_000_000
CONFIG = Path(".claude") / "upstream-exec.json"


def has_marker(path: str) -> bool:
    """Absolute path: marker components count below the outermost `.git`-holding ancestor; quarantine anywhere."""
    parts = Path(path).parts
    floor = next(
        (
            k
            for k in range(1, len(parts) + 1)
            if os.path.exists(os.path.join(*parts[:k], ".git"))
        ),
        0,
    )
    return any(
        c == "quarantine" or (k >= floor and MARKER_PART.fullmatch(c))
        for k, c in enumerate(parts)
    )


class Config:
    def __init__(self, root: Path, data: dict) -> None:
        names = data.get("names")
        if not (isinstance(names, list) and all(isinstance(n, str) for n in names)):
            names = []
        names = [re.escape(n) for n in names if n]
        self.names = re.compile("|".join(names)) if names else None
        sandbox = data.get("sandbox")
        self.sandbox = (
            os.path.realpath(root / sandbox)
            if isinstance(sandbox, str) and sandbox
            else None
        )
        if self.sandbox and has_marker(self.sandbox):
            self.sandbox = None
        stem = Path(self.sandbox).stem if self.sandbox else None
        self.sandboxed_file = (
            re.compile(
                rf"^\s*(import {re.escape(stem)}\b|from {re.escape(stem)} import)",
                re.MULTILINE,
            )
            if stem
            else None
        )


def load_config(cwd: str) -> Config | None:
    """`.claude/upstream-exec.json` at the nearest `.git` root; None outside a repo, in a marker dir, or on any error."""
    if has_marker(cwd):
        return None
    for d in (Path(cwd), *Path(cwd).parents):
        if (d / ".git").exists():
            try:
                data = json.loads((d / CONFIG).read_text())
                return Config(d, data) if isinstance(data, dict) else None
            except (OSError, ValueError):
                return None
    return None


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(filename)
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Info:
    def __init__(self, text, st, hdocs, ins, env) -> None:
        self.text, self.st, self.hdocs, self.ins, self.env = text, st, hdocs, ins, env


class Gate:
    def __init__(self, raw: str, cwd: str, cfg: Config | None) -> None:
        self.fq = _load("fqg", "fetch-quarantine-gate.py")
        self.p = self.fq._load_parser()
        self.tok = self.p.CMDSUB_TOKEN
        self.ctx = self.fq.Ctx(raw, cwd, [], [], self.p)
        self.raw, self.origin, self.cfg = raw, cwd, cfg
        self.hdocs: list[str] = []

    def marked(self, path: str, cwd: str) -> bool:
        if not path or "$" in path or self.tok in path:
            return False
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            if cwd == self.fq.UNRESOLVED:
                return False
            path = os.path.join(cwd, path)
        return has_marker(os.path.normpath(path)) or has_marker(os.path.realpath(path))

    def names_in(self, text: str) -> bool:
        return bool(self.cfg and self.cfg.names and self.cfg.names.search(text))

    def is_sandbox(self, path: str, cwd: str) -> bool:
        if not (self.cfg and self.cfg.sandbox) or cwd == self.fq.UNRESOLVED:
            return False
        return (
            os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
            == self.cfg.sandbox
        )

    def marker_path_in(self, text: str) -> bool:
        """A marker-dir token that exists (relative to the origin cwd), has a file extension, or is a glob."""
        for tok in PATHISH.findall(text):
            comps = tok.split("/")
            k = next((k for k, c in enumerate(comps) if MARKER_PART.fullmatch(c)), None)
            if k is None:
                continue
            if re.search(r"[\w-]\.[A-Za-z]\w*$", comps[-1]) or re.search(
                r"[*?\[]", tok
            ):
                return True
            for cand in (tok, "/".join(comps[k:])):
                if os.path.exists(os.path.join(self.origin, os.path.expanduser(cand))):
                    return True
        return False

    def fallback(
        self, text: str, subs: list[str], dynamic: str, raw_too: bool
    ) -> str | None:
        """Unresolved cwd/arg: scan the stage, its pipeline's subs and the referenced vars' sources."""
        parts = [text, *subs]
        refs = set(VARREF.findall(dynamic))
        if raw_too or any(not re.fullmatch(r"[A-Za-z_]\w*", r) for r in refs):
            parts.append(self.raw)
        else:
            for r in refs:
                for m in re.finditer(
                    rf"(?<![\w$]){r}=(\S*)|\bfor\s+{r}\s+in\s+([^;\n]*)", self.raw
                ):
                    val = m.group(1) or m.group(2) or ""
                    parts.append(self.raw if "$(" in val or "`" in val else val)
        blob = "\n".join(parts)
        if self.marker_path_in(blob) or self.names_in(blob):
            return "a runner on an unresolved path or cwd, with foreign code in play"
        return None

    def code_reason(
        self, code: str, cwd: str, what: str, py: bool = False
    ) -> str | None:
        if self.names_in(code):
            return f"{what} names upstream code"
        hit = self._py_hit(code, cwd) if py else None
        if hit is None:
            hit = any(
                LOAD.search(ln) and CODE_MARKER.search(ln) for ln in code.splitlines()
            ) or any(
                self._marker_dir(m.group(1), cwd) for m in PY_IMPORT.finditer(code)
            )
        return f"{what} loads or runs foreign code" if hit else None

    def _marker_dir(self, name: str, cwd: str) -> bool:
        return (
            bool(MARKER_PART.fullmatch(name))
            and cwd != self.fq.UNRESOLVED
            and os.path.isdir(os.path.join(cwd, name))
        )

    def _py_hit(self, code: str, cwd: str) -> bool | None:
        """Python: a marker-path string (or a name, when one exists) inside a load/exec call; None if unparsable."""
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError):
            return None
        any_marker = any(
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and PATH_STR.search(n.value)
            for n in ast.walk(tree)
        )
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                if any(self._marker_dir(m.split(".")[0], cwd) for m in mods):
                    return True
            if isinstance(node, ast.Call):
                target, values = (
                    ast.unparse(node.func),
                    [*node.args, *(k.value for k in node.keywords)],
                )
            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                target, values = " ".join(map(ast.unparse, targets)), [node.value]
            else:
                continue
            if not PY_LOADER.search(target):
                continue
            for n in (n for v in values for n in ast.walk(v)):
                if (
                    isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and PATH_STR.search(n.value)
                ):
                    return True
                if isinstance(n, ast.Name) and any_marker:
                    return True
        return False

    def build_reason(self, name: str, args: list[str], cwd: str) -> str | None:
        if self.marked(cwd, cwd):
            return f"`{name}` runs inside {cwd}"
        if name == "go" and args[:2] == ["mod", "vendor"]:
            return None
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a.startswith("-"):
                flag, eq, val = a.partition("=")
                if SKIP_FLAG.fullmatch(flag):
                    skip = not eq
                    continue
                if eq:
                    a = val
                elif re.match(r"-[A-Za-z][^-]", a) and "/" in a:
                    a = a[2:]
                else:
                    continue
            elif ASSIGN.fullmatch(a):
                continue
            a = a.split("::", 1)[0]
            if ("/" in a or os.path.exists(os.path.join(cwd, a))) and self.marked(
                a, cwd
            ):
                return f"`{name}` on {a}"
        return None

    def python_file(self, path: str, cwd: str) -> str | None:
        if self.is_sandbox(path, cwd):
            return None
        if self.marked(path, cwd):
            return f"python runs {path}"
        if not (self.cfg and self.cfg.names) or cwd == self.fq.UNRESOLVED:
            return None
        f = Path(cwd) / os.path.expanduser(path)
        try:
            if not f.is_file() or f.stat().st_size > MAX_READ:
                return None
            text = f.read_text(errors="replace")
        except OSError:
            return None
        sandboxed = self.cfg.sandboxed_file and self.cfg.sandboxed_file.search(text)
        return (
            f"python script {path} names upstream code"
            if self.names_in(text) and not sandboxed
            else None
        )

    def python(self, args: list[str], cwd: str) -> tuple[str | None, bool]:
        """(reason, reads code from stdin)."""
        while args:
            a = args.pop(0)
            if a == "-":
                break
            if a in ("--version", "--help"):
                return None, False
            if a == "--":
                if args:
                    a = args[0]
                    return (
                        (None, True)
                        if a in ("/dev/stdin", self.tok)
                        else (self.python_file(a, cwd), False)
                    )
                break
            if a.startswith("--"):
                continue
            if not a.startswith("-"):
                return (
                    (None, True)
                    if a in ("/dev/stdin", self.tok)
                    else (self.python_file(a, cwd), False)
                )
            for k, ch in enumerate(a[1:], 2):
                if ch in "Vh?":
                    return None, False
                if ch in "cmWX":
                    val = a[k:] or (args.pop(0) if args else "")
                    if ch == "c":
                        if self.marked(cwd, cwd):
                            return f"python -c inside {cwd}", False
                        return self.code_reason(
                            val, cwd, "python -c code", py=True
                        ), False
                    if ch == "m":
                        return self.module_reason(val, args, cwd), False
                    break
        return None, True

    def module_reason(self, mod: str, args: list[str], cwd: str) -> str | None:
        if self.names_in(mod):
            return f"python -m {mod} is upstream code"
        head = mod.split(".")[0]
        if (
            MARKER_PART.fullmatch(head)
            and cwd != self.fq.UNRESOLVED
            and os.path.isdir(os.path.join(cwd, head))
        ):
            return f"python -m {mod}"
        return self.build_reason(f"python -m {mod}", args, cwd)

    def shell(self, name: str, args: list[str], cwd: str) -> tuple[str | None, bool]:
        if name in ("source", "."):
            return self.build_reason(name, args, cwd), False
        i, stdin = 0, False
        while i < len(args):
            a = args[i]
            if a in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file"):
                i += 2
                continue
            if a == "--":
                i += 1
                break
            if re.fullmatch(r"[-+][A-Za-z]+", a):
                stdin = stdin or (a[0] == "-" and "s" in a)
            elif not a.startswith("--"):
                break
            i += 1
        script = args[i] if i < len(args) else None
        stdin = stdin or script in (None, "-", "/dev/stdin", self.tok)
        return self.build_reason(name, args, cwd), stdin

    def code_runner(
        self, name: str, args: list[str], cwd: str
    ) -> tuple[str | None, bool]:
        rest, code, pos = [], [], []
        it = iter(args)
        for a in it:
            if a in CODE_FLAGS[name]:
                code.append(next(it, ""))
                continue
            rest.append(a)
            if not a.startswith("-") or a == "-":
                pos.append(a)
        for c in code:
            reason = self.code_reason(c, cwd, f"`{name}` code")
            if reason:
                return reason, False
        stdin = not code and all(p in STDIN_ARGS or p == self.tok for p in pos)
        return self.build_reason(name, rest, cwd), stdin

    def stdin_reason(
        self, info: Info, feeders: list[Info], lang: str, depth: int
    ) -> str | None:
        cwd = info.st.cwd
        if self.marked(cwd, cwd):
            return f"stdin code runs inside {cwd}"
        for code in info.hdocs + [c for f in feeders for c in f.hdocs]:
            if lang == "sh":
                reason = self.walk(code, cwd, depth + 1)
            else:
                reason = self.code_reason(code, cwd, "stdin code", py=lang == "py")
            if reason:
                return reason
        for t in info.ins:
            if self.marked(t, cwd):
                return f"stdin from {t}"
        for f in feeders:
            for a in f.st.argv[1:] + f.ins:
                fcwd = f.st.cwd
                if (
                    not a.startswith("-")
                    and self.marked(a, fcwd)
                    and os.path.exists(os.path.join(fcwd, a))
                ):
                    return f"stdin from {a}"
        return None

    def xargs_reason(self, name: str, feeders: list[Info]) -> str | None:
        for f in feeders:
            text = f.text
            if f.st.name in GREPS and any(
                a == "--invert-match" or re.fullmatch(r"-[A-Za-z]*v[A-Za-z]*", a)
                for a in f.st.argv[1:]
            ):
                text = " ".join(_grep_files(f.st.argv))
            if MARKER_WORD.search(text):
                return f"xargs feeds `{name}` with foreign code in play"
        return None

    def stage_reason(
        self, info: Info, feeders: list[Info], subs: list[str], depth: int
    ) -> str | None:
        st = info.st
        argv, cwd = list(st.argv), st.cwd
        while argv[:2] == ["uv", "run"]:
            argv = argv[2:]
            if self.marked(cwd, cwd):
                return f"`uv run` inside {cwd}"
            while argv and argv[0].startswith("-"):
                flag = argv.pop(0)
                if flag == "--":
                    break
                if flag in UV_VALUE_FLAGS and argv:
                    val = argv.pop(0)
                    if flag in ("--project", "--directory") and self.marked(val, cwd):
                        return f"`uv run {flag}` {val}"
        if not argv:
            return None
        prog = argv[0]
        name = os.path.basename(prog)
        if "/" in prog and not self.is_sandbox(prog, cwd) and self.marked(prog, cwd):
            return f"runs {prog}"
        dynamic = "$" in prog or self.tok in prog
        runner = (
            PYTHON.fullmatch(name)
            or name.endswith(".py")
            or name in SHELLS
            or name in RUNNERS
        )
        if not (runner or dynamic):
            return None
        unresolved = [a for a in argv + info.ins if "$" in a or self.tok in a]
        if cwd == self.fq.UNRESOLVED or unresolved:
            reason = self.fallback(
                info.text, subs, " ".join(unresolved), cwd == self.fq.UNRESOLVED
            )
            if reason or dynamic:
                return reason
        if st.xargs:
            reason = self.xargs_reason(name, feeders)
            if reason:
                return reason
        if name.endswith(".py"):
            return self.python_file(prog, cwd)
        if PYTHON.fullmatch(name):
            reason, stdin = self.python(argv[1:], cwd)
        elif name in SHELLS:
            reason, stdin = self.shell(name, argv[1:], cwd)
        elif name in CODE_FLAGS:
            reason, stdin = self.code_runner(name, argv[1:], cwd)
        else:
            return self.build_reason(name, argv[1:], cwd)
        if reason or not stdin or st.xargs:
            return reason
        lang = "sh" if name in SHELLS else "py" if PYTHON.fullmatch(name) else ""
        return self.stdin_reason(info, feeders, lang, depth)

    def env_reason(self, words: list[str], cwd: str) -> str | None:
        for w in words:
            m = ASSIGN.fullmatch(w)
            if (
                m
                and m.group(1) in ENV_PATHS
                and any(self.marked(v, cwd) for v in m.group(2).split(":"))
            ):
                return f"{m.group(1)} points into {m.group(2)}"
        return None

    def walk(self, text: str, cwd: str, depth: int = 0) -> str | None:
        if depth > self.fq.MAX_DEPTH:
            raise self.p.ParseFailure("nesting too deep")
        for is_sub, chunk, _ in self.fq._subshells(text) or [(False, text, "")]:
            if is_sub:
                reason = self.walk(chunk, cwd, depth + 1)
            else:
                reason, cwd = self._walk_flat(chunk, cwd, depth)
            if reason:
                return reason
        return None

    def _walk_flat(self, text: str, cwd: str, depth: int) -> tuple[str | None, str]:
        pipelines, subs = self.p.split_pipelines(self._heredocs(text))
        counts = [sum(s.count(self.tok) for s in pl) for pl in pipelines]
        aligned, k = sum(counts) == len(subs), 0
        seen = {cwd}
        for pipeline, n in zip(pipelines, counts):
            psubs = subs[k : k + n] if aligned else subs
            k += n
            infos = [self._info(s, cwd) for s in pipeline]
            for idx, info in enumerate(infos):
                reason = info.env
                for nested in info.st.nested:
                    if reason:
                        break
                    if "$" in nested or self.tok in nested:
                        reason = self.fallback(info.text, psubs, nested, False)
                    reason = reason or self.walk(nested, info.st.cwd, depth + 1)
                reason = reason or self.stage_reason(info, infos[:idx], psubs, depth)
                if reason:
                    return reason, cwd
            if len(infos) == 1 and infos[0].st.name in ("cd", "pushd", "popd"):
                cwd = self.fq._cd(infos[0].st, self.ctx)
                seen.add(cwd)
        for sub in subs:
            for c in seen:
                reason = self.walk(sub, c, depth + 1)
                if reason:
                    return reason, cwd
        return None, cwd

    def _info(self, text: str, cwd: str) -> Info:
        try:
            toks = shlex.split(text, posix=True)
        except ValueError as e:
            raise self.p.ParseFailure(str(e)) from e
        argv, outs, ins, hdocs = [], [], [], []
        i = 0
        while i < len(toks):
            m = self.fq.REDIRECT.fullmatch(toks[i])
            h = HDOC_TOKEN.fullmatch(toks[i])
            if h and int(h.group(1)) < len(self.hdocs):
                hdocs.append(self.hdocs[int(h.group(1))])
            elif m:
                op, target = m.group(2), m.group(3)
                if not target and op not in (">&", "<&") and i + 1 < len(toks):
                    i += 1
                    target = toks[i]
                if ">" in op and m.group(1) in ("", "1", "&") and target:
                    outs.append(target)
                elif op == "<" and target:
                    ins.append(target)
                elif op == "<<<":
                    hdocs.append(target)
            else:
                argv.append(toks[i])
            i += 1
        st = self.fq.unwrap(argv, cwd, self.ctx, outs)
        env = argv[: len(argv) - len(st.argv)] if st.argv else argv
        if st.name == "export":
            env = env + st.argv[1:]
        return Info(text, st, hdocs, ins, self.env_reason(env, cwd))

    def _heredocs(self, text: str) -> str:
        """Tag each heredoc `<<DELIM` with ` __HDOC<n>__ ` (n indexes self.hdocs) so its body follows its stage."""
        out: list[str] = []
        pending: list[tuple[int, str, bool]] = []
        i, n, quote = 0, len(text), ""
        while i < n:
            c = text[i]
            if quote == "'":
                quote = "" if c == "'" else quote
            elif c == "\\":
                out.append(text[i : i + 2])
                i += 2
                continue
            elif quote == '"':
                quote = "" if c == '"' else quote
            elif c in "'\"":
                quote = c
            elif c == "#" and (i == 0 or text[i - 1] in " \t\n;&|("):
                eol = text.find("\n", i)
                eol = n if eol < 0 else eol
                out.append(text[i:eol])
                i = eol
                continue
            elif text.startswith("<<<", i):
                out.append("<<<")
                i += 3
                continue
            elif m := HDOC.match(text, i):
                pending.append((len(self.hdocs), m.group(3), bool(m.group(1))))
                self.hdocs.append("")
                out.append(f"{m.group(0)} __HDOC{pending[-1][0]}__ ")
                i = m.end()
                continue
            elif c == "\n" and pending:
                out.append(c)
                i += 1
                for idx, delim, strip in pending:
                    body = []
                    while i < n:
                        eol = text.find("\n", i)
                        eol = n if eol < 0 else eol
                        line = text[i:eol]
                        out.append(text[i : eol + 1])
                        i = eol + 1
                        if (line.lstrip("\t") if strip else line) == delim:
                            break
                        body.append(line.lstrip("\t") if strip else line)
                    self.hdocs[idx] = "\n".join(body)
                pending = []
                continue
            out.append(c)
            i += 1
        return "".join(out)

    def raw_reason(self, cwd: str) -> str | None:
        if not (RUNNER_RAW.search(self.raw) or SOURCE_RAW.search(self.raw)):
            return None
        if (
            self.marked(cwd, cwd)
            or self.marker_path_in(self.raw)
            or self.names_in(self.raw)
        ):
            return "a runner the parser can't follow, with foreign code in play"
        return None


def _grep_files(argv: list[str]) -> list[str]:
    """grep's file operands (pattern args dropped)."""
    out, it, have_pattern = [], iter(argv[1:]), False
    for a in it:
        if a in ("-e", "--regexp", "-f", "--file"):
            next(it, None)
            have_pattern = True
        elif a.startswith("-"):
            continue
        elif not have_pattern:
            have_pattern = True
        else:
            out.append(a)
    return out


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = os.path.realpath(payload.get("cwd") or os.getcwd())
    cfg = load_config(cwd)
    # Line continuations, quotes and backslashes stripped first: walk() sees shlex words, so ven""dor/x must still trip the prefilter.
    if cfg is None and not PREFILTER.search(re.sub(r"\\\n|[\"'\\]", "", command)) and not has_marker(cwd):
        return 0
    gate = Gate(command, cwd, cfg)
    try:
        reason = gate.walk(command, cwd)
    except (gate.p.ParseFailure, RecursionError):
        reason = gate.raw_reason(cwd)
    if not reason:
        return 0
    sys.stderr.write(
        f"upstream-exec-gate BLOCKED: {reason}. Nothing ran. Code under {MARKER_LIST} "
        "runs only through its reviewed sandbox entry (the project's `sandbox` in "
        ".claude/upstream-exec.json) or `devc-untrusted` in the quarantine dir; read/grep it freely. Do NOT retry "
        "variants — if nothing foreign actually runs, ask the user to run it. Playbook: ~/.claude/hooks/README.md\n"
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
