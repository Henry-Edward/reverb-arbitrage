"""
Reverb Arbitrage - Web Dashboard
Flask app serving the settings UI and scan history.
Run locally with: python web/app.py
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Allow importing bot modules
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from flask import Flask, render_template_string, request, jsonify, redirect
from config_loader import load_config, save_config

app = Flask(__name__)

# ── HTML Template ─────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reverb Arbitrage — Control Panel</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0b; --surface: #111114; --surface2: #18181d;
    --border: #2a2a32; --accent: #ff5533; --accent2: #ffaa00;
    --text: #e8e8ec; --muted: #666678; --green: #2ecc71; --red: #e74c3c;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; min-height: 100vh; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
  .logo { font-family: 'Bebas Neue', sans-serif; font-size: 26px; letter-spacing: 3px; color: var(--accent); }
  .logo span { color: var(--text); }
  .subtitle { font-family: 'DM Mono', monospace; font-size: 11px; color: var(--muted); letter-spacing: 1px; border-left: 1px solid var(--border); padding-left: 16px; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; margin-left: auto; }
  .status-dot.active { background: var(--green); box-shadow: 0 0 8px var(--green); }
  .status-dot.inactive { background: var(--muted); }
  .container { max-width: 1100px; margin: 0 auto; padding: 32px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .card { background: var(--surface); border: 1px solid var(--border); padding: 24px; }
  .card-title { font-family: 'DM Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: var(--muted); margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
  .card-title::after { content: ''; flex: 1; height: 1px; background: var(--border); }
  label { font-family: 'DM Mono', monospace; font-size: 11px; color: var(--muted); display: block; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
  input[type=text], input[type=number], input[type=password] {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); font-family: 'DM Mono', monospace; font-size: 14px;
    padding: 10px 12px; outline: none; transition: border-color 0.2s; margin-bottom: 16px;
  }
  input:focus { border-color: var(--accent); }
  .toggle { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
  .toggle-switch { position: relative; width: 44px; height: 24px; cursor: pointer; flex-shrink: 0; }
  .toggle-switch input { opacity: 0; width: 0; height: 0; }
  .toggle-slider { position: absolute; inset: 0; background: var(--border); transition: 0.2s; border-radius: 24px; }
  .toggle-slider:before { content: ''; position: absolute; height: 18px; width: 18px; left: 3px; bottom: 3px; background: var(--muted); transition: 0.2s; border-radius: 50%; }
  input:checked + .toggle-slider { background: rgba(46,204,113,0.3); }
  input:checked + .toggle-slider:before { transform: translateX(20px); background: var(--green); }
  .toggle-label { font-family: 'DM Mono', monospace; font-size: 12px; color: var(--text); }
  .btn { background: var(--accent); color: white; border: none; font-family: 'Bebas Neue', sans-serif; font-size: 16px; letter-spacing: 2px; padding: 12px 24px; cursor: pointer; transition: all 0.15s; }
  .btn:hover { background: #ff7755; }
  .btn-sm { font-size: 12px; padding: 8px 16px; letter-spacing: 1px; }
  .btn-danger { background: var(--red); }
  .btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--muted); font-family: 'DM Mono', monospace; font-size: 11px; padding: 8px 14px; cursor: pointer; letter-spacing: 1px; }
  .btn-ghost:hover { border-color: var(--accent); color: var(--accent); }
  .watches-list { display: flex; flex-direction: column; gap: 12px; }
  .watch-item { background: var(--surface2); border: 1px solid var(--border); padding: 16px; position: relative; }
  .watch-item.disabled { opacity: 0.5; }
  .watch-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .watch-query { font-family: 'DM Mono', monospace; font-size: 14px; font-weight: 500; flex: 1; }
  .watch-fields { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  .watch-fields input { margin-bottom: 0; }
  .watch-notes { font-family: 'DM Mono', monospace; font-size: 10px; color: var(--muted); margin-top: 8px; }
  .add-watch { border: 1px dashed var(--border); padding: 16px; text-align: center; cursor: pointer; transition: all 0.15s; font-family: 'DM Mono', monospace; font-size: 12px; color: var(--muted); }
  .add-watch:hover { border-color: var(--accent); color: var(--accent); }
  .toast { position: fixed; bottom: 24px; right: 24px; background: var(--green); color: white; font-family: 'DM Mono', monospace; font-size: 13px; padding: 12px 20px; transform: translateY(80px); transition: transform 0.3s; z-index: 9999; }
  .toast.show { transform: translateY(0); }
  .toast.error { background: var(--red); }
  .stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border); margin-bottom: 24px; }
  .stat-box { background: var(--surface2); padding: 16px; text-align: center; }
  .stat-num { font-family: 'Bebas Neue', sans-serif; font-size: 28px; color: var(--accent); }
  .stat-lbl { font-family: 'DM Mono', monospace; font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
  .section-gap { margin-top: 24px; }
  .help-text { font-family: 'DM Mono', monospace; font-size: 10px; color: var(--muted); margin-top: -12px; margin-bottom: 16px; line-height: 1.6; }
  a { color: var(--accent); }
  .run-btn-wrap { display: flex; gap: 12px; align-items: center; margin-top: 20px; }
  #runStatus { font-family: 'DM Mono', monospace; font-size: 11px; color: var(--muted); }
  .full-width { grid-column: 1 / -1; }
  .condition-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
  .cond-tag { font-family: 'DM Mono', monospace; font-size: 10px; padding: 4px 10px; border: 1px solid var(--border); cursor: pointer; color: var(--muted); user-select: none; }
  .cond-tag.selected { border-color: var(--accent); color: var(--accent); background: rgba(255,85,51,0.1); }
  @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } .watch-fields { grid-template-columns: 1fr 1fr; } }
</style>
</head>
<body>

<header>
  <div class="logo">Reverb<span>Arb</span></div>
  <div class="subtitle">Control Panel</div>
  <div class="status-dot {{ 'active' if config.ntfy_topic else 'inactive' }}" title="{{ 'Notifications configured' if config.ntfy_topic else 'No ntfy topic set' }}"></div>
</header>

<div class="container">

  <div class="stat-row">
    <div class="stat-box">
      <div class="stat-num">{{ watches_enabled }}</div>
      <div class="stat-lbl">Active Watches</div>
    </div>
    <div class="stat-box">
      <div class="stat-num">${{ "%.0f"|format(config.default_min_profit) }}</div>
      <div class="stat-lbl">Default Min Profit</div>
    </div>
    <div class="stat-box">
      <div class="stat-num">{{ seen_count }}</div>
      <div class="stat-lbl">Listings Scanned</div>
    </div>
  </div>

  <form id="mainForm">
  <div class="grid">

    <!-- Global Settings -->
    <div class="card">
      <div class="card-title">Global Settings</div>

      <label>ntfy.sh Topic (your unique alert channel)</label>
      <input type="text" name="ntfy_topic" value="{{ config.ntfy_topic }}" placeholder="my-reverb-alerts-xyz123">
      <div class="help-text">
        1. Download the ntfy app (iOS/Android) or go to ntfy.sh<br>
        2. Subscribe to any topic name you make up (make it unique!)<br>
        3. Paste that topic name here — alerts will appear on your phone instantly
      </div>

      <label>Default Min Profit ($)</label>
      <input type="number" name="default_min_profit" value="{{ config.default_min_profit }}" step="1" min="0">
      <div class="help-text">Used when a watch doesn't have its own min profit set. Start loose (~$10) then tighten.</div>

      <div class="toggle">
        <label class="toggle-switch">
          <input type="checkbox" name="skip_red_flags" {{ 'checked' if config.skip_red_flags }}>
          <span class="toggle-slider"></span>
        </label>
        <span class="toggle-label">Auto-skip "as-is", "for parts", "untested" listings</span>
      </div>

      <div class="toggle">
        <label class="toggle-switch">
          <input type="checkbox" name="use_price_guide" {{ 'checked' if config.use_price_guide }}>
          <span class="toggle-slider"></span>
        </label>
        <span class="toggle-label">Use Price Guide API (real sold data — recommended)</span>
      </div>

      <div class="run-btn-wrap">
        <button type="button" class="btn btn-sm" onclick="runScan()">▶ Run Scan Now</button>
        <span id="runStatus"></span>
      </div>
    </div>

    <!-- AI Settings (future) -->
    <div class="card">
      <div class="card-title">AI Scoring (Future)</div>
      <div class="toggle">
        <label class="toggle-switch">
          <input type="checkbox" name="use_ai" {{ 'checked' if config.get('use_ai') }} disabled>
          <span class="toggle-slider"></span>
        </label>
        <span class="toggle-label" style="color:var(--muted)">Enable AI deal analysis (coming soon)</span>
      </div>
      <div class="help-text" style="margin-top:8px;">
        When enabled, Claude will analyze each listing's title and description for nuanced signals beyond keyword matching — estimating how quickly it'll sell, spotting undervalued vintage gear, and flagging listings where the condition description doesn't match the price.<br><br>
        Will use Anthropic API (fractions of a cent per listing).
      </div>

      <label style="margin-top:16px;">Anthropic API Key (when ready)</label>
      <input type="password" name="anthropic_api_key" value="{{ config.get('anthropic_api_key', '') }}" placeholder="sk-ant-...">

      <label>AI Min Confidence Score (0–100)</label>
      <input type="number" name="ai_min_confidence" value="{{ config.get('ai_min_confidence', 70) }}" min="0" max="100">
      <div class="help-text">Only fire alerts when AI confidence is above this threshold.</div>
    </div>

    <!-- Watches -->
    <div class="card full-width">
      <div class="card-title">Search Watches</div>
      <div class="watches-list" id="watchesList">
        {% for i, watch in watches %}
        <div class="watch-item {{ '' if watch.enabled else 'disabled' }}" data-index="{{ i }}">
          <div class="watch-header">
            <label class="toggle-switch" style="margin-bottom:0">
              <input type="checkbox" class="watch-enabled" {{ 'checked' if watch.enabled }} onchange="toggleWatch(this)">
              <span class="toggle-slider"></span>
            </label>
            <input type="text" class="watch-query" value="{{ watch.query }}" placeholder="Search query..." style="background:transparent;border:none;border-bottom:1px solid var(--border);padding:4px 0;font-size:15px;margin-bottom:0;">
            <button type="button" class="btn-ghost" onclick="removeWatch(this)" style="flex-shrink:0">Remove</button>
          </div>
          <div class="watch-fields">
            <div>
              <label>Min Profit ($)</label>
              <input type="number" class="watch-min-profit" value="{{ watch.min_profit }}" placeholder="{{ config.default_min_profit }}" step="1" min="0">
            </div>
            <div>
              <label>Max Buy Price ($)</label>
              <input type="number" class="watch-max-buy" value="{{ watch.max_buy_price or '' }}" placeholder="No limit" step="5" min="0">
            </div>
            <div>
              <label>Scan Limit</label>
              <input type="number" class="watch-scan-limit" value="{{ watch.scan_limit or 30 }}" min="5" max="100">
            </div>
          </div>
          <div>
            <label style="margin-top:8px;">Filter by Condition (leave empty for all)</label>
            <div class="condition-tags">
              {% for slug, label in conditions %}
              <div class="cond-tag {{ 'selected' if slug in (watch.condition_slugs or []) }}" data-slug="{{ slug }}" onclick="toggleCondition(this)">{{ label }}</div>
              {% endfor %}
            </div>
          </div>
          <div class="watch-notes">{{ watch.notes or '' }}</div>
        </div>
        {% endfor %}
      </div>
      <div class="add-watch section-gap" onclick="addWatch()">+ Add New Watch</div>
    </div>

  </div>

  <div style="margin-top:24px; display:flex; gap:12px;">
    <button type="button" class="btn" onclick="saveConfig()">Save Settings</button>
    <button type="button" class="btn-ghost" onclick="resetSeen()">Clear Seen Listings</button>
  </div>
  </form>

</div>

<div class="toast" id="toast"></div>

<script>
const CONDITIONS = [
  ["brand-new", "Brand New"], ["mint-inventory", "Mint (Dealer)"], ["mint", "Mint"],
  ["excellent", "Excellent"], ["very-good", "Very Good"],
  ["good", "Good"], ["fair", "Fair"], ["poor", "Poor"]
];

function toggleCondition(el) {
  el.classList.toggle('selected');
}

function toggleWatch(checkbox) {
  const item = checkbox.closest('.watch-item');
  item.classList.toggle('disabled', !checkbox.checked);
}

function addWatch() {
  const list = document.getElementById('watchesList');
  const idx = list.children.length;
  const condTags = CONDITIONS.map(([slug, label]) =>
    `<div class="cond-tag" data-slug="${slug}" onclick="toggleCondition(this)">${label}</div>`
  ).join('');

  const html = `
    <div class="watch-item" data-index="${idx}">
      <div class="watch-header">
        <label class="toggle-switch" style="margin-bottom:0">
          <input type="checkbox" class="watch-enabled" checked onchange="toggleWatch(this)">
          <span class="toggle-slider"></span>
        </label>
        <input type="text" class="watch-query" value="" placeholder="e.g. Fender Telecaster MIM" style="background:transparent;border:none;border-bottom:1px solid var(--border);padding:4px 0;font-size:15px;margin-bottom:0;">
        <button type="button" class="btn-ghost" onclick="removeWatch(this)" style="flex-shrink:0">Remove</button>
      </div>
      <div class="watch-fields">
        <div><label>Min Profit ($)</label><input type="number" class="watch-min-profit" placeholder="15" step="1" min="0"></div>
        <div><label>Max Buy Price ($)</label><input type="number" class="watch-max-buy" placeholder="No limit" step="5" min="0"></div>
        <div><label>Scan Limit</label><input type="number" class="watch-scan-limit" value="30" min="5" max="100"></div>
      </div>
      <div>
        <label style="margin-top:8px;">Filter by Condition</label>
        <div class="condition-tags">${condTags}</div>
      </div>
    </div>`;
  list.insertAdjacentHTML('beforeend', html);
}

function removeWatch(btn) {
  btn.closest('.watch-item').remove();
}

function collectConfig() {
  const watches = [];
  document.querySelectorAll('.watch-item').forEach(item => {
    const condSlugs = [...item.querySelectorAll('.cond-tag.selected')].map(t => t.dataset.slug);
    watches.push({
      query: item.querySelector('.watch-query').value.trim(),
      enabled: item.querySelector('.watch-enabled').checked,
      min_profit: parseFloat(item.querySelector('.watch-min-profit').value) || null,
      max_buy_price: parseFloat(item.querySelector('.watch-max-buy').value) || null,
      scan_limit: parseInt(item.querySelector('.watch-scan-limit').value) || 30,
      condition_slugs: condSlugs,
      notes: item.querySelector('.watch-notes')?.textContent || '',
    });
  });

  const f = document.querySelector('form');
  return {
    ntfy_topic: f.ntfy_topic.value.trim(),
    default_min_profit: parseFloat(f.default_min_profit.value) || 15,
    skip_red_flags: f.skip_red_flags.checked,
    use_price_guide: f.use_price_guide.checked,
    use_ai: false, // future
    anthropic_api_key: f.anthropic_api_key.value.trim(),
    ai_min_confidence: parseInt(f.ai_min_confidence.value) || 70,
    watches,
  };
}

async function saveConfig() {
  const config = collectConfig();
  const resp = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(config)
  });
  const data = await resp.json();
  showToast(data.ok ? '✓ Settings saved' : '✗ ' + data.error, !data.ok);
}

async function runScan() {
  const status = document.getElementById('runStatus');
  status.textContent = 'Running...';
  // Save first
  await saveConfig();
  const resp = await fetch('/api/run', {method: 'POST'});
  const data = await resp.json();
  status.textContent = data.ok ? `Done — ${data.alerts} alert(s) fired` : 'Error: ' + data.error;
  setTimeout(() => status.textContent = '', 8000);
}

async function resetSeen() {
  if (!confirm('Clear all seen listing IDs? The next scan will re-evaluate everything.')) return;
  const resp = await fetch('/api/reset-seen', {method: 'POST'});
  const data = await resp.json();
  showToast(data.ok ? '✓ Cleared' : '✗ Error');
}

function showToast(msg, isError=false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => t.className = 'toast', 3000);
}
</script>
</body>
</html>
"""

