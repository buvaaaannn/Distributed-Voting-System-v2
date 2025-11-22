# Demo Web UI for Voting System

A Flask-based web interface for the electronic voting system with real-time results display.

## Features

- **Voting Form**: Submit votes with NAS, validation code, law selection, and vote choice
- **Real-time Validation**: Client-side form validation with instant feedback
- **Results Display**: Live results with auto-refresh every 5 seconds
- **Interactive Charts**: Visual representation of voting data using Chart.js
- **Responsive Design**: Mobile-friendly Bootstrap 5 interface
- **Dark Theme**: Professional dark color scheme matching the original design
- **Error Handling**: Comprehensive error messages for all scenarios

## Installation

### Local Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Configure the API URL in `.env`:
```
INGESTION_API_URL=http://localhost:8000
SECRET_KEY=your-secret-key-here
```

4. Run the application:
```bash
python app.py
```

5. Access the UI at `http://localhost:3000`

### Docker Setup

1. Build the Docker image:
```bash
docker build -t voting-ui .
```

2. Run the container:
```bash
docker run -p 3000:3000 \
  -e INGESTION_API_URL=http://host.docker.internal:8000 \
  voting-ui
```

## Routes

- **GET /** - Main voting page with form and current results
- **POST /vote** - Submit a vote (AJAX endpoint)
- **GET /results** - Full results page with charts and tables
- **GET /api/results** - JSON API for fetching current results
- **GET /health** - Health check endpoint

## API Responses

### Vote Submission

**Success (202 Accepted):**
```json
{
  "success": true,
  "message": "Vote enregistré avec succès!"
}
```

**Validation Error (400 Bad Request):**
```json
{
  "success": false,
  "message": "NAS invalide. Doit contenir exactement 9 chiffres."
}
```

**Duplicate Vote (409 Conflict):**
```json
{
  "success": false,
  "message": "Vote déjà enregistré pour cette loi."
}
```

## Configuration

Edit `config.py` to customize:

- `INGESTION_API_URL`: URL of the ingestion API
- `AUTO_REFRESH_INTERVAL`: Results refresh interval (milliseconds)
- `SECRET_KEY`: Flask secret key for sessions
- `DEBUG`: Enable/disable debug mode

## Technologies Used

- **Backend**: Flask 3.0
- **Frontend**: Bootstrap 5, Chart.js
- **HTTP Client**: Requests library
- **Styling**: Custom CSS with dark theme
- **JavaScript**: Vanilla JS with AJAX

## File Structure

```
demo_ui/
├── app.py                 # Flask application
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── .env.example          # Environment variables template
├── templates/
│   ├── index.html        # Voting page
│   └── results.html      # Results page with charts
└── static/
    ├── style.css         # Custom styling
    └── script.js         # Client-side logic
```

## Development

To run in development mode:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
export DEBUG=True
flask run --host=0.0.0.0 --port=3000
```

## Production Deployment

1. Set production environment variables:
```bash
export FLASK_ENV=production
export DEBUG=False
export SECRET_KEY=<strong-random-key>
```

2. Use a production WSGI server (e.g., Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:3000 app:app
```

## Security Notes

- Change the `SECRET_KEY` in production
- Use HTTPS in production environments
- Validate all inputs on both client and server side
- Keep dependencies up to date
- Run as non-root user in containers

## License

Part of the Electronic Voting System - Version 2
