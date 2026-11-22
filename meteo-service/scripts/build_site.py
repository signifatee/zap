"""Сборка статического HTML-отчёта.

Запуск:  uv run python scripts/build_site.py [каталог_data] [выходной_html]
По умолчанию: data -> dist/index.html

Результат — один самодостаточный файл: данные и Plotly.js встроены в него,
страница работает офлайн (кроме вкладки «Прогноз», которая обращается
к Open-Meteo из браузера). Новый файл наблюдений того же формата ->
просто положить в data/ и пересобрать отчёт этой же командой.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meteo.site_data import build_site_data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "web" / "template.html"


def get_plotly_js() -> str:
    """Plotly.js локально (из пакета plotly) или с CDN как запасной вариант."""
    try:
        from plotly.offline import get_plotlyjs
        return get_plotlyjs()
    except ImportError:
        import requests
        url = "https://cdn.plot.ly/plotly-2.35.2.min.js"
        return requests.get(url, timeout=30).text


def get_xlsx_js() -> str:
    """SheetJS для экспорта Excel. Если CDN недоступен — пустая строка,
    кнопка «Скачать Excel» в странице автоматически откатится на CSV."""
    try:
        import requests
        url = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"
        return requests.get(url, timeout=30).text
    except Exception:
        return ""


def main() -> None:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("dist/index.html")

    print(f"Читаю данные из {data_dir} …")
    site_data = build_site_data(data_dir)
    n = {k: len(v["daily"]) for k, v in site_data["stations"].items()}
    print("Суточных записей по станциям:", n)

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__DATA__", json.dumps(site_data, ensure_ascii=False))
    print("Встраиваю Plotly.js …")
    html = html.replace("/*__PLOTLY_JS__*/", get_plotly_js())
    xlsx_js = get_xlsx_js()
    html = html.replace("/*__XLSX_JS__*/", xlsx_js)
    print("SheetJS (Excel-экспорт):", "встроен" if xlsx_js else "недоступен, будет CSV")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    size_mb = out.stat().st_size / 1e6
    print(f"Готово: {out} ({size_mb:.1f} МБ) — открывается двойным кликом, интернет не нужен.")


if __name__ == "__main__":
    main()
