# MO2 Load Order Auditor — Build Specification

**Status:** Phase 1 not started
**Target:** Python 3.10+, Windows, standard library only
**License intent:** MIT, public GitHub repo

---

## 0. Read this first

This document is the authoritative spec. Build Phase 1 only. Do not implement
Phase 2 or Phase 3 features unless explicitly asked — the phase boundaries exist
to keep the core logic clean.

**The single most important architectural rule:** the check logic must have zero
knowledge of file formats and zero MO2 imports. Checks take plain Python data
structures in and return findings out. Parsing is a separate layer. This is what
makes the Phase 2 MO2 plugin a wrapper rather than a rewrite.

---

## 1. Problem statement

Mod Organizer 2 users accumulate 100+ mods over months. Two independent orderings
must both be correct:

- **Left pane** — mod priority, decides which mod wins when two mods ship the
  same loose file (mesh, texture, script, animation).
- **Right pane** — plugin load order, decides which ESP's record edits win.

LOOT solves the right pane and solves it well. **Nothing automatically audits the
left pane.** That is the gap this tool fills. Most silently-broken modded installs
break there — generated output from FNIS, Nemesis, BodySlide, or DynDOLOD gets
overwritten by the very mods it was generated to unify, and the game runs without
crashing while quietly using the wrong files.

## 2. Goals

Produce a readable report identifying concrete, actionable problems in an MO2
setup, with each finding naming the specific mods involved and the specific fix.

## 3. Non-goals (Phase 1)

- Writing, modifying, or deleting **any** file. The tool is strictly read-only.
- Network calls of any kind. No Nexus API, no Anthropic API.
- Replacing LOOT. Plugin load order sorting is out of scope.
- GUI. CLI output only.
- Third-party dependencies. Standard library only, so users can run it without
  a pip install.

---

## 4. Repository layout

```
mo2audit/
    __init__.py
    parsing/
        __init__.py
        modlist.py        # modlist.txt -> list[ModEntry]
        plugins.py        # plugins.txt / loadorder.txt -> list[PluginEntry]
        meta.py           # per-mod meta.ini -> ModMeta
        esp.py            # TES4 header -> masters, ESM/ESL flags
        filescan.py       # walk mods dir -> per-mod file index
    model.py              # dataclasses, no logic
    checks/
        __init__.py       # registry, run_all()
        overwrite.py
        plugins.py
        integrity.py
        limits.py
        rules.py          # declarative known-ordering table
    report/
        __init__.py
        text.py
        json_out.py
        markdown.py
    cli.py
tests/
    fixtures/
    test_*.py
README.md
.gitignore
```

`checks/` may import from `model.py` only. If a check module ever imports from
`parsing/`, the design has been violated.

---

## 5. Input file formats

Verified against a real MO2 2.5 profile. Do not guess these; they are specified
here because getting them wrong is the most likely failure mode.

### 5.1 `modlist.txt`

Located at `<mo2_base>/profiles/<profile>/modlist.txt`.

**CRITICAL: this file is stored in REVERSE priority order.**

The first line after the header is the **highest priority** mod — the one that
appears at the **bottom** of MO2's left pane and **wins** all file conflicts. The
last line is the lowest priority. Implementers get this backwards constantly.
Reverse the list on parse and store an explicit integer `priority` where higher
means wins.

Sanity check to assert on parse: the DLC and `Unmanaged:` entries should end up
with the **lowest** priorities, because MO2 pins them to the top of the pane.

Line prefixes:

| Prefix | Meaning |
|---|---|
| `+` | Managed mod, enabled |
| `-` | Managed mod, disabled |
| `*` | Unmanaged entry — DLC, Creation Club, base game resource |

Separators are ordinary entries whose name ends in `_separator`. They are UI
organizers with no content. Parse them, mark `is_separator=True`, exclude them
from conflict analysis, but keep them in the ordering — they are useful context
when reporting a mod's position.

First line is a `#` comment. Encoding is UTF-8.

### 5.2 `plugins.txt`

Located in the same profile folder.

- One plugin filename per line, in load order, top to bottom.
- `*` prefix means enabled. **No prefix means disabled.** This is the opposite
  polarity from modlist.txt; do not unify the two parsers.
- Omits the base game masters (`Skyrim.esm`, `Update.esm`, DLC ESMs). Their
  absence is normal and must not be reported as a problem.

