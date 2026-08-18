# Subsidy Leakage Detection System

A Flask-based dashboard for detecting possible subsidy leakage and risk patterns in public welfare programs. The project includes a district-level audit dashboard and an SLDS-style fraud detection prototype that visualizes suspicious activity patterns.

## Features

- District-level subsidy monitoring dashboard
- Risk scoring across districts
- High-risk district summary and audit tables
- Cross-verification analysis for income and asset signals
- Fraud detection prototype dashboard for suspicious beneficiary/officer patterns
- PNG chart generation using Matplotlib
- Render-ready Python deployment configuration

<img width="1595" height="860" alt="image" src="https://github.com/user-attachments/assets/c43f3e37-2340-479e-8250-8445d89ac6f4" />


## Project Structure

```text
.
├── app.py
├── requirements.txt
├── render.yaml
├── README.md
├── MP_Labour_DataSet.csv
├── RealWorldData/
│   ├── MP_Labour_DataSet.csv
│   ├── synthetic_subsidy_data.xlsx
│   ├── Data_set_Generator.py
│   ├── SLDS.py
│   └── Subsidy_Leakage_Detection_System.py
├── static/
│   ├── dashboard/
│   └── slds/
└── templates/
    ├── dashboard.html
    ├── dashboard_fallback.html
    ├── slds.html
    └── slds_fallback.html
```

## Tech Stack

- Python 3.11
- Flask
- Pandas
- NumPy
- Matplotlib
- scikit-learn
- NetworkX
- OpenPyXL
- Gunicorn

## Local Setup

1. Clone the repository
2. Open a terminal in the project folder
3. Create a virtual environment (optional but recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

4. Install dependencies

```bash
pip install -r requirements.txt
```

5. Run the application

```bash
python app.py
```

6. Open the app in your browser

```text
http://localhost:5000
```

## Routes

- `/` → District dashboard
- `/slds` → Subsidy leakage detection prototype dashboard

## Screen-Shorts

<img width="1193" height="861" alt="image" src="https://github.com/user-attachments/assets/0fdcd25d-3ce3-4bfd-8be9-98f40bcf0d10" />

<img width="1251" height="517" alt="image" src="https://github.com/user-attachments/assets/d56ff895-4d9e-4f69-82bc-d99247ed61de" />

<img width="1570" height="792" alt="image" src="https://github.com/user-attachments/assets/6ffef20c-0155-48e7-ad3d-13640d00fcf8" />

## License

This project is provided for educational and demonstration purposes.
