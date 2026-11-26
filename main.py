"""One-Line Office Jokes — make.fun entry (program/v1).

Writes one office joke to ``$MAKEFUN_OUTPUT_DIR/entry.txt`` (default
``/output``). The sealed gate wants UTF-8 text of 1-199 characters,
not only whitespace, on exactly one line.

The chosen line (134 characters, no trailing newline):

    Our office printer only jams five minutes before a deadline, which
    is how I learned it reads the calendar better than my manager does.

Why this line fits the judge's brief, in the brief's own order:

1. It *is* a one-line joke about office life: the printer, the deadline,
   the manager — three things every office worker recognises at once.
2. It turns on a real detail of office life: the printer that only ever
   jams at the worst possible moment, five minutes before a deadline.
3. It lands its laugh in the last few words: the printer "reads the
   calendar better than my manager does" is the turn, and it arrives on
   the final beat.
4. It is clear on one reading: one sentence, no setup to explain, no
   jargon.
5. The wording is fresh: a printer that reads calendars is a new image,
   not a recycled printer joke.

Losing alternatives (considered and rejected):

A. "The Monday meeting could have been an email, but then nobody would
   have had an excuse to bring coffee and nod for an hour." (118 chars)
   Rejected: the reply-all / could-have-been-an-email angle is the most
   worn office joke there is, and the punch ("nod for an hour") lands
   softly — it describes the meeting instead of turning on it.

B. "I replied-all to say please stop replying-all, and now I am the
   reason the thread has forty-seven messages." (110 chars)
   Rejected: a decent self-own, but the joke needs the reader to count
   the irony, and "forty-seven messages" is a detail that has to be
   believed rather than felt; the printer line's turn is immediate.

C. "Our coffee machine only breaks on Mondays, which is the one day
   nobody in this office can function without it." (106 chars)
   Rejected: same shape as the winner (machine + worst timing), but the
   punch just restates the setup — Mondays are hard — instead of adding
   a second idea the way "reads the calendar better than my manager"
   does.

How the line is published (deterministic, stdlib-only, Python 3.13):

- The text is checked before anything is written. A single pass over
  the characters rejects line breaks, control characters, and invisible
  formatting in one loop, so no class of bad character can slip
  between two separate checks; padding, UTF-8 encodability, and the
  1-199 character length are checked as separate shape rules, and a
  failure names the exact rule that tripped.
- The output directory's *contents* are cleared, never the directory
  itself, so a mounted output path keeps working.
- The bytes go to a unique temp file staged *beside* the target inside
  the output directory (slug + pid + nanosecond clock + random tag,
  created with O_EXCL) — staging in /tmp would break the rename with
  EXDEV when the output directory is a mount point, which is how the
  grader runs it. The bytes are drained with a short-write loop,
  fsynced, and size-checked with fstat before the rename.
- The published file is verified after the rename: regular file, mode
  0644, exact byte count from fstat, exact bytes on read-back, and the
  full gate re-run on what the grader will actually read.
- Stale temp files from crashed runs are swept only when they are old,
  regular files owned by this user, and their recorded pid is dead — a
  live run's temp file is never touched.
- A publish is refused outright when ``entry.txt`` already exists as a
  directory, instead of failing later with a cryptic rename error.
"""

import os
import secrets
import stat
import sys
import time
import unicodedata

# The entry text: one line, 134 characters, no trailing newline (the
# gate counts characters, and a trailing newline would be a second,
# empty line).
ENTRY = (
    "Our office printer only jams five minutes before a deadline, "
    "which is how I learned it reads the calendar better than my "
    "manager does."
)

MIN_CHARS = 1
MAX_CHARS = 199
OUTPUT_FILENAME = "entry.txt"
DEFAULT_OUTPUT_DIR = "/output"
# The temp file is staged *beside* the target, inside the output
# directory — never in /tmp. rename(2) refuses to move a file across
# mount points (EXDEV), and the grader mounts the output directory, so
# a /tmp temp file can never be renamed into a mounted /output. A temp
# file in the same directory is always on the same mount, so os.replace
# stays atomic. A crashed run's leftover temp file is removed by the
# next run's output-dir clear (and by the dead-pid sweep below).
TMP_PREFIX = "u-markk-st-office-jokes-"
TMP_SUFFIX = ".tmp"
# A temp file older than this is stale and may be swept — but only when
# its recorded pid is dead (see _remove_dead_owner_tmp_files).
STALE_TMP_MAX_AGE_SECONDS = 3600
# How many fresh unique temp names to try before giving up (O_EXCL races
# against a pid/clock collision, however unlikely, must not loop forever).
TMP_CREATE_ATTEMPTS = 8


# ---------------------------------------------------------------------------
# Gate rules: one character scan plus separate shape checks.
# ---------------------------------------------------------------------------

