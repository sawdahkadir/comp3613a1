# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
COPY ./manage.py ./
COPY ./vendor ./vendor
COPY ./.env.example ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Create tables and seed the demo users before serving, so a fresh database is
# never left empty on boot. --no-drop keeps existing rows across restarts.
CMD ["sh", "-c", "python manage.py init --no-drop && python manage.py run --host 0.0.0.0 --port 8000"]