### 5.3 `loadorder.txt`

Same folder. Full load order **including** base game masters. No enable flags.
Use it only to cross-check `plugins.txt`; report a warning if the two disagree
on relative ordering of shared entries.

### 5.4 `meta.ini`

Located at `<mo2_base>/mods/<Mod Name>/meta.ini`. Standard INI. Useful keys in
`[General]`: `modid`, `version`, `newestVersion`, `installationFile`, `gameName`.

Absent for manually created mods (FNIS output, BodySlide output, Overwrite).
Absence is normal — do not report it.

### 5.5 Plugin headers (`.esp` / `.esm` / `.esl`)

Read the TES4 record at byte 0 to extract masters and flags. Binary layout:

```
offset  size  field
0       4     "TES4" literal
4       4     uint32  dataSize (bytes of subrecord data following the header)
8       4     uint32  flags
12      4     uint32  formID
16      4     -       version control info
20      2     uint16  internal version
22      2     -       unknown
24      ...   subrecord data begins
```

Flags: `0x00000001` = ESM (master), `0x00000200` = ESL (light).

Subrecords within the data block, repeating until `dataSize` is consumed:

```
4 bytes  subrecord type ("HEDR", "CNAM", "SNAM", "MAST", "DATA", ...)
2 bytes  uint16 size
n bytes  payload
```

Each `MAST` payload is a null-terminated master filename. Each is followed by a
`DATA` subrecord (8-byte file size) which can be skipped. Collect every `MAST`
in order — that is the master list.

Read only the first ~4 KB of each file. Never load a full plugin into memory.
Wrap all parsing in try/except; a malformed plugin should produce a finding, not
a traceback.

---

## 6. Data model (`model.py`)

Dataclasses only, no behavior.

```python
@dataclass
class ModEntry:
    name: str
    enabled: bool
    priority: int          # higher wins conflicts
    is_separator: bool
    is_unmanaged: bool
    path: Path | None

@dataclass
class ModMeta:
    nexus_mod_id: int | None
    version: str | None
    newest_version: str | None
    install_file: str | None

@dataclass
class PluginEntry:
    filename: str
    enabled: bool
    load_index: int
    owning_mod: str | None
    is_esm: bool
    is_esl: bool
    masters: list[str]

@dataclass
class Finding:
    check_id: str          # e.g. "OVERWRITE_GENERATED_OUTPUT"
    severity: str          # "critical" | "warning" | "info"
    title: str
    detail: str
    affected: list[str]    # mod or plugin names
    fix: str               # imperative, specific, actionable

@dataclass
class Setup:
    mo2_base: Path
    profile: str
    mods: list[ModEntry]
    plugins: list[PluginEntry]
    meta: dict[str, ModMeta]
    file_index: dict[str, list[str]]   # normalized rel path -> mod names, priority ascending
```

`Setup` is the only thing checks receive. Building a `Setup` by hand in a test
must be possible without touching the filesystem.

---

## 7. Phase 1 checks

Each check is a function `(Setup) -> list[Finding]`, registered in
`checks/__init__.py`. Adding a check must require no changes to the CLI.

### 7.1 `OVERWRITE_GENERATED_OUTPUT` — severity: critical

The flagship check.

Generated-output mods must sit at the highest priority, because they are built
*from* the mods they must then override. Identify them by name match
(case-insensitive substring, configurable table):

| Generator | Output mod name patterns | Must outrank |
|---|---|---|
| FNIS | `fnis output`, `fnis - output` | every mod supplying `meshes/actors/**/animations/**`, and XPMSE |
| Nemesis | `nemesis output`, `nemesis_output` | same as FNIS |
| BodySlide | `bodyslide output`, `overwrite output` | every mod supplying `meshes/actors/character/**` body or outfit meshes |
| DynDOLOD | `dyndolod output` | every mod supplying `meshes/lod/**` or `textures/lod/**` |
| TexGen | `texgen output` | same as DynDOLOD |

For each detected output mod, find every enabled mod with **higher** priority
that contributes a file the output mod also contributes. Report each as a
violation naming the specific overriding mods.

Special case worth its own sentence in the finding text: XPMSE ships its own
behavior files and *must* be overridden by FNIS/Nemesis output. If XPMSE
outranks the output mod, say so explicitly — it is the most common single cause.

Fix text should name the drag target: move the output mod to the bottom of the
left pane, then regenerate.

