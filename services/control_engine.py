"""
services/control_engine.py
"""

class PIDController:
    def __init__(
        self,
        kp: float = 0.8,
        ki: float = 0.2,
        kd: float = 0.05,
        output_min: float = 0.0,
        output_max: float = 1800.0,
        alpha: float = 0.1,
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.alpha = alpha

        self._integral   = 0.0
        self._last_meas  = None
        self._d_filtered = 0.0
        self._last_out   = 0.0

    def compute(self, setpoint: float, measured: float, dt: float) -> float:
        if dt <= 0:
            return self._last_out

        error = setpoint - measured

        # Proporcional
        p = self.kp * error

        # Integral com anti-windup
        if self.output_min < self._last_out < self.output_max:
            self._integral += error * dt
        i = self.ki * self._integral

        # Derivada sobre a medição (evita derivative kick)
        if self._last_meas is None:
            self._last_meas = measured

        raw_d = -(measured - self._last_meas) / dt
        self._d_filtered += self.alpha * (raw_d - self._d_filtered)
        d = self.kd * self._d_filtered
        self._last_meas = measured

        output = max(self.output_min, min(self.output_max, p + i + d))
        self._last_out = output
        return output

    def reset(self):
        self._integral   = 0.0
        self._last_meas  = None
        self._d_filtered = 0.0
        self._last_out   = 0.0

    def tune(self, kp=None, ki=None, kd=None):
        if kp is not None: self.kp = kp
        if ki is not None: self.ki = ki
        if kd is not None: self.kd = kd
        self.reset()

    def params(self) -> dict:
        return {"kp": self.kp, "ki": self.ki, "kd": self.kd,
                "output_min": self.output_min, "output_max": self.output_max}