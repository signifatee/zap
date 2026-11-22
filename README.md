# zap

```bash
uv sync
uv run python scripts/build_site.py data dist/index.html   # собрать отчёт
uv run python scripts/validate_coverage.py data      # сверка с эталоном
uv run pytest                                        # тесты ядра
```