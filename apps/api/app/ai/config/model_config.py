"""AI model configuration."""

import yaml
from pathlib import Path

def load_model_config():
    """Load AI model configuration."""
    config_path = Path(__file__).parent / "model_config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}
