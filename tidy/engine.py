"""
tidy.engine — File scanning, sorting, dedup, junk detection, renaming, stats, undo.
Pure logic, no UI.
"""

import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ── Category Definitions ─────────────────────────────────────────────────────

CATEGORIES: dict[str, set[str]] = {
    "PDFs":           {".pdf"},
    "Images":         {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
                       ".ico", ".tiff", ".tif", ".heic", ".heif", ".avif"},
    "Documents":      {".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".tex",
                       ".pages", ".epub", ".mobi"},
    "Spreadsheets":   {".xls", ".xlsx", ".csv", ".tsv", ".ods", ".numbers"},
    "Presentations":  {".ppt", ".pptx", ".key", ".odp"},
    "Videos":         {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
                       ".m4v", ".mpg", ".mpeg", ".3gp"},
    "Audio":          {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
                       ".opus", ".aiff"},
    "Archives":       {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz",
                       ".zst", ".tgz"},
    "Installers":     {".exe", ".msi", ".pkg", ".deb", ".rpm", ".dmg", ".appimage"},
    "Code":           {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
                       ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb",
                       ".php", ".swift", ".kt", ".sql", ".sh", ".ipynb"},
    "Fonts":          {".ttf", ".otf", ".woff", ".woff2"},
}

_EXT_MAP: dict[str, str] = {}
for _cat, _exts in CATEGORIES.items():
    for _ext in _exts:
        _EXT_MAP[_ext] = _cat

JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini", ".localized"}
JUNK_EXTENSIONS = {".crdownload", ".part", ".tmp", ".temp", ".swp", ".bak", ".log"}
RESERVED_FOLDERS = set(CATEGORIES.keys()) | {"Review", "Trash"}

LOG_DIR = Path.home() / ".tidy"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class FileItem:
    path: Path
    name: str
    size: int
    category: str


@dataclass
class DupeGroup:
    hash: str
    size: int
    files: list[Path]


@dataclass
class RenameItem:
    old_path: Path
    new_path: Path
    old_name: str
    new_name: str


@dataclass
class SortPlan:
    items: list[FileItem] = field(default_factory=list)
    target_dir: Path = field(default_factory=lambda: Path.home() / "Downloads")

    @property
    def by_category(self) -> dict[str, list[FileItem]]:
        groups: dict[str, list[FileItem]] = defaultdict(list)
        for item in self.items:
            groups[item.category].append(item)
        return dict(groups)

    @property
    def total_files(self) -> int:
        return len(self.items)

    @property
    def total_size(self) -> int:
        return sum(i.size for i in self.items)


# ── Helpers ──────────────────────────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    else:
        return f"{size_bytes / (1024*1024*1024):.1f} GB"


def _safe_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _safe_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _file_hash(path: Path, quick: bool = True) -> str:
    """Hash a file. If quick=True, only hash first/last 8KB for speed."""
    h = hashlib.md5()
    size = path.stat().st_size
    with open(path, "rb") as f:
        if quick and size > 16384:
            h.update(f.read(8192))
            f.seek(-8192, 2)
            h.update(f.read(8192))
            h.update(str(size).encode())
        else:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    return h.hexdigest()


def _save_log(log: list[dict], action: str = "sort"):
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"tidy_{action}_{ts}.json"
    with open(path, "w") as f:
        json.dump(log, f, indent=2)


def _get_last_log() -> tuple[list[dict], Path] | None:
    LOG_DIR.mkdir(exist_ok=True)
    logs = sorted(LOG_DIR.glob("tidy_*.json"), reverse=True)
    if not logs:
        return None
    with open(logs[0]) as f:
        return json.load(f), logs[0]


# ── Sort ─────────────────────────────────────────────────────────────────────

def scan_sort(target: Path) -> SortPlan:
    plan = SortPlan(target_dir=target)
    if not target.exists() or not target.is_dir():
        return plan

    for item in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if item.name.startswith(".") and item.name.lower() not in JUNK_NAMES:
            continue
        if item.is_dir() and item.name in RESERVED_FOLDERS:
            continue
        if item.is_dir():
            continue

        name_lower = item.name.lower()
        ext = item.suffix.lower()

        if name_lower in JUNK_NAMES or ext in JUNK_EXTENSIONS:
            cat = "Trash"
        else:
            cat = _EXT_MAP.get(ext, "Review")

        plan.items.append(FileItem(
            path=item, name=item.name,
            size=_safe_size(item), category=cat,
        ))
    return plan


