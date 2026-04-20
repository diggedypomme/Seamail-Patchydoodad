#!/usr/bin/env python3
"""
Mock Weather Server for Seaman PC
Mimics Japanese Meteorological Agency (JMA) weather forecast format
"""

from flask import Flask, Response
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# Weather template values (based on database variable structure)
WEATHER_TYPES = [
    'None',
    '晴れ',      # Clear/Sunny
    '曇り',      # Cloudy
    '雨',        # Rain
    '雪'         # Snow
]

CONNECTIONS = [
    '',          # No connection word
    '時々',      # Sometimes/Occasionally (tokidoki)
    'のち'       # Later/Then (nochi)
]

PRECIPITATION_OPTIONS = ['None', '0%', '10%', '20%', '30%', '40%', '50%',
                         '60%', '70%', '80%', '90%', '100%']

def generate_weather_html():
    """
    Generate HTML table matching the EXACT format expected by WeatherGet.dll parser.

    Parser searches for these EXACT patterns:
    - <th colspan=4 align=left>  (note: no quotes on attribute values!)
    - <th id="normal" rowspan=2>
    - <td nowrap>
    - alt="..." for weather icons
    """

    # CRITICAL: Use exact attribute format with no quotes (colspan=4 not colspan="4")
    html = '''<!DOCTYPE html>
<html>
<head>
<meta charset="Shift_JIS">
<title>週間天気予報</title>
</head>
<body>

<table border=1>
<tr><th colspan=4 align=left>週間天気予報（東京地方）</th></tr>
<tr>
<th id="normal" rowspan=2>日付</th>
<th id="normal" rowspan=2>天気</th>
<th colspan=2>気温</th>
</tr>
<tr>
<th>最高</th>
<th>最低</th>
</tr>
'''

    # Generate 7 days of weather data
    for day_num in range(1, 8):
        date = datetime.now() + timedelta(days=day_num)
        date_str = date.strftime('%m月%d日')

        # Generate random but realistic weather
        weather_first = random.choice(WEATHER_TYPES[1:])  # Skip 'None'
        weather_second = random.choice([WEATHER_TYPES[0]] + WEATHER_TYPES[1:])
        connection = random.choice(CONNECTIONS)

        # Build weather description
        if weather_second == 'None' or weather_second == weather_first:
            weather_text = weather_first
            weather_alt = weather_first
        else:
            weather_text = f'{weather_first}{connection}{weather_second}'
            weather_alt = f'{weather_first}'

        # Temperature range (realistic for Tokyo)
        temp_max = random.randint(15, 30)
        temp_min = random.randint(5, temp_max - 5)

        # Precipitation percentage
        precip = random.choice(PRECIPITATION_OPTIONS[1:])  # Skip 'None'

        # CRITICAL: Use exact format - <td nowrap> not <td nowrap="nowrap">
        html += f'''<tr>
<td id="normal" nowrap>{date_str}</td>
<td>{weather_text}<br><img src="weather.png" alt="{weather_alt}">降水確率: {precip}</td>
<td nowrap>{temp_max}</td>
<td nowrap>{temp_min}</td>
</tr>
'''

    html += '''
</table>

</body>
</html>
'''

    return html


@app.route('/JMA_HP/jp/week/tokyo.html')
@app.route('/JMA_HP/jp/week/index.html')
@app.route('/JMA_HP/jp/week')
def weather_week():
    """Weekly weather forecast endpoint"""
    html = generate_weather_html()
    return Response(html, mimetype='text/html; charset=shift_jis')


@app.route('/JMA_HP/jp/yoho/tokyo.html')
@app.route('/JMA_HP/jp/yoho/index.html')
@app.route('/JMA_HP/jp/yoho')
def weather_day():
    """Daily weather forecast endpoint"""
    html = generate_weather_html()
    return Response(html, mimetype='text/html; charset=shift_jis')


@app.route('/JMA_HP/jp/')
@app.route('/JMA_HP/jp')
@app.route('/')
def index():
    """Root endpoint - show available routes"""
    return '''<html><body><h1>Seaman Weather Mock Server</h1>
<ul>
<li><a href="/JMA_HP/jp/week">Weekly Forecast</a></li>
<li><a href="/JMA_HP/jp/yoho">Daily Forecast</a></li>
</ul>
<p>Server is running and ready to serve weather data to Seaman PC.</p>
</body></html>'''


@app.route('/debug')
def debug():
    """Debug endpoint showing current weather data"""
    html = generate_weather_html()
    return f'''<html><body>
<h2>Raw HTML Output (as seen by WeatherGet.dll parser)</h2>
<pre>{html.replace('<', '&lt;').replace('>', '&gt;')}</pre>
<hr>
<h2>Rendered Preview</h2>
{html}
</body></html>'''


if __name__ == '__main__':
    import sys

    # Default to port 80 for XP network setup
    port = 80 if len(sys.argv) < 2 else int(sys.argv[1])

    print("="*60)
    print("Seaman PC - Mock Weather Server")
    print("="*60)
    print(f"Starting server on http://0.0.0.0:{port}")
    print(f"")
    print(f"Network setup (XP + Dev PC):")
    print(f"  Dev PC IP: 192.168.0.6 (this machine)")
    print(f"  XP PC: Network client running Seaman.exe")
    print(f"")
    print(f"Available endpoints:")
    print(f"  http://192.168.0.6:{port}/JMA_HP/jp/week  - Weekly forecast")
    print(f"  http://192.168.0.6:{port}/JMA_HP/jp/yoho  - Daily forecast")
    print(f"  http://192.168.0.6:{port}/debug           - Debug view")
    print(f"")
    print(f"Setup on XP machine:")
    print(f"  1. Run: python patch_weather_dll.py")
    print(f"     (patches DLL to http://192.168.0.6/JMA_HP/jp/)")
    print(f"  2. Start Seaman PC")
    print(f"  3. Weather fetch happens automatically")
    print(f"  4. Monitor database proxy at http://192.168.0.6:5075")
    print(f"")
    if port < 1024:
        print(f"⚠️  Port {port} requires admin privileges on Windows!")
        print(f"   Run as administrator or use port >= 1024")
        print(f"")
    print(f"Press Ctrl+C to stop server")
    print("="*60)

    app.run(host='0.0.0.0', port=port, debug=True)
