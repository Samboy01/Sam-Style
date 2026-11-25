FROM python:3.13-slim

WORKDIR /app

# Installera beroenden först, så att Docker kan återanvända lagret när bara koden ändras.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
