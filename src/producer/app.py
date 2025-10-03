import os
import json
import time
import random
import uuid 
from kafka import KafkaProducer
from faker import Faker

# Konfiguracija
KAFKA_BROKER_URL = os.environ.get('KAFKA_BROKER_URL')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'transaction_events')

if not KAFKA_BROKER_URL:
    print("FATAL: KAFKA_BROKER_URL nije definisan.")
    exit(1)

fake = Faker()

def serializer(message):
    return json.dumps(message).encode('utf-8')


try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER_URL],
        value_serializer=serializer
    )
    print(f"INFO: Uspešno povezan sa Kafka brokerom na {KAFKA_BROKER_URL}")
except Exception as e:
    print(f"FATAL: Greška prilikom povezivanja na Kafku: {e}")
    exit(1)


def generate_event_data():
    return {
        "event_id": f"evt_{uuid.uuid4()}",
        "user_id": f"{uuid.uuid4()}", 
        "session_id": f"sess_{uuid.uuid4()}",
        "product": random.choice(['sportsbook', 'casino', 'virtual']),
        "tx_type": random.choice(['bet', 'win', 'deposit', 'withdraw']), 
        "currency": fake.currency_code(),
        "amount": random.randint(10, 5000),
        "event_time": time.time(),
        "metadata": {"sport":"football","market":"1x2"}
    }


def start_streaming():
    print(f"INFO: Pokrećem striming transakcionih događaja na temu '{KAFKA_TOPIC}'...")

    try:
        while True: 
            event_data = generate_event_data()
            
            if event_data:
                key = str(event_data['user_id']).encode('utf-8')

                producer.send(
                    topic=KAFKA_TOPIC,
                    value=event_data,
                    key=key
                )
                
                print(f"-> POSLATO: {event_data['tx_type']} - event_id {event_data['event_id']}")

            producer.flush()

            time.sleep(random.uniform(0.1, 0.5))

    except KeyboardInterrupt:
        print("\nINFO: Striming zaustavljen od strane korisnika.")
    except Exception as e:
        print(f"ERROR: Neočekivana greška tokom striminga: {e}")
    finally:
        producer.close()
        print("INFO: Kafka producent zatvoren.")


if __name__ == '__main__':
    time.sleep(10)
    start_streaming()