### 7.2 `LOOSE_FILE_CONFLICT` — severity: info

Build the full conflict map from `Setup.file_index`. For every path claimed by
more than one enabled mod, record the winner (highest priority) and the losers.

Do not emit one finding per file — that produces thousands of lines. Aggregate
per mod pair: "Mod B overrides 47 files from Mod A." Provide a `--verbose-conflicts`
flag for the full per-file listing.

Normalize paths to lowercase with forward slashes before comparing. Windows is
case-insensitive; the mod authors are not consistent.

**Known limitation to document in the README:** this only sees loose files. Mods
that ship BSA archives are not inspected in Phase 1. Loose files override BSA
content in SSE, so the analysis is still directionally correct, but a mod whose
content is entirely in a BSA will appear to contribute nothing.

### 7.3 `ENABLED_MOD_NO_PLUGIN` — severity: warning

A mod is enabled, its folder contains one or more `.esp`/`.esm`/`.esl` files,
but those filenames do not appear in `plugins.txt`. This means MO2 cannot see
them — almost always a bad FOMOD selection or an archive that installed one
directory level too deep.

Exclude mods that legitimately ship no plugin (texture replacers, SKSE DLL-only
mods, animation mods). The check is only triggered by the presence of a plugin
file on disk that is missing from the list.

### 7.4 `ORPHANED_PLUGIN` — severity: warning

The inverse: a plugin is listed in `plugins.txt` but no enabled mod folder
contains a file of that name. Usually left over from a removed mod. Check the
`Overwrite` folder before reporting — a plugin living there is a separate,
lesser finding (`PLUGIN_IN_OVERWRITE`, severity info).

### 7.5 `MISSING_MASTER` — severity: critical

For every enabled plugin, confirm every entry in its `masters` list is present
and enabled. A missing master is a guaranteed crash on load.

Also verify each master loads **before** its dependent. Report ordering
violations separately as `MASTER_ORDER` (severity: critical).

Base game masters (`Skyrim.esm`, `Update.esm`, `Dawnguard.esm`, `HearthFires.esm`,
`Dragonborn.esm`) are always present and always first — treat them as satisfied
even though they are absent from `plugins.txt`.

### 7.6 `PLUGIN_LIMIT` — severity: warning at 90%, critical at 100%

Count plugins **without** the ESL flag against a ceiling of 254. Count ESL-flagged
plugins separately against 4096. Base game masters count toward the 254.

If the regular count is above 200, additionally report which plugins are small
enough to be ESL-flagged as candidates for relief — but Phase 1 only reports the
count and names candidates by heuristic (record count from `HEDR` under 2048 and
no new-record FormIDs above the ESL range). Do not attempt to flag anything.

### 7.7 `NO_VALID_GAME_DATA` — severity: warning

A mod folder containing none of the recognized Data-relative top-level entries:
`meshes`, `textures`, `scripts`, `sound`, `music`, `interface`, `seq`, `shadersfx`,
`grass`, `lodsettings`, `dialogueviews`, `skse`, `strings`, `video`, or any
`.esp`/`.esm`/`.esl`/`.bsa` at the root.

Nearly always means the archive was installed with the wrong data directory and
the mod is doing nothing at all.

### 7.8 `KNOWN_ORDER_RULE` — severity: warning

A small declarative table in `rules.py`:

```python
ORDER_RULES = [
    ("Unofficial Skyrim Special Edition Patch", "*", "should_be_early"),
    ("*occlusion*", "JK's Skyrim", "should_load_after"),
    # ...
]
```

Start with fewer than a dozen entries covering rules that are genuinely
uncontroversial. Resist the urge to encode opinions. The table format matters
more than its initial contents — it is the extension point where community
knowledge accumulates.

### 7.9 `DISABLED_MOD_ENABLED_PLUGIN` — severity: warning

A mod is disabled in the left pane but one of its plugins is still enabled in
`plugins.txt`, or vice versa. Indicates a partial toggle.

---

## 8. Output

Default: plain text to stdout, grouped by severity, critical first. Each finding
prints title, affected mods, and fix on separate lines. Keep it under 100 columns.
No ANSI color by default; add `--color` as opt-in since Windows terminals vary.

`--json <path>` writes the full findings list. This is the interface the Phase 2
plugin and any future AI layer will consume, so it must be complete and stable —
include everything, not just what the text report shows.

