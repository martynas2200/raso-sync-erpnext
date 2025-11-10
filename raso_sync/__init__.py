import json
import os

# Read version from package.json
_package_json = os.path.join(os.path.dirname(__file__), "..", "package.json")
__version__ = "0.0.1"  # fallback
if os.path.exists(_package_json):
	with open(_package_json) as f:
		__version__ = json.load(f).get("version", "0.0.1")
