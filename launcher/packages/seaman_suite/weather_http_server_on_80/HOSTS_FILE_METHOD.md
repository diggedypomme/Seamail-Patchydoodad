# Hosts File Method (Recommended)

Instead of patching the DLL, you can redirect the JMA website to your local server using the Windows hosts file.

## Advantages
- No DLL modification needed
- No backup/restore required
- Easy to enable/disable
- Works with original game files

## Setup on Windows XP

### 1. Edit Hosts File

The hosts file is located at:
```
C:\WINDOWS\system32\drivers\etc\hosts
```

Open it with Notepad (as Administrator):
```
notepad C:\WINDOWS\system32\drivers\etc\hosts
```

### 2. Add Redirect Entry

Add this line at the end:
```
192.168.0.6  www.jma.go.jp
```

This redirects all requests to `www.jma.go.jp` to your dev PC at `192.168.0.6`.

### 3. Save the File

- Click File → Save
- Close Notepad

### 4. Flush DNS Cache

```cmd
ipconfig /flushdns
```

### 5. Test the Redirect

```cmd
ping www.jma.go.jp
```

Should show:
```
Pinging www.jma.go.jp [192.168.0.6] with 32 bytes of data:
```

## Start Weather Server on Dev PC

On your dev PC (192.168.0.6):

```bash
cd C:\2026_projects\ghi\weather_server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python weather_mock.py 80
```

**Important**: Use port 80 (default HTTP port) since the DLL doesn't specify a port number!

Running on port 80 requires Administrator privileges on Windows.

## Alternative: Use Port 8080 with URL Rewrite

If you can't run on port 80, you'll need to:

1. Run server on port 8080
2. Use a reverse proxy (nginx, IIS) on port 80 to forward to 8080
3. OR patch the DLL to add :8080 to the URL

## Testing

1. Start weather server on 192.168.0.6:80
2. On XP machine, test in browser:
   ```
   http://www.jma.go.jp/JMA_HP/jp/week
   ```
   Should show weather forecast page!
3. Launch Seaman PC
4. Monitor database proxy for weather variable writes

## Removing the Redirect

To restore normal operation:

1. Edit hosts file again
2. Remove or comment out the line:
   ```
   # 192.168.0.6  www.jma.go.jp
   ```
3. Save and flush DNS cache

## Troubleshooting

### "Access Denied" when saving hosts file
- Make sure you opened Notepad as Administrator
- Right-click Notepad → Run as Administrator

### Ping still shows old IP
- Run `ipconfig /flushdns` again
- Restart XP machine
- Check for typos in hosts file

### Browser shows "Cannot connect"
- Make sure weather server is running on 192.168.0.6:80
- Check Windows Firewall on dev PC allows port 80
- Verify network connectivity: `ping 192.168.0.6`

### Game doesn't fetch weather
- Delete `WeatherIndex.dat` to force refresh
- Check exact URL game requests (might not be `/week` or `/yoho`)
- Monitor HTTP requests on dev PC

## Port 80 on Windows

To run on port 80:

1. **Run as Administrator**:
   ```cmd
   python weather_mock.py 80
   ```

2. **Or use IIS/nginx** as reverse proxy:
   - IIS or nginx listens on :80
   - Forwards to Flask on :8080
   - No admin privileges needed for Flask

3. **Or disable Windows HTTP service**:
   ```cmd
   net stop http
   sc config http start= disabled
   ```
   (Caution: May break other services!)

## Network Architecture

```
┌─────────────────────────────────────────────────────┐
│  XP Machine (Game PC)                               │
│                                                     │
│  Seaman.exe → WeatherGet.dll                       │
│       ↓                                             │
│  InternetOpenUrl("http://www.jma.go.jp/...")       │
│       ↓                                             │
│  Hosts file: www.jma.go.jp → 192.168.0.6           │
│       ↓                                             │
│  HTTP GET to 192.168.0.6:80                        │
└─────────────────────────────────────────────────────┘
              ↓ (network)
┌─────────────────────────────────────────────────────┐
│  Dev PC (192.168.0.6)                               │
│                                                     │
│  weather_mock.py (Flask on :80)                     │
│       ↓                                             │
│  Generates HTML with weather table                  │
│       ↓                                             │
│  Returns Shift-JIS encoded response                 │
└─────────────────────────────────────────────────────┘
              ↓ (HTTP response)
┌─────────────────────────────────────────────────────┐
│  WeatherGet.dll parses HTML                         │
│       ↓                                             │
│  Writes to database variables:                      │
│  SeamanPC\Bio\F_WeatherGet\Day_N\...                │
│       ↓                                             │
│  Seaman discusses weather!                          │
└─────────────────────────────────────────────────────┘
```

## Exact HTML Format Required

WeatherGet.dll searches for these EXACT patterns:

```html
<th colspan=4 align=left>Header</th>
<th id="normal" rowspan=2>Column</th>
<td nowrap>Temperature</td>
<td id="normal" nowrap>Date</td>
<img alt="晴れ">
```

**Note**: Attributes have NO quotes! `colspan=4` not `colspan="4"`

The weather_mock.py generates HTML in exactly this format.
