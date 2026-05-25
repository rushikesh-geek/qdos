import numpy as np
from scipy.integrate import odeint
from tumor_model import GompertzTumorModel

class TumorSimulator:
    def __init__(self, initial_cells=1e7, days=14, dt=0.1, patient_profile=None, subtype_scores=None):
        self.initial_cells = initial_cells
        self.days = days
        self.dt = dt
        self.time_points = np.arange(0, days, dt)
        self.model = GompertzTumorModel()
        if patient_profile:
            self.model.set_patient_profile(patient_profile, subtype_scores or {})

    def simulate_treatment(self, schedule):
        self.model.set_schedule(schedule)
        
        # ODE simulation
        result = odeint(
            self.model.gompertz_equation, 
            self.initial_cells, 
            self.time_points
        )
        return self.time_points, result.flatten()

    def simulate_no_treatment(self):
        result = odeint(
            self.model.gompertz_no_treatment, 
            self.initial_cells, 
            self.time_points
        )
        return self.time_points, result.flatten()