def execute_sort(plan: SortPlan, on_progress=None) -> list[dict]:
    log = []
    total = plan.total_files
    for i, item in enumerate(plan.items):
        dest_dir = plan.target_dir / item.category
        dest_dir.mkdir(exist_ok=True)
        dst = _safe_dest(dest_dir / item.name)

        entry = {"src": str(item.path), "dst": str(dst),
                 "category": item.category, "action": "sort",
                 "time": datetime.now().isoformat()}
        try:
            shutil.move(str(item.path), str(dst))
            entry["ok"] = True
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)

        log.append(entry)
        if on_progress:
            on_progress(i + 1, total, item.name)

    _save_log(log, "sort")
    return log


# ── Duplicates ───────────────────────────────────────────────────────────────

def scan_dupes(target: Path) -> list[DupeGroup]:
    # Group by size first (fast filter)
    size_map: dict[int, list[Path]] = defaultdict(list)
    for item in target.rglob("*"):
        if item.is_file() and not item.name.startswith("."):
            size = _safe_size(item)
            if size > 0:
                size_map[size].append(item)

    # Hash only size-collisions
    hash_map: dict[str, list[Path]] = defaultdict(list)
    for size, files in size_map.items():
        if len(files) < 2:
            continue
        for f in files:
            try:
                h = _file_hash(f)
                hash_map[h].append(f)
            except (OSError, PermissionError):
                continue

    groups = []
    for h, files in hash_map.items():
        if len(files) >= 2:
            groups.append(DupeGroup(
                hash=h, size=_safe_size(files[0]), files=sorted(files),
            ))
    return sorted(groups, key=lambda g: g.size, reverse=True)


def remove_dupes(groups: list[DupeGroup], keep: str = "first") -> list[dict]:
    """Remove duplicates, keeping the first (oldest path) by default."""
    log = []
    for g in groups:
        # Keep first, remove rest
        to_remove = g.files[1:] if keep == "first" else g.files[:-1]
        for f in to_remove:
            entry = {"src": str(f), "dst": "", "action": "dedup",
                     "size": g.size, "time": datetime.now().isoformat()}
            try:
                # Move to trash folder instead of deleting
                trash_dir = f.parent
                # Walk up to find the target root (non-category folder)
                while trash_dir.name in RESERVED_FOLDERS or trash_dir.name in CATEGORIES:
                    trash_dir = trash_dir.parent
                trash_dir = trash_dir / "Trash"
                trash_dir.mkdir(exist_ok=True)
                dst = _safe_dest(trash_dir / f.name)
                shutil.move(str(f), str(dst))
                entry["dst"] = str(dst)
                entry["ok"] = True
            except Exception as e:
                entry["ok"] = False
                entry["error"] = str(e)
            log.append(entry)

    _save_log(log, "dedup")
    return log


# ── Junk Detection ───────────────────────────────────────────────────────────

def scan_junk(target: Path) -> list[FileItem]:
    junk = []
    for item in target.rglob("*"):
        if not item.is_file():
            continue
        name_lower = item.name.lower()
        ext = item.suffix.lower()
        is_junk = (
            name_lower in JUNK_NAMES
            or ext in JUNK_EXTENSIONS
            or name_lower.startswith("._")
            or (name_lower.startswith(".") and ext in {".swp", ".swo"})
        )
        if is_junk:
            junk.append(FileItem(
                path=item, name=item.name,
                size=_safe_size(item), category="Trash",
            ))
    return sorted(junk, key=lambda f: f.size, reverse=True)


def trash_junk(junk: list[FileItem], target: Path) -> list[dict]:
    log = []
    trash_dir = target / "Trash"
    trash_dir.mkdir(exist_ok=True)
    for item in junk:
        dst = _safe_dest(trash_dir / item.name)
        entry = {"src": str(item.path), "dst": str(dst),
                 "action": "junk", "time": datetime.now().isoformat()}
        try:
            shutil.move(str(item.path), str(dst))
            entry["ok"] = True
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        log.append(entry)

    _save_log(log, "junk")
    return log


