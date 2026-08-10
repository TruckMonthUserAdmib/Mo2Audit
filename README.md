# MO2 Load Order Auditor

A read-only auditor for Mod Organizer 2 (Skyrim SE/AE and similar Bethesda
games) that checks the thing LOOT doesn't: **left-pane mod priority.**

LOOT sorts your plugin load order (the right pane) and does it well.
Nothing automatically checks whether your *mod* priority (the left pane) is
correct. That's the gap this tool fills -- the most common silently-broken
setup is generated output (FNIS, Nemesis, BodySlide, DynDOLOD) sitting at
the wrong priority and getting overwritten by the very mods it was
generated to unify. The game doesn't crash. It just quietly uses the wrong
files.

## Read-only. No network. No telemetry.

This tool never writes, modifies, or deletes anything in your MO2 install.
It makes no network calls of any kind -- no Nexus API, no update checks,
nothing. It only reads `modlist.txt`, `plugins.txt`, `loadorder.txt`,
`meta.ini` files, and plugin headers (first ~4KB only, never a full
plugin). Modders are justifiably wary of tools that touch their setups;
this one only looks.

**MO2 itself holds `modlist.txt` and `plugins.txt` in memory while running
and rewrites them on exit.** This tool only reads them, so it's safe to run
while MO2 is open -- but if a future version ever adds a write feature,
MO2 will need to be closed first.

## Install

Requires Python 3.10+. No third-party dependencies for the tool itself --
standard library only, so there's nothing to `pip install` to run it.

```
git clone <this repo>
cd mo2-audit
python -m mo2audit --mo2 "C:\Games\MO2" --profile "Default"
```

