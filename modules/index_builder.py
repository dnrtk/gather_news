import json
import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_PATTERN = re.compile(r"(\d{8})_(morning|evening|weekly)\.html$")
_SLOT_ORDER = {"morning": 0, "evening": 1, "weekly": 2}
_SLOT_LABELS = {"morning": "朝刊", "evening": "夕刊", "weekly": "週刊"}
_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def update_index(pages_dir: Path, index_path: Path, project_root: Path) -> None:
    entries = _scan_entries(pages_dir, project_root)

    _write_nav_json(entries, project_root)
    _write_index_html(entries, index_path)

    logger.info("index: index.html / nav.json 更新")


# ── Internal ────────────────────────────────────────────────────────────────

def _scan_entries(pages_dir: Path, project_root: Path) -> list[dict]:
    entries = []
    for html_path in pages_dir.glob("**/*.html"):
        entry = _parse_entry(html_path, project_root)
        if entry:
            entries.append(entry)
    entries.sort(key=lambda e: (e["date_str"], _SLOT_ORDER.get(e["slot"], 9)), reverse=True)
    return entries


def _parse_entry(html_path: Path, project_root: Path) -> dict | None:
    m = _PATTERN.search(html_path.name)
    if not m:
        return None
    date_str, slot = m.group(1), m.group(2)
    try:
        d = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except ValueError:
        return None
    rel_path = str(html_path.relative_to(project_root)).replace("\\", "/")
    return {
        "date_str": date_str,
        "date": d,
        "slot": slot,
        "label": _SLOT_LABELS.get(slot, slot),
        "is_weekly": slot == "weekly",
        "rel_path": rel_path,
        "display": f"{d.month:02d}/{d.day:02d}（{_WEEKDAY_JA[d.weekday()]}）",
    }


