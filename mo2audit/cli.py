"""CLI entry point. Orchestrates parsing/ -> checks/ -> report/. This is the
only layer that touches argparse, discovery, and process exit codes.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from mo2audit.checks import list_checks, run_all
from mo2audit.classify.classifier import classify_setup
from mo2audit.model import ModMeta, PluginEntry, Setup
from mo2audit.parsing.esp import PluginParseError, parse_plugin_header
from mo2audit.parsing.filescan import build_file_index
from mo2audit.parsing.gameconfig import read_game_config, read_overwrite_files
from mo2audit.parsing.meta import parse_meta
from mo2audit.parsing.modlist import parse_modlist
from mo2audit.parsing.plugins import parse_loadorder, parse_plugins
from mo2audit.report.crossref import cross_reference
from mo2audit.report.explain import render_explain
from mo2audit.report.json_out import render_json
from mo2audit.report.markdown import render_markdown
from mo2audit.report.text import render_text

PLUGIN_EXTENSIONS = (".esp", ".esm", ".esl")


class CliError(Exception):
    """A user-facing, non-traceback error -- path wrong, ambiguous discovery, etc."""


def build_setup(mo2_base: Path, profile: str) -> Setup:
    mo2_base = Path(mo2_base)
    profile_dir = mo2_base / "profiles" / profile
    mods_dir = mo2_base / "mods"

    mods = parse_modlist(profile_dir / "modlist.txt")
    for mod in mods:
        if not mod.is_unmanaged and not mod.is_separator:
            mod.path = mods_dir / mod.name

    file_index = build_file_index(mods)
    mod_path_by_name = {m.name: m.path for m in mods if m.path is not None}

    # basename (lower) -> (owning mod name, real on-disk path) for plugin
    # header parsing. Highest-priority contributor wins ownership when more
    # than one mod folder ships a same-named plugin file.
    owner_info: dict[str, tuple[str, Path]] = {}
    for path, contributors in file_index.items():
        if not path.endswith(PLUGIN_EXTENSIONS):
            continue
        winner = contributors[-1]
        owner_info[Path(path).name] = (winner, mod_path_by_name[winner] / path)

    raw_plugins = parse_plugins(profile_dir / "plugins.txt")
    plugins: list[PluginEntry] = []
    for filename, enabled, load_index in raw_plugins:
        owner = owner_info.get(filename.lower())
        owning_mod = owner[0] if owner else None
        plugin_path = owner[1] if owner else None

        masters: list[str] = []
        is_esm = False
        is_esl = False
        hedr_num_records = None
        parse_error = None

        if plugin_path is not None and plugin_path.is_file():
            try:
                info = parse_plugin_header(plugin_path)
            except PluginParseError as exc:
                parse_error = str(exc)
            else:
                masters = info.masters
                is_esm = info.is_esm
                is_esl = info.is_esl
                hedr_num_records = info.hedr_num_records

        plugins.append(
            PluginEntry(
                filename=filename,
                enabled=enabled,
                load_index=load_index,
                owning_mod=owning_mod,
                is_esm=is_esm,
                is_esl=is_esl,
                masters=masters,
                parse_error=parse_error,
                hedr_num_records=hedr_num_records,
            )
        )

    meta: dict[str, ModMeta] = {}
    for mod in mods:
        if mod.path is None:
            continue
        mod_meta = parse_meta(mod.path / "meta.ini")
        if mod_meta is not None:
            meta[mod.name] = mod_meta

    loadorder_path = profile_dir / "loadorder.txt"
    loadorder = parse_loadorder(loadorder_path) if loadorder_path.is_file() else []

    overwrite_files = read_overwrite_files(mo2_base)

    ccc_managed_plugins, game_data_plugins, mo2_executables = read_game_config(mo2_base)

    return Setup(
        mo2_base=mo2_base,
        profile=profile,
        mods=mods,
        plugins=plugins,
        meta=meta,
        file_index=file_index,
        loadorder=loadorder,
        overwrite_files=overwrite_files,
        ccc_managed_plugins=ccc_managed_plugins,
        game_data_plugins=game_data_plugins,
        mo2_executables=mo2_executables,
    )


def discover_mo2_base() -> Path | None:
    """Best-effort only (CLAUDE.md): returns a single unambiguous candidate,
    or None if nothing/more-than-one is found. Callers must fail with a
    readable message asking for --profile-dir rather than guessing further.
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        mo2_root = Path(local_appdata) / "ModOrganizer"
        if mo2_root.is_dir():
            candidates = [d for d in mo2_root.iterdir() if d.is_dir() and (d / "mods").is_dir() and (d / "profiles").is_dir()]
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                return None

    cwd = Path.cwd()
    if (cwd / "mods").is_dir() and (cwd / "profiles").is_dir():
        return cwd

    return None


def discover_profile(mo2_base: Path) -> str | None:
    profiles_dir = mo2_base / "profiles"
    if not profiles_dir.is_dir():
        return None
    candidates = [d.name for d in profiles_dir.iterdir() if d.is_dir()]
    return candidates[0] if len(candidates) == 1 else None


