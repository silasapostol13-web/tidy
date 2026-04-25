"""
tidy.app — Textual TUI for the tidy file organizer.
Run with: tidy [path]
"""

import sys
import click
from pathlib import Path
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal, Center
from textual.widgets import Static, Button, Footer, ProgressBar, DataTable, Rule
from textual.reactive import reactive
from textual.binding import Binding
from textual.theme import Theme
from textual import work

from tidy.engine import scan, execute, undo, format_size, Plan


# ── Purple Theme ──────────────────────────────────────────────────────────────

PURPLE_THEME = Theme(
    name="tidy-purple",
    primary="#7c3aed",
    secondary="#a78bfa",
    accent="#7c3aed",
    warning="#f59e0b",
    error="#ef4444",
    success="#10b981",
    background="#111111",
    surface="#1a1a2e",
    panel="#232340",
    foreground="#f0eef6",
)


# ── Mascot ────────────────────────────────────────────────────────────────────

LOGO = """\
  ╭───────╮
  │ ┏━━━┓ │
  │ ┃ ▫ ┃ │
  │ ┗━━━┛ │
  ╰───┬───╯\
"""

LOGO_BUSY = """\
  ╭───────╮
  │ ┏━━━┓ │
  │ ┃ ◌ ┃ │
  │ ┗━━━┛ │
  ╰───┬───╯\
"""

LOGO_DONE = """\
  ╭───────╮
  │ ┏━━━┓ │
  │ ┃ ✓ ┃ │
  │ ┗━━━┛ │
  ╰───┬───╯\
"""


# ── Stylesheet ────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #111111;
}

/* ── Shared ────────────────────────────────────────── */

.screen-wrap {
    width: 100%;
    height: 100%;
    align: center middle;
}

.card {
    width: 64;
    max-width: 90%;
    height: auto;
    padding: 2 4;
    background: #1a1a2e;
    border: tall #7c3aed;
}

.logo {
    text-align: center;
    color: #a78bfa;
    width: 100%;
    margin-bottom: 1;
}

.logo-busy {
    text-align: center;
    color: #f59e0b;
    width: 100%;
    margin-bottom: 1;
}

.logo-done {
    text-align: center;
    color: #10b981;
    width: 100%;
    margin-bottom: 1;
}

.title {
    text-align: center;
    text-style: bold;
    color: #f0eef6;
    width: 100%;
}

.subtitle {
    text-align: center;
    color: #8b85a0;
    width: 100%;
}

.accent-text {
    text-align: center;
    color: #a78bfa;
    width: 100%;
}

.dim-text {
    text-align: center;
    color: #5c5775;
    width: 100%;
}

Rule {
    color: #2d2b45;
    margin: 1 0;
}

.btn-row {
    align: center middle;
    width: 100%;
    height: auto;
    margin-top: 1;
}

.btn-row Button {
    margin: 0 1;
    min-width: 16;
}

Button {
    background: #7c3aed;
    color: #f0eef6;
    border: none;
}

Button:hover {
    background: #6d28d9;
}

Button.-secondary {
    background: #232340;
    color: #a78bfa;
    border: tall #3b3660;
}

Button.-secondary:hover {
    background: #2d2b55;
}

Button.-danger {
    background: #232340;
    color: #ef4444;
    border: tall #3b3660;
}

Button.-success {
    background: #10b981;
    color: #f0eef6;
}

Button.-success:hover {
    background: #059669;
}

Button.-warning {
    background: #f59e0b;
    color: #111111;
}

/* ── Preview Screen ────────────────────────────────── */

#preview-wrap {
    width: 100%;
    height: 100%;
    padding: 1 2;
}

.preview-top {
    width: 100%;
    height: auto;
    padding: 0 1;
}

.preview-top .title {
    text-align: left;
}

.preview-top .subtitle {
    text-align: left;
    margin-bottom: 1;
}

#file-table {
    height: 1fr;
    margin: 0 0 1 0;
    background: #1a1a2e;
    scrollbar-color: #7c3aed;
    scrollbar-color-hover: #a78bfa;
}

DataTable > .datatable--header {
    background: #232340;
    color: #a78bfa;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #7c3aed;
    color: #f0eef6;
}

DataTable > .datatable--even-row {
    background: #1a1a2e;
}

DataTable > .datatable--odd-row {
    background: #191930;
}

.preview-bottom {
    dock: bottom;
    width: 100%;
    height: auto;
    align: center middle;
    padding: 0 1;
}

.preview-bottom Button {
    margin: 0 1;
}

/* ── Progress ──────────────────────────────────────── */

#progress-bar {
    width: 100%;
    margin: 1 0;
}

Bar > .bar--bar {
    color: #7c3aed;
}

