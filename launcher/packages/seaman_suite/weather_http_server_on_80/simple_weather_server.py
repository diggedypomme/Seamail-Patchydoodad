#!/usr/bin/env python3
"""
Simple standalone weather server for Seaman PC
Runs on port 8081 by default (can change if needed)
"""

from flask import Flask, Response
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# Weather template values
WEATHER_TYPES = ['晴れ', '曇り', '雨', '雪']
CONNECTIONS = ['', '時々', 'のち']
PRECIPITATION_OPTIONS = ['0%', '10%', '20%', '30%', '40%', '50%', '60%', '70%', '80%', '90%', '100%']

def generate_weather_html():
    """
    Generate HTML matching EXACT format expected by WeatherGet.dll parser.

    Parser searches for these EXACT patterns (NO quotes on attributes!):
    - <th colspan=4 align=left>
    - <th id="normal" rowspan=2>
    - <td nowrap>
    - alt="晴れ" for weather icons
    """

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

    # Generate 7 days
    for day_num in range(1, 8):
        date = datetime.now() + timedelta(days=day_num)
        date_str = date.strftime('%m月%d日')

        # Random weather
        weather_first = random.choice(WEATHER_TYPES)
        weather_second = random.choice([weather_first] + WEATHER_TYPES)
        connection = random.choice(CONNECTIONS)

        if weather_second == weather_first or not connection:
            weather_text = weather_first
            weather_alt = weather_first
        else:
            weather_text = f'{weather_first}{connection}{weather_second}'
            weather_alt = weather_first

        temp_max = random.randint(15, 30)
        temp_min = random.randint(5, temp_max - 5)
        precip = random.choice(PRECIPITATION_OPTIONS)

        # EXACT format required by parser
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
@app.route('/JMA_HP/jp/yoho/tokyo.html')
@app.route('/JMA_HP/jp/yoho/index.html')
@app.route('/JMA_HP/jp/yoho')
@app.route('/JMA_HP/jp/')
@app.route('/JMA_HP/jp')
def weather():
    """All weather endpoints return same forecast"""
    html = generate_weather_html()
    return Response(html, mimetype='text/html; charset=shift_jis')


@app.route('/')
def index():
    """Root - show status"""
    return '''<html><body>
<h1>Seaman PC Weather Server</h1>
<p>Server is running and ready.</p>
<ul>
<li><a href="/JMA_HP/jp/week">Weekly Forecast</a></li>
<li><a href="/debug">Debug View</a></li>
</ul>
</body></html>'''


@app.route('/debug')
def debug():
    """Debug view showing raw HTML"""
    html = generate_weather_html()
    return f'''<html><body>
<h2>Debug View - Raw HTML Sent to Game</h2>
<pre>{html.replace('<', '&lt;').replace('>', '&gt;')}</pre>
<hr>
<h2>Rendered Preview</h2>
{html}
</body></html>'''


if __name__ == '__main__':
    import sys

    # Default port 80 for direct hosts file method
    port = 80 if len(sys.argv) < 2 else int(sys.argv[1])

    print("="*60)
    print("Seaman PC - Weather Mock Server")
    print("="*60)
    print(f"Starting on: http://0.0.0.0:{port}")
    print(f"")
    print(f"Endpoints:")
    print(f"  http://192.168.0.6:{port}/JMA_HP/jp/week")
    print(f"  http://192.168.0.6:{port}/JMA_HP/jp/yoho")
    print(f"  http://192.168.0.6:{port}/debug")
    print(f"")
    print(f"Setup:")
    print(f"  1. On XP: Add to hosts file:")
    print(f"     192.168.0.6  www.jma.go.jp")
    print(f"")
    print(f"  2. If using port {port} (not 80), patch DLL or use reverse proxy")
    print(f"")
    print(f"Press Ctrl+C to stop")
    print("="*60)

    app.run(host='0.0.0.0', port=port, debug=True)