(`pytest` is only needed if you want to run the test suite -- see
[Development](#development).)

## Usage

```
python -m mo2audit --mo2 "C:\Games\MO2" --profile "Default"
python -m mo2audit --profile-dir "C:\Games\MO2\profiles\Default"
python -m mo2audit --mo2 ... --profile ... --json findings.json --markdown report.md
python -m mo2audit --mo2 ... --profile ... --only OVERWRITE_GENERATED_OUTPUT
python -m mo2audit --profile-dir ... --skip LOOSE_FILE_CONFLICT --explain
python -m mo2audit --list-checks
```

- `--profile-dir <path>` is the recommended way to point at your install --
  give it the profile folder directly (`<mo2_base>/profiles/<profile>/`)
  and it works out the instance base itself. `--mo2`/`--profile` (instance
  base + profile name separately) are also supported.
- If `--mo2`/`--profile-dir` is omitted, the tool makes a best-effort guess
  (checks `%LOCALAPPDATA%\ModOrganizer\` for a single unambiguous instance,
  then the current directory). If it can't confidently resolve one, it
  says so and asks for `--profile-dir` rather than guessing further.
- `--json <path>` writes the complete findings list (never capped, stable
  schema) -- this is the format a future MO2 plugin or AI layer would
  consume.
- `--markdown <path>` writes a report meant to be pasted into a forum post
  (e.g. r/skyrimmods) instead of a wall of screenshots.
- `--only CHECK_ID[,CHECK_ID...]` restricts the run to specific checks.
- `--skip CHECK_ID[,CHECK_ID...]` excludes specific checks. Composes with
  `--only` (`--only` picks the set, then `--skip` removes from it).
- Both filters validate their IDs against the live check registry. An
  unrecognized ID is a warning and the remaining valid checks still run --
  but if the filter ends up selecting *no* registered check, the tool
  errors out and exits non-zero rather than printing a clean bill of
  health for a run in which nothing was examined. Use `--list-checks` for
  the valid IDs.
- `--explain` prints each mod's classification (type, confidence, and the
  reasons behind it) before the report -- this is how you check the
  classifier's reasoning when a finding looks wrong.
- `--verbose-conflicts` shows the full per-file list for
  `LOOSE_FILE_CONFLICT` findings instead of just the aggregate count.
- `--full` shows every finding per check ID in the text report instead of
  capping at 10 (`--json` is never capped, regardless of this flag).
- `--color` enables ANSI color in the text report (off by default, since
  Windows terminal color support varies).
- Exit codes: `0` clean, `1` warnings only, `2` any critical finding.

## Checks

| Check ID | Severity | What it catches |
|---|---|---|
| `OVERWRITE_GENERATED_OUTPUT` | critical | The flagship check. A generated-output mod (FNIS/Nemesis/BodySlide/DynDOLOD/TexGen output) is outranked by a mod it must override -- most commonly XPMSE outranking FNIS/Nemesis output. |
| `MISSING_MASTER` | critical | An enabled plugin's master isn't present or isn't enabled -- a guaranteed crash on load. |
| `MASTER_ORDER` | critical | An enabled plugin's master loads *after* it instead of before. |
| `PLUGIN_LIMIT` | warning at 90%, critical at 100% | Non-ESL plugin count approaching/at the 254 ceiling, ESL-flagged count approaching/at the 4096 ceiling. Above 200 non-ESL plugins, also names plugins that are small enough (by `HEDR.numRecords`) to be considered ESL-candidates -- a heuristic suggestion only, never auto-flagged. |
| `ENABLED_MOD_NO_PLUGIN` | warning | An enabled mod ships a `.esp`/`.esm`/`.esl` on disk that isn't in `plugins.txt` -- almost always a bad FOMOD selection or an archive installed one folder level too deep. |
| `ORPHANED_PLUGIN` | warning | A plugin is listed in `plugins.txt` but no enabled mod folder contains it -- usually left over from a removed mod. |
| `PLUGIN_IN_OVERWRITE` | info | Same as above, except the plugin lives in the MO2 `overwrite/` folder -- a lesser, separate finding. **Sub-finding of `ORPHANED_PLUGIN`, not a registered check:** it isn't a valid `--only`/`--skip` target (filter on `ORPHANED_PLUGIN` instead), and `--skip ORPHANED_PLUGIN` suppresses this finding along with it. |
| `OVERWRITE_HYGIENE` | warning (substantive), info (ambiguous) | The MO2 `Overwrite` folder is holding generated content instead of it being saved as a real mod. Loose in `Overwrite` it always wins priority, which masks exactly the ordering problems `OVERWRITE_GENERATED_OUTPUT` exists to catch. Substantive output (meshes, scripts, generated data) is a warning; regenerable config is info. |
| `DISABLED_MOD_ENABLED_PLUGIN` | warning | A mod's enabled state and its plugin's enabled state disagree -- a partial toggle. |
| `MALFORMED_PLUGIN_HEADER` | warning | A plugin's TES4 header couldn't be parsed (corrupt or truncated file). |
| `LOADORDER_MISMATCH` | warning | `plugins.txt` and `loadorder.txt` disagree on the relative order of a shared entry. |
| `NO_VALID_GAME_DATA` | warning | A mod folder contains none of the recognized Data-relative entries -- almost always installed with the wrong archive root. |
| `KNOWN_ORDER_RULE` | warning | A small declarative table of uncontroversial, community-known ordering rules (e.g. an occlusion patch should outrank the mod it patches). Deliberately minimal -- this is an extension point, not an opinion engine. |
| `LOOSE_FILE_CONFLICT` | info | Aggregate report of which mod wins each loose-file conflict against which other mod(s). Not inherently a problem -- this is how MO2 is supposed to work. Pass `--verbose-conflicts` for the full per-file list. |

### Known limitation: BSA archives aren't inspected

`LOOSE_FILE_CONFLICT` and the file-overlap side of
`OVERWRITE_GENERATED_OUTPUT` only see **loose files**. Mods that ship their
entire content inside a BSA archive appear to contribute nothing to the
conflict analysis. Loose files override BSA content in Skyrim SE, so the
analysis is still directionally correct -- but a BSA-only mod's real file
contributions won't be seen. This is a Phase 1 scope limitation, not a bug.

### Files excluded from conflict analysis

The file scanner (`mo2audit/parsing/filescan.py`) skips a small, explicit
list of filenames when building the conflict index used by
`LOOSE_FILE_CONFLICT` and `OVERWRITE_GENERATED_OUTPUT`, because they are
MO2/mod-manager bookkeeping, never real game content:

| Excluded path | Why |
|---|---|
| `meta.ini` (mod folder root) | MO2's own per-mod metadata (Nexus ID, version, install file -- see `ModMeta`), never loaded into the game. If it isn't excluded, every mod that has one (nearly all of them) spuriously "conflicts" with every other mod that has one, since they all normalize to the identical literal path `meta.ini`. This produced a false critical `OVERWRITE_GENERATED_OUTPUT` finding the first time this tool ran against a real install -- see `mo2audit/parsing/filescan.py`'s `_EXCLUDED_ROOT_FILES`. |

This list is intentionally short and lives in `_EXCLUDED_ROOT_FILES` in
that file. If a real conflict ever looks like it's being swallowed, check
that constant first -- an over-broad exclusion here would hide genuine
findings, which is exactly the failure mode this table exists to make
visible rather than silent.

### Known false positive: Creation Club plugins in the game's Data folder

On Anniversary Edition builds, `ORPHANED_PLUGIN` may flag
`ccBGSSSE001-Fish.esm` and `_ResourcePack.esl`. These are Creation Club
plugins that live in the game's own `Data` folder rather than in a managed
mod folder, and they load correctly -- the check doesn't yet account for that
placement, so it reports them as orphans. The tool is read-only, so the flag
itself is harmless, but **don't follow the finding's advice to remove them
from `plugins.txt`** -- that would disable working content. A fix is planned:
`ORPHANED_PLUGIN` and `MISSING_MASTER` will adopt game-`Data` presence
semantics together.

## Development

```
python -m pip install pytest
python -m pytest -v
```

Every check function is `(Setup, SetupClassification) -> list[Finding]` and
imports only from `mo2audit/model.py` and `mo2audit/classify/types.py` --
never from `mo2audit/parsing/`, never a file path, never an MO2 API. The
dependency chain runs one way: parsing -> classify -> checks -> report. This
is enforced mechanically by `tests/test_architecture.py`, not just by
convention, so Phase 3 (a native MO2 plugin, reusing `checks/` unchanged
against a `Setup` built from the live MO2 API instead of disk) doesn't
require touching check logic.

## Roadmap

- **Phase 1** (done): the read-only standalone auditor. Validated against
  two real builds.
- **Phase 2** (done): smarter checks. A mod-classification layer (mod types,
  confidence, reasons) feeding conflict directionality, Overwrite hygiene,
  and Creation Club awareness. Still read-only, still standalone, still
  standard library only.
- **Phase 3** (not built yet): an MO2 plugin (`IPluginTool`) that builds
  `Setup` from the live `IOrganizer`/`IModList` API instead of parsing files
  from disk, with a Qt results dialog. Read-only still: it may *propose*
  priority changes, but never reorders anything itself.
- **Phase 4** (not built yet): **FORGE** -- the fix engine, where the tool
  first acts on a finding. Each finding offers ranked actions with the
  highest-confidence one marked `[Recommended]`; the user always chooses.
  Fixes requiring judgment are never applied automatically.

## License

MIT.
