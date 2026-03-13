# codeman

Стартовий Python-проєкт у репозиторії з уже підключеним BMAD workspace.

## Що тут є

- `src/codeman/` - Python package з мінімальним CLI entry point
- `tests/` - базові smoke-тести без зовнішніх залежностей
- `_bmad/` - BMAD конфігурація та workflow-артефакти
- `_bmad-output/` - вихідні артефакти BMAD-процесу
- `.agents/skills/` - локальні skills, які підхоплює агентний workflow

## Швидкий старт

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m codeman --name BMAD
```

## BMAD

Цей репозиторій уже підготовлений під BMAD-процес. Кодова частина живе окремо в `src/`, а planning / implementation artifacts залишаються в `_bmad` та `_bmad-output`.