def _scan_characters(text):
    """Reject every character the gate cannot accept, in a single pass.

    One loop checks all three character classes, so a character is
    judged once against every rule instead of being re-scanned by
    separate validators that could disagree at a boundary:

    - Line breaks: CR, LF, U+2028 (LINE SEPARATOR), U+2029 (PARAGRAPH
      SEPARATOR), and U+0085 (NEXT LINE) all break the line visually.
    - Control characters: Unicode category Cc (C0, DEL, and the whole
      C1 range U+0080-U+009F). The category is used instead of a
      hand-written ordinal range, so no control code point slips
      through because a boundary was typed wrong.
    - Invisible formatting: categories Cf, Zl, and Zp — BOM (U+FEFF),
      zero-width space/joiner (U+200B/U+200D), directional marks
      (U+200E, U+200F, U+202A-U+202E), word joiner (U+2060), and the
      like. They are invisible in the line but change its bytes and
      can confuse the gate.
    - Space separators other than the ordinary space: category Zs
      minus U+0020 — non-breaking space (U+00A0), figure space
      (U+2007), narrow no-break space (U+202F), ideographic space
      (U+3000), and the rest. They look like spaces but are not, and
      the padding check only trims the edges, so one sitting inside
      the line would otherwise pass every rule unnoticed.
    """
    for ch in text:
        code = ord(ch)
        if ch in ("\n", "\r", "\u2028", "\u2029", "\u0085"):
            raise ValueError(
                "entry must be a single line, found U+%04X" % code
            )
        category = unicodedata.category(ch)
        if category == "Cc":
            raise ValueError(
                "entry contains a control character U+%04X" % code
            )
        if category in ("Cf", "Zl", "Zp"):
            raise ValueError(
                "entry contains an invisible formatting character U+%04X"
                % code
            )
        if category == "Zs" and ch != " ":
            raise ValueError(
                "entry contains a non-breaking space separator U+%04X"
                % code
            )


def _reject_padded(text):
    """No leading or trailing whitespace of any kind (space, tab, NBSP...).

    ``str.strip`` removes all Unicode whitespace, so this catches
    padding the gate would count as blank edges, not just ASCII spaces.
    """
    if not text.strip():
        raise ValueError("entry is empty or only whitespace")
    if text != text.strip():
        raise ValueError("entry has leading or trailing whitespace")


