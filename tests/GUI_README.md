# 🗳️ Voting System Test GUI

Interactive web-based testing interface for the voting system.

## Features

### 🚀 Load Testing
- Configure number of votes (1 - 1,000,000)
- Set vote submission rate (10 - 10,000 votes/sec)
- **Error Injection:**
  - Choose percentage or fixed count of errors
  - Error types:
    - Scrambled Data (invalid NAS/code)
    - Invalid Hash (not in database)
    - Already Voted (duplicate)

### 📝 Manual Vote Submission
- Enter NAS and Code manually
- **Autofill from Valid Hashes:**
  - Load list of 100 valid hashes
  - Select from dropdown
  - Automatically fills NAS/code
- **Generate Scrambled Data:**
  - Randomly generate invalid credentials for testing
- Live validation:
  - Shows if hash is valid
  - Shows if already voted
  - Preview vote JSON before submission

### 🔧 Database Control
- **Reset Database to Zero:**
  - Clears all vote results
  - Clears audit log
  - Clears duplicate attempts
  - Clears voted hashes in Redis
- **Reload Test Hashes:**
  - Quick link to regenerate 100K test hashes
- **Quick Stats:**
  - Vote results count
  - Audit log entries
  - Duplicate attempts

### 📊 Live Monitoring
- Real-time vote counts per law
- Total votes across all laws
- Valid hashes in Redis
- Voted hashes in Redis
- Vote distribution charts

### 📈 Results Tracking
- View submission history
- See status codes and responses
- Export results
- Clear history

## Installation

```bash
# Install dependencies
pip3 install -r tests/gui_requirements.txt
```

## Usage

### Quick Start

```bash
# Run the GUI (easiest)
./tests/run_gui.sh
```

Or manually:

```bash
# From project root
streamlit run tests/voting_test_gui.py
```

The GUI will open in your browser at: **http://localhost:8501**

## Workflow Examples

### Example 1: Load Test with Errors

1. Go to **"Load Testing"** tab
2. Set "Number of Votes": 10,000
3. Set "Votes per Second": 1,000
4. Enable "Error Injection"
5. Choose "Percentage" mode
6. Set error percentage: 5%
7. Select error types (e.g., "Scrambled Data", "Already Voted")
8. Click "Start Load Test"
9. Run the displayed command in terminal
10. Monitor results in **"📊 Live Statistics"** sidebar

### Example 2: Manual Vote Testing

1. Go to **"Manual Vote"** tab
2. Check "Autofill from Valid Hashes"
3. Click "Load Valid Hashes"
4. Select a hash from dropdown
5. NAS and Code will auto-fill
6. Select Law ID (e.g., L2025-001)
7. Choose vote (oui/non)
8. Review preview JSON
9. Click "Submit Vote"
10. Check **"Results"** tab for submission history

### Example 3: Test Invalid Data

1. Go to **"Manual Vote"** tab
2. Click "Generate Scrambled Data"
3. Copy the generated NAS/Code
4. Paste into form
5. Submit vote
6. Observe error response (should be rejected)

### Example 4: Reset Everything

1. Go to **"Database Control"** tab
2. Check "I understand this will delete all data"
3. Click "Reset Database to Zero"
4. Click "Reload Test Hashes" (run command in terminal)
5. Start fresh testing

## Tips

- **Always reset database** before major load tests for clean results
- **Use autofill** to test with valid credentials quickly
- **Generate scrambled data** to test error handling
- **Monitor sidebar stats** during load tests to see real-time progress
- **Error injection** helps test validation worker and review queue

## Troubleshooting

### GUI won't start
```bash
# Reinstall dependencies
pip3 install --upgrade -r tests/gui_requirements.txt

# Check if ports are available
lsof -i :8501
```

### Can't connect to services
- Ensure Docker containers are running: `docker ps`
- Check API is accessible: `curl http://localhost:8000/health`
- Verify Redis: `redis-cli -h localhost ping`
- Check PostgreSQL: `docker exec voting-postgres pg_isready`

### Load test commands not working
- The GUI shows the command to run
- Copy and paste into a separate terminal
- The GUI coordinates with the command-line tool

## Screenshots

### Load Testing Tab
Configure vote count, rate, and error injection options.

### Manual Vote Tab
Submit individual votes with autofill and validation.

### Database Control Tab
Reset database and manage test data.

### Results Tab
View submission history and vote distribution.

## Technical Details

- **Frontend:** Streamlit (Python web framework)
- **Database:** PostgreSQL + Redis
- **API:** FastAPI (localhost:8000)
- **Real-time Updates:** Auto-refresh on action

## Security Note

⚠️ This GUI is for **TESTING ONLY**. Do not expose to public networks.

## Support

For issues or feature requests, please refer to the main project documentation.
