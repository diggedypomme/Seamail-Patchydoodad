# DataBase.dll Proxy Monitoring System

## Quick Reference

**Target EXE:** `Seaman.exe` (all versions)
**Monitored DLL:** `DataBase.dll`
**Web Dashboard:** http://localhost:5075
**UDP Port:** 9999

## Files & Scripts

### Build Files (frida_xp/)
- `database_proxy.cpp` - Proxy source (edit line 23 for your IP)
- `database_proxy.def` - Export definitions
- `BUILD_DATABASE_PROXY.bat` - **BUILD SCRIPT** - Run this to compile
- `DataBase.dll` - **OUTPUT** - Install in SeaMail folder

### Analyzer Scripts (bridge/database_proxy/)
- `web_analyzer.py` - **BEST** - Web dashboard on port 5075
- `db_analyzer.py` - Terminal dashboard with colors
- `db_monitor.py` - Simple text output

### Installation
```batch
# 1. Build proxy
cd C:\2026_projects\ghi\frida_xp
BUILD_DATABASE_PROXY.bat

# 2. Install in game folder
cd C:\path\to\SeaMail
copy DataBase.dll DataBase_real.dll
copy C:\2026_projects\ghi\frida_xp\DataBase.dll DataBase.dll

# 3. Start analyzer (on your dev PC)
cd C:\2026_projects\ghi\bridge\database_proxy
python web_analyzer.py

# 4. Run game
Seaman.exe
```

## Monitored Operations Explained

### GET (ReadElementKey)
**What:** Reads a variable's current value
**Used by:** `:COMP` opcode in SDP files (conditionals)
**Example:** `GET SeamanPC\bio\hunger → 'レベル３'`
**Why frequent:** Game checks variables constantly for state decisions

### SET (WriteElementKey)
**What:** Writes a new value to a variable
**Used by:** `:DBSET` opcode in SDP files
**Example:** `SET SeamanPC\control\calendarflag = '2'`
**Why frequent:** Scripts update game state, track progress

### GETIDX (GetIndex)
**What:** Converts template string value → numeric index
**Used by:** `:JUMP` opcode - array/table lookups
**Example:** `GETIDX SeamanPC\bio\grow → 3` (converts 'ＢＧ−３' → 3)
**Why frequent:**
- `:JUMP` opcodes use this to select which script to execute
- State machine uses indices for switch statements
- Faster numeric comparisons vs string comparisons

### SETIDX (SetIndex)
**What:** Sets variable to template value at specific index
**Used by:** State transitions, evolution triggers
**Example:** `SETIDX SeamanPC\bio\grow = 5` (sets to 'ＢＧ−５')
**Why frequent:**
- Evolution system advances growth stages
- Template-based value assignment
- Ensures values stay within valid template range

## Why GetIdx/SetIdx Keep Running

The game uses **template-based storage**:
- **Storage format:** Full-width Japanese strings ('ＢＧ−１', 'レベル３')
- **Runtime format:** Numeric indices (0, 1, 2, 3...)

**Conversion is needed because:**
1. `:JUMP` opcode jumps to script index N based on variable value
2. Growth stage determines which model/animation to use (array lookup)
3. State machine uses switch(index) for performance
4. Prevents string comparison overhead (O(n) → O(1))

**Example flow:**
```
1. GET bio\grow → 'ＢＧ−３'          (Read current growth)
2. GETIDX bio\grow → 3              (Convert to index)
3. :JUMP uses index 3 → b_idle.sdp  (Select script)
4. Game logic: if (index == 5) ...  (Numeric comparison)
```

## Variable Categories

| ID | Category | Examples |
|----|----------|----------|
| 0 | SeamanPC | bio\grow, bio\hunger, control\calendarflag |
| 1 | User | name, birthday, sex |
| 2 | Relation | like, relation_level |
| 3 | Schedule | Time-based events |

## Network Configuration

**For remote monitoring (game on different PC):**

Edit `database_proxy.cpp` line 23:
```cpp
#define UDP_HOST "192.168.0.6"  // Your dev PC IP
```

Then rebuild with `BUILD_DATABASE_PROXY.bat`

Analyzers already listen on `0.0.0.0` (all interfaces).

## Web Dashboard Features

### Real-time Monitoring
- Live stats updating every 2 seconds
- Bar charts of top read/written variables
- Recent changes feed with timestamps
- Full variable table with operation counts
- No page reload needed - AJAX updates
- Scroll position preserved during auto-refresh

### Variable Details (Expandable Rows)
- Click any variable row to expand
- **Template Values**: Shows all valid options from DPE files (e.g., 'レベル１', 'レベル２', 'レベル３' for hunger)
- **Value History**: Complete chronological list of value changes with timestamps
- Expanded state persists through auto-refresh

### Column Sorting
- Click any column header to sort
- Click again to reverse sort direction (▲ ascending / ▼ descending)
- Sort by: Variable Path, Reads, Writes, GetIdx, SetIdx, Last Value, Changes, or Template count
- Default sort: Total activity (reads + writes)

## Template System Integration

The analyzer automatically loads template definitions from DPC/DPE file pairs on startup:

**Files loaded:**
- `SeaMail\Resource\SeamanPC.dpc/.dpe` - Seaman creature variables
- `SeaMail\Resource\User.dpc/.dpe` - User profile variables
- `SeaMail\Resource\Relation.dpc/.dpe` - Relationship variables
- `SeaMail\Resource\Schedule.dpc/.dpe` - Scheduling system
- `SeaMail\Resource\PersonalCalendar.dpc/.dpe` - Calendar events
- `SeaMail\Resource\LargeSchedule.dpc/.dpe` - Extended scheduling

**What templates show:**
Templates are the valid values a variable can hold. For example:
- `SeamanPC\bio\grow`: ['ＢＧ−０', 'ＢＧ−１', 'ＢＧ−３', 'ＢＧ−５', 'ＧＨ−２']
- `SeamanPC\bio\hunger`: ['レベル１', 'レベル２', 'レベル３', 'レベル４']
- `SeamanPC\bio\mood`: ['良い', '普通', '悪い']

This helps understand:
- What values GetIndex/SetIndex operations map to
- Valid ranges for conditional logic in SDP scripts
- State machine transitions and bounds checking

## Purpose

**Research Goal:** Determine why E_Idle.sdp (emotion-based listening) never loads.

**Method:** Monitor which variables are read before each SDP file load to understand selection logic.

## Restore Original

```batch
cd C:\path\to\SeaMail
copy DataBase_real.dll DataBase.dll
```

## Related Files
- `frida_xp/DATABASE_PROXY_README.md` - Detailed technical guide
- `documentation/database_specification.md` - DataBase.dll full spec
- `documentation/sdp_opcode_table.md` - SDP opcode reference