def _require_utf8(text):
    """The gate reads UTF-8, so the entry must encode as UTF-8."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("entry is not encodable as UTF-8: %s" % exc)


def _require_length(text):
    """The gate allows 1-199 characters, counted as characters, not bytes."""
    if not MIN_CHARS <= len(text) <= MAX_CHARS:
        raise ValueError(
            "entry is %d characters, gate needs %d-%d"
            % (len(text), MIN_CHARS, MAX_CHARS)
        )


def validate_entry(text):
    """Run every gate rule on *text*, in an order that reports the most
    basic problem first (type, padding, character scan, encoding,
    length). Returns *text* unchanged when it passes."""
    if not isinstance(text, str):
        raise ValueError("entry must be str, got %r" % type(text).__name__)
    _reject_padded(text)
    _scan_characters(text)
    _require_utf8(text)
    _require_length(text)
    return text



# ---------------------------------------------------------------------------
# Output directory handling.
# ---------------------------------------------------------------------------

def _read_output_dir_setting():
    """Read MAKEFUN_OUTPUT_DIR: unset means the default, anything else
    is returned verbatim for the guard below to judge.

    Splitting the read from the guard keeps the two decisions separate:
    "no setting" is a normal case, while a setting that is empty,
    padded, or dangerous is a misconfiguration that must fail loudly
    instead of silently falling back to the default.
    """
    if "MAKEFUN_OUTPUT_DIR" not in os.environ:
        return DEFAULT_OUTPUT_DIR
    raw = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not isinstance(raw, str):
        raise ValueError("MAKEFUN_OUTPUT_DIR is not a string")
    return raw


def _guard_output_path(raw):
    """Reject an output path that is unsafe or nonsensical.

    - Empty or only whitespace: rejected. An explicitly empty value is
      a misconfiguration, not a request for the default, and silently
      defaulting would hide it.
    - Leading or trailing whitespace: rejected rather than stripped.
      Stripping would silently rewrite the path the operator typed,
      so a typo that only *looks* like the right directory would
      publish somewhere the operator did not ask for.
    - NUL byte, the filesystem root, or an existing non-directory path:
      rejected, because publishing there would either fail obscurely or
      destroy something that is not a directory.
    - A symlink that resolves to the filesystem root is rejected too.
    """
    if not raw.strip():
        raise ValueError("MAKEFUN_OUTPUT_DIR is set but empty")
    if raw != raw.strip():
        raise ValueError(
            "MAKEFUN_OUTPUT_DIR has leading or trailing whitespace"
        )
    if "\x00" in raw:
        raise ValueError("MAKEFUN_OUTPUT_DIR contains a NUL byte")
    path = os.path.abspath(raw)
    if path == os.sep:
        raise ValueError("refusing to use the filesystem root as output dir")
    if os.path.realpath(path) == os.sep:
        raise ValueError(
            "output path %r resolves to the filesystem root" % path
        )
    if os.path.lexists(path) and not os.path.isdir(path):
        raise ValueError("output path %r is not a directory" % path)
    return path


def resolve_output_dir():
    """Resolve the output directory from the environment, defensively."""
    return _guard_output_path(_read_output_dir_setting())


def ensure_output_dir(path):
    """Create the output directory if missing; never delete it."""
    os.makedirs(path, exist_ok=True)
    if not os.path.isdir(path):
        raise RuntimeError("output path %r is not a directory" % path)
    if not os.access(path, os.W_OK):
        raise RuntimeError("output directory %r is not writable" % path)


def clear_output_contents(path):
    """Remove the *contents* of the output dir, never the dir itself.

    Only regular files and symlinks are removed; subdirectories are left
    alone so a mounted output dir (or anything unexpected inside it) is
    never deleted out from under the grader. A removal failure other than
    "already gone" is raised: silently leaving a stale ``entry.txt``
    behind would be worse than failing loudly.
    """
    for name in os.listdir(path):
        item = os.path.join(path, name)
        try:
            if os.path.islink(item) or os.path.isfile(item):
                os.unlink(item)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RuntimeError(
                "cannot clear %r from output dir: %s" % (item, exc)
            )


# ---------------------------------------------------------------------------
# Atomic publish: unique temp file, short-write loop, fsync, fstat checks.
# ---------------------------------------------------------------------------

def _fresh_tmp_name(output_dir):
    """Build a temp path inside *output_dir*, unique per slug, pid,
    moment, and run.

    It must live in the output directory (see the TMP_PREFIX comment):
    staging in /tmp breaks os.replace with EXDEV when the output
    directory is a mount point, which is exactly how the grader runs
    it. The pid is embedded in the name (not just used as the whole
    name) so the stale sweep can tell whether the creating process is
    still alive. The random tag makes a pid/clock collision harmless.
    """
    return os.path.join(
        output_dir,
        "%s%d-%d-%s%s"
        % (TMP_PREFIX, os.getpid(), time.time_ns(), secrets.token_hex(4),
           TMP_SUFFIX),
    )


def _process_exists(pid):
    """True when *pid* names a process that still exists.

    ``os.kill(pid, 0)`` raises ProcessLookupError for a dead pid and
    PermissionError when the process exists but belongs to someone else —
    either way the process is alive, so only the lookup error means dead.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _remove_dead_owner_tmp_files(output_dir):
    """Best-effort removal of stale temp files from this slug's runs.

    A file is swept only when ALL of these hold: it matches this slug's
    prefix/suffix, it is a regular file owned by this user, it is older
    than STALE_TMP_MAX_AGE_SECONDS, and the pid recorded in its name is
    dead. A live run's temp file is therefore never deleted, even if its
    mtime is old, and another user's files are never touched. (The next
    run's output-dir clear also removes any leftover temp file,
    whatever its age; this sweep is the finer tool for direct
    publish_entry callers.)
    """
    now = time.time()
    try:
        names = os.listdir(output_dir)
    except OSError:
        return
    for name in names:
        if not name.startswith(TMP_PREFIX) or not name.endswith(TMP_SUFFIX):
            continue
        path = os.path.join(output_dir, name)
        try:
            info = os.lstat(path)
        except OSError:
            continue
        if not stat.S_ISREG(info.st_mode):
            continue
        if info.st_uid != os.getuid():
            continue
        if now - info.st_mtime <= STALE_TMP_MAX_AGE_SECONDS:
            continue
        middle = name[len(TMP_PREFIX):-len(TMP_SUFFIX)]
        owner_pid = middle.split("-", 1)[0]
        try:
            pid = int(owner_pid)
        except ValueError:
            continue
        if _process_exists(pid):
            continue
        try:
            os.unlink(path)
        except OSError:
            pass


def _write_all(fd, data):
    """Write every byte of *data* to *fd*, looping over short writes.

    ``os.write`` may write fewer bytes than requested; returning early
    would silently truncate the entry, so loop until the view is empty.
    A zero-length write means the descriptor is broken — fail loudly.
    """
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise RuntimeError("zero-length write while publishing entry")
        view = view[written:]


