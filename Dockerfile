# ---- Build Stage ----
FROM python:3.12-slim as builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --user -r requirements.txt

# ---- Final Stage ----
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

ENV FLASK_ENV=production

# Expose port for Fly.io
EXPOSE 8080

# Run Gunicorn with eventlet for Flask-SocketIO
CMD ["gunicorn", "main:app", "-k", "eventlet", "--bind", "0.0.0.0:8080", "--timeout", "60"] 