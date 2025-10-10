FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY ./data/user_data.csv ./data/user_data.csv
CMD [ "python", "-u", "app.py" ]