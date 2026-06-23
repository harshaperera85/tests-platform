"""Simulated-examinee capability.

Generates genuine simulated sessions so the platform can demonstrate end-to-end
workflows without real examinees. Response generation uses the canonical 2PL model
(``psychometrics``); the walk itself reuses the registered ``LinearStrategy`` — no
engine/assembly/contract code is duplicated or changed.
"""

from app.simulation.examinee import SimulationResult, SimulationStep, simulate_linear

__all__ = ["SimulationResult", "SimulationStep", "simulate_linear"]
