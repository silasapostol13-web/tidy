"""
tidy.cli — CLI entry point.

Usage:
    tidy                    Interactive mode
    tidy sort [PATH]        Sort files by type
    tidy dupes [PATH]       Find & remove duplicates
    tidy junk [PATH]        Find & trash junk files
    tidy rename [PATH]      Clean up messy filenames
    tidy stats [PATH]       Show folder breakdown
    tidy undo               Undo last operation
"""

import sys
import click
from pathlib import Path

from tidy import __version__
from tidy.engine import (
    scan_sort, execute_sort, scan_dupes, remove_dupes,
    scan_junk, trash_junk, scan_renames, execute_renames,
    get_stats, undo_last, format_size,
)
from tidy.ui import (
    console, print_logo, print_header, print_success, print_warn,
    print_error, print_dim, print_divider, confirm,
    sort_preview_table, dupes_table, renames_table, junk_table,
    stats_table, progress_bar,
)

DEFAULT_PATH = "~/Downloads"


def resolve_path(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        print_error(f"Path does not exist: {target}")
        sys.exit(1)
    if not target.is_dir():
        print_error(f"Not a directory: {target}")
        sys.exit(1)
    return target


# ── Interactive Mode ─────────────────────────────────────────────────────────

def interactive_mode(target: Path):
    """Main interactive flow."""
    print_logo()
    print_dim(f"Target: {target}\n")

    while True:
        print_divider()
        console.print(f"""
  [bold white]What would you like to do?[/]

  [{__import__('tidy.ui', fromlist=['PURPLE']).PURPLE}]1[/]  Sort files by type
  [{__import__('tidy.ui', fromlist=['PURPLE']).PURPLE}]2[/]  Find duplicates
  [{__import__('tidy.ui', fromlist=['PURPLE']).PURPLE}]3[/]  Clean up filenames
  [{__import__('tidy.ui', fromlist=['PURPLE']).PURPLE}]4[/]  Find junk files
  [{__import__('tidy.ui', fromlist=['PURPLE']).PURPLE}]5[/]  Folder stats
  [{__import__('tidy.ui', fromlist=['PURPLE']).PURPLE}]6[/]  Undo last action
  [{__import__('tidy.ui', fromlist=['PURPLE']).PURPLE}]q[/]  Quit
""")
        choice = console.input(f"  [#a78bfa]▸[/] ").strip().lower()

        if choice == "1":
            do_sort(target)
        elif choice == "2":
            do_dupes(target)
        elif choice == "3":
            do_rename(target)
        elif choice == "4":
            do_junk(target)
        elif choice == "5":
            do_stats(target)
        elif choice == "6":
            do_undo()
        elif choice in ("q", "quit", "exit"):
            print_dim("Bye!\n")
            break
        else:
            print_warn("Pick a number 1-6, or q to quit.")


# ── Sort ─────────────────────────────────────────────────────────────────────

def do_sort(target: Path):
    print_header("Sort files by type")

    plan = scan_sort(target)
    if plan.total_files == 0:
        print_success("Nothing to sort — already tidy!")
        return

    console.print(f"  Found [bold white]{plan.total_files}[/] files ({format_size(plan.total_size)})\n")
    sort_preview_table(plan.by_category, format_size)

    if not confirm("Move these files into folders?"):
        print_dim("Cancelled.")
        return

    with progress_bar() as prog:
        task = prog.add_task("Sorting", total=plan.total_files)

        def on_progress(done, total, name):
            prog.update(task, completed=done, description=f"Moving {name[:30]}")

        log = execute_sort(plan, on_progress=on_progress)

    ok = sum(1 for e in log if e.get("ok"))
    fail = sum(1 for e in log if not e.get("ok"))
    print_success(f"Sorted {ok} files into folders.")
    if fail:
        print_warn(f"{fail} files failed to move.")
    print_dim("Run `tidy undo` to reverse this.\n")


# ── Duplicates ───────────────────────────────────────────────────────────────

def do_dupes(target: Path):
    print_header("Find duplicates")

    with progress_bar() as prog:
        task = prog.add_task("Scanning for duplicates...", total=None)
        groups = scan_dupes(target)
        prog.update(task, completed=1, total=1)

    if not groups:
        print_success("No duplicates found!")
        return

    total_waste = sum(g.size * (len(g.files) - 1) for g in groups)
    console.print(f"  Found [bold white]{len(groups)}[/] duplicate groups ({format_size(total_waste)} wasted)\n")
    dupes_table(groups, format_size)

    if not confirm(f"Move {sum(len(g.files) - 1 for g in groups)} duplicate files to Trash folder?"):
        print_dim("Cancelled.")
        return

    log = remove_dupes(groups)
    ok = sum(1 for e in log if e.get("ok"))
    print_success(f"Moved {ok} duplicates to Trash folder.")
    print_dim("Run `tidy undo` to reverse this.\n")


# ── Rename ───────────────────────────────────────────────────────────────────

def do_rename(target: Path):
    print_header("Clean up filenames")

    renames = scan_renames(target)
    if not renames:
        print_success("All filenames look clean!")
        return

    console.print(f"  Found [bold white]{len(renames)}[/] files to rename\n")
    renames_table(renames)

    if not confirm("Rename these files?"):
        print_dim("Cancelled.")
        return

    log = execute_renames(renames)
    ok = sum(1 for e in log if e.get("ok"))
    print_success(f"Renamed {ok} files.")
    print_dim("Run `tidy undo` to reverse this.\n")


# ── Junk ─────────────────────────────────────────────────────────────────────

def do_junk(target: Path):
    print_header("Find junk files")

    junk = scan_junk(target)
    if not junk:
        print_success("No junk files found!")
        return

    total_size = sum(j.size for j in junk)
    console.print(f"  Found [bold white]{len(junk)}[/] junk files ({format_size(total_size)})\n")
    junk_table(junk, format_size)

    if not confirm("Move these to Trash folder?"):
        print_dim("Cancelled.")
        return

    log = trash_junk(junk, target)
    ok = sum(1 for e in log if e.get("ok"))
    print_success(f"Trashed {ok} junk files.")
    print_dim("Run `tidy undo` to reverse this.\n")


# ── Stats ────────────────────────────────────────────────────────────────────

def do_stats(target: Path):
    print_header("Folder stats")

    with progress_bar() as prog:
        task = prog.add_task("Analyzing...", total=None)
        stats = get_stats(target)
        prog.update(task, completed=1, total=1)

    stats_table(stats, format_size)
    console.print()


# ── Undo ─────────────────────────────────────────────────────────────────────

def do_undo():
    print_header("Undo last action")

    ok, fail, action = undo_last()
    if ok == 0 and fail == 0:
        print_dim("Nothing to undo.")
        return

    action_name = {"sort": "sort", "dedup": "duplicate removal",
                   "junk": "junk cleanup", "rename": "rename"}.get(action, action)

    if fail == 0:
        print_success(f"Reversed {action_name}: restored {ok} files.")
    else:
        print_warn(f"Restored {ok} files, {fail} failed.")


# ── CLI ──────────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.argument("path", default=DEFAULT_PATH, required=False)
@click.version_option(__version__, prog_name="tidy")
@click.pass_context
def cli(ctx, path):
    """tidy — a terminal file organizer.

    Run without a command for interactive mode.
    """
    ctx.ensure_object(dict)
    ctx.obj["path"] = path

    if ctx.invoked_subcommand is None:
        target = resolve_path(path)
        interactive_mode(target)


@cli.command()
@click.argument("path", default=DEFAULT_PATH, required=False)
def sort(path):
    """Sort files by type into folders."""
    print_logo()
    target = resolve_path(path)
    print_dim(f"Target: {target}\n")
    do_sort(target)


@cli.command()
@click.argument("path", default=DEFAULT_PATH, required=False)
def dupes(path):
    """Find and remove duplicate files."""
    print_logo()
    target = resolve_path(path)
    print_dim(f"Target: {target}\n")
    do_dupes(target)


@cli.command()
@click.argument("path", default=DEFAULT_PATH, required=False)
def rename(path):
    """Clean up messy filenames."""
    print_logo()
    target = resolve_path(path)
    print_dim(f"Target: {target}\n")
    do_rename(target)


@cli.command()
@click.argument("path", default=DEFAULT_PATH, required=False)
def junk(path):
    """Find and trash junk/temp files."""
    print_logo()
    target = resolve_path(path)
    print_dim(f"Target: {target}\n")
    do_junk(target)


@cli.command()
@click.argument("path", default=DEFAULT_PATH, required=False)
def stats(path):
    """Show folder breakdown and largest files."""
    print_logo()
    target = resolve_path(path)
    print_dim(f"Target: {target}\n")
    do_stats(target)


@cli.command()
def undo():
    """Undo the last tidy operation."""
    print_logo()
    do_undo()


def main():
    cli()


if __name__ == "__main__":
    main()
