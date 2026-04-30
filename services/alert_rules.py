"""
services/alert_rules.py - Regras de alerta centralizadas

Unica fonte de verdade para avaliacao de limites.
Usada pelo route /modbus/collect e por qualquer outro ponto que precise
gerar alertas programaticamente.

Uso:
    from services.alert_rules import evaluate_alert, check_field

    alerts = evaluate_alert(temperature=87.0, vibration_rms=5.2)
    for a in alerts:
        # a = {"alert_type": ..., "severity": ..., "message": ...}
"""

from typing import Optional
from config import settings

# Unica fonte de verdade para limites - lidos do config / .env
LIMITS = {
    "temperature":   {"warning": settings.TEMP_WARNING,  "critical": settings.TEMP_CRITICAL},
    "vibration_rms": {"warning": settings.VIB_WARNING,   "critical": settings.VIB_CRITICAL},
}


def _classify(value: float, field: str) -> Optional[str]:
    """Retorna 'critical', 'warning' ou None para um campo e valor."""
    lim = LIMITS.get(field, {})
    if value >= lim.get("critical", float("inf")):
        return "critical"
    if value >= lim.get("warning", float("inf")):
        return "warning"
    return None


def check_field(field: str, value: float) -> Optional[dict]:
    """Avalia um unico campo e retorna um dict de alerta ou None."""
    severity = _classify(value, field)
    if severity is None:
        return None
    lim_value = LIMITS[field][severity]
    return {
        "alert_type": field,
        "severity":   severity,
        "message":    f"{field} {severity}: {value:.2f} (limite {lim_value})",
    }


def evaluate_alert(temperature: float, vibration_rms: float) -> list:
    """
    Avalia temperatura e vibracao e retorna lista de alertas disparados.

    Args:
        temperature:   Temperatura em graus Celsius
        vibration_rms: Vibracao RMS em g

    Returns:
        Lista de dicts (pode ser vazia se nenhum limite foi ultrapassado)
    """
    alerts = []
    for field, value in [
        ("temperature",   temperature),
        ("vibration_rms", vibration_rms),
    ]:
        result = check_field(field, value)
        if result:
            alerts.append(result)
    return alerts
