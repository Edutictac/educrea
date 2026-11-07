FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY educrea_api ./educrea_api
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir .
RUN useradd --system --uid 10001 educrea
COPY entrypoint.py ./entrypoint.py
CMD ["python", "/app/entrypoint.py"]

