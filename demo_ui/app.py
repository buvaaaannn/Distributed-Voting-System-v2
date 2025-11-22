"""
Flask application for voting demo UI.

Author: David Marleau
Project: Distributed Voting System - Demo Version
Description: Web interface for law voting and electoral elections
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
import config

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['DEBUG'] = config.DEBUG


@app.route('/')
def index():
    """Display voting form and current results."""
    # Fetch available laws and current results
    try:
        results_response = requests.get(f'{config.INGESTION_API_URL}/results', timeout=5)
        if results_response.status_code == 200:
            results = results_response.json()
        else:
            results = {}
    except Exception as e:
        print(f"Error fetching results: {e}")
        results = {}

    # Generate law options (you can make this dynamic by calling an API)
    law_ids = ['L2025-001', 'L2025-002', 'L2025-003']

    return render_template('index.html', law_ids=law_ids, results=results)


@app.route('/vote', methods=['POST'])
def vote():
    """Submit a vote to the ingestion API."""
    try:
        # Get form data
        nas = request.form.get('nas', '').strip()
        code = request.form.get('code', '').strip()
        law_id = request.form.get('law_id', '').strip()
        vote_choice = request.form.get('vote', '').strip()

        # Validate input
        if not all([nas, code, law_id, vote_choice]):
            return jsonify({
                'success': False,
                'message': 'Tous les champs sont requis.'
            }), 400

        # Validate NAS format (9 digits)
        if not nas.isdigit() or len(nas) != 9:
            return jsonify({
                'success': False,
                'message': 'NAS invalide. Doit contenir exactement 9 chiffres.'
            }), 400

        # Validate code format (6 characters)
        if len(code) != 6:
            return jsonify({
                'success': False,
                'message': 'Code invalide. Doit contenir exactement 6 caractères.'
            }), 400

        # Prepare vote data
        vote_data = {
            'nas': nas,
            'code': code,
            'law_id': law_id,
            'vote': vote_choice
        }

        # Submit to ingestion API
        response = requests.post(
            f'{config.INGESTION_API_URL}/vote',
            json=vote_data,
            timeout=10
        )

        # Handle responses
        if response.status_code == 202:
            return jsonify({
                'success': True,
                'message': 'Vote enregistré avec succès!'
            }), 202
        elif response.status_code == 400:
            error_data = response.json()
            return jsonify({
                'success': False,
                'message': f"Erreur: {error_data.get('detail', 'Requête invalide')}"
            }), 400
        elif response.status_code == 409:
            return jsonify({
                'success': False,
                'message': 'Vote déjà enregistré pour cette loi.'
            }), 409
        else:
            return jsonify({
                'success': False,
                'message': f"Erreur serveur: {response.status_code}"
            }), 500

    except requests.RequestException as e:
        return jsonify({
            'success': False,
            'message': f"Erreur de connexion à l'API: {str(e)}"
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Erreur inattendue: {str(e)}"
        }), 500


@app.route('/results')
def results():
    """Display results page with all voting statistics."""
    try:
        response = requests.get(f'{config.INGESTION_API_URL}/api/v1/results', timeout=5)
        if response.status_code == 200:
            results_data = response.json()
        else:
            results_data = []
    except Exception as e:
        print(f"Error fetching results: {e}")
        results_data = []

    return render_template('results.html', results=results_data)


@app.route('/api/results')
def api_results():
    """API endpoint to fetch current results (for AJAX calls)."""
    try:
        response = requests.get(f'{config.INGESTION_API_URL}/api/v1/results', timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Failed to fetch results'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/health')
def health():
    """Health check endpoint."""
    try:
        # Check if ingestion API is reachable
        response = requests.get(f'{config.INGESTION_API_URL}/health', timeout=2)
        api_healthy = response.status_code == 200
    except:
        api_healthy = False

    return jsonify({
        'status': 'healthy' if api_healthy else 'degraded',
        'ui': 'up',
        'ingestion_api': 'up' if api_healthy else 'down'
    }), 200 if api_healthy else 503


# ═══════════════════════════════════════════════════════════════════
# ELECTION VOTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.route('/api/elections')
def get_elections():
    """Get all elections."""
    try:
        response = requests.get(f'{config.INGESTION_API_URL}/api/v1/elections', timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Failed to fetch elections'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/api/regions')
def get_regions():
    """Get all regions."""
    try:
        response = requests.get(f'{config.INGESTION_API_URL}/api/v1/regions', timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Failed to fetch regions'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/api/elections/<int:election_id>/regions/<int:region_id>/candidates')
def get_candidates(election_id, region_id):
    """Get candidates for a specific election and region."""
    try:
        url = f'{config.INGESTION_API_URL}/api/v1/elections/{election_id}/regions/{region_id}/candidates'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Failed to fetch candidates'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 503


@app.route('/elections/vote', methods=['POST'])
def submit_election_vote():
    """Submit an election vote."""
    try:
        # Get JSON data
        vote_data = request.get_json()

        # Validate input
        required_fields = ['nas', 'code', 'election_id', 'region_id', 'candidate_id']
        if not all(field in vote_data for field in required_fields):
            return jsonify({
                'success': False,
                'message': 'Tous les champs sont requis.'
            }), 400

        # Submit to ingestion API
        response = requests.post(
            f'{config.INGESTION_API_URL}/api/v1/elections/vote',
            json=vote_data,
            timeout=10
        )

        # Handle responses
        if response.status_code == 202:
            return jsonify({
                'success': True,
                'message': 'Vote enregistré avec succès!'
            }), 202
        elif response.status_code == 400:
            error_data = response.json()
            return jsonify({
                'success': False,
                'message': f"Erreur: {error_data.get('detail', 'Requête invalide')}"
            }), 400
        elif response.status_code == 409:
            return jsonify({
                'success': False,
                'message': 'Vous avez déjà voté.'
            }), 409
        else:
            return jsonify({
                'success': False,
                'message': f"Erreur serveur: {response.status_code}"
            }), 500

    except requests.RequestException as e:
        return jsonify({
            'success': False,
            'message': f"Erreur de connexion à l'API: {str(e)}"
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Erreur inattendue: {str(e)}"
        }), 500


@app.route('/api/elections/<int:election_id>/regions/<int:region_id>/results')
def get_election_results(election_id, region_id):
    """Get election results for a specific region."""
    try:
        url = f'{config.INGESTION_API_URL}/api/v1/elections/{election_id}/regions/{region_id}/results'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        elif response.status_code == 404:
            return jsonify({'error': 'Election or region not found'}), 404
        else:
            return jsonify({'error': 'Failed to fetch results'}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=config.DEBUG)
