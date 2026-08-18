import pandas as pd
import matplotlib.pyplot as plt

# =============================
# LOAD DATA
# =============================

df = pd.read_csv("MP_Labour_DataSet.csv")

# =============================
# AGGREGATE TO DISTRICT LEVEL
# =============================

district_df = df.groupby("district_name").agg({
    "Approved_Labour_Budget": "sum",
    "Total_Exp": "sum",
    "Number_of_Completed_Works": "sum",
    "percentage_payments_gererated_within_15_days": "mean"
}).reset_index()

# =============================
# FINANCIAL ANOMALY
# =============================

district_df["exp_to_budget_ratio"] = (
    district_df["Total_Exp"] /
    (district_df["Approved_Labour_Budget"] + 1)
)

mean_ratio = district_df["exp_to_budget_ratio"].mean()
std_ratio = district_df["exp_to_budget_ratio"].std()

district_df["financial_anomaly"] = (
    abs((district_df["exp_to_budget_ratio"] - mean_ratio) / std_ratio) > 2
).astype(int)

# =============================
# PRODUCTIVITY ANOMALY
# =============================

district_df["exp_per_work"] = (
    district_df["Total_Exp"] /
    (district_df["Number_of_Completed_Works"] + 1)
)

mean_epw = district_df["exp_per_work"].mean()
std_epw = district_df["exp_per_work"].std()

district_df["productivity_anomaly"] = (
    abs((district_df["exp_per_work"] - mean_epw) / std_epw) > 2
).astype(int)

# =============================
# PAYMENT DELAY RISK
# =============================

district_df["payment_delay_flag"] = (
    district_df["percentage_payments_gererated_within_15_days"] < 95
).astype(int)

# =============================
# COMPOSITE RISK SCORE
# =============================

district_df["district_risk_score"] = (
    district_df["financial_anomaly"] * 0.4 +
    district_df["productivity_anomaly"] * 0.4 +
    district_df["payment_delay_flag"] * 0.2
)

district_df["high_risk_district"] = (
    district_df["district_risk_score"] >= 0.4
).astype(int)

# =============================
# RISK CATEGORY FOR VISUAL
# =============================

district_df["risk_category"] = pd.cut(
    district_df["district_risk_score"],
    bins=[-1, 0.2, 0.5, 1],
    labels=["Low", "Medium", "High"]
)

risk_counts = district_df["risk_category"].value_counts()

plt.figure()
risk_counts.plot(kind="bar")
plt.title("District Risk Distribution (MGNREGA)")
plt.xlabel("Risk Level")
plt.ylabel("Number of Districts")
plt.xticks(rotation=0)
plt.show()

# =============================
# SUMMARY OUTPUT
# =============================

total_districts = len(district_df)
financial_count = district_df["financial_anomaly"].sum()
productivity_count = district_df["productivity_anomaly"].sum()
payment_count = district_df["payment_delay_flag"].sum()
high_risk_count = district_df["high_risk_district"].sum()

print("\n===== DISTRICT-LEVEL RISK SUMMARY =====")
print(f"Total Districts Analyzed: {total_districts}")
print(f"Financial Anomalies: {financial_count}")
print(f"Productivity Anomalies: {productivity_count}")
print(f"Payment Delay Risks: {payment_count}")
print(f"High-Risk Districts: {high_risk_count}")

print("\nHigh-Risk Districts:")
print(
    district_df[district_df["high_risk_district"] == 1][
        ["district_name", "district_risk_score"]
    ].sort_values("district_risk_score", ascending=False)
)
audit_reduction = (1 - (4/52)) * 100
print(f"Audit workload reduced by approximately {audit_reduction:.2f}%")
# =============================
# BUSINESS-FRIENDLY VISUALS
# =============================

plt.figure()
plt.scatter(district_df["Approved_Labour_Budget"], district_df["Total_Exp"])
plt.xlabel("Approved Labour Budget")
plt.ylabel("Total Expenditure")
plt.title("Budget vs Expenditure (District Level)")
plt.show()

plt.figure()
plt.scatter(district_df["Number_of_Completed_Works"], district_df["Total_Exp"])
plt.xlabel("Completed Works")
plt.ylabel("Total Expenditure")
plt.title("Productivity vs Expenditure (District Level)")
plt.show()

# =============================
# PIE CHART – RISK DISTRIBUTION
# =============================

high_risk_count = district_df["high_risk_district"].sum()
safe_count = len(district_df) - high_risk_count

labels = ["High Risk Districts", "Safe Districts"]
sizes = [high_risk_count, safe_count]

plt.figure()
plt.pie(
    sizes,
    labels=labels,
    autopct='%1.1f%%',
    startangle=90
)
plt.title("Audit Risk Distribution Across Districts")
plt.axis('equal')  
plt.show()