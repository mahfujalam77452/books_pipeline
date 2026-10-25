FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BOOKS_OUTPUT_DIR=/app/output

WORKDIR /app

# Install dependencies first so Docker can cache this layer.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Non-root user and writable directories (also used to initialise named volumes).
RUN useradd --create-home --uid 1000 scrapy \
    && mkdir -p /app/output /var/lib/scrapyd /etc/scrapyd

COPY scrapyd.conf /etc/scrapyd/scrapyd.conf
COPY . .

# Fix Windows line endings in the entrypoint and set permissions.
RUN sed -i 's/\r$//' docker/entrypoint.sh \
    && chmod +x docker/entrypoint.sh \
    && chown -R scrapy:scrapy /app /var/lib/scrapyd

USER scrapy

EXPOSE 6800

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6800/daemonstatus.json', timeout=3)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]