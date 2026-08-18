import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from sklearn.metrics import confusion_matrix, classification_report

# LOAD DATA
df = pd.read_excel("synthetic_subsidy_data.xlsx")

# RULE-BASED FRAUD DETECTION

# 1. Shared Bank Accounts
bank_counts = df.groupby("bank_account").size().reset_index(name="count")
suspicious_accounts = bank_counts[bank_counts["count"] >= 3]

df["shared_account_flag"] = df["bank_account"].isin(
    suspicious_accounts["bank_account"]
).astype(int)

# 2. Officer Concentration
officer_counts = df.groupby("officer_id").size().reset_index(name="count")
suspicious_officers = officer_counts[officer_counts["count"] > 15]

df["suspicious_officer_flag"] = df["officer_id"].isin(
    suspicious_officers["officer_id"]
).astype(int)

# 3. Income Eligibility
df["high_income_flag"] = (df["income"] > 600000).astype(int)

# RISK SCORING
df["rule_risk_score"] = (
    df["shared_account_flag"] * 0.4 +
    df["suspicious_officer_flag"] * 0.3 +
    df["high_income_flag"] * 0.3
)

df["predicted_fraud"] = (df["rule_risk_score"] >= 0.3).astype(int)

# PERFORMANCE METRICS
print("Confusion Matrix:")
print(confusion_matrix(df["fraud_flag"], df["predicted_fraud"]))
print("\nClassification Report:")
print(classification_report(df["fraud_flag"], df["predicted_fraud"]))

# FINANCIAL IMPACT ANALYSIS
fraud_amount = df[df["predicted_fraud"] == 1]["subsidy_amount"].sum()
total_amount = df["subsidy_amount"].sum()
clean_amount = total_amount - fraud_amount

leakage_percent = (fraud_amount / total_amount) * 100

print(f"\nTotal Distributed: ₹{total_amount:,.0f}")
print(f"Amount At Risk: ₹{fraud_amount:,.0f}")
print(f"Estimated Leakage: {leakage_percent:.2f}%")

# VISUALIZATION 1: OFFICER RISK
fraud_by_officer = df[df["predicted_fraud"] == 1].groupby("officer_id").size()

plt.figure()
fraud_by_officer.sort_values(ascending=False).plot(kind="bar")
plt.title("Fraud Cases Linked Per Officer")
plt.xlabel("Officer ID")
plt.ylabel("Number of High-Risk Cases")
plt.xticks(rotation=45)
plt.show()

# VISUALIZATION 2: LEAKAGE PIE
plt.figure()
plt.pie(
    [fraud_amount, clean_amount],
    labels=["At Risk", "Verified Clean"],
    autopct="%1.1f%%"
)
plt.title("Estimated Subsidy Leakage (Prototype Simulation)")
plt.show()

# VISUALIZATION 3: FRAUD NETWORK
G = nx.Graph()
suspicious_df = df[df["predicted_fraud"] == 1]

for _, row in suspicious_df.iterrows():
    beneficiary = f"B_{row['beneficiary_id']}"
    bank = f"BA_{row['bank_account']}"
    officer = f"O_{row['officer_id']}"

    G.add_node(beneficiary, type="beneficiary")
    G.add_node(bank, type="bank")
    G.add_node(officer, type="officer")

    G.add_edge(beneficiary, bank)
    G.add_edge(beneficiary, officer)

plt.figure(figsize=(10,8))
pos = nx.spring_layout(G, seed=42)

node_colors = []
for node in G.nodes(data=True):
    if node[1]["type"] == "beneficiary":
        node_colors.append("blue")
    elif node[1]["type"] == "bank":
        node_colors.append("red")
    else:
        node_colors.append("green")

nx.draw(G, pos, node_size=150, node_color=node_colors, with_labels=False)
plt.title("Detected Fraud Relationship Cluster")
plt.show()