FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY model_reg.pkl .
CMD [ "python", "-u", "app.py" ]