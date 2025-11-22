#!/bin/bash
# Launch the Voting System Test GUI

echo "🗳️  Starting Voting System Test GUI..."
echo ""
echo "The GUI will open in your browser at http://localhost:8501"
echo ""

# Install dependencies if needed
pip3 install -q -r tests/gui_requirements.txt

# Run Streamlit
streamlit run tests/voting_test_gui.py
