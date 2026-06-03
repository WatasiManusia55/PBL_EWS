# utils.py
import numpy as np
import re
import json

def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON/DB storage"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    return obj

def noise_label(v):
    """Label noise berdasarkan nilai RSSI"""
    if v <= -115:
        return "Bersih"
    elif v <= -105:
        return "Normal"
    elif v <= -95:
        return "Sedikit Noise"
    else:
        return "Bising"

def parse_packet(raw):
    """Parse LoRa packet to dictionary"""
    raw = raw.strip()
    if not raw:
        return None

    if raw.startswith('":'):
        raw = raw[3:]
        if not raw.startswith('{'):
            raw = '{' + raw

    if raw.startswith(':'):
        raw = '{"t"' + raw

    if not raw.startswith('{'):
        raw = '{' + raw

    if not raw.endswith('}'):
        raw += '}'

    raw = re.sub(r'([a-zA-Z]+):', r'"\1":', raw)
    raw = raw.replace("'", '"')
    raw = re.sub(r'[^\x20-\x7E]', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = {}
            pairs = re.findall(r'"?([a-zA-Z]+)"?\s*:\s*([0-9.]+)', raw)
            for key, value in pairs:
                if '.' in value:
                    data[key] = float(value)
                else:
                    data[key] = int(value)
            return data if data else None
        except:
            return None

def format_rupiah(amount):
    return "Rp{:,.0f}".format(int(amount)).replace(",", ".")