`--markdown <path>` writes a report suitable for pasting into a forum post when
asking for help. This is a real use case: the report becomes the thing users
share on r/skyrimmods instead of a wall of screenshots.

Exit codes: `0` clean, `1` warnings only, `2` any critical finding.

---

## 9. CLI

```
mo2audit --mo2 "C:\Games\MO2" --profile "Default"
mo2audit --mo2 ... --profile ... --json findings.json --markdown report.md
mo2audit --mo2 ... --profile ... --only OVERWRITE_GENERATED_OUTPUT
mo2audit --list-checks
```

If `--mo2` is omitted, attempt discovery in this order and report which was used:

1. `%LOCALAPPDATA%\ModOrganizer\` — instance installs, may contain several
   game folders; if more than one, list them and exit rather than guessing.
2. Current working directory, if it contains both `mods/` and `profiles/`.

If `--profile` is omitted and exactly one profile exists, use it. Otherwise list
them and exit.

Fail with a clear message, never a traceback, when a path is wrong. The target
user is a modder, not a developer.

---

## 10. Correctness constraints

- **Read-only. No exceptions.** Open every file with mode `"r"` or `"rb"`. There
  should be no `"w"` in the codebase outside the report writers, and those only
  write to paths the user explicitly passed.
- MO2 holds `modlist.txt` and `plugins.txt` in memory while running and rewrites
  them on exit. Phase 1 never writes them, so this is safe — but the README must
  warn users that any future write feature requires MO2 to be closed.
- Never assume a file exists. Missing `meta.ini`, missing `loadorder.txt`, and
  empty mod folders are all normal states.
- Large setups have 150+ mods and 100k+ files. Build the file index in a single
  pass with `os.scandir`. Do not stat files repeatedly.

---

## 11. Testing

Fixtures live in `tests/fixtures/` as real MO2 files. A `modlist.txt`,
`plugins.txt`, and `loadorder.txt` from a genuine 150-mod Skyrim SE install are
available and should be committed as the primary fixture.

Required tests before Phase 1 is done:

- **Priority reversal.** Assert the first line of `modlist.txt` parses to the
  highest priority value and that DLC/unmanaged entries land lowest. This is the
  bug most likely to ship silently.
- Prefix polarity: `+`/`-` in modlist vs `*`/bare in plugins.
- Separators excluded from conflict analysis but present in ordering.
- TES4 parsing against a hand-built binary fixture with two `MAST` subrecords.
- ESL and ESM flag detection.
- Every check runs against a hand-constructed `Setup` with no filesystem access.
- Malformed plugin produces a finding, not an exception.

---

## 12. Definition of done, Phase 1

- Runs against a real 150-mod profile without crashing.
- Correctly identifies a deliberately mis-prioritized FNIS output.
- All checks have unit tests using synthetic `Setup` objects.
- `--json` output is complete.
- README documents install, usage, every check ID, and the BSA limitation.
- `.gitignore` covers `__pycache__`, `*.pyc`, `config.json`, `*.log`.
- No file in `checks/` imports from `parsing/`.

---

## 13. Phase 2 — MO2 plugin (do not build yet)

MO2 exposes a Python plugin API. A plugin implementing `IPluginTool` appears in
the tools menu. `IOrganizer` provides `modList()` and `pluginList()`; `IModList`
exposes priorities and can **set** them.

The Phase 2 work is a new parsing layer that produces a `Setup` from the live API
instead of from disk, plus a Qt results dialog. **Every module under `checks/`
is reused unchanged.** If Phase 2 requires editing a check, Phase 1 got the
abstraction wrong.

Phase 2 may propose and apply priority changes, but only with per-change user
approval. Never reorder autonomously.

## 14. Phase 3 — optional AI layer (do not build yet)

Consumes the `--json` output. Interprets crash logs, recommends patches for
detected mod combinations, explains findings in plain language. Strictly
optional; the rules engine must remain fully functional with no API key. User
supplies their own key, stored in `config.json`, which is gitignored from the
first commit.

---

## 15. Repo hygiene

- `.gitignore` before the first commit, including `config.json`.
- No API keys, no personal paths, no real usernames in fixtures or examples.
- README states plainly: read-only, no network, no telemetry. Modders are
  justifiably suspicious of tools that touch their setups.
- Ship v1 read-only and say so prominently. It caps both liability and support
  burden.
