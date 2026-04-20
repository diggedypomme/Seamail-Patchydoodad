# Seaman PC - Weather System Mock Server

## Overview

This mock server provides weather forecast data to Seaman PC in the format expected by `WeatherGet.dll`. It mimics the Japanese Meteorological Agency (JMA) website structure.

## Architecture

```
Seaman.exe
    ↓ (calls)
WeatherGet.dll
    ↓ (HTTP GET via WinINET)
http://www.jma.go.jp/JMA_HP/jp/...
    ↓ (patched to redirect)
http://localhost:8080/JMA_HP/jp/...
    ↓ (served by)
weather_mock.py (Flask server)
    ↓ (populates)
SeamanPC\Bio\F_WeatherGet\Day_N\* variables
```

## Database Variables Populated

For each day (Day_1 through Day_7):

- `Weather\First` - Primary weather condition (晴れ/曇り/雨/雪)
- `Weather\Connection` - Transition word (時々/のち)
- `Weather\Second` - Secondary weather condition
- `Precipitation` - Rain probability (0%-100%)
- `Tenperature\Min` - Minimum temperature (°C)
- `Tenperature\Max` - Maximum temperature (°C)

Plus:
- `GetDay` - Date of last fetch (YYYYMMDD format)

## Quick Start

### 1. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Patch WeatherGet.dll

```bash
python patch_weather_dll.py
```

This will:
- Create backup: `WeatherGet.dll.bak`
- Replace `http://www.jma.go.jp` with `http://localhost:8080`

### 3. Start Weather Server

```bash
python weather_mock.py
```

Server will run on: `http://localhost:8080`

### 4. Test in Browser

- Weekly forecast: http://localhost:8080/JMA_HP/jp/week
- Daily forecast: http://localhost:8080/JMA_HP/jp/yoho
- Debug view: http://localhost:8080/debug

### 5. Launch Seaman PC

The game will automatically fetch weather data at startup or periodically. Monitor the database proxy to see variables being populated.

## HTML Format Expected

WeatherGet.dll parser looks for this structure:

```html
<table>
<tr><th colspan="4" align="left">週間天気予報</th></tr>
<tr>
  <th id="normal" rowspan="2">日付</th>
  <th id="normal" rowspan="2">天気</th>
  <th colspan="2">気温</th>
</tr>
<tr><th>最高</th><th>最低</th></tr>

<!-- For each day -->
<tr>
  <td>3月15日</td>
  <td><img alt="晴れ"> 晴れ時々曇り<br>降水確率: 20%</td>
  <td nowrap>22℃</td>
  <td nowrap>12℃</td>
</tr>
</table>
```

### Parsing Details

The DLL extracts:
- **Weather condition**: From `<img alt="...">` attribute
- **Temperature**: From `<td nowrap>` cells, strips `℃`, `<`, `(`, spaces
- **Date header**: From first `<td>` in row
- **Precipitation**: From text after "降水確率:" (if present)

## File Output

WeatherGet.dll saves parsed data to:

- `temp_day.dat` - Today's forecast (9 bytes)
- `temp_week.dat` - Weekly forecast (7 days × 9 bytes = 63 bytes)
- `WeatherIndex.dat` - Cache index with timestamp

### Binary Format (per day)

```
Offset  Size  Content
------  ----  -------
0x00    12    Reserved (0x9C padding)
0x0C    2     Date header
0x0E    1     Unknown
0x0F    4     Temperature data
0x13    2     Weather condition code
```

## Weather Template Values

Based on database variable structure:

### Weather Types (5 options)
- None
- 晴れ (Clear/Sunny)
- 曇り (Cloudy)
- 雨 (Rain)
- 雪 (Snow)

### Connection Words (3 options)
- (empty) - No transition
- 時々 (tokidoki) - Sometimes/Occasionally
- のち (nochi) - Later/Then

### Precipitation (12 options)
- None, 0%, 10%, 20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%, 100%

### Temperature Range (92 options)
- -40°C to +50°C (estimated range)
- Game likely converts to full-width Japanese text format

## Monitoring Weather Fetch

### Using Database Proxy

Watch these operations in `bridge/database_proxy/web_analyzer.py`:

```
[WRITE] SeamanPC\Bio\F_WeatherGet\GetDay = 20260315
[WRITE] SeamanPC\Bio\F_WeatherGet\Day_1\Weather\First = 晴れ
[WRITE] SeamanPC\Bio\F_WeatherGet\Day_1\Tenperature\Max = 22
```

### Manual Testing with curl

```bash
curl http://localhost:8080/JMA_HP/jp/week
```

Should return Shift-JIS encoded HTML with weather table.

## Restoring Original DLL

```bash
python patch_weather_dll.py restore
```

This copies `WeatherGet.dll.bak` back to `WeatherGet.dll`.

## Troubleshooting

### Server not starting
- Check port 8080 is not in use: `netstat -ano | findstr :8080`
- Change port in weather_mock.py if needed

### DLL patch fails
- URL might already be patched - check with hex editor
- Original URL format might differ from expected
- Try restoring backup first

### Game not fetching weather
- Check WeatherIndex.dat timestamp (may cache for 24 hours)
- Delete `WeatherIndex.dat` to force refresh
- Monitor HTTP requests with Wireshark/Fiddler

### Variables not populating
- Check HTML response encoding (must be Shift-JIS or UTF-8)
- Verify table structure matches expected format
- Use `/debug` endpoint to view raw HTML
- Check database proxy for WRITE operations

## Advanced Usage

### Custom Weather Data

Edit `weather_mock.py` to:
- Set specific weather conditions
- Use realistic temperature ranges
- Match current real-world weather
- Test edge cases (extreme temps, 100% precipitation)

### Different URL Paths

If the game requests a different URL path:
1. Check decompiled code for exact URL
2. Add new route to Flask app
3. Update patch_weather_dll.py if base URL differs

### Network Monitoring

Use Frida to intercept InternetOpenUrlA:

```javascript
Interceptor.attach(Module.findExportByName('wininet.dll', 'InternetOpenUrlA'), {
  onEnter: function(args) {
    console.log('URL:', args[1].readAnsiString());
  }
});
```

## Files

- `weather_mock.py` - Flask server serving mock weather data
- `patch_weather_dll.py` - DLL patcher to redirect URL
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Technical References

- [weather_system_analysis.md](../documentation/weather_system_analysis.md) - Full analysis
- [ghidra_decompiled_ALL_WeatherGet_dll.c](../documentation/SMALLOUTPUT/) - Decompiled source
- JMA website: http://www.jma.go.jp/JMA_HP/jp/ (original)

## Next Steps

1. ✅ Create mock HTML generator
2. ✅ Build Flask server
3. ✅ Create DLL patcher
4. ⏳ Test with actual game
5. ⏳ Verify all 7 days populate correctly
6. ⏳ Confirm Seaman discusses weather in dialogue
7. ⏳ Extract exact URL path from network capture
8. ⏳ Refine HTML format if parser fails
9. ⏳ Add logging to track parse failures
10. ⏳ Document speech system integration