def _write_nav_json(entries: list[dict], project_root: Path) -> None:
    # group by date_str, newest first
    groups: dict[str, dict] = {}
    for e in entries:
        if e["date_str"] not in groups:
            groups[e["date_str"]] = {
                "display": e["display"],
                "pages": [],
            }
        groups[e["date_str"]]["pages"].append({
            "label": e["label"],
            "path": e["rel_path"],
            "is_weekly": e["is_weekly"],
        })

    nav = [{"date": k, "display": v["display"], "pages": v["pages"]} for k, v in groups.items()]
    nav_path = project_root / "nav.json"
    nav_path.write_text(json.dumps(nav, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_index_html(entries: list[dict], index_path: Path) -> None:
    # Build sidebar item list for index.html (inline, no fetch needed at root)
    nav_items = ""
    current_date = None
    for e in entries:
        if e["date_str"] != current_date:
            if current_date is not None:
                nav_items += "    </div>\n"
            current_date = e["date_str"]
            nav_items += f'    <div class="nav-group"><div class="nav-date">{e["display"]}</div>\n'
        badge = ' <span class="nav-badge">週刊</span>' if e["is_weekly"] else ""
        nav_items += f'      <a href="{e["rel_path"]}" class="nav-link">{e["label"]}{badge}</a>\n'
    if current_date is not None:
        nav_items += "    </div>\n"

    html = f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ニュースダイジェスト</title>
  <style>
    :root {{
      --sidebar-w: 240px;
      --bg: #ffffff; --bg-sidebar: #f3f4f6; --fg: #111827;
      --fg-muted: #6b7280; --accent: #2563eb; --border: #e5e7eb; --btn-bg: #e5e7eb;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #111827; --bg-sidebar: #1f2937; --fg: #f9fafb;
        --fg-muted: #9ca3af; --accent: #60a5fa; --border: #374151; --btn-bg: #374151;
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--fg); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.7; }}
    #hamburger {{
      position: fixed; top: .75rem; left: .75rem; z-index: 300;
      width: 36px; height: 36px; border: none; border-radius: 6px;
      background: var(--btn-bg); color: var(--fg); font-size: 1.2rem; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
    }}
    #sidebar {{
      position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-w);
      background: var(--bg-sidebar); border-right: 1px solid var(--border);
      overflow-y: auto; z-index: 200; display: flex; flex-direction: column;
      transform: translateX(calc(-1 * var(--sidebar-w))); transition: transform .25s ease;
    }}
    #sidebar.open {{ transform: translateX(0); }}
    #sidebar.closed {{ transform: translateX(calc(-1 * var(--sidebar-w))); }}
    .sidebar-title {{ padding: .85rem 1rem .85rem 3.5rem; font-weight: 700; font-size: .9rem; border-bottom: 1px solid var(--border); }}
    #nav-list {{ flex: 1; padding: .5rem 0; }}
    .nav-group {{ padding: .15rem 0; }}
    .nav-date {{ padding: .5rem 1rem .2rem; font-size: .72rem; color: var(--fg-muted); font-weight: 600; letter-spacing: .04em; }}
    .nav-link {{ display: flex; align-items: center; gap: .35rem; padding: .35rem 1rem .35rem 1.5rem; font-size: .875rem; color: var(--fg); text-decoration: none; border-radius: 0 4px 4px 0; margin-right: .5rem; }}
    .nav-link:hover {{ background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); }}
    .nav-badge {{ font-size: .65rem; padding: .05rem .35rem; border-radius: 3px; background: #dbeafe; color: #1d4ed8; }}
    @media (prefers-color-scheme: dark) {{ .nav-badge {{ background: #1e3a5f; color: #93c5fd; }} }}
    #overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 150; }}
    #overlay.show {{ display: block; }}
    #main {{ min-height: 100vh; padding: 1.5rem 1rem 2rem 3.5rem; transition: margin-left .25s ease; }}
    .welcome {{ max-width: 520px; padding-top: 2rem; }}
    .welcome h1 {{ font-size: 1.5rem; margin-bottom: .75rem; }}
    .welcome p {{ color: var(--fg-muted); font-size: .95rem; }}
    @media (min-width: 768px) {{
      #sidebar {{ transform: translateX(0); }}
      #sidebar.closed {{ transform: translateX(calc(-1 * var(--sidebar-w))); }}
      #main {{ margin-left: var(--sidebar-w); padding-left: 2rem; }}
      #main.sidebar-closed {{ margin-left: 0; padding-left: 3.5rem; }}
      #overlay {{ display: none !important; }}
    }}
  </style>
</head>
<body>
  <button id="hamburger" aria-label="メニュー">☰</button>
  <aside id="sidebar">
    <div class="sidebar-title">ニュースダイジェスト</div>
    <nav id="nav-list">
{nav_items}    </nav>
  </aside>
  <div id="overlay"></div>
  <main id="main">
    <div class="welcome">
      <h1>ニュースダイジェスト</h1>
      <p>左のサイドバーから日付を選択してください。</p>
    </div>
  </main>
  <script>
    const hamburger = document.getElementById('hamburger');
    const sidebar   = document.getElementById('sidebar');
    const overlay   = document.getElementById('overlay');
    const main      = document.getElementById('main');
    function isMobile() {{ return window.innerWidth < 768; }}
    function isOpen()   {{ return sidebar.classList.contains('open') || (!isMobile() && !sidebar.classList.contains('closed')); }}
    function openSidebar()  {{ sidebar.classList.add('open'); sidebar.classList.remove('closed'); if (isMobile()) overlay.classList.add('show'); else main.classList.remove('sidebar-closed'); }}
    function closeSidebar() {{ sidebar.classList.remove('open'); sidebar.classList.add('closed'); overlay.classList.remove('show'); if (!isMobile()) main.classList.add('sidebar-closed'); }}
    if (isMobile()) closeSidebar(); else openSidebar();
    hamburger.addEventListener('click', () => isOpen() ? closeSidebar() : openSidebar());
    overlay.addEventListener('click', closeSidebar);
  </script>
</body>
</html>
"""
    index_path.write_text(html, encoding="utf-8")