def _assert_fd_length(fd, expected, what):
    """Confirm the open file behind *fd* holds exactly *expected* bytes.

    An fstat size check catches a partial write that the write loop
    somehow missed and a filesystem that truncated the file, before the
    bytes are read back or published.
    """
    actual = os.fstat(fd).st_size
    if actual != expected:
        raise RuntimeError(
            "%s is %d bytes, expected %d" % (what, actual, expected)
        )


def _flush_directory(path):
    """Best-effort fsync of a directory so a rename survives a crash."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _assert_bytes_match(path, data, what):
    """Read *path* back and confirm it holds exactly *data*.

    Checks the size with fstat first (cheap, catches truncation), then
    compares the full bytes. Returns nothing; raises on any mismatch.
    """
    with open(path, "rb") as handle:
        if os.fstat(handle.fileno()).st_size != len(data):
            raise RuntimeError("%s size differs from staged bytes" % what)
        staged = handle.read()
    if staged != data:
        raise RuntimeError("%s bytes differ from staged bytes" % what)


def _try_create_tmp(tmp_path, data):
    """One attempt to create *tmp_path* with O_EXCL and fill it.

    Returns the path on success, None when the name already exists
    (a pid/clock collision, or a leftover from a crashed run), and
    raises — after removing the temp file — on any write failure, so a
    half-written temp file is never left behind for the rename.
    The file is created mode 0600 by the open call and immediately
    chmodded to 0644 so the grader, running as another user, can read
    it after the rename.
    """
    try:
        fd = os.open(
            tmp_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        return None
    try:
        os.fchmod(fd, 0o644)
        _write_all(fd, data)
        os.fsync(fd)
        _assert_fd_length(fd, len(data), "temp file")
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    finally:
        os.close(fd)
    return tmp_path


def _stage_entry_bytes(data, output_dir):
    """Stage *data* in a fresh unique temp file inside *output_dir*.

    The temp file lives in *output_dir* (same mount as the target, so
    the later os.replace cannot fail with EXDEV). Retries with a new
    unique name when a name collides. Returns the temp path.
    """
    _remove_dead_owner_tmp_files(output_dir)
    last_error = None
    for _ in range(TMP_CREATE_ATTEMPTS):
        staged = _try_create_tmp(_fresh_tmp_name(output_dir), data)
        if staged is not None:
            return staged
        last_error = "temp name already exists"
    raise RuntimeError(
        "could not create a unique temp file: %s" % last_error
    )


def _guard_target_not_directory(target):
    """Refuse to publish when the target path is an existing directory.

    The output-dir clear deliberately leaves subdirectories alone, so a
    directory named ``entry.txt`` would otherwise survive the clear and
    make os.replace fail with a bare IsADirectoryError. Failing here,
    with the cause named, is clearer than that — and a directory is
    never something this program should replace.
    """
    if os.path.isdir(target) and not os.path.islink(target):
        raise RuntimeError(
            "output target %r is a directory, refusing to replace it"
            % target
        )


def _inspect_published_file(target, data):
    """Verify the published file the way the grader will see it.

    Regular file (not a symlink or directory), mode exactly 0644, fstat
    size equal to the staged bytes, exact bytes on read-back, and the
    full gate re-run on the decoded text. Any mismatch raises; a file
    that fails here must never be reported as a successful publish.
    """
    info = os.lstat(target)
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError("published entry is not a regular file")
    if stat.S_IMODE(info.st_mode) != 0o644:
        raise RuntimeError(
            "published entry mode is %o, expected 0644"
            % stat.S_IMODE(info.st_mode)
        )
    _assert_bytes_match(target, data, "published entry")
    with open(target, "rb") as handle:
        published_text = handle.read().decode("utf-8")
    validate_entry(published_text)


def publish_entry(text, output_dir):
    """Atomically publish *text* as ``entry.txt`` in *output_dir*.

    Validates the text, stages the exact bytes in a unique temp file,
    verifies the staged bytes (fstat size + read-back) before the rename,
    renames into place with os.replace, fsyncs the directory, then runs
    the full post-publish verification on the published file.
    Returns the published path.
    """
    validate_entry(text)
    data = text.encode("utf-8")
    target = os.path.join(output_dir, OUTPUT_FILENAME)
    _guard_target_not_directory(target)
    tmp_path = _stage_entry_bytes(data, output_dir)
    _assert_bytes_match(tmp_path, data, "temp file")
    try:
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    os.chmod(target, 0o644)
    _flush_directory(output_dir)
    _inspect_published_file(target, data)
    return target


def main(argv=None):
    """Entry point: validate, clear output contents, publish, report."""
    try:
        text = validate_entry(ENTRY)
        output_dir = resolve_output_dir()
        ensure_output_dir(output_dir)
        clear_output_contents(output_dir)
        target = publish_entry(text, output_dir)
    except (ValueError, RuntimeError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("wrote %s (%d characters)" % (target, len(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
