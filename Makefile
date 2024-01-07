.PHONY: lint code-style type-check test

lint:
poetry run pylint --recursive=y main.py streamlit_app.py streamlit_admin_app.py celery_app.py tests config utils celery_tasks

code-style:
poetry run isort --check-only --diff .
poetry run black --check .

type-check:
poetry run mypy --check-untyped-defs .
poetry run pyright

test:
poetry run python -m unittest discover -s tests
