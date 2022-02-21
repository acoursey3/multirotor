from typing import Iterable, List, Union
from dataclasses import dataclass

import numpy as np



@dataclass
class MotorParams:

    # See: http://learningrc.com/motor-kv/, http://web.mit.edu/first/scooter/motormath.pdf
    k_m: float
    "Motor constant, where omega = k_m * back_emf, and k_m = 1/k_e"
    k_e: float = None
    "Back-EMF constant, relates motor speed induced voltage, back_emf = k_e * omega"
    k_q: float = None
    "Torque constant k_q, where torque Q = k_q * current. Equal to k_e"


@dataclass
class PropellerParams:

    moment_of_inertia: float
    
    # Manufacturer propeller length x pitch specification:
    diameter: float = 6  #inches
    pitch: float = 3   #inches

    a: float = 5.7
    "Lift curve slope used in example in Stevens & Lewis (eq 2.2-6a)"
    # d C_L / d alpha = 2 pi / (sqrt(1-M^2)), where M is mach number, alpha is 
    # aerodynamic angle of x-axis of body and x-axis of stability
    b: float = 2
    "Number of blades"
    c: float = 0.0274
    "Mean chord length (m) of the propeller blade"
    eta: float = 1.
    "Propeller efficiency"

    k_thrust: float = None
    "Propeller's aerodynamic thrust coefficient, where thrust =  k_thrust * angular velocity^2"
    k_torque: float = None
    "Torque constant, where torque = k_torque * angular velocity^2"

    motor: MotorParams = None
    "The parameters of the motor to simulate speed, otherwise instantaneous."

    def __post_init__(self):
        # ensure torque function gets floats so adding float + int in the njit
        # torque function is not ignored
        self.moment_of_inertia = float(self.moment_of_inertia)
        self.R = self.diameter * 0.0254 # inches to metres
        "Radius in metres"
        self.A = np.pi * self.R**2
        "Area of propeller disc in metres squared"
        self.theta0 = 2*np.arctan2(self.pitch, (2 * np.pi * 3/4 * self.diameter/2))
        "Pitch angle at root of blade"
        self.theta1 = -4 / 3 * np.arctan2(self.pitch, 2 * np.pi * 3/4 * self.diameter/2)
        "Change in pitch angle towards tip of blade"
        # Pitch angel is reduced to allow for even lift as blade velocity increases
        # with increasing radius. Assuming linear reduction from root to tip.



@dataclass
class VehicleParams:

    propellers: List[PropellerParams]
    angles: np.ndarray
    "Angle (radians) of propeller arm from the positive x-axis (forward) of the body frame."
    distances: np.ndarray
    "Distance (m) of each propeller from the centre of mass."
    clockwise: np.ndarray = None
    """1 if motor spins clockwise, -1 if anti-clockwise, looking from the top.
    Defaults to alternating clockwise/anti-clockwise."""

    mass: float = 1.
    inertia_matrix: np.matrix = np.eye(3)


    def __post_init__(self):
        self.distances = self.distances.astype(float)
        self.inertia_matrix_inverse = np.linalg.inv(self.inertia_matrix)
        if self.clockwise is None:
            self.clockwise = np.ones(len(self.propellers), dtype=int)
            self.clockwise[::2] = 1
            self.clockwise[1::2] = -1
        
        # Set up control allocation matrix if thrust and motor torque constants
        # are provided
        if (
            all([p.k_thrust is not None for p in self.propellers]) and \
            all([p.k_torque is not None for p in self.propellers])
        ):
            alloc = np.zeros((4, len(self.propellers))) #[Fz, Mx, My, Mz] x n-Propellers
            x = self.distances * np.sin(self.angles)
            y = self.distances * np.cos(self.angles)
            for i, p in enumerate(self.propellers):
                alloc[0, i] = -p.k_thrust                       # vertical force (negative up)
                alloc[1, i] = p.k_thrust * x[i]                 # torque about x-axis
                alloc[2, i] = p.k_thrust * y[i]                 # torque about y-axis
                alloc[3, i] = p.k_torque * self.clockwise[i]    # torque about z-axis
            self.alloc = alloc
            self.alloc_inverse = np.linalg.pinv(alloc)
        else:
            self.alloc = None
            self.alloc_inverse = None



@dataclass
class SimulationParams:

    dt: float = 1e-2
    """Timestep of simulation"""
    g: float = 9.81
    """Gravitational acceleration"""
    rho: float = 1.225
    "Air density kg/m^3 at MSL"