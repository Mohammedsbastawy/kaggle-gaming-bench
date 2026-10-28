from IPython.display import display, HTML
from pathlib import Path
port_file = Path('/tmp/kaggle-game-dev-bench/preferred-stream-port')
stream_port = port_file.read_text().strip() if port_file.is_file() else '8080'
html = r"""
<div style="font:16px system-ui, -apple-system, sans-serif;padding:24px;border-radius:16px;background:#0d1729;color:#f4f8ff;max-width:760px;box-shadow:0 8px 24px rgba(0,0,0,0.5)">
  <h2 style="margin-top:0;color:#4dcdf2;display:flex;align-items:center;gap:10px">
    <span>🎮</span> 7BZ Dev Cloud Game
  </h2>
  <p style="color:#b0c4de;line-height:1.5">
    Controller-first cloud game library with <b>Steam</b>, <b>Heroic</b>, <b>Legendary</b>, <b>Minigalaxy</b>, and <b>Lutris</b>.
  </p>

  <div style="background:#132238;padding:16px;border-radius:12px;margin:16px 0;border-left:4px solid #4dcdf2">
    <b>Connection Steps:</b>
    <ol style="margin:8px 0 0 18px;padding:0;color:#c8daf0;line-height:1.6">
      <li>In Kaggle, open <b>Run → Kaggle Jupyter Server</b> and copy the <b>VSCode Compatible URL</b>.</li>
      <li>Paste it into the field below and click <b>Connect to Stream</b>.</li>
      <li>Open the 7BZ HUD and select <b>Audio Unmute</b> for Opus stereo audio.</li>
      <li>For FPS mouse look, use a normal Chrome or Edge tab and enable <b>Gaming Mode</b>; embedded viewers may block pointer lock.</li>
      <li>Set your local keyboard layout to English (EN), then use mouse, keyboard, or gamepad navigation.</li>
    </ol>
  </div>

  <div style="margin:16px 0">
    <input id="kaggle-base" type="text" style="width:96%;padding:12px;border-radius:8px;border:1px solid #233b5d;background:#080e1a;color:#fff;font-size:14px" placeholder="Paste VSCode Compatible URL (https://...)">
    <button id="kaggle-open" style="margin-top:12px;padding:12px 24px;border-radius:8px;border:none;background:#4dcdf2;color:#081325;font-weight:bold;font-size:15px;cursor:pointer">Connect to Stream</button>
  </div>
  <p id="kaggle-result" style="font-size:13px;color:#9bdcf5;margin-top:6px"></p>

  <div style="border-top:1px solid #1a2a44;padding-top:14px;margin-top:18px;font-size:13px;color:#8ba2c4">
    <b>Empirical Hardware & Security Reality:</b>
    <ul style="margin:6px 0 0 16px;padding:0;line-height:1.5">
      <li><b>User state:</b> Storefronts run as <code>gamer</code>; their temporary credentials and caches are under <code>/home/gamer</code>.</li>
      <li><b>Storefront EULA:</b> Valve's Subscriber Agreement is presented to the user directly in the Steam GUI on first launch.</li>
      <li><b>GPU path:</b> GPU 0 renders the direct NVIDIA Xorg desktop and games; GPU 1 encodes the unified 8080 stream with NVENC.</li>
      <li><b>Custom Builds:</b> Upload test Linux builds into <code style="color:#4dcdf2">/tmp/game-builds</code> via Selkies Files panel.</li>
    </ul>
  </div>
</div>
<script>
document.getElementById('kaggle-open').onclick = function () {
  try {
    const raw = document.getElementById('kaggle-base').value.trim();
    if (!raw) throw new Error('Please paste your URL.');
    const u = new URL(raw);
    let p = u.pathname.replace(/\/(tree|lab|notebooks)(\/.*)?$/, '/');
    if (!p.endsWith('/')) p += '/';
    u.pathname = p + 'proxy/__STREAM_PORT__/';
    const target = u.toString();
    document.getElementById('kaggle-result').textContent = 'Opening authenticated Jupyter proxy route...';
    window.open(target, '_blank', 'noopener,noreferrer');
  } catch (e) {
    document.getElementById('kaggle-result').textContent = 'Please enter a valid https:// Kaggle Jupyter Server URL.';
  }
};
</script>
"""
display(HTML(html.replace('__STREAM_PORT__', stream_port)))
