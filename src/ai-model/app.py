import pandas as pd
from sklearn.ensemble import IsolationForest
import matplotlib.pyplot as plt
import joblib 


try:
    df = pd.read_csv('random_transactions_10k.csv', header=None)
    df.columns = ['amount', 'hour_of_day', 'currency', 'user_id_mod']
except FileNotFoundError:
    print("GREŠKA: Datoteka 'random_transactions_10k.csv' nije pronađena. Proverite putanju.")
    exit()
except ValueError:
    print("GREŠKA: Broj kolona u CSV fajlu se ne slaže sa definisanim (amount, hour_of_day, currency, user_id_mod).")
    exit()

# One-Hot Encoding za kodiranje 'currency' vrednosti
df_encoded = pd.get_dummies(df, columns=['currency'], prefix='curr', drop_first=True)
TRAINING_FEATURES = df_encoded.columns.tolist()
joblib.dump(TRAINING_FEATURES, "features_10k.pkl")

print(df_encoded.head())

# Parametri za IsolationForest
N_ESTIMATORS = 300
CONTAMINATION = 0.05 
MAX_SAMPLES = 10000

iso_forest = IsolationForest(n_estimators=N_ESTIMATORS,
                             contamination=CONTAMINATION,
                             max_samples=MAX_SAMPLES,
                             random_state=42,
                             n_jobs=-1)

iso_forest.fit(df_encoded)
MODEL_FILE = "model_10k.pkl"
joblib.dump(iso_forest, MODEL_FILE)
print(f"Model je uspešno sačuvan kao: {MODEL_FILE}")

df['anomaly_score'] = iso_forest.decision_function(df_encoded)
df['anomaly'] = iso_forest.predict(df_encoded)
print(df['anomaly'].value_counts())

#Vizuelizacija
plt.figure(figsize=(12, 6))

normal = df[df['anomaly'] == 1]
anomalies = df[df['anomaly'] == -1]

# normalne vrednosti
plt.scatter(normal.index, normal['anomaly_score'], 
            label='Normalna transakcija (Score > 0)', 
            alpha=0.6, s=20, color='blue')

# anomalije
plt.scatter(anomalies.index, anomalies['anomaly_score'], 
            label='Anomalija (Score < 0)', 
            alpha=0.9, s=30, color='red', marker='x')

plt.title("Isolation Forest")
plt.xlabel("Transakcija")
plt.ylabel("Anomaly Score")
plt.legend()
plt.grid(True, axis='y', linestyle=':', alpha=0.5)
plt.show()

plt.scatter(normal['amount'], normal['hour_of_day'], label='Normal')
plt.scatter(anomalies['amount'], anomalies['hour_of_day'], label='Anomaly')
plt.xlabel("amount")
plt.ylabel("hour_of_day")
plt.xlim(-1000, 1000)
plt.legend()
plt.show()
