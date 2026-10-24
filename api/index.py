import sys
import os

# Add parent directory (project root) to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