PercentageStatus {
    color: #a78bfa;
    text-style: bold;
}

.file-label {
    text-align: center;
    color: #5c5775;
    width: 100%;
    height: 1;
}

/* ── Step Indicator ────────────────────────────────── */

.steps {
    text-align: center;
    color: #5c5775;
    width: 100%;
    margin-bottom: 1;
}

/* ── Footer ────────────────────────────────────────── */

Footer {
    background: #1a1a2e;
}

FooterKey > .footer-key--key {
    background: #7c3aed;
    color: #f0eef6;
}

FooterKey > .footer-key--description {
    color: #8b85a0;
}
"""


# ── Home Screen ───────────────────────────────────────────────────────────────

class HomeScreen(Screen):

    BINDINGS = [
        Binding("s", "scan", "Scan"),
        Binding("u", "undo", "Undo last"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, target: Path):
        super().__init__()
        self.target = target

    def compose(self) -> ComposeResult:
        with Center(classes="screen-wrap"):
            with Vertical(classes="card"):
                yield Static(LOGO, classes="logo")
                yield Static("t i d y", classes="title")
                yield Static("clean up your downloads", classes="subtitle")
                yield Rule()
                yield Static(f"{self.target}", classes="accent-text")
                yield Static("scan → preview → organize", classes="dim-text")
                yield Rule()
                with Horizontal(classes="btn-row"):
                    yield Button("Scan", id="btn-scan")
                    yield Button("Undo Last", id="btn-undo", classes="-secondary")
                with Horizontal(classes="btn-row"):
                    yield Button("Quit", id="btn-quit", classes="-danger")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-scan":
            self.action_scan()
        elif event.button.id == "btn-undo":
            self.action_undo()
        elif event.button.id == "btn-quit":
            self.action_quit_app()

    def action_scan(self):
        plan = scan(self.target)
        if plan.total_files == 0:
            self.notify(
                "Nothing to organize — already tidy!",
                title="✓ All clean",
            )
        else:
            self.app.push_screen(PreviewScreen(plan))

    def action_undo(self):
        ok, fail = undo()
        if ok == 0 and fail == 0:
            self.notify("No operations to undo.", title="Undo")
        elif fail == 0:
            self.notify(f"Restored {ok} file{'s' if ok != 1 else ''}.", title="✓ Undone")
        else:
            self.notify(f"Restored {ok}, failed {fail}.", title="Undo", severity="warning")

    def action_quit_app(self):
        self.app.exit()


# ── Preview Screen ────────────────────────────────────────────────────────────

class PreviewScreen(Screen):

    BINDINGS = [
        Binding("enter", "confirm", "Organize"),
        Binding("escape", "go_back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, plan: Plan):
        super().__init__()
        self.plan = plan

    def compose(self) -> ComposeResult:
        with Vertical(id="preview-wrap"):
            with Vertical(classes="preview-top"):
                yield Static("scan → [bold]preview[/bold] → organize", classes="steps")
                yield Static(
                    f"Found {self.plan.total_files} files  ·  "
                    f"{format_size(self.plan.total_size)}  ·  "
                    f"{self.plan.category_count} categories",
                    classes="title",
                )
                yield Static(
                    "These files will be sorted into folders inside your Downloads.",
                    classes="subtitle",
                )
            yield DataTable(id="file-table")
            with Horizontal(classes="preview-bottom"):
                yield Button("← Back", id="btn-back", classes="-secondary")
                yield Button("Organize Now", id="btn-go", classes="-success")
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("Folder", "Count", "Size", "Files")
        table.cursor_type = "row"
        table.zebra_stripes = True

        for cat, items in sorted(self.plan.by_category.items()):
            count = len(items)
            size = format_size(sum(i.size for i in items))
            names = ", ".join(i.name for i in items[:3])
            if count > 3:
                names += f"  (+{count - 3} more)"
            table.add_row(f"  {cat}", str(count), size, names)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-back":
            self.action_go_back()
        elif event.button.id == "btn-go":
            self.action_confirm()

    def action_confirm(self):
        self.app.push_screen(ProgressScreen(self.plan))

    def action_go_back(self):
        self.app.pop_screen()

    def action_quit_app(self):
        self.app.exit()


# ── Progress Screen ───────────────────────────────────────────────────────────

class ProgressScreen(Screen):

    progress_pct = reactive(0.0)
    current_file = reactive("")
    status_text = reactive("Organizing…")

    def __init__(self, plan: Plan):
        super().__init__()
        self.plan = plan
        self.log: list[dict] = []

    def compose(self) -> ComposeResult:
        with Center(classes="screen-wrap"):
            with Vertical(classes="card"):
                yield Static("scan → preview → [bold]organize[/bold]", classes="steps")
                yield Static(LOGO_BUSY, classes="logo-busy")
                yield Static("Organizing…", classes="title", id="status")
                yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="progress-bar")
                yield Static("", classes="file-label", id="current-file")

    def on_mount(self):
        self.run_organize()

    @work(thread=True)
    def run_organize(self):
        def on_progress(done, total, name):
            self.progress_pct = (done / total) * 100 if total else 100
            self.current_file = name
            self.status_text = f"Moving file {done} of {total}…"

        self.log = execute(self.plan, on_progress=on_progress)
        self.progress_pct = 100
        self.current_file = ""
        self.status_text = "Done"
        self.app.call_from_thread(self._finish)

    def _finish(self):
        ok = sum(1 for e in self.log if e.get("ok"))
        fail = sum(1 for e in self.log if not e.get("ok"))
        self.app.switch_screen(DoneScreen(ok, fail))

    def watch_progress_pct(self, value: float):
        try:
            self.query_one("#progress-bar", ProgressBar).update(progress=value)
        except Exception:
            pass

    def watch_current_file(self, value: str):
        try:
            display = value if len(value) < 44 else value[:20] + "…" + value[-20:]
            self.query_one("#current-file", Static).update(display)
        except Exception:
            pass

    def watch_status_text(self, value: str):
        try:
            self.query_one("#status", Static).update(value)
        except Exception:
            pass


# ── Done Screen ───────────────────────────────────────────────────────────────

class DoneScreen(Screen):

    BINDINGS = [
        Binding("u", "undo_now", "Undo"),
        Binding("q", "quit_app", "Quit"),
        Binding("enter", "go_home", "Home"),
    ]

    def __init__(self, ok: int, fail: int):
        super().__init__()
        self.ok = ok
        self.fail = fail

    def compose(self) -> ComposeResult:
        with Center(classes="screen-wrap"):
            with Vertical(classes="card"):
                yield Static("scan → preview → [bold]done[/bold]", classes="steps")
                yield Static(LOGO_DONE, classes="logo-done")
                yield Static("All tidy.", classes="title")
                yield Rule()
                summary = f"{self.ok} file{'s' if self.ok != 1 else ''} organized"
                if self.fail:
                    summary += f"  ·  {self.fail} failed"
                yield Static(summary, classes="accent-text")
                yield Static("Rollback saved to ~/.tidy/", classes="dim-text")
                yield Rule()
                with Horizontal(classes="btn-row"):
                    yield Button("Undo", id="btn-undo", classes="-warning")
                    yield Button("Home", id="btn-home", classes="-secondary")
                    yield Button("Done", id="btn-quit")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-undo":
            self.action_undo_now()
        elif event.button.id == "btn-home":
            self.action_go_home()
        elif event.button.id == "btn-quit":
            self.action_quit_app()

    def action_undo_now(self):
        ok, fail = undo()
        if fail == 0:
            self.notify(f"Restored {ok} file{'s' if ok != 1 else ''}.", title="✓ Undone")
        else:
            self.notify(f"Restored {ok}, failed {fail}.", title="Undo", severity="warning")
        self.action_go_home()

    def action_go_home(self):
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_quit_app(self):
        self.app.exit()


# ── Main App ──────────────────────────────────────────────────────────────────

class TidyApp(App):
    """tidy — clean up your downloads."""

    TITLE = "tidy"
    CSS = CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, target: Path):
        super().__init__()
        self.target = target

    def on_mount(self):
        self.register_theme(PURPLE_THEME)
        self.theme = "tidy-purple"
        self.push_screen(HomeScreen(self.target))


# ── CLI Entry Point ───────────────────────────────────────────────────────────

@click.command()
@click.argument("path", default="~/Downloads", type=click.Path())
@click.option("--undo", "do_undo", is_flag=True, help="Undo the last tidy operation and exit.")
def main(path: str, do_undo: bool):
    """Tidy up a folder. Defaults to ~/Downloads."""
    target = Path(path).expanduser().resolve()

    if do_undo:
        ok, fail = undo()
        if ok == 0 and fail == 0:
            click.echo("Nothing to undo.")
        elif fail == 0:
            click.echo(f"✓ Restored {ok} file{'s' if ok != 1 else ''}.")
        else:
            click.echo(f"Restored {ok}, failed to restore {fail}.")
        return

    if not target.exists():
        click.echo(f"Error: {target} does not exist.", err=True)
        sys.exit(1)
    if not target.is_dir():
        click.echo(f"Error: {target} is not a directory.", err=True)
        sys.exit(1)

    app = TidyApp(target)
    app.run()


if __name__ == "__main__":
    main()
