"""
Configuration Manager for Audio Processing Pipeline

This module provides utilities to load and manage configuration from:
- JSON files (config.json)
- Environment variables (.env files)
- Default values

Usage:
    from config_manager import ConfigManager
    
    # Load from JSON
    config = ConfigManager.from_json("config.json")
    
    # Load from .env
    config = ConfigManager.from_env(".env")
    
    # Get specific settings
    input_path = config.get_input_audio_path()
    fir_settings = config.get_fir_filter_settings()
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """Manages audio processing configuration from multiple sources."""
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        """Initialize ConfigManager with configuration dictionary."""
        self.config = config_dict or self._get_default_config()
    
    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """Return default configuration values."""
        return {
            "audio_paths": {
                "input_audio": None,
                "output_audio": None,
                "reference_audio": None
            },
            "audio_processing": {
                "fir_filter": {
                    "enabled": True,
                    "low_freq": 250,
                    "high_freq": 3400,
                    "numtaps": 401,
                    "equalize": True
                },
                "wiener_denoise": {
                    "enabled": True,
                    "noise_window_s": 1.5,
                    "alpha_spec": 0.8,
                    "alpha_dd": 0.98,
                    "bias_correction": 1.5,
                    "min_gain_db": -15.0
                },
                "neural_enhancement": {
                    "enabled": True,
                    "strategy": "complex",
                    "dry_wet": 0.9,
                    "device": "cuda",
                    "model_name": "dns64"
                },
                "vad_gate": {
                    "enabled": True,
                    "frame_ms": 30,
                    "mode": 3,
                    "hang_ms": 150,
                    "atten_db": 80
                },
                "loudness_normalize": {
                    "enabled": True,
                    "target_dbfs": -20.0,
                    "top_db": 25.0
                },
                "resampling": {
                    "enabled": True,
                    "target_sr": 16000,
                    "res_type": "kaiser_best"
                }
            },
            "output_settings": {
                "save_filtered_audio": True,
                "save_vad_segments": False,
                "save_metrics": False,
                "log_processing": True
            },
            "metrics": {
                "compute_lsd": False,
                "compute_mfcc": False,
                "compute_snr": False,
                "n_fft": 512,
                "hop_length": 160
            }
        }
    
    @classmethod
    def from_json(cls, json_path: str) -> "ConfigManager":
        """Load configuration from JSON file."""
        json_path = Path(json_path)
        
        if not json_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        # Merge with defaults
        default_config = cls._get_default_config()
        merged_config = cls._merge_configs(default_config, config_dict)
        
        return cls(merged_config)
    
    @classmethod
    def from_env(cls, env_path: str = ".env") -> "ConfigManager":
        """Load configuration from environment variables (.env file)."""
        from dotenv import load_dotenv
        
        env_path = Path(env_path)
        
        if env_path.exists():
            load_dotenv(env_path)
        
        config_dict = cls._parse_env_vars()
        default_config = cls._get_default_config()
        merged_config = cls._merge_configs(default_config, config_dict)
        
        return cls(merged_config)
    
    @staticmethod
    def _parse_env_vars() -> Dict[str, Any]:
        """Parse environment variables into configuration dictionary."""
        def str_to_bool(value: str) -> bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        
        def str_to_float(value: str) -> Optional[float]:
            try:
                return float(value) if value else None
            except ValueError:
                return None
        
        def str_to_int(value: str) -> Optional[int]:
            try:
                return int(value) if value else None
            except ValueError:
                return None
        
        config = {
            "audio_paths": {
                "input_audio": os.getenv("INPUT_AUDIO_PATH"),
                "output_audio": os.getenv("OUTPUT_AUDIO_PATH"),
                "reference_audio": os.getenv("REFERENCE_AUDIO_PATH")
            },
            "audio_processing": {
                "fir_filter": {
                    "enabled": str_to_bool(os.getenv("FIR_FILTER_ENABLED", "true")),
                    "low_freq": str_to_int(os.getenv("FIR_LOW_FREQ", "250")) or 250,
                    "high_freq": str_to_int(os.getenv("FIR_HIGH_FREQ", "3400")) or 3400,
                    "numtaps": str_to_int(os.getenv("FIR_NUMTAPS", "401")) or 401,
                    "equalize": str_to_bool(os.getenv("FIR_EQUALIZE", "true"))
                },
                "wiener_denoise": {
                    "enabled": str_to_bool(os.getenv("WIENER_DENOISE_ENABLED", "true")),
                    "noise_window_s": str_to_float(os.getenv("WIENER_NOISE_WINDOW_S", "1.5")) or 1.5,
                    "alpha_spec": str_to_float(os.getenv("WIENER_ALPHA_SPEC", "0.8")) or 0.8,
                    "alpha_dd": str_to_float(os.getenv("WIENER_ALPHA_DD", "0.98")) or 0.98,
                    "bias_correction": str_to_float(os.getenv("WIENER_BIAS_CORRECTION", "1.5")) or 1.5,
                    "min_gain_db": str_to_float(os.getenv("WIENER_MIN_GAIN_DB", "-15.0")) or -15.0
                },
                "neural_enhancement": {
                    "enabled": str_to_bool(os.getenv("NEURAL_ENHANCEMENT_ENABLED", "true")),
                    "strategy": os.getenv("NEURAL_STRATEGY", "complex"),
                    "dry_wet": str_to_float(os.getenv("NEURAL_DRY_WET", "0.9")) or 0.9,
                    "device": os.getenv("NEURAL_DEVICE", "cuda"),
                    "model_name": os.getenv("NEURAL_MODEL_NAME", "dns64")
                },
                "vad_gate": {
                    "enabled": str_to_bool(os.getenv("VAD_GATE_ENABLED", "true")),
                    "frame_ms": str_to_int(os.getenv("VAD_FRAME_MS", "30")) or 30,
                    "mode": str_to_int(os.getenv("VAD_MODE", "3")) or 3,
                    "hang_ms": str_to_int(os.getenv("VAD_HANG_MS", "150")) or 150,
                    "atten_db": str_to_int(os.getenv("VAD_ATTEN_DB", "80")) or 80
                },
                "loudness_normalize": {
                    "enabled": str_to_bool(os.getenv("LOUDNESS_NORMALIZE_ENABLED", "true")),
                    "target_dbfs": str_to_float(os.getenv("LOUDNESS_TARGET_DBFS", "-20.0")) or -20.0,
                    "top_db": str_to_float(os.getenv("LOUDNESS_TOP_DB", "25.0")) or 25.0
                },
                "resampling": {
                    "enabled": str_to_bool(os.getenv("RESAMPLING_ENABLED", "true")),
                    "target_sr": str_to_int(os.getenv("RESAMPLING_TARGET_SR", "16000")) or 16000,
                    "res_type": os.getenv("RESAMPLING_RES_TYPE", "kaiser_best")
                }
            },
            "output_settings": {
                "save_filtered_audio": str_to_bool(os.getenv("SAVE_FILTERED_AUDIO", "true")),
                "save_vad_segments": str_to_bool(os.getenv("SAVE_VAD_SEGMENTS", "false")),
                "save_metrics": str_to_bool(os.getenv("SAVE_METRICS", "false")),
                "log_processing": str_to_bool(os.getenv("LOG_PROCESSING", "true"))
            },
            "metrics": {
                "compute_lsd": str_to_bool(os.getenv("COMPUTE_LSD", "false")),
                "compute_mfcc": str_to_bool(os.getenv("COMPUTE_MFCC", "false")),
                "compute_snr": str_to_bool(os.getenv("COMPUTE_SNR", "false")),
                "n_fft": str_to_int(os.getenv("METRICS_N_FFT", "512")) or 512,
                "hop_length": str_to_int(os.getenv("METRICS_HOP_LENGTH", "160")) or 160
            }
        }
        
        return config
    
    @staticmethod
    def _merge_configs(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge override config into default config."""
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._merge_configs(result[key], value)
            elif value is not None:
                result[key] = value
        
        return result
    
    # Getters for common configuration values
    
    def get_input_audio_path(self) -> Optional[str]:
        """Get input audio file path."""
        return self.config["audio_paths"]["input_audio"]
    
    def get_output_audio_path(self) -> Optional[str]:
        """Get output audio file path."""
        return self.config["audio_paths"]["output_audio"]
    
    def get_reference_audio_path(self) -> Optional[str]:
        """Get reference audio file path (for metrics)."""
        return self.config["audio_paths"]["reference_audio"]
    
    def get_fir_filter_settings(self) -> Dict[str, Any]:
        """Get FIR filter settings."""
        return self.config["audio_processing"]["fir_filter"]
    
    def get_wiener_denoise_settings(self) -> Dict[str, Any]:
        """Get Wiener denoise settings."""
        return self.config["audio_processing"]["wiener_denoise"]
    
    def get_neural_enhancement_settings(self) -> Dict[str, Any]:
        """Get neural enhancement settings."""
        return self.config["audio_processing"]["neural_enhancement"]
    
    def get_vad_gate_settings(self) -> Dict[str, Any]:
        """Get VAD gate settings."""
        return self.config["audio_processing"]["vad_gate"]
    
    def get_loudness_normalize_settings(self) -> Dict[str, Any]:
        """Get loudness normalization settings."""
        return self.config["audio_processing"]["loudness_normalize"]
    
    def get_resampling_settings(self) -> Dict[str, Any]:
        """Get resampling settings."""
        return self.config["audio_processing"]["resampling"]
    
    def get_output_settings(self) -> Dict[str, Any]:
        """Get output settings."""
        return self.config["output_settings"]
    
    def get_metrics_settings(self) -> Dict[str, Any]:
        """Get metrics settings."""
        return self.config["metrics"]
    
    def is_enabled(self, component: str) -> bool:
        """Check if a processing component is enabled."""
        components = {
            "fir_filter": "fir_filter",
            "wiener": "wiener_denoise",
            "neural": "neural_enhancement",
            "vad": "vad_gate",
            "loudness": "loudness_normalize",
            "resample": "resampling"
        }
        
        if component not in components:
            raise ValueError(f"Unknown component: {component}")
        
        return self.config["audio_processing"][components[component]]["enabled"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return self.config
    
    def to_json(self, output_path: str) -> None:
        """Save configuration to JSON file."""
        output_path = Path(output_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        print(f"Configuration saved to {output_path}")
    
    def validate(self) -> bool:
        """Validate configuration values."""
        errors = []
        
        # Check required paths
        if not self.get_input_audio_path():
            errors.append("INPUT_AUDIO_PATH is not set")
        
        if not self.get_output_audio_path():
            errors.append("OUTPUT_AUDIO_PATH is not set")
        
        # Check filter frequencies
        fir_settings = self.get_fir_filter_settings()
        if fir_settings["low_freq"] >= fir_settings["high_freq"]:
            errors.append("FIR low_freq must be less than high_freq")
        
        # Check neural enhancement strategy
        neural_settings = self.get_neural_enhancement_settings()
        valid_strategies = ["lite", "offline", "complex"]
        if neural_settings["strategy"] not in valid_strategies:
            errors.append(f"Neural strategy must be one of {valid_strategies}")
        
        # Check VAD mode
        vad_settings = self.get_vad_gate_settings()
        if vad_settings["mode"] not in (0, 1, 2, 3):
            errors.append("VAD mode must be 0, 1, 2, or 3")
        
        if errors:
            print("Configuration validation errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True


if __name__ == "__main__":
    # Example usage
    print("Loading configuration from config.json...")
    config = ConfigManager.from_json("config.json")
    
    if config.validate():
        print("✓ Configuration is valid")
        print(f"Input: {config.get_input_audio_path()}")
        print(f"Output: {config.get_output_audio_path()}")
        print(f"Neural Strategy: {config.get_neural_enhancement_settings()['strategy']}")
    else:
        print("✗ Configuration has errors")