CONDITIONS = [
    ("brand-new", "Brand New"), ("mint-inventory", "Mint (Dealer)"), ("mint", "Mint"),
    ("excellent", "Excellent"), ("very-good", "Very Good"),
    ("good", "Good"), ("fair", "Fair"), ("poor", "Poor"),
]

SEEN_FILE = Path(__file__).parent.parent / "bot" / "seen_listings.json"


@app.route("/")
def index():
    config = load_config()
    watches = list(enumerate(config.get("watches", [])))
    watches_enabled = sum(1 for _, w in watches if w.get("enabled", True))

    seen_count = 0
    if SEEN_FILE.exists():
        try:
            data = json.loads(SEEN_FILE.read_text())
            seen_count = len(data.get("ids", []))
        except Exception:
            pass

    return render_template_string(
        HTML,
        config=config,
        watches=watches,
        watches_enabled=watches_enabled,
        seen_count=seen_count,
        conditions=CONDITIONS,
    )


@app.route("/api/config", methods=["POST"])
def api_save_config():
    try:
        config = request.get_json()
        save_config(config)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/run", methods=["POST"])
def api_run():
    try:
        # Import here to avoid circular at startup
        sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))
        from scanner import run_scan
        alerts = run_scan()
        return jsonify({"ok": True, "alerts": alerts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/reset-seen", methods=["POST"])
def api_reset_seen():
    try:
        if SEEN_FILE.exists():
            SEEN_FILE.write_text(json.dumps({"ids": []}))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🎸 Reverb Arbitrage Dashboard → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
