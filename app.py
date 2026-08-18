from flask import Flask, render_template
import os
import zlib
from pathlib import Path
import pandas as pd

app = Flask(__name__)


def _truthy_env(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip())


def _mock_registry_lookup(aadhaar_id: str, declared_income: float | None):
    """Deterministic mock lookup for demo/offline mode.

    This exists because the current workspace has no live Government APIs wired in.
    When API integrations are added, replace this with real calls.
    """
    seed = zlib.crc32(str(aadhaar_id).encode("utf-8"))

    # Income Tax (ITR) declared income (adds a deterministic +-0..45% drift)
    base_income = float(declared_income) if declared_income is not None else float((seed % 900_000) + 50_000)
    drift = ((seed % 91) - 45) / 100.0
    itr_income = max(0.0, base_income * (1.0 + drift))

    # Assets / Registries
    land_owned = (seed % 100) < 18  # ~18%
    vehicle_count = (seed // 101) % 4  # 0..3
    gst_registered = ((seed // 10_007) % 100) < 10  # ~10%

    return {
        "itr_income": round(float(itr_income), 2),
        "land_owned": bool(land_owned),
        "vehicle_count": int(vehicle_count),
        "gst_registered": bool(gst_registered),
        "mode": "mock",
    }


def analyze_income_asset_cross_verification():
    """Cross-verify beneficiary data against Income/Asset registries.

    Notes:
    - MP_Labour_DataSet.csv is district-aggregated and doesn't contain beneficiary identifiers.
    - For cross-verification, we use the beneficiary-level Excel already present in RealWorldData.
    """
    candidate_paths = [
        Path("RealWorldData") / "synthetic_subsidy_data.xlsx",
        Path("RealWorldData") / "synthetic_subsidy_data.csv",
    ]
    dataset_path = next((p for p in candidate_paths if p.exists()), None)
    if dataset_path is None:
        return None

    if dataset_path.suffix.lower() == ".xlsx":
        beneficiaries_df = pd.read_excel(dataset_path)
    else:
        beneficiaries_df = pd.read_csv(dataset_path)

    required = {"beneficiary_id", "aadhaar_id"}
    if not required.issubset(set(map(str, beneficiaries_df.columns))):
        return {
            "dataset_path": str(dataset_path),
            "error": "Beneficiary dataset is missing required columns: beneficiary_id, aadhaar_id",
        }

    api_status = {
        "income_tax": _truthy_env("INCOME_TAX_API_KEY"),
        "land_records": _truthy_env("LAND_RECORDS_API_KEY"),
        "vehicle_registration": _truthy_env("VEHICLE_REG_API_KEY"),
        "gst": _truthy_env("GST_API_KEY"),
    }

    declared_income_series = beneficiaries_df["income"] if "income" in beneficiaries_df.columns else pd.Series([None] * len(beneficiaries_df))

    registry_rows = []
    for aadhaar_id, declared_income in zip(beneficiaries_df["aadhaar_id"].astype(str), declared_income_series):
        declared = None
        try:
            if pd.notna(declared_income):
                declared = float(declared_income)
        except Exception:
            declared = None
        registry_rows.append(_mock_registry_lookup(aadhaar_id=aadhaar_id, declared_income=declared))

    registry_df = pd.DataFrame(registry_rows)
    merged = pd.concat([beneficiaries_df.reset_index(drop=True), registry_df.reset_index(drop=True)], axis=1)

    # Flagging rules
    income_threshold = 600_000
    merged["high_income_flag"] = ((merged.get("itr_income", 0) > income_threshold)).astype(int)

    if "income" in merged.columns:
        declared = pd.to_numeric(merged["income"], errors="coerce")
        itr = pd.to_numeric(merged["itr_income"], errors="coerce")
        diff_ratio = (declared - itr).abs() / (itr.abs() + 1.0)
        merged["income_tax_mismatch_flag"] = ((diff_ratio > 0.25) & itr.notna() & declared.notna()).astype(int)
    else:
        merged["income_tax_mismatch_flag"] = 0

    merged["land_record_flag"] = merged.get("land_owned", False).astype(int)
    merged["vehicle_flag"] = (pd.to_numeric(merged.get("vehicle_count", 0), errors="coerce").fillna(0) >= 2).astype(int)
    merged["gst_flag"] = merged.get("gst_registered", False).astype(int)

    merged["cross_verification_risk_score"] = (
        merged["income_tax_mismatch_flag"] * 0.35
        + merged["high_income_flag"] * 0.25
        + merged["land_record_flag"] * 0.20
        + merged["vehicle_flag"] * 0.10
        + merged["gst_flag"] * 0.10
    ).round(3)

    merged["needs_cross_verification"] = (merged["cross_verification_risk_score"] >= 0.30).astype(int)

    summary = {
        "total_beneficiaries": int(len(merged)),
        "flagged_for_verification": int(merged["needs_cross_verification"].sum()),
        "income_tax_mismatches": int(merged["income_tax_mismatch_flag"].sum()),
        "high_income_itr": int(merged["high_income_flag"].sum()),
        "land_records_hits": int(merged["land_record_flag"].sum()),
        "vehicle_hits": int(merged["vehicle_flag"].sum()),
        "gst_hits": int(merged["gst_flag"].sum()),
    }

    top = (
        merged.sort_values(["needs_cross_verification", "cross_verification_risk_score"], ascending=[False, False])
        .head(25)
        .fillna("")
    )

    top_columns = [
        "beneficiary_id",
        "district",
        "scheme_type",
        "income",
        "itr_income",
        "land_owned",
        "vehicle_count",
        "gst_registered",
        "cross_verification_risk_score",
        "needs_cross_verification",
    ]
    available_cols = [c for c in top_columns if c in top.columns]

    return {
        "dataset_path": str(dataset_path),
        "api_status": api_status,
        "summary": summary,
        "top_cases": top[available_cols].to_dict(orient="records"),
        "mode": "mock" if not any(api_status.values()) else "mock",  # API integrations not implemented yet
    }


def analyze_slds_web():
    """Runs the SLDS prototype analysis and saves its graphs for web display."""
    # Local imports so the dashboard can still load if optional libs are missing.
    import time

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        return {"error": f"Matplotlib not available: {type(exc).__name__}: {exc}"}

    try:
        import networkx as nx
    except Exception as exc:
        nx = None

    try:
        from sklearn.metrics import confusion_matrix, classification_report
    except Exception as exc:
        return {"error": f"scikit-learn not available: {type(exc).__name__}: {exc}"}

    dataset_path = Path("RealWorldData") / "synthetic_subsidy_data.xlsx"
    if not dataset_path.exists():
        return {"error": "Expected dataset not found: RealWorldData/synthetic_subsidy_data.xlsx"}

    df = pd.read_excel(dataset_path)

    required_cols = {"bank_account", "officer_id", "income", "subsidy_amount", "fraud_flag"}
    missing = sorted([c for c in required_cols if c not in df.columns])
    if missing:
        return {"error": f"Dataset missing columns: {', '.join(missing)}"}

    # Rule-based signals (same spirit as RealWorldData/SLDS.py)
    bank_counts = df.groupby("bank_account").size().reset_index(name="count")
    suspicious_accounts = bank_counts[bank_counts["count"] >= 3]
    df["shared_account_flag"] = df["bank_account"].isin(suspicious_accounts["bank_account"]).astype(int)

    officer_counts = df.groupby("officer_id").size().reset_index(name="count")
    suspicious_officers = officer_counts[officer_counts["count"] > 15]
    df["suspicious_officer_flag"] = df["officer_id"].isin(suspicious_officers["officer_id"]).astype(int)

    df["high_income_flag"] = (pd.to_numeric(df["income"], errors="coerce").fillna(0) > 600000).astype(int)

    df["rule_risk_score"] = (
        df["shared_account_flag"] * 0.4
        + df["suspicious_officer_flag"] * 0.3
        + df["high_income_flag"] * 0.3
    )
    df["predicted_fraud"] = (df["rule_risk_score"] >= 0.3).astype(int)

    cm = confusion_matrix(df["fraud_flag"], df["predicted_fraud"]).tolist()
    report = classification_report(df["fraud_flag"], df["predicted_fraud"], digits=3)

    fraud_amount = float(df[df["predicted_fraud"] == 1]["subsidy_amount"].sum())
    total_amount = float(df["subsidy_amount"].sum())
    clean_amount = float(total_amount - fraud_amount)
    leakage_percent = float((fraud_amount / total_amount) * 100) if total_amount else 0.0

    # Save plots
    out_dir = Path("static") / "slds"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = str(int(time.time()))

    image_files: list[str] = []

    # Plot 1: officer risk bar
    try:
        fraud_by_officer = df[df["predicted_fraud"] == 1].groupby("officer_id").size().sort_values(ascending=False)
        plt.figure(figsize=(10, 4))
        if len(fraud_by_officer) == 0:
            plt.text(0.5, 0.5, "No predicted fraud cases", ha="center", va="center")
            plt.axis("off")
        else:
            fraud_by_officer.plot(kind="bar")
            plt.title("Fraud Cases Linked Per Officer")
            plt.xlabel("Officer ID")
            plt.ylabel("Number of High-Risk Cases")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
        officer_png = out_dir / f"fraud_by_officer_{stamp}.png"
        plt.savefig(officer_png, dpi=140)
        plt.close()
        image_files.append(f"slds/{officer_png.name}")
    except Exception:
        plt.close("all")

    # Plot 2: leakage pie
    try:
        plt.figure(figsize=(6, 4))
        plt.pie(
            [fraud_amount, clean_amount],
            labels=["At Risk", "Verified Clean"],
            autopct="%1.1f%%",
            startangle=90,
        )
        plt.title("Estimated Subsidy Leakage (Prototype Simulation)")
        plt.axis("equal")
        plt.tight_layout()
        pie_png = out_dir / f"leakage_pie_{stamp}.png"
        plt.savefig(pie_png, dpi=140)
        plt.close()
        image_files.append(f"slds/{pie_png.name}")
    except Exception:
        plt.close("all")

    # Plot 3: fraud network
    if nx is not None:
        try:
            G = nx.Graph()
            suspicious_df = df[df["predicted_fraud"] == 1]
            for _, row in suspicious_df.iterrows():
                beneficiary = f"B_{row.get('beneficiary_id', '')}" if "beneficiary_id" in df.columns else "B"
                bank = f"BA_{row['bank_account']}"
                officer = f"O_{row['officer_id']}"
                G.add_node(beneficiary, type="beneficiary")
                G.add_node(bank, type="bank")
                G.add_node(officer, type="officer")
                G.add_edge(beneficiary, bank)
                G.add_edge(beneficiary, officer)

            plt.figure(figsize=(10, 7))
            if G.number_of_nodes() == 0:
                plt.text(0.5, 0.5, "No nodes to display", ha="center", va="center")
                plt.axis("off")
            else:
                pos = nx.spring_layout(G, seed=42)
                node_colors = []
                for _, meta in G.nodes(data=True):
                    t = meta.get("type")
                    if t == "beneficiary":
                        node_colors.append("#2563eb")  # uses an existing common blue; kept only inside image
                    elif t == "bank":
                        node_colors.append("#dc2626")
                    else:
                        node_colors.append("#16a34a")
                nx.draw(G, pos, node_size=140, node_color=node_colors, with_labels=False, width=0.8)
                plt.title("Detected Fraud Relationship Cluster")
                plt.tight_layout()
            net_png = out_dir / f"fraud_network_{stamp}.png"
            plt.savefig(net_png, dpi=140)
            plt.close()
            image_files.append(f"slds/{net_png.name}")
        except Exception:
            plt.close("all")

    top_cases = (
        df.sort_values(["predicted_fraud", "rule_risk_score"], ascending=[False, False])
        .head(25)
        .fillna("")
        .to_dict(orient="records")
    )

    return {
        "dataset_path": str(dataset_path),
        "confusion_matrix": cm,
        "classification_report": report,
        "total_distributed": round(total_amount, 2),
        "amount_at_risk": round(fraud_amount, 2),
        "estimated_leakage_percent": round(leakage_percent, 2),
        "images": image_files,
        "top_cases": top_cases,
    }

def analyze_data():
    df = pd.read_csv("MP_Labour_DataSet.csv")

    district_df = df.groupby("district_name").agg({
        "Approved_Labour_Budget": "sum",
        "Total_Exp": "sum",
        "Number_of_Completed_Works": "sum",
        "percentage_payments_gererated_within_15_days": "mean"
    }).reset_index()

    # Financial anomaly
    district_df["exp_to_budget_ratio"] = (
        district_df["Total_Exp"] /
        (district_df["Approved_Labour_Budget"] + 1)
    )

    mean_ratio = district_df["exp_to_budget_ratio"].mean()
    std_ratio = district_df["exp_to_budget_ratio"].std()

    district_df["financial_anomaly"] = (
        abs((district_df["exp_to_budget_ratio"] - mean_ratio) / std_ratio) > 2
    ).astype(int)

    # Productivity anomaly
    district_df["exp_per_work"] = (
        district_df["Total_Exp"] /
        (district_df["Number_of_Completed_Works"] + 1)
    )

    mean_epw = district_df["exp_per_work"].mean()
    std_epw = district_df["exp_per_work"].std()

    district_df["productivity_anomaly"] = (
        abs((district_df["exp_per_work"] - mean_epw) / std_epw) > 2
    ).astype(int)

    # Payment delay risk (aligns with RealWorldData/Subsidy_Leakage_Detection_System.py)
    payments_15d = pd.to_numeric(
        district_df["percentage_payments_gererated_within_15_days"],
        errors="coerce",
    )
    district_df["payment_delay_flag"] = (payments_15d < 95).fillna(False).astype(int)

    # Composite risk
    district_df["risk_score"] = (
        district_df["financial_anomaly"] * 0.4 +
        district_df["productivity_anomaly"] * 0.4 +
        district_df["payment_delay_flag"] * 0.2
    )

    district_df["high_risk"] = (
        district_df["risk_score"] >= 0.4
    ).astype(int)

    total = len(district_df)
    high_risk = district_df["high_risk"].sum()
    reduction = round((1 - high_risk / total) * 100, 2)

    high_risk_list = district_df[district_df["high_risk"] == 1]

    return df, district_df, total, high_risk, reduction, high_risk_list


def generate_dashboard_graphs(district_df: pd.DataFrame):
    """Generate the same district-level graphs as in RealWorldData/Subsidy_Leakage_Detection_System.py."""
    import time

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    out_dir = Path("static") / "dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = str(int(time.time()))

    images = []

    # 1) Risk distribution bar
    try:
        risk_category = pd.cut(
            district_df["risk_score"],
            bins=[-1, 0.2, 0.5, 1],
            labels=["Low", "Medium", "High"],
        )
        risk_counts = risk_category.value_counts().reindex(["Low", "Medium", "High"]).fillna(0)
        plt.figure(figsize=(7, 4))
        risk_counts.plot(kind="bar")
        plt.title("District Risk Distribution (MGNREGA)")
        plt.xlabel("Risk Level")
        plt.ylabel("Number of Districts")
        plt.xticks(rotation=0)
        plt.tight_layout()
        p = out_dir / f"risk_distribution_{stamp}.png"
        plt.savefig(p, dpi=140)
        plt.close()
        images.append({"title": "Risk Distribution", "file": f"dashboard/{p.name}", "v": stamp})
    except Exception:
        plt.close("all")

    # 2) Budget vs Expenditure scatter
    try:
        plt.figure(figsize=(7, 4))
        plt.scatter(district_df["Approved_Labour_Budget"], district_df["Total_Exp"], s=18)
        plt.xlabel("Approved Labour Budget")
        plt.ylabel("Total Expenditure")
        plt.title("Budget vs Expenditure (District Level)")
        plt.tight_layout()
        p = out_dir / f"budget_vs_exp_{stamp}.png"
        plt.savefig(p, dpi=140)
        plt.close()
        images.append({"title": "Budget vs Expenditure", "file": f"dashboard/{p.name}", "v": stamp})
    except Exception:
        plt.close("all")

    # 3) Productivity vs Expenditure scatter
    try:
        plt.figure(figsize=(7, 4))
        plt.scatter(district_df["Number_of_Completed_Works"], district_df["Total_Exp"], s=18)
        plt.xlabel("Completed Works")
        plt.ylabel("Total Expenditure")
        plt.title("Productivity vs Expenditure (District Level)")
        plt.tight_layout()
        p = out_dir / f"works_vs_exp_{stamp}.png"
        plt.savefig(p, dpi=140)
        plt.close()
        images.append({"title": "Works vs Expenditure", "file": f"dashboard/{p.name}", "v": stamp})
    except Exception:
        plt.close("all")

    # 4) Audit risk distribution pie
    try:
        high_risk_count = int(district_df["high_risk"].sum())
        safe_count = int(len(district_df) - high_risk_count)
        plt.figure(figsize=(6, 4))
        plt.pie(
            [high_risk_count, safe_count],
            labels=["High Risk Districts", "Safe Districts"],
            autopct="%1.1f%%",
            startangle=90,
        )
        plt.title("Audit Risk Distribution Across Districts")
        plt.axis("equal")
        plt.tight_layout()
        p = out_dir / f"audit_risk_pie_{stamp}.png"
        plt.savefig(p, dpi=140)
        plt.close()
        images.append({"title": "Audit Risk Pie", "file": f"dashboard/{p.name}", "v": stamp})
    except Exception:
        plt.close("all")

    return images


def _static_images(folder_name: str):
    """Return all ready-made images from the asset folders so the UI still works offline."""
    folder = Path("static") / folder_name
    if not folder.exists():
        return []

    results = []
    for image_path in sorted(folder.glob("*.png")):
        results.append({
            "title": image_path.stem.replace("_", " ").title(),
            "file": f"{folder_name}/{image_path.name}",
            "v": int(image_path.stat().st_mtime),
        })
    return results


def _dashboard_fallback_payload():
    payload = {
        "total": 0,
        "high_risk": 0,
        "reduction": 0,
        "table": [],
        "dashboard_graphs": _static_images("dashboard"),
    }

    try:
        df = pd.read_csv("MP_Labour_DataSet.csv")
        if len(df) > 0:
            district_df = df.groupby("district_name").agg({
                "Approved_Labour_Budget": "sum",
                "Total_Exp": "sum",
                "Number_of_Completed_Works": "sum",
                "percentage_payments_gererated_within_15_days": "mean",
            }).reset_index()
            district_df["exp_to_budget_ratio"] = district_df["Total_Exp"] / (district_df["Approved_Labour_Budget"] + 1)
            mean_ratio = district_df["exp_to_budget_ratio"].mean()
            std_ratio = district_df["exp_to_budget_ratio"].std()
            district_df["financial_anomaly"] = (abs((district_df["exp_to_budget_ratio"] - mean_ratio) / std_ratio) > 2).astype(int)
            district_df["exp_per_work"] = district_df["Total_Exp"] / (district_df["Number_of_Completed_Works"] + 1)
            mean_epw = district_df["exp_per_work"].mean()
            std_epw = district_df["exp_per_work"].std()
            district_df["productivity_anomaly"] = (abs((district_df["exp_per_work"] - mean_epw) / std_epw) > 2).astype(int)
            district_df["payment_delay_flag"] = (pd.to_numeric(district_df["percentage_payments_gererated_within_15_days"], errors="coerce") < 95).fillna(False).astype(int)
            district_df["risk_score"] = district_df["financial_anomaly"] * 0.4 + district_df["productivity_anomaly"] * 0.4 + district_df["payment_delay_flag"] * 0.2
            district_df["high_risk"] = (district_df["risk_score"] >= 0.4).astype(int)
            payload["total"] = int(len(district_df))
            payload["high_risk"] = int(district_df["high_risk"].sum())
            payload["reduction"] = round((1 - (payload["high_risk"] / payload["total"])) * 100, 2) if payload["total"] else 0
            payload["table"] = district_df[district_df["high_risk"] == 1][["district_name", "risk_score"]].to_dict(orient="records")
    except Exception:
        pass

    return payload


def _slds_fallback_payload():
    payload = {
        "dataset_path": "Offline/demo mode",
        "confusion_matrix": [[0, 0], [0, 0]],
        "classification_report": "Offline demo mode active. The app is using pre-generated static charts because the live backend or data pipeline is unavailable.",
        "total_distributed": 0,
        "amount_at_risk": 0,
        "estimated_leakage_percent": 0,
        "images": _static_images("slds"),
        "top_cases": [],
        "error": None,
    }
    return payload


@app.route("/")
def dashboard():
    try:
        df, district_df, total, high_risk, reduction, high_risk_list = analyze_data()
        cross_verification = analyze_income_asset_cross_verification()
        dashboard_graphs = generate_dashboard_graphs(district_df)
        preview_limit = 50
        df_preview = df.head(preview_limit).fillna("")
        return render_template(
            "dashboard.html",
            total=total,
            high_risk=high_risk,
            reduction=reduction,
            table=high_risk_list.to_dict(orient="records"),
            cross_verification=cross_verification,
            dashboard_graphs=dashboard_graphs,
            csv_filename="MP_Labour_DataSet.csv",
            csv_preview_count=len(df_preview),
            csv_columns=[str(c) for c in df_preview.columns.tolist()],
            csv_rows=df_preview.to_dict(orient="records"),
        )
    except Exception:
        fallback = _dashboard_fallback_payload()
        return render_template(
            "dashboard_fallback.html",
            total=fallback["total"],
            high_risk=fallback["high_risk"],
            reduction=fallback["reduction"],
            table=fallback["table"],
            cross_verification=None,
            dashboard_graphs=fallback["dashboard_graphs"],
            csv_filename="MP_Labour_DataSet.csv",
            csv_preview_count=0,
            csv_columns=[],
            csv_rows=[],
        )


@app.route("/slds")
def slds_page():
    try:
        result = analyze_slds_web()
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(result.get("error"))
        return render_template("slds.html", slds=result)
    except Exception:
        return render_template("slds_fallback.html", slds=_slds_fallback_payload())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)