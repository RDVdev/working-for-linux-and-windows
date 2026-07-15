"""
Flask backend for the dashboard.
BUG-10 fix: Uses sys.executable instead of hardcoded 'python3'.
"""
from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import subprocess
import sys
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/run-phase', methods=['POST'])
@cross_origin()
def run_phase():
    data = request.get_json()
    phase = data.get('phase', '')
    
    script_map = {
        'phase1': 'phase1_data_profiling.py',
        'phase2': 'phase2_sequence_construction.py',
        'phase3': 'phase3_feature_engineering.py',
        'phase4': 'phase4_model_architecture.py',
        'phase5': 'phase5_evaluation.py',
        'phase6': 'phase6_preference_alignment.py',
        'phase7': 'phase7_reporting_layer.py',
    }
    
    script_name = script_map.get(phase)
    if not script_name:
        return jsonify({'status': 'error', 'message': f'Unknown phase: {phase}'}), 400
    
    if not os.path.exists(script_name):
        return jsonify({'status': 'error', 'message': f'Script not found: {script_name}'}), 404
    
    try:
        # BUG-10 fix: Use sys.executable instead of 'python3' for Windows compatibility
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Phase execution timed out (600s)'}), 504
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/status', methods=['GET'])
@cross_origin()
def get_status():
    """Check which phases have completed based on output files."""
    status = {
        'phase1': os.path.exists('data/cleaned_dataset.csv'),
        'phase2': os.path.exists('models/best_seq_len.json'),
        'phase3': os.path.exists('data/engineered_dataset.csv'),
        'phase4': os.path.exists('data/model_predictions.csv'),
        'phase5': os.path.exists('data/evaluation_metrics.csv'),
        'phase6': os.path.exists('models/rlhf_checkpoints'),
        'phase7': os.path.exists('reports/final_evaluation_report.md'),
    }
    return jsonify(status)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
