
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copier les dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code du backend
COPY src/ ./src/

# Copier les migrations Alembic
COPY migrations/ ./migrations/
COPY alembic.ini .

# Exposer le port FastAPI
EXPOSE 8000

# Démarrer FastAPI
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
