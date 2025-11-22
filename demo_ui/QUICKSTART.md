# Quick Start Guide - Voting Demo UI

## Fastest Way to Get Started

### Option 1: Using the run script (Recommended for development)

```bash
cd /home/tesearchteamtango/Aifolders/electionscript/version2/demo_ui
./run.sh
```

The script will:
- Create a virtual environment
- Install all dependencies
- Start the Flask application on port 3000

### Option 2: Using Docker

```bash
cd /home/tesearchteamtango/Aifolders/electionscript/version2/demo_ui

# Build and run with docker-compose
docker-compose up --build
```

### Option 3: Manual setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env to set your API URL
nano .env

# Run the application
python app.py
```

## Accessing the Application

Once running, access:
- **Voting Page**: http://localhost:3000
- **Results Page**: http://localhost:3000/results
- **Health Check**: http://localhost:3000/health

## Configuration

Edit `.env` file to configure:

```env
INGESTION_API_URL=http://localhost:8000
SECRET_KEY=your-secret-key-here
DEBUG=False
```

## Testing the UI

1. **Submit a Vote**:
   - Enter a 9-digit NAS (e.g., 123456789)
   - Enter a 6-character code (e.g., ABC123)
   - Select a law from the dropdown
   - Choose Pour (Yes) or Contre (No)
   - Click "Soumettre le Vote"

2. **View Results**:
   - Results appear below the form (auto-refreshes every 5s)
   - Click "Voir les Résultats" for the full results page
   - Charts update automatically

## Troubleshooting

**Problem**: Cannot connect to API
- **Solution**: Check that INGESTION_API_URL in .env points to your running API

**Problem**: Port 3000 already in use
- **Solution**: Change port in app.py or docker-compose.yml

**Problem**: Dependencies installation fails
- **Solution**: Ensure Python 3.11+ is installed, upgrade pip: `pip install --upgrade pip`

## Next Steps

- Customize law options in `app.py` (line 24)
- Modify styling in `static/style.css`
- Add authentication if needed
- Deploy to production with Gunicorn
