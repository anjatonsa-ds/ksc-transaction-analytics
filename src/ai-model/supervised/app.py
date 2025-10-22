import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression 

df = pd.read_csv('data.csv')
df.drop(columns=['description'], inplace=True)
print(df.info())

#Kodiranje hour_of_day koriscenjem sin i cos funkcija
def apply_cyclical_encoding(df, col, max_val):
    df[col + '_sin'] = np.sin(2 * np.pi * df[col] / max_val)
    df[col + '_cos'] = np.cos(2 * np.pi * df[col] / max_val)
    return df

df = apply_cyclical_encoding(df, 'hour_of_day', 24)
print(df.head())

df['abs_amount'] = np.abs(df['amount'])

x = df.drop('is_anomaly', axis=1)
y = df['is_anomaly']

numerical_features = ['amount', 'abs_amount', 'hour_of_day_sin', 'hour_of_day_cos']
categorical_features = ['tx_type', 'currency']
pass_through_features = ['user_id_mod']

#Preprocessing 
numerical_pipeline = Pipeline([
    ('scaler', StandardScaler())
])

categorical_pipeline = Pipeline([
    ('onehot', OneHotEncoder(handle_unknown='ignore'))
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numerical_pipeline, numerical_features),
        ('cat', categorical_pipeline, categorical_features),
        ('passthrough', 'passthrough', pass_through_features)
    ],
    remainder='drop'
)

#model training
logistic_regression_classifier = LogisticRegression(
    solver='liblinear',
    random_state=42,
    class_weight='balanced' 
)

model_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', logistic_regression_classifier)
])

# Train the model
model_pipeline.fit(x, y)

#testing and visualization
test_data = {
    'user_id_mod': [9, 2, 7],
    'hour_of_day': [16, 18, 23],
    'amount': [15.00, -20.00, 9000.00],
    'tx_type': ['win', 'bet', 'deposit'],
    'currency': ['EUR', 'USD', 'JPY'],
}

df_new_test = pd.DataFrame(test_data)

df_new_test['abs_amount'] = np.abs(df_new_test['amount'])
df_new_test = apply_cyclical_encoding(df_new_test, 'hour_of_day', 24)
x = df_new_test
y_pred_test = model_pipeline.predict(x)
df_new_test['predicted_anomaly'] = y_pred_test

for i, row in df_new_test.iterrows():
    print(f"Test {i+1}: Hour={int(row['hour_of_day'])}, Amount={row['amount']:.2f}, Type={row['tx_type']}, PREDICTED ANOMALY: {row['predicted_anomaly']}")

normal = df[df['is_anomaly'] == 0]
anomaly = df[df['is_anomaly'] == 1]

plt.figure(figsize=(10, 6))

plt.scatter(
    normal['hour_of_day'], 
    normal['amount'], 
    color='green', 
    label='Normal', 
    alpha=0.6,
    s=50
)

plt.scatter(
    anomaly['hour_of_day'], 
    anomaly['amount'], 
    color='red', 
    label='Anomaly', 
    alpha=0.9,
    marker='X',
    s=100
)

normal = df_new_test[df_new_test['predicted_anomaly'] == 0]
anomaly = df_new_test[df_new_test['predicted_anomaly'] == 1]


plt.scatter(
    anomaly['hour_of_day'], 
    anomaly['amount'], 
    color='blue', 
    marker='x',
    s=100,            
    alpha=0.9,
    linewidth=1.5,
    label='Test - anomaly'
)

plt.scatter(
    normal['hour_of_day'], 
    normal['amount'], 
    color='blue', 
    linewidth=1.5,
    label="Test - not anomaly"
)

plt.title('Casino Transaction Anomaly Visualization (Amount vs. Time of Day)')
plt.xlabel('Hour of Day')
plt.ylabel('Transaction Amount')
plt.xticks(range(0, 24))
plt.grid(True, linestyle='--', alpha=0.5)
plt.ylim(-9500, 9500)
plt.legend()
plt.tight_layout()
plt.show()

