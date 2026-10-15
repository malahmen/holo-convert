"""The shell semantics the bash engine relies on, made explicit.

Each function here reproduces one construct of the bash engine this replaced
(v1.0.0) exactly - `cd dir && pwd`, `basename x .md`, `$(...)` stripping
trailing newlines, a sed address range, awk's record handling - because the
golden harness holds the output to that engine's, byte for byte.
"""
import os
import shutil
import subprocess


def which(name: str) -> bool:
    return shutil.which(name) is not None


def run(cmd, **kw) -> int:
    """Run with the terminal attached; the exit status (127 if missing)."""
    try:
        return subprocess.call(cmd, **kw)
    except FileNotFoundError:
        return 127


def capture(cmd, **kw):
    """`$(cmd)`: stdout with trailing newlines stripped; None if it failed."""
    kw.setdefault("stderr", subprocess.PIPE)
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, **kw)
    except (FileNotFoundError, PermissionError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.rstrip("\n")


def subst(text: str) -> str:
    """What `$(...)` does to output: trailing newlines removed."""
    return text.rstrip("\n")


def logical_dir(path: str):
    """`(cd path && pwd)`: the logical absolute path, symlinks NOT resolved
    (bash's pwd reads $PWD). None when the directory cannot be entered."""
    target = path or "."
    if not os.path.isdir(target):
        return None
    base = os.environ.get("PWD")
    if not base or not os.path.isabs(base) or not os.path.samefile(base, os.getcwd()):
        base = os.getcwd()
    joined = target if os.path.isabs(target) else os.path.join(base, target)
    return os.path.normpath(joined)


def dirname(path: str) -> str:
    """`dirname path`."""
    p = path.rstrip("/") or "/"
    if "/" not in p:
        return "."
    d = p.rsplit("/", 1)[0].rstrip("/")
    return d or "/"


def basename(path: str, suffix: str = "") -> str:
    """`basename path [suffix]`: the suffix is removed unless it is the whole name."""
    p = path.rstrip("/")
    b = p.rsplit("/", 1)[-1] if p else "/"
    if suffix and b.endswith(suffix) and b != suffix:
        b = b[: -len(suffix)]
    return b


def strip_suffix(s: str, suffix: str) -> str:
    """`${s%suffix}` for a literal suffix."""
    return s[: -len(suffix)] if suffix and s.endswith(suffix) else s


def expand_tilde(s: str) -> str:
    """`${s/#\\~/$HOME}`: a leading ~ only."""
    return os.environ.get("HOME", "") + s[1:] if s.startswith("~") else s


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
        return fh.read()


def write_shared(path: str, text: str) -> None:
    """write(), atomically: into a temporary file beside it, then renamed over
    it. For the ./.fcc/ files every run regenerates (monofont.tex,
    fallback.tex): two runs in one folder would otherwise each truncate the
    file while the other's LaTeX is reading it."""
    import tempfile
    fd, part = tempfile.mkstemp(prefix=".", suffix=".part", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(text)
        os.chmod(part, 0o644)
        os.replace(part, path)
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        fh.write(text)


# --- sed and awk ------------------------------------------------------------------

def sed_lines(text: str):
    """sed's view of a file: (lines, final newline?). A missing final newline
    is kept missing on output, as GNU sed does."""
    if text == "":
        return [], True
    has_nl = text.endswith("\n")
    lines = text.split("\n")
    if has_nl:
        lines = lines[:-1]
    return lines, has_nl


def sed_join(lines, has_nl: bool) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + ("\n" if has_nl else "")


def outside_fences(text: str, fn) -> str:
    """sed '/^```/,/^```/!<cmd>': apply fn to every line OUTSIDE a fence range.

    A range starts on a line beginning with ``` and ends on the NEXT such line
    (inclusive); an unclosed range runs to the end of the file.
    """
    lines, has_nl = sed_lines(text)
    out, in_range = [], False
    for line in lines:
        if in_range:
            out.append(line)
            if line.startswith("```"):
                in_range = False
        elif line.startswith("```"):
            in_range = True
            out.append(line)
        else:
            out.append(fn(line))
    return sed_join(out, has_nl)


def awk_records(text: str):
    """awk's records (RS="\\n"): a final newline does not make an empty record."""
    if text == "":
        return []
    recs = text.split("\n")
    if text.endswith("\n"):
        recs = recs[:-1]
    return recs


def awk_print(records) -> str:
    """awk `print` for each record: always newline-terminated."""
    return "".join(r + "\n" for r in records)


SPACE = " \t\r\n\v\f"   # [[:space:]]


def is_rule(line: str, marks=("---",)) -> bool:
    """/^(---|...)[[:space:]]*$/"""
    for m in marks:
        if line.startswith(m) and line[len(m):].strip(SPACE) == "" and \
                all(c in SPACE for c in line[len(m):]):
            return True
    return False
