"""
dna_app.py — DNA Selector
Flask micro-app served on port 5076.
Shows the 14x14 trait matrix; click any cell to pick Element1+Element2,
then Apply to write them to Seaman.udb.
"""

from __future__ import annotations

import os
import random
import sys

from flask import Flask, jsonify, render_template_string, request

# ── Path setup ────────────────────────────────────────────────────────────────

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_MANAGER = os.path.join(PACKAGE_ROOT, "db_manager_main")

for p in (PACKAGE_ROOT, DB_MANAGER):
    if p not in sys.path:
        sys.path.insert(0, p)

from db_parser import parse_udb, save_udb          # noqa: E402
from path_helpers import resolve_hostdb_dir         # noqa: E402

# ── DNA constants ─────────────────────────────────────────────────────────────

LETTERS = list("ABCDEFGHIJKLMN")

# Full-width katakana A–N (values stored in the UDB)
DNA_MAP: dict[str, str] = {
    "A": "\uff21", "B": "\uff22", "C": "\uff23", "D": "\uff24",
    "E": "\uff25", "F": "\uff26", "G": "\uff27", "H": "\uff28",
    "I": "\uff29", "J": "\uff2a", "K": "\uff2b", "L": "\uff2c",
    "M": "\uff2d", "N": "\uff2e",
}
REV_MAP: dict[str, str] = {v: k for k, v in DNA_MAP.items()}

# Trait matrix: MATRIX[elem1_idx][elem2_idx]  (0-indexed, A=0 … N=13)
MATRIX = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # A
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # B
    [0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3],  # C
    [0, 0, 2, 0, 2, 0, 0, 0, 0, 0, 0, 0, 3, 3],  # D
    [0, 0, 0, 2, 1, 2, 1, 1, 1, 1, 1, 1, 3, 3],  # E
    [0, 0, 0, 0, 2, 1, 2, 1, 1, 1, 1, 1, 3, 3],  # F
    [0, 0, 0, 0, 1, 2, 1, 2, 1, 1, 1, 1, 3, 3],  # G
    [0, 0, 0, 0, 1, 1, 2, 0, 0, 0, 0, 0, 4, 4],  # H
    [0, 0, 0, 0, 1, 1, 1, 0, 3, 3, 3, 3, 4, 4],  # I
    [0, 0, 0, 0, 1, 1, 1, 0, 3, 3, 3, 3, 4, 4],  # J
    [0, 0, 0, 0, 1, 1, 1, 0, 3, 3, 3, 3, 4, 4],  # K
    [0, 0, 0, 0, 1, 1, 1, 0, 3, 3, 3, 3, 4, 4],  # L
    [0, 0, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5],  # M
    [0, 0, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5],  # N
]

VARIANT_LABELS = {
    0: "Default",
    1: "Central Mutation",
    2: "Diagonal Stripe",
    3: "Mid-Right / Bottom-Left",
    4: "Bottom-Right",
    5: "Rarest (M/N lines)",
}

PATH_E1 = r"SeamanPC\Bio\DNA\Mine\Element01"
PATH_E2 = r"SeamanPC\Bio\DNA\Mine\Element02"

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)


def _udb_path() -> str:
    return str(resolve_hostdb_dir() / "Seaman.udb")


def _read_dna() -> tuple[str | None, str | None]:
    try:
        records = parse_udb(_udb_path())
        e1 = e2 = None
        for r in records:
            if r["path"] == PATH_E1 and r.get("elements"):
                e1 = REV_MAP.get(r["elements"][0]["value"])
            if r["path"] == PATH_E2 and r.get("elements"):
                e2 = REV_MAP.get(r["elements"][0]["value"])
        return e1, e2
    except Exception:
        return None, None


