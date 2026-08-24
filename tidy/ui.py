"""
tidy.ui — Terminal output helpers using Rich.
Clean colored text, tables, progress bars, prompts.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm
from rich import box

console = Console()

# ── Colors ───────────────────────────────────────────────────────────────────

PURPLE = "#a78bfa"
DIM = "#6b7280"
GREEN = "#10b981"
RED = "#ef4444"
YELLOW = "#f59e0b"
WHITE = "#f0eef6"


# ── Logo ─────────────────────────────────────────────────────────────────────

LOGO = f"""[{PURPLE}]
  ╭───────╮
  │ ┏━━━┓ │
  │ ┃ ▫ ┃ │
  │ ┗━━━┛ │
  ╰───┬───╯
[/]"""


def print_logo():
    console.print(LOGO)
    console.print(f"  [{PURPLE} bold]t i d y[/]")
    console.print(f"  [{DIM}]file organizer[/]\n")


def print_header(text: str):
    console.print(f"\n[{PURPLE} bold]▸ {text}[/]\n")


def print_success(text: str):
    console.print(f"  [{GREEN}]✓[/] {text}")


def print_warn(text: str):
    console.print(f"  [{YELLOW}]![/] {text}")


def print_error(text: str):
    console.print(f"  [{RED}]✗[/] {text}")


def print_dim(text: str):
    console.print(f"  [{DIM}]{text}[/]")


def print_item(label: str, value: str):
    console.print(f"  [{DIM}]{label}[/]  {value}")


def confirm(prompt: str, default: bool = True) -> bool:
    return Confirm.ask(f"  [{PURPLE}]?[/] {prompt}", default=default)


def print_divider():
    console.print(f"  [{DIM}]{'─' * 50}[/]")


# ── Tables ───────────────────────────────────────────────────────────────────

def sort_preview_table(by_category: dict, format_size_fn):
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style=f"bold {PURPLE}",
        padding=(0, 2),
        pad_edge=True,
    )
    table.add_column("Folder", style="bold white")
    table.add_column("Files", justify="right", style=PURPLE)
    table.add_column("Size", justify="right", style=DIM)
    table.add_column("Examples", style=DIM, max_width=40)

    for cat, items in sorted(by_category.items()):
        count = str(len(items))
        size = format_size_fn(sum(i.size for i in items))
        names = ", ".join(i.name for i in items[:3])
        if len(items) > 3:
            names += f" (+{len(items) - 3})"
        table.add_row(cat, count, size, names)

    console.print(table)


def dupes_table(groups, format_size_fn):
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style=f"bold {PURPLE}",
        padding=(0, 2),
    )
    table.add_column("#", style=DIM, justify="right")
    table.add_column("File", style="white")
    table.add_column("Size", justify="right", style=DIM)
    table.add_column("Copies", justify="right", style=YELLOW)
    table.add_column("Locations", style=DIM, max_width=50)

    for i, g in enumerate(groups, 1):
        name = g.files[0].name
        locations = ", ".join(str(f.parent) for f in g.files)
        if len(locations) > 50:
            locations = locations[:47] + "..."
        table.add_row(
            str(i), name, format_size_fn(g.size),
            str(len(g.files)), locations,
        )

    console.print(table)


def renames_table(renames):
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style=f"bold {PURPLE}",
        padding=(0, 2),
    )
    table.add_column("Current Name", style=DIM)
    table.add_column("→", style=PURPLE, justify="center")
    table.add_column("New Name", style="bold white")

    for r in renames:
        table.add_row(r.old_name, "→", r.new_name)

    console.print(table)


def junk_table(junk, format_size_fn):
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style=f"bold {PURPLE}",
        padding=(0, 2),
    )
    table.add_column("File", style="white")
    table.add_column("Size", justify="right", style=DIM)
    table.add_column("Location", style=DIM, max_width=40)

    for item in junk[:20]:
        loc = str(item.path.parent)
        if len(loc) > 40:
            loc = "..." + loc[-37:]
        table.add_row(item.name, format_size_fn(item.size), loc)

    if len(junk) > 20:
        table.add_row(f"... and {len(junk) - 20} more", "", "")

    console.print(table)


def stats_table(stats, format_size_fn):
    console.print(f"  [bold white]{stats.total_files}[/] files  ·  [bold white]{format_size_fn(stats.total_size)}[/] total\n")

    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style=f"bold {PURPLE}",
        padding=(0, 2),
    )
    table.add_column("Type", style="bold white")
    table.add_column("Files", justify="right", style=PURPLE)
    table.add_column("Size", justify="right", style=DIM)
    table.add_column("", style=DIM, width=20)

    max_size = max((s for _, s in stats.by_category.values()), default=1)
    for cat, (count, size) in stats.by_category.items():
        bar_len = int((size / max_size) * 15) if max_size else 0
        bar = f"[{PURPLE}]{'█' * bar_len}[/][{DIM}]{'░' * (15 - bar_len)}[/]"
        table.add_row(cat, str(count), format_size_fn(size), bar)

    console.print(table)

    if stats.largest_files:
        console.print(f"\n  [{PURPLE} bold]Largest files:[/]")
        for path, size in stats.largest_files[:5]:
            name = path.name
            if len(name) > 40:
                name = name[:37] + "..."
            console.print(f"  [{DIM}]{format_size_fn(size):>10}[/]  {name}")


# ── Progress ─────────────────────────────────────────────────────────────────

def progress_bar():
    return Progress(
        SpinnerColumn(style=PURPLE),
        TextColumn("[bold white]{task.description}"),
        BarColumn(complete_style=PURPLE, finished_style=GREEN),
        TaskProgressColumn(),
        console=console,
    )
