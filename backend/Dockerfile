FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN groupadd --system app && useradd --system --gid app app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read() else 1)"

# Migrations are a separate one-shot `migrate` service (python -m app.migrate) that
# runs under a Postgres advisory lock before this container starts. Never migrate
# on API boot: replicas would race and a failed upgrade would leave a half-started API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
