# tidy

A terminal file organizer. Sort, deduplicate, rename, and clean up any folder.

```
  ╭───────╮
  │ ┏━━━┓ │
  │ ┃ ▫ ┃ │
  │ ┗━━━┛ │
  ╰───┬───╯
```

## Install

```bash
pip install .
```

## Usage

```bash
tidy                        # interactive mode (~/Downloads)
tidy ~/Desktop              # interactive mode on a specific folder
tidy sort                   # sort files by type
tidy dupes ~/Documents      # find duplicates
tidy rename                 # clean up messy filenames
tidy junk                   # find and trash temp/junk files
tidy stats                  # show folder breakdown
tidy undo                   # undo the last operation
```

### Interactive Mode

Just run `tidy` — you get a menu:

```
  1  Sort files by type
  2  Find duplicates
  3  Clean up filenames
  4  Find junk files
  5  Folder stats
  6  Undo last action
  q  Quit
```

Every action shows a preview before doing anything. Nothing moves without your confirmation.

### Direct Commands

Power user? Skip the menu:

```bash
tidy sort ~/Downloads       # sort files into type folders
tidy dupes ~/Documents      # find & remove duplicates
tidy rename ~/Downloads     # clean up filenames
tidy junk ~/Desktop         # find & trash junk
tidy stats ~/Downloads      # see what's taking up space
tidy undo                   # undo the last thing you did
```

## What it sorts

| Folder         | File types                                      |
|----------------|------------------------------------------------|
| PDFs           | `.pdf`                                          |
| Images         | `.png`, `.jpg`, `.gif`, `.svg`, `.webp`, etc.   |
| Documents      | `.doc`, `.docx`, `.txt`, `.md`, `.epub`, etc.   |
| Spreadsheets   | `.xls`, `.xlsx`, `.csv`, `.ods`, etc.           |
| Presentations  | `.ppt`, `.pptx`, `.key`, `.odp`                 |
| Videos         | `.mp4`, `.avi`, `.mkv`, `.mov`, etc.            |
| Audio          | `.mp3`, `.wav`, `.flac`, `.aac`, etc.           |
| Archives       | `.zip`, `.tar`, `.gz`, `.7z`, `.rar`, etc.      |
| Installers     | `.exe`, `.msi`, `.pkg`, `.dmg`, etc.            |
| Code           | `.py`, `.js`, `.ts`, `.html`, `.css`, etc.      |
| Fonts          | `.ttf`, `.otf`, `.woff`, `.woff2`               |
| Trash          | `.tmp`, `.crdownload`, `.DS_Store`, etc.        |
| Review         | Everything else                                 |

## Safety

- **Never overwrites files** — duplicates get a numbered suffix
- **Rollback logs** saved to `~/.tidy/` after every operation
- **Undo** any action with `tidy undo`
- **Preview before action** — nothing moves without confirmation
- **Trash folder** — junk and dupes go to a Trash folder, not deleted

## Requirements

- Python 3.10+
- macOS, Linux, or Windows

## License

MIT
