FROM python:3.13-slim
ENV DEBIAN_FRONTEND=noninteractive
# System tools used inside bubblewrap: document conversion, PDF, OCR, PNG rendering and the sandbox itself.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fontconfig fonts-dejavu-core \
    pandoc poppler-utils tesseract-ocr tesseract-ocr-spa tesseract-ocr-cat \
    texlive-xetex texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended lmodern \
    chromium bubblewrap \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY educrea_api ./educrea_api
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir .
RUN useradd --system --uid 10001 educrea
COPY entrypoint.py ./entrypoint.py
CMD ["python", "/app/entrypoint.py"]

