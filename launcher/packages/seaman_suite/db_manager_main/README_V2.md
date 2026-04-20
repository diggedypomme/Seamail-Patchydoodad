# Database Editor V2

Improved version of the Seaman PC database editor with better UX and change tracking.

## Features

### V2 Improvements over V1
- **Table View**: All records displayed in a clean, scannable table instead of tree navigation
- **Combined View**: Monitor ALL three UDB files at once (Seaman, User, Calender)
- **Folder Selection**: Choose which Seaman installation to monitor (for multiple installs)
- **Inline Editing**: Click "Edit" on any row to modify values directly
- **Live Refresh**: Manual refresh button + auto-refresh with configurable intervals (2s, 5s, 10s, 30s, 60s)
- **Change Tracking**:
  - Changed rows highlighted in green when refreshed
  - Side panel showing recent changes with "old → new" values
  - Change log persists during session (cleared manually or on restart)
  - Combined view shows changes across all files
- **Search/Filter**: Filter table by file, path, or value
- **File Modification Time**: Shows when each file was last modified
- **Error Handling**:
  - Detects locked files (game running) and shows notification
  - Status indicator shows load success/warning/error
  - Toast notifications for errors (5s timeout)
  - Partial loading in combined view (shows available files if some are locked)
- **DPC Explanation**: Built-in info about what DPC files are (variable path templates)
- **Modern UI**: Dark theme with VSCode-inspired styling

## Usage

### Starting the Server

```bash
cd db_editor
venv\Scripts\python app_v2.py
```

Navigate to: **http://localhost:5074**

(Original V1 runs on port 5073 if you want to compare)

### Workflow

1. **Set folder** (optional):
   - Enter path to your SeaMail folder (e.g., `C:\SeamanInstall\SeaMail`)
   - Click "Set Folder" to load files from that location
   - Default: uses `C:\2026_projects\ghi\SeaMail`

2. **Select a file** from the dropdown:
   - **"All UDB Files"** - Monitor all three databases at once (recommended!)
   - Individual files: Seaman.udb, User.udb, or Calender.udb
   - DPC files: Read-only templates showing variable structure

3. **Browse records** in the table view:
   - Combined view shows "File" column to identify which database each record is from
   - Search bar filters by file, path, or value

4. **Edit values**:
   - Click "Edit" button on any row
   - Modify the value
   - Click "Save" (or "Cancel" to revert)

5. **Track changes**:
   - Changes panel visible by default on the right side
   - Recent edits appear with timestamp and old→new value comparison
   - Load failures also logged (red background, shows error message)
   - Combined view shows which file was modified/failed
   - Badge shows total change + error count

6. **Refresh data**:
   - Click "↻ Refresh" button to reload from disk
   - Enable "Auto-refresh" checkbox and select interval for live updates
   - Changed values will be highlighted in green
   - Status indicator (colored dot) shows:
     - 🟢 Green: All files loaded successfully
     - 🟡 Yellow: Some files failed (combined view only)
     - 🔴 Red: Load failed completely

### Auto-Refresh Use Case

Enable auto-refresh when:
- Running the game and wanting to see live database changes
- Testing modifications with external tools
- Monitoring specific variables during gameplay

The change detection will highlight any row that changed between refreshes.

### File Locking & Error Handling

**If files are locked** (game is running):
- Single file view: Shows error notification "File locked: in use by game"
- Combined view: Loads available files, shows warning for locked ones
- Status indicator changes to yellow/red to indicate issues
- Error messages displayed as toast notifications (bottom right)
- **Errors logged to changes panel** with timestamp and red background

**Tip**: If you want to monitor the game in real-time, the game may lock the files while writing. The combined view is more resilient - it will show data from unlocked files and warn about locked ones.

## API Endpoints

### GET /api/files
List all available .udb and .dpc files

### GET /api/udb/:name
Load a UDB file (returns flat record list)

### POST /api/udb/:name/edit
Edit a value:
```json
{
  "path": "SeamanPC\\Bio\\Hunger",
  "value": "レベル１"
}
```

### GET /api/changes/:name
Get change log for a specific file

### POST /api/changes/:name/clear
Clear change log

## File Types Explained

### UDB Files (.udb) - Save Files
These are the actual game save files, encrypted with IDEA cipher:
- **Seaman.udb**: Main creature data (hunger, mood, growth stage, DNA, stats)
- **User.udb**: Player profile (name, age, occupation, preferences)
- **Calender.udb**: Game calendar and scheduling data

Values are stored as XOR 0xFF encoded Shift-JIS text with timestamps.

### DPC Files (.dpc) - Variable Path Templates
These are read-only template files that define the database structure:
- Maps numeric record IDs to variable path strings
- Example: `ID 42 → "SeamanPC\Bio\Hunger"`
- The game uses these to look up where to store/retrieve each value
- Think of them as the "schema" or "blueprint" for the database

**Why view DPC files?**
- See all possible variables that can exist in a save file
- Understand the hierarchy (SeamanPC → Bio → Hunger)
- Find variable paths for manual editing or scripting

## Technical Details

- **Backend**: Flask (Python)
- **Port**: 5074 (V1 uses 5073)
- **Session Storage**: Change logs + folder path stored in Flask session (cookie-based)
- **Change Detection**: Compares current data with previous fetch to highlight modifications
- **File Monitoring**: Checks file mtime to detect external modifications
- **Combined View**: Loads all three UDB files and merges into single table

## Files

- `app_v2.py` - Flask server
- `templates/index_v2.html` - Frontend UI
- `db_parser.py` - Shared parser (used by both V1 and V2)
- `idea_cipher.py` - IDEA encryption/decryption

## V1 vs V2 Comparison

| Feature | V1 | V2 |
|---------|----|----|
| Navigation | Tree view (hierarchical) | Table view (flat) |
| Reading | Click nodes, view in sidebar | See all at once |
| Editing | Sidebar panel | Inline in table |
| Refresh | Reload page | Button + auto-refresh |
| Change Tracking | ❌ | ✅ Highlights + log panel |
| Search | Filter tree | Filter table |
| Layout | Sidebar + detail panel | Toolbar + table + changes |

**Use V1 when**: You want to explore hierarchical structure (e.g., SeamanPC → Bio → Hunger)

**Use V2 when**: You want to quickly scan/edit many values and track changes over time
