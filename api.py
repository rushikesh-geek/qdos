from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import numpy as np

from quantum_optimizer import (
    DEFAULT_DRUG_LIBRARY,
    OptimizationConfig,
    run_optimization,
    compute_synergy_matrix,
    get_qubo_terms,
)
from schedule_input import generate_standard_schedule_for_drugs
from simulator import TumorSimulator

app = FastAPI(title="Q-DOS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PatientData(BaseModel):
    age: int = 40
    days: int = 14
    dt: float = 1.0
    selected_drugs: List[str] = ["Pembrolizumab", "Cisplatin", "Paclitaxel"]
    patient_profile: Dict[str, float] = {"kidney": 1.0, "liver": 1.0, "marrow": 1.0, "immune": 1.0, "vascular": 1.0}
    subtype_scores: Dict[str, float] = {"BRCA": 0.5, "PDL1": 0.5, "VEGF": 0.5}
    mutually_exclusive_pairs: List[List[str]] = []
    gap_constraints: Dict[str, int] = {}
    dose_levels: Dict[str, float] = {}
    efficacy_levels: Dict[str, float] = {}
    toxicity_levels: Dict[str, float] = {}
    max_drugs_per_day: int = 2
    base_toxicity_budget: float = 10.0
    toxicity_weight: float = 0.1
    toxicity_flush_rate: float = 0.0  # patient clearance rate (0..1)

@app.get("/drugs")
def get_drugs():
    return DEFAULT_DRUG_LIBRARY

@app.post("/simulate")
def simulate(patient: PatientData):
    if not patient.selected_drugs:
        return {"error": "No drugs selected. Choose at least one drug to optimize a schedule."}

    profile_with_age = {**patient.patient_profile, "age": patient.age}
    
    config = OptimizationConfig(
        days=patient.days,
        selected_drugs=patient.selected_drugs,
        patient_profile=profile_with_age,
        subtype_scores=patient.subtype_scores,
        mutually_exclusive_pairs=[tuple(p) for p in patient.mutually_exclusive_pairs],
        gap_constraints=patient.gap_constraints,
        dose_levels=patient.dose_levels,
        efficacy_levels=patient.efficacy_levels,
        toxicity_levels=patient.toxicity_levels,
        max_drugs_per_day=patient.max_drugs_per_day,
        base_toxicity_budget=patient.base_toxicity_budget,
        beta=patient.toxicity_weight,
        toxicity_flush_rate=patient.toxicity_flush_rate,
    )

    try:
        solution = run_optimization(config)
    except Exception as e:
        return {"error": str(e)}

    simulator = TumorSimulator(
        days=patient.days,
        dt=float(patient.dt),
        patient_profile=profile_with_age,
        subtype_scores=patient.subtype_scores
    )

    standard_schedule = generate_standard_schedule_for_drugs(patient.selected_drugs, patient.days)

    dose_levels = patient.dose_levels or {}
    efficacy_levels = patient.efficacy_levels or {}

    def build_dose_schedule(binary_schedule: Dict[str, Any]) -> Dict[str, List[float]]:
        out: Dict[str, List[float]] = {}
        for drug in patient.selected_drugs:
            series = binary_schedule.get(drug, [0] * patient.days)
            dlevel = float(dose_levels.get(drug, 1.0))
            emult = float(efficacy_levels.get(drug, 1.0))
            out[drug] = [float(v) * dlevel * emult for v in series]
        return out

    # Use dose-aware schedules internally for simulation
    dose_schedule = build_dose_schedule(solution.schedule)
    dose_standard_schedule = build_dose_schedule(standard_schedule)

    t_notx, pop_notx = simulator.simulate_no_treatment()
    t_standard, pop_standard = simulator.simulate_treatment(dose_standard_schedule)
    t_tx, pop_tx = simulator.simulate_treatment(dose_schedule)

    # Calculate toxicity arrays (with flushing)
    from quantum_optimizer import get_effective_toxicity
    budget = patient.base_toxicity_budget - 0.5 * (patient.age - 40)
    tox_daily = np.zeros(patient.days)
    tox_standard_daily = np.zeros(patient.days)

    organ_toxicity = {
        "kidney": np.zeros(patient.days),
        "liver": np.zeros(patient.days),
        "marrow": np.zeros(patient.days),
        "immune": np.zeros(patient.days),
        "vascular": np.zeros(patient.days),
    }
    standard_organ_toxicity = {
        "kidney": np.zeros(patient.days),
        "liver": np.zeros(patient.days),
        "marrow": np.zeros(patient.days),
        "immune": np.zeros(patient.days),
        "vascular": np.zeros(patient.days),
    }

    toxicity_levels = patient.toxicity_levels or {}

    def accumulate_toxicity(schedule, daily_target, organ_target):
        for drug in patient.selected_drugs:
            if drug not in schedule:
                continue

            drug_toxicity = DEFAULT_DRUG_LIBRARY.get(drug, {}).get("toxicity", {})
            t_eff = get_effective_toxicity(drug, config)
            dose_level = float(dose_levels.get(drug, 1.0))
            tox_level = float(toxicity_levels.get(drug, 1.0))

            for t, val in enumerate(schedule[drug]):
                dose_factor = float(val)
                if dose_factor <= 0:
                    continue

                daily_target[t] += t_eff * dose_factor

                for organ, organ_value in drug_toxicity.items():
                    profile_value = profile_with_age.get(organ, 1.0)
                    if profile_value > 0:
                        organ_target[organ][t] += (organ_value * dose_level * tox_level * dose_factor) / profile_value

    accumulate_toxicity(solution.schedule, tox_daily, organ_toxicity)
    accumulate_toxicity(standard_schedule, tox_standard_daily, standard_organ_toxicity)

    clearance = float(patient.toxicity_flush_rate)
    clearance = min(max(clearance, 0.0), 1.0)

    def flush_series(daily: np.ndarray) -> np.ndarray:
        """Toxicity burden that decreases on rest days.

        - If no drug is given that day (daily tox == 0), toxicity burden clears by (1-clearance).
        - If drug is given, toxicity burden accumulates.
        """
        state = np.zeros_like(daily, dtype=float)
        eps = 1e-12
        for i in range(len(daily)):
            prev = state[i - 1] if i > 0 else 0.0
            if daily[i] <= eps:
                prev = prev * (1.0 - clearance)
                state[i] = prev
            else:
                state[i] = prev + float(daily[i])
        return state

    tox_state = flush_series(tox_daily)
    tox_standard_state = flush_series(tox_standard_daily)

    organ_state = {organ: flush_series(values) for organ, values in organ_toxicity.items()}
    standard_organ_state = {organ: flush_series(values) for organ, values in standard_organ_toxicity.items()}

    daily_drug_count = [int(sum(1 for drug in patient.selected_drugs if solution.schedule.get(drug, [0])[t])) for t in range(patient.days)]

    serialized_schedule = {k: v.tolist() if hasattr(v, "tolist") else v for k, v in solution.schedule.items()}
    serialized_standard_schedule = {k: v.tolist() if hasattr(v, "tolist") else v for k, v in standard_schedule.items()}
    # Intentionally omit dose/time schedule from API output (kept internal only)

    # Synergy matrix + energy vector (QUBO linear terms)
    synergy = compute_synergy_matrix(config)
    qubo_terms = get_qubo_terms(config)
    linear_terms = qubo_terms.get("linear", {})
    energy_vector = {
        drug: [float(linear_terms.get(f"x_{drug}_{t}", 0.0)) for t in range(patient.days)]
        for drug in patient.selected_drugs
    }

    return {
        "solution": {
            "schedule": serialized_schedule,
            "standard_schedule": serialized_standard_schedule,
            "metrics": {
                "objective_score": solution.metrics.get("score", 0.0),
                "total_efficacy": 0.0, # We can omit or calculate
                "total_toxicity": float(np.sum(tox_daily))
            }
        },
        "model": {
            "dt": float(patient.dt),
            "toxicity_weight": float(patient.toxicity_weight),
            "toxicity_flush_rate": float(patient.toxicity_flush_rate),
            "synergy_matrix": synergy,
            "energy_vector": energy_vector,
        },
        "charts": {
            "tumor_no_treatment": pop_notx.tolist(),
            "tumor_standard": pop_standard.tolist(),
            "tumor_std": pop_notx.tolist(),
            "tumor_qdos": pop_tx.tolist(),
            "tox_qdos": tox_state.tolist(),
            "tox_standard": tox_standard_state.tolist(),
            "t_days": t_notx.tolist(),
            "budget": budget,
            "daily_drug_count": daily_drug_count,
            "organ_toxicity": {organ: values.tolist() for organ, values in organ_state.items()},
            "standard_organ_toxicity": {organ: values.tolist() for organ, values in standard_organ_state.items()},
        }
    }
