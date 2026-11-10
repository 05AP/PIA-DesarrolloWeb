# Dockerfile para despliegue en la nube (Render, Railway, Fly.io, AWS)
FROM python:3.11-slim

# Evitar escritura de bytecode y habilitar buffer inmediato de logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2-binary trae libpq incluido: no se requieren compiladores ni paquetes del sistema
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar solo el código necesario para ejecutar la API
COPY app ./app
COPY frontend ./frontend

# Ejecutar con un usuario sin privilegios (buena práctica de seguridad en contenedores)
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)"

# Comando de ejecución con variable PORT dinámica
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
