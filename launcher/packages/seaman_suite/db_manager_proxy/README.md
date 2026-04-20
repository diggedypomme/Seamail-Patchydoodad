# DataBase.dll Proxy Bridge

## What This Is

UDP receiver for real-time monitoring of DataBase.dll variable access operations.

## Related Components

**Target EXE:** `Seaman.exe` (all versions)
**Proxy DLL:** `frida_xp\DataBase.dll`
**Original DLL:** DataBase.dll (renamed to DataBase_real.dll)

## How It Works

1. **DataBase.dll proxy** intercepts 4 key functions:
   - `ReadElementKey` - Variable reads (used by :COMP opcode)
   - `WriteElementKey` - Variable writes (used by :DBSET opcode)
   - `GetIndex` - Get numeric index from template (used by :JUMP opcode)
   - `SetIndex` - Set variable to template value by index

2. **Proxy sends UDP packets** to 127.0.0.1:9999 with timestamped logs

3. **This Python script** receives and displays logs in real-time with statistics

## Usage

**Start the receiver:**
```batch
cd C:\2026_projects\ghi\bridge\database_proxy
python db_monitor.py
```

**In another terminal, install the proxy:**
```batch
cd C:\path\to\SeaMail
copy DataBase.dll DataBase_real.dll
copy C:\2026_projects\ghi\frida_xp\DataBase.dll DataBase.dll
```

**Run Seaman.exe** and watch variable access logs stream in real-time!

Press **Ctrl+C** to stop and see statistics summary.

## Example Output

```
[12:34:56] GET SeamanPC\bio\grow
  -> 'ＢＧ−１'
[12:34:56] GETIDX SeamanPC\bio\grow
  -> 3
[12:34:57] GET SeamanPC\bio\hunger
  -> 'レベル３'
[12:34:58] SET SeamanPC\control\calendarflag = '2' (type=str)
```

## Purpose

Understand how the game selects which SDP (dialogue script) files to load by monitoring which database variables are read before each script execution.

**Key question being investigated:**
Why does E_Idle.sdp (emotion-based listening) never load despite having :CTX listening opcodes?

## Files

- `db_monitor.py` - UDP receiver (this file)
- `../frida_xp/DataBase.dll` - Proxy DLL to install
- `../frida_xp/DATABASE_PROXY_README.md` - Full technical documentation

## Statistics Tracked

- Total reads/writes/GetIndex/SetIndex operations
- Top 5 variable categories accessed
- Top 10 individual variable keys accessed
- Real-time streaming display

## Related Documentation

- `../../documentation/database_specification.md` - DataBase.dll technical spec
- `../../documentation/sdp_opcode_table.md` - SDP opcode reference
- `../../frida_xp/DATABASE_PROXY_README.md` - Full proxy installation guide