# ── Rename ───────────────────────────────────────────────────────────────────

def _clean_name(name: str) -> str:
    """Clean up a messy filename while preserving extension."""
    stem = Path(name).stem
    ext = Path(name).suffix

    # Replace underscores, multiple spaces, dashes with single space
    cleaned = re.sub(r"[_\-]+", " ", stem)
    # Remove common junk patterns
    cleaned = re.sub(r"\s*\(\d+\)\s*$", "", cleaned)  # trailing (1), (2)
    cleaned = re.sub(r"\s*copy\s*\d*\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*Copy\s*$", "", cleaned, flags=re.IGNORECASE)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Title case if it's all lower or all upper
    if cleaned == cleaned.lower() or cleaned == cleaned.upper():
        cleaned = cleaned.title()

    if not cleaned:
        cleaned = stem

    return cleaned + ext.lower()


def scan_renames(target: Path) -> list[RenameItem]:
    renames = []
    for item in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if item.is_dir() or item.name.startswith("."):
            continue
        new_name = _clean_name(item.name)
        if new_name != item.name:
            new_path = _safe_dest(item.parent / new_name)
            renames.append(RenameItem(
                old_path=item, new_path=new_path,
                old_name=item.name, new_name=new_path.name,
            ))
    return renames


def execute_renames(renames: list[RenameItem]) -> list[dict]:
    log = []
    for r in renames:
        dst = _safe_dest(r.new_path)
        entry = {"src": str(r.old_path), "dst": str(dst),
                 "action": "rename", "time": datetime.now().isoformat()}
        try:
            r.old_path.rename(dst)
            entry["ok"] = True
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        log.append(entry)

    _save_log(log, "rename")
    return log


# ── Stats ────────────────────────────────────────────────────────────────────

@dataclass
class FolderStats:
    total_files: int = 0
    total_size: int = 0
    by_category: dict[str, tuple[int, int]] = field(default_factory=dict)  # cat -> (count, size)
    largest_files: list[tuple[Path, int]] = field(default_factory=list)


def get_stats(target: Path) -> FolderStats:
    stats = FolderStats()
    cat_counts: dict[str, int] = defaultdict(int)
    cat_sizes: dict[str, int] = defaultdict(int)
    all_files: list[tuple[Path, int]] = []

    for item in target.rglob("*"):
        if not item.is_file() or item.name.startswith("."):
            continue
        size = _safe_size(item)
        stats.total_files += 1
        stats.total_size += size
        all_files.append((item, size))

        ext = item.suffix.lower()
        cat = _EXT_MAP.get(ext, "Other")
        cat_counts[cat] += 1
        cat_sizes[cat] += size

    stats.by_category = {
        cat: (cat_counts[cat], cat_sizes[cat])
        for cat in sorted(cat_counts.keys(), key=lambda c: cat_sizes[c], reverse=True)
    }
    stats.largest_files = sorted(all_files, key=lambda x: x[1], reverse=True)[:10]
    return stats


# ── Undo ─────────────────────────────────────────────────────────────────────

def undo_last() -> tuple[int, int, str]:
    """Undo most recent operation. Returns (ok, fail, action_type)."""
    result = _get_last_log()
    if not result:
        return (0, 0, "")

    log, log_path = result
    action = log[0].get("action", "sort") if log else "sort"
    ok = fail = 0

    for entry in reversed(log):
        if not entry.get("ok"):
            continue
        src = Path(entry["dst"])
        dst = Path(entry["src"])
        try:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1

    # Clean up empty folders
    if log:
        target = Path(log[0]["src"]).parent
        for folder_name in RESERVED_FOLDERS:
            folder = target / folder_name
            if folder.is_dir():
                try:
                    if not any(folder.iterdir()):
                        folder.rmdir()
                except OSError:
                    pass

    log_path.unlink(missing_ok=True)
    return (ok, fail, action)
