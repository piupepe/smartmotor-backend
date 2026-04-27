def evaluate_alert(temperature: float, vibration_x: float, vibration_y: float, vibration_z: float):
    max_vibration = max(vibration_x, vibration_y, vibration_z)

    temp_high = temperature >= 80
    vib_high = max_vibration >= 0.30

    if temp_high and vib_high:
        return {
            "alert_type": "temperature_and_vibration",
            "severity": "critical",
            "message": "Temperatura e vibração acima do limite"
        }

    if temp_high:
        return {
            "alert_type": "temperature_high",
            "severity": "high",
            "message": "Temperatura acima do limite recomendado"
        }

    if vib_high:
        return {
            "alert_type": "vibration_high",
            "severity": "high",
            "message": "Vibração acima do limite recomendado"
        }

    return None