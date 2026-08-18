import pandas as pd
import numpy as np
import random
np.random.seed(42)
num_rows = 100
districts = ["Indore", "Bhopal", "Ujjain", "Gwalior"]
schemes = ["PM-KISAN", "PDS", "Scholarship", "MNREGA"]
officers = [f"O{str(i).zfill(3)}" for i in range(1, 11)]

data = []

for i in range(num_rows):
    beneficiary_id = f"B{str(i+1).zfill(4)}"
    aadhaar_id = ''.join([str(np.random.randint(0,10)) for _ in range(12)])
    bank_account = ''.join([str(np.random.randint(0,10)) for _ in range(10)])
    officer_id = random.choice(officers)
    district = random.choice(districts)
    scheme = random.choice(schemes)
    
    income = np.random.randint(50000, 500000)
    subsidy_amount = np.random.randint(2000, 15000)
    
    fraud_flag = 0
    
    data.append([
        beneficiary_id,
        aadhaar_id,
        bank_account,
        officer_id,
        district,
        income,
        subsidy_amount,
        scheme,
        fraud_flag
    ])

df = pd.DataFrame(data, columns=[
    "beneficiary_id",
    "aadhaar_id",
    "bank_account",
    "officer_id",
    "district",
    "income",
    "subsidy_amount",
    "scheme_type",
    "fraud_flag"
])

shared_account = 9999999999
for i in range(5):
    df.loc[i, "bank_account"] = shared_account
    df.loc[i, "fraud_flag"] = 1

for i in range(5, 10):
    df.loc[i, "income"] = 800000
    df.loc[i, "fraud_flag"] = 1

for i in range(10, 20):
    df.loc[i, "officer_id"] = "O001"
    df.loc[i, "fraud_flag"] = 1

print(df.head(15))

df.to_csv("synthetic_subsidy_data.csv", index=False)
df.to_excel(r"C:\Users\ANOOP\Desktop\synthetic_subsidy_data.xlsx", index=False)