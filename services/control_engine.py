class PIDController:
    def __init__(self, kp=0.8, ki=0.2, kd=0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd

        self.integral = 0
        self.last_error = 0

    def compute(self, setpoint, measured, dt):
        error = setpoint - measured

        self.integral += error * dt
        derivative = (error - self.last_error) / dt

        output = (
            self.kp * error +
            self.ki * self.integral +
            self.kd * derivative
        )

        self.last_error = error

        return output