def _write_dna(e1: str, e2: str) -> None:
    import datetime

    def ts() -> str:
        return datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    def set_val(records: list, path: str, value: str) -> None:
        for r in records:
            if r["path"] == path:
                r["elements"] = [{"value": value, "timestamp": ts()}]
                return
        records.append({"path": path, "elements": [{"value": value, "timestamp": ts()}]})

    records = parse_udb(_udb_path())
    set_val(records, PATH_E1, DNA_MAP[e1])
    set_val(records, PATH_E2, DNA_MAP[e2])
    save_udb(_udb_path(), records)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/dna", methods=["GET"])
def api_get_dna():
    e1, e2 = _read_dna()
    variant = MATRIX[LETTERS.index(e1)][LETTERS.index(e2)] if e1 and e2 else None
    return jsonify({"element1": e1, "element2": e2, "variant": variant})


@app.route("/api/dna", methods=["POST"])
def api_set_dna():
    body = request.get_json(force=True)
    e1 = str(body.get("element1", "")).upper()
    e2 = str(body.get("element2", "")).upper()
    if e1 not in LETTERS or e2 not in LETTERS:
        return jsonify({"error": "Invalid element letter"}), 400
    try:
        _write_dna(e1, e2)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    variant = MATRIX[LETTERS.index(e1)][LETTERS.index(e2)]
    return jsonify({"ok": True, "element1": e1, "element2": e2, "variant": variant})


@app.route("/api/dna/random", methods=["POST"])
def api_random_dna():
    e1 = random.choice(LETTERS)
    e2 = random.choice(LETTERS)
    return jsonify({"element1": e1, "element2": e2,
                    "variant": MATRIX[LETTERS.index(e1)][LETTERS.index(e2)]})


@app.route("/")
def index():
    matrix_json = str(MATRIX).replace("'", '"')
    letters_json = str(LETTERS).replace("'", '"')
    variant_labels = {str(k): v for k, v in VARIANT_LABELS.items()}
    return render_template_string(HTML,
        letters=LETTERS,
        matrix=MATRIX,
        letters_json=letters_json,
        matrix_json=matrix_json,
        variant_labels=variant_labels,
    )


