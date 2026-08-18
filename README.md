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

## Render Deployment

This project is configured for Render using the included `render.yaml` file and `gunicorn` as the production server.

### Deploy on Render

1. Push the project to GitHub
2. Go to Render dashboard
3. Click `New` → `Web Service`
4. Connect your GitHub repository
5. Use the following settings:

```bash
Build Command:
pip install -r requirements.txt

Start Command:
gunicorn app:app
```

Render will automatically start the Flask app using the WSGI entry point.

## Notes

- The app is designed to run in a demo/offline-friendly mode when data or API integrations are not available.
- The project includes fallback templates and static visualization assets so the UI still renders gracefully.
- The live deployment should use the environment variables provided by Render and the app will respect the `PORT` variable automatically.

## License

This project is provided for educational and demonstration purposes.