def _resolve_mo2_base_and_profile(args: argparse.Namespace) -> tuple[Path, str]:
    if args.profile_dir:
        profile_dir = Path(args.profile_dir)
        if not profile_dir.is_dir():
            raise CliError(f"--profile-dir does not exist: {profile_dir}")
        return profile_dir.parent.parent, profile_dir.name

    mo2_base = Path(args.mo2) if args.mo2 else discover_mo2_base()
    if mo2_base is None:
        raise CliError(
            "Could not determine the MO2 instance location. Pass --profile-dir "
            "(pointing at <mo2_base>/profiles/<profile>/) or --mo2 explicitly."
        )
    if not mo2_base.is_dir():
        raise CliError(f"--mo2 path does not exist: {mo2_base}")

    profile = args.profile or discover_profile(mo2_base)
    if profile is None:
        profiles_dir = mo2_base / "profiles"
        available = sorted(d.name for d in profiles_dir.iterdir() if d.is_dir()) if profiles_dir.is_dir() else []
        raise CliError(
            "Could not determine which profile to use. "
            f"Available profiles: {', '.join(available) if available else '(none found)'}. "
            "Pass --profile explicitly."
        )

    profile_dir = mo2_base / "profiles" / profile
    if not profile_dir.is_dir():
        raise CliError(f"Profile {profile!r} not found under {mo2_base / 'profiles'}")

    return mo2_base, profile


def _split_check_ids(value: str | None) -> set[str] | None:
    """None when the flag was absent; otherwise the comma-separated IDs, with
    surrounding whitespace and empty entries dropped. A flag that was passed
    but names nothing yields an empty set, not None -- the user asked to
    filter, so we must not silently fall back to running everything."""
    if value is None:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def _no_checks_selected_message(unknown: list[str]) -> str:
    lines = ["--only/--skip selected no registered checks, so no check was run."]
    if unknown:
        lines.append(f"  Unrecognized check ID(s): {', '.join(unknown)}")
    lines.append("  Nothing was audited -- this run says NOTHING about your load order.")
    lines.append("  Valid check IDs:")
    lines.extend(f"    {check_id}" for check_id in list_checks())
    return "\n".join(lines)


def _resolve_check_filter(only: set[str] | None, skip: set[str] | None) -> tuple[set[str], list[str]]:
    """Resolve --only/--skip against the live registry.

    Returns (selected check IDs, unrecognized IDs the user passed). The valid-ID
    list always comes from `list_checks()`, never a copy, so registering a new
    check updates the filter and this error message automatically.

    Unrecognized IDs are collected, not fatal: the caller warns about them and
    runs whatever valid checks remain. The one hard error is an empty selection
    -- a zero-check run must never reach the reporter, whose all-clear line
    would tell the user the load order is clean when nothing was examined
    (PHASE2-BACKLOG.md gate item b).
    """
    registered = set(list_checks())
    requested = (only or set()) | (skip or set())
    unknown = sorted(requested - registered)

    selected = registered if only is None else registered & only
    if skip:
        selected = selected - skip
    if not selected:
        raise CliError(_no_checks_selected_message(unknown))
    return selected, unknown


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mo2audit", description="Audit an MO2 install for left-pane priority and load-order problems."
    )
    parser.add_argument("--mo2", type=Path, help="Path to the MO2 instance base (contains mods/ and profiles/).")
    parser.add_argument("--profile", help="Profile name.")
    parser.add_argument(
        "--profile-dir",
        type=Path,
        help="Path directly to <mo2_base>/profiles/<profile>/. Recommended -- takes precedence over --mo2/--profile.",
    )
    parser.add_argument("--json", type=Path, help="Write the full findings list as JSON to this path.")
    parser.add_argument("--markdown", type=Path, help="Write a forum-postable Markdown report to this path.")
    parser.add_argument("--only", help="Comma-separated check IDs to run (default: all).")
    parser.add_argument("--skip", help="Comma-separated check IDs to exclude (composes with --only).")
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show each mod's classification (type, confidence, reasons) before the report.",
    )
    parser.add_argument(
        "--verbose-conflicts", action="store_true", help="Show the full per-file list for LOOSE_FILE_CONFLICT findings."
    )
    parser.add_argument("--color", action="store_true", help="Enable ANSI color in text output (off by default).")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show every finding per check ID in the text report instead of capping at 10 (--json is never capped).",
    )
    parser.add_argument("--list-checks", action="store_true", help="List all registered check IDs and exit.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.list_checks:
        for check_id in list_checks():
            print(check_id)
        return 0

    # Resolve the check filter before touching the filesystem: a typo'd ID is a
    # usage error, and there is no point scanning a 150-mod tree to report it.
    try:
        selected_checks, unknown_checks = _resolve_check_filter(
            _split_check_ids(args.only), _split_check_ids(args.skip)
        )
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if unknown_checks:
        print(
            f"Warning: ignoring unrecognized check ID(s): {', '.join(unknown_checks)}"
            " -- run --list-checks for the valid IDs.",
            file=sys.stderr,
        )

    try:
        mo2_base, profile = _resolve_mo2_base_and_profile(args)
        setup = build_setup(mo2_base, profile)
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error reading MO2 files: {exc}", file=sys.stderr)
        return 2

    classification = classify_setup(setup)
    findings = cross_reference(run_all(setup, classification, only=selected_checks))

    if args.explain:
        print(render_explain(setup.mods, classification))
    print(render_text(findings, verbose_conflicts=args.verbose_conflicts, color=args.color, full=args.full))

    if args.json:
        args.json.write_text(render_json(findings, mo2_base=str(mo2_base), profile=profile), encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(render_markdown(findings), encoding="utf-8")

    if any(f.severity == "critical" for f in findings):
        return 2
    if any(f.severity == "warning" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