# ── Template ──────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DNA Selector</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #30363d;
    --text:     #e6edf3;
    --muted:    #8b949e;
    --v0: #2d333b;
    --v1: #1a3a5c;
    --v2: #3a1a5c;
    --v3: #1a4a2a;
    --v4: #5c3a00;
    --v5: #5c1a1a;
    --v0h: #3d444d;
    --v1h: #235080;
    --v2h: #502380;
    --v3h: #236632;
    --v4h: #7a4e00;
    --v5h: #7a2323;
    --sel: #f0a830;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", monospace;
    background: var(--bg);
    color: var(--text);
    font-size: 13px;
    padding: 1rem;
    min-height: 100vh;
  }

  h2 { font-size: 1rem; font-weight: 600; margin-bottom: 0.15rem; }
  p.muted { color: var(--muted); font-size: 0.8rem; margin-bottom: 0.75rem; }

  .row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem; }

  .pill {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.25rem 0.6rem;
    font-size: 0.8rem;
    color: var(--muted);
  }
  .pill strong { color: var(--text); }

  button {
    cursor: pointer;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.35rem 0.75rem;
    font-size: 0.8rem;
    font-family: inherit;
    transition: background 0.1s;
  }
  .btn-primary { background: #238636; color: #fff; border-color: #2ea043; }
  .btn-primary:hover { background: #2ea043; }
  .btn-primary:disabled { background: #1a3a20; color: #4a6a4a; cursor: default; }
  .btn-ghost { background: var(--surface); color: var(--text); }
  .btn-ghost:hover { background: var(--v0h); }
  .btn-random { background: #1a3a5c; color: #cde; border-color: #235080; }
  .btn-random:hover { background: #235080; }

  /* Matrix */
  .matrix-wrap { overflow-x: auto; margin-bottom: 0.75rem; }

  table.matrix {
    border-collapse: collapse;
    font-size: 0.75rem;
  }
  table.matrix th, table.matrix td {
    width: 32px; height: 28px;
    text-align: center; vertical-align: middle;
    border: 1px solid var(--border);
  }
  table.matrix th {
    background: var(--surface);
    color: var(--muted);
    font-weight: 600;
    position: sticky;
  }
  table.matrix th.corner { background: var(--bg); }

  table.matrix td {
    cursor: pointer;
    transition: filter 0.1s;
    user-select: none;
  }
  table.matrix td[data-v="0"] { background: var(--v0); color: #8b949e; }
  table.matrix td[data-v="1"] { background: var(--v1); color: #7eb3e8; }
  table.matrix td[data-v="2"] { background: var(--v2); color: #c07ee8; }
  table.matrix td[data-v="3"] { background: var(--v3); color: #7ec87e; }
  table.matrix td[data-v="4"] { background: var(--v4); color: #e8a850; }
  table.matrix td[data-v="5"] { background: var(--v5); color: #e87e7e; }

  table.matrix td:hover { filter: brightness(1.4); }

  table.matrix td.selected {
    outline: 2px solid var(--sel);
    outline-offset: -2px;
    filter: brightness(1.5);
  }
  table.matrix th.active-col,
  table.matrix th.active-row {
    color: var(--sel);
    background: #1a1500;
  }

  /* Selection info */
  .selection-info {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.6rem 0.85rem;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .selection-info .combo {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--sel);
    letter-spacing: 0.05em;
  }
  .selection-info .variant-badge {
    font-size: 0.75rem;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-weight: 600;
  }

  .toast {
    position: fixed; bottom: 1rem; right: 1rem;
    background: #1a4a2a; border: 1px solid #2ea043; color: #7ec87e;
    padding: 0.5rem 1rem; border-radius: 4px;
    font-size: 0.8rem; opacity: 0; transition: opacity 0.3s;
    pointer-events: none;
  }
  .toast.show { opacity: 1; }
  .toast.error { background: #4a1a1a; border-color: #e87e7e; color: #e87e7e; }

  .variant-legend {
    display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.75rem;
  }
  .legend-chip {
    font-size: 0.7rem;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    border: 1px solid var(--border);
  }
</style>
</head>
<body>

<h2>DNA Selector</h2>
<p class="muted">Click any cell to select Element 1 (row) + Element 2 (column), then Apply.</p>

<div class="row">
  <span class="pill">Current in DB — E1: <strong id="cur-e1">…</strong> &nbsp; E2: <strong id="cur-e2">…</strong> &nbsp; Variant: <strong id="cur-v">…</strong></span>
  <button class="btn-ghost" onclick="loadCurrent()">Refresh</button>
</div>

<div class="variant-legend">
  {% for v, label in variant_labels.items() %}
  <span class="legend-chip" data-v="{{ v }}">{{ v }}: {{ label }}</span>
  {% endfor %}
</div>

<div class="matrix-wrap">
<table class="matrix" id="matrix">
  <thead>
    <tr>
      <th class="corner">E1 ↓ / E2 →</th>
      {% for col in letters %}
      <th id="col-{{ col }}" data-col="{{ col }}">{{ col }}</th>
      {% endfor %}
    </tr>
  </thead>
  <tbody>
    {% for row_idx in range(letters|length) %}
    <tr>
      <th id="row-{{ letters[row_idx] }}" data-row="{{ letters[row_idx] }}">{{ letters[row_idx] }}</th>
      {% for col_idx in range(letters|length) %}
      <td
        data-e1="{{ letters[row_idx] }}"
        data-e2="{{ letters[col_idx] }}"
        data-v="{{ matrix[row_idx][col_idx] }}"
        onclick="selectCell('{{ letters[row_idx] }}', '{{ letters[col_idx] }}')">{{ matrix[row_idx][col_idx] }}</td>
      {% endfor %}
    </tr>
    {% endfor %}
  </tbody>
</table>
</div>

<div class="selection-info" id="sel-info">
  <span class="combo" id="sel-combo">— / —</span>
  <span class="variant-badge" id="sel-variant-badge">no selection</span>
  <div style="margin-left:auto; display:flex; gap:0.5rem;">
    <button class="btn-random" onclick="pickRandom()">Random</button>
    <button class="btn-primary" id="apply-btn" onclick="applyDNA()" disabled>Apply to DB</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const VARIANT_LABELS = {{ variant_labels | tojson }};
const VARIANT_COLORS = { "0":"#2d333b","1":"#1a3a5c","2":"#3a1a5c","3":"#1a4a2a","4":"#5c3a00","5":"#5c1a1a" };
const VARIANT_TEXT   = { "0":"#8b949e","1":"#7eb3e8","2":"#c07ee8","3":"#7ec87e","4":"#e8a850","5":"#e87e7e" };

let selE1 = null, selE2 = null;

// ── Legend chip styles ────────────────────────────────────────────
document.querySelectorAll(".legend-chip[data-v]").forEach(el => {
  const v = el.dataset.v;
  el.style.background = VARIANT_COLORS[v];
  el.style.color = VARIANT_TEXT[v];
});

function selectCell(e1, e2) {
  selE1 = e1; selE2 = e2;

  // Clear previous highlights
  document.querySelectorAll("td.selected").forEach(td => td.classList.remove("selected"));
  document.querySelectorAll("th.active-col, th.active-row").forEach(th => {
    th.classList.remove("active-col","active-row");
  });

  const cell = document.querySelector(`td[data-e1="${e1}"][data-e2="${e2}"]`);
  if (cell) cell.classList.add("selected");

  const rowTh = document.getElementById("row-" + e1);
  const colTh = document.getElementById("col-" + e2);
  if (rowTh) rowTh.classList.add("active-row");
  if (colTh) colTh.classList.add("active-col");

  const v = cell ? parseInt(cell.dataset.v) : null;
  const combo = document.getElementById("sel-combo");
  const badge = document.getElementById("sel-variant-badge");
  combo.textContent = `${e1} + ${e2}`;

  if (v !== null) {
    badge.textContent = `Variant ${v} — ${VARIANT_LABELS[String(v)]}`;
    badge.style.background = VARIANT_COLORS[String(v)];
    badge.style.color       = VARIANT_TEXT[String(v)];
  }

  document.getElementById("apply-btn").disabled = false;
}

async function applyDNA() {
  if (!selE1 || !selE2) return;
  const btn = document.getElementById("apply-btn");
  btn.disabled = true;
  btn.textContent = "Applying…";
  try {
    const res = await fetch("/api/dna", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({element1: selE1, element2: selE2}),
    });
    const data = await res.json();
    if (data.ok) {
      showToast(`Applied E1=${data.element1}, E2=${data.element2} (Variant ${data.variant})`);
      loadCurrent();
    } else {
      showToast(data.error || "Error writing DB", true);
    }
  } catch(e) {
    showToast("Network error", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Apply to DB";
  }
}

async function pickRandom() {
  const res = await fetch("/api/dna/random", {method:"POST"});
  const data = await res.json();
  selectCell(data.element1, data.element2);
}

async function loadCurrent() {
  try {
    const res = await fetch("/api/dna");
    const data = await res.json();
    document.getElementById("cur-e1").textContent = data.element1 || "?";
    document.getElementById("cur-e2").textContent = data.element2 || "?";
    document.getElementById("cur-v").textContent  = data.variant !== null ? data.variant : "?";
    if (data.element1 && data.element2) {
      selectCell(data.element1, data.element2);
    }
  } catch(e) {}
}

function showToast(msg, isError = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "toast show" + (isError ? " error" : "");
  setTimeout(() => { t.className = "toast"; }, 3000);
}

loadCurrent();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("DNA Selector running on http://127.0.0.1:5076/", flush=True)
    app.run(host="127.0.0.1", port=5076, debug=False)
