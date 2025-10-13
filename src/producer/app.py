import os
import json
import random
import uuid 
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from kafka import KafkaProducer
from faker import Faker

KAFKA_BROKER_URL = os.environ.get('KAFKA_BROKER_URL')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'transaction_events')

csv_file_path = 'data/user_data.csv'
users_df = pd.read_csv(csv_file_path)

alpha = 1.16

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

def choose_user():
    transaction_probabilities = {
        'whale': 0.05,
        'dolphin': 0.15,
        'minnow': 0.80,
    }

    user_groups = ['whale', 'dolphin', 'minnow']
    group_weights = np.array([transaction_probabilities[group] for group in user_groups])

    chosen_group = np.random.choice(user_groups, p=group_weights)
    
    # Izbor nasumičnog korisnika iz izabrane grupe
    chosen_user_data = users_df[users_df['user_group'] == chosen_group].sample(n=1)
    chosen_user_id = chosen_user_data['user_id'].iloc[0]

    return chosen_user_id, chosen_group

def generate_event_data(session_id, user_data, event_timestamp):

    user_id = user_data[0]
    chosen_group = user_data[1]
    
    # Određivanje amount na osnovu grupe
    if chosen_group == 'whale':
        amount = np.random.pareto(alpha) * 1000 + 100
    elif chosen_group == 'dolphin':
        amount = np.random.pareto(alpha) * 100 + 10
    else:
        amount = np.random.pareto(alpha) * 10 + 1

    if random.random() < 0.20:
        event_data = generate_bad_data(user_id, session_id, amount, event_timestamp)
    else:
        event_data = generate_good_data(user_id, session_id, amount, event_timestamp)
    return event_data

def generate_good_data(user_id, session_id, amount, event_timestamp):
    
    tx_options = ['bet', 'win', 'deposit', 'withdraw']
    tx_weights = [50, 5, 25, 20]
    selected_tx_type = random.choices(tx_options, weights=tx_weights, k=1)[0]
    data = {
        "event_id": f"evt_{uuid.uuid4()}",
        "user_id": user_id,
        "session_id": session_id,
        "product": random.choice(['sportsbook', 'casino', 'virtual']),
        "tx_type": selected_tx_type, 
        "currency": fake.currency_code(),
        "amount": amount,
        "event_time": event_timestamp,
        "metadata": "some metadata"
    }
    
    if data["tx_type"]=='deposit' or data['tx_type']=='withdraw':
        data['amount'] = - data['amount']

    return data

def generate_bad_data(user_id, session_id, amount, event_timestamp):
    return {
        "event_id": random.choice(["",f"evt_{uuid.uuid4()}"]),
        "user_id": random.choice(["",user_id]), 
        "session_id": random.choice(["",session_id]),
        "product": random.choice(['sportsbook', 'casino', 'virtual', "", "xxx", "abcde"]),
        "tx_type": random.choice(['bet', 'win', 'deposit', 'withdraw', 'invalid']), 
        "currency": random.choice([fake.currency_code(), 'BAD', 'XXX', 'RSD-INVALID']),
        "amount": random.choice([amount, -amount]), 
        "event_time": random.choice([event_timestamp * 1000, event_timestamp]),
        "metadata": "data quality test case"
    }

def start_streaming():
    print(f"INFO: Pokrećem streaming transakcionih događaja na temu '{KAFKA_TOPIC}'...")

    try:
        while True: 
            #kreiranje random sesije
            session_id=f"sess_{uuid.uuid4()}"
            user_data = choose_user()
            num_transactions_in_session = random.randint(1, 10)
            sess_start_time = datetime.now() - timedelta(hours=random.randint(0, 23),
                                             minutes=random.randint(0, 59),
                                             seconds=random.randint(0, 59))
            random_sess_interval = random.uniform(10, 60) #sesija random traje izmedju 10 i 60 min
            sess_end_time = sess_start_time + timedelta(minutes=random_sess_interval)
            total_seconds_in_interval = (sess_end_time - sess_start_time).total_seconds()

            for _ in range(num_transactions_in_session):
                random_seconds  = random.uniform(0, total_seconds_in_interval)
                event_timestamp = (sess_start_time + timedelta(seconds=random_seconds)).timestamp()

                event_data=generate_event_data(session_id, user_data, event_timestamp)
                
                if event_data:
                    key = str(event_data['user_id']).encode('utf-8')

                    producer.send(
                        topic=KAFKA_TOPIC,
                        value=event_data,
                        key=key
                    )
                    
                    print(f"-> POSLATO: {event_data['tx_type']} - event_id {event_data['event_id']}")

                producer.flush()

            time.sleep(0.1)

    except Exception as e:
        print(f"ERROR: Neočekivana greška tokom striminga: {e}")
    finally:
        producer.close()
        print("INFO: Kafka producent zatvoren.")


if __name__ == '__main__':
    time.sleep(10)
    start_streaming()
