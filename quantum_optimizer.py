import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from qiskit_optimization import QuadraticProgram
from qiskit_algorithms.minimum_eigensolvers import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_optimization.algorithms import MinimumEigenOptimizer


DEFAULT_DRUG_LIBRARY = {
    "Pembrolizumab": {"efficacy": 3.0, "toxicity": {"kidney": 0.2, "liver": 0.1, "marrow": 0.4, "immune": 0.1, "vascular": 0.2}},
    "Cisplatin": {"efficacy": 2.5, "toxicity": {"kidney": 0.1, "liver": 0.3, "marrow": 0.2, "immune": 0.3, "vascular": 0.1}},
    "Paclitaxel": {"efficacy": 3.5, "toxicity": {"kidney": 0.4, "liver": 0.2, "marrow": 0.1, "immune": 0.1, "vascular": 0.2}},
}

DEFAULT_SYNERGY = {
    ("Pembrolizumab", "Cisplatin"): {"base_synergy": 0.5, "optimal_delay": 0, "beta": 1.0, "pathway_weights": {"BRCA": 0.5, "PDL1": 0.1, "VEGF": 0.4}},
    ("Pembrolizumab", "Paclitaxel"): {"base_synergy": -0.2, "optimal_delay": 1, "beta": 0.5, "pathway_weights": {"BRCA": 0.2, "PDL1": 0.6, "VEGF": 0.2}},
}

@dataclass
class OptimizationConfig:
    days: int = 14
    selected_drugs: list = field(default_factory=list)
    patient_profile: dict = field(default_factory=dict)
    subtype_scores: dict = field(default_factory=dict)
    mutually_exclusive_pairs: list = field(default_factory=list)
    gap_constraints: dict = field(default_factory=dict)
    dose_levels: Dict[str, float] = field(default_factory=dict)
    efficacy_levels: Dict[str, float] = field(default_factory=dict)
    toxicity_levels: Dict[str, float] = field(default_factory=dict)
    max_drugs_per_day: int = 2
    base_toxicity_budget: float = 10.0
    alpha: float = 10.0  # Increased from 1.0 - weight efficacy more heavily
    beta: float = 0.1   # Toxicity penalty weight
    toxicity_flush_rate: float = 0.0  # 0.0=no recovery, 1.0=instant recovery
    gamma: float = 100.0
    lambda_daily: float = 50.0
    lambda_gap: float = 500.0

@dataclass
class OptimizationSolution:
    schedule: Dict[str, np.ndarray]
    per_day_drugs: Dict[int, List[str]]
    metrics: dict
    status: str

def get_effective_toxicity(drug, config):
    """
    Calculate effective toxicity of a drug based on patient organ function.
    Returns the base toxicity scaled by organ health (lower = more toxic to patient).
    """
    profile = config.patient_profile
    tox = DEFAULT_DRUG_LIBRARY.get(drug, {}).get("toxicity", {})
    if not tox: return 0.0
    
    # Sum toxicity across organs, scaled inversely by organ function
    # If organ_health = 0.5 (compromised), toxicity is amplified (divide by 0.5 = 2x)
    eff_tox = 0.0
    for organ, tox_val in tox.items():
        organ_health = profile.get(organ, 1.0)
        if organ_health > 0:
            eff_tox += tox_val / organ_health
        else:
            eff_tox += tox_val * 10  # Organ failure = extreme toxicity
    
    # Scale by age adjustment
    age = profile.get("age", 40)
    age_factor = 1.0 + 0.01 * (age - 40)  # 1% increase per year over 40
    
    dose = float(config.dose_levels.get(drug, 1.0)) if hasattr(config, "dose_levels") else 1.0
    tox_level = float(config.toxicity_levels.get(drug, 1.0)) if hasattr(config, "toxicity_levels") else 1.0
    return eff_tox * age_factor * dose * tox_level


def get_effective_efficacy(drug, config):
    base_eff = DEFAULT_DRUG_LIBRARY.get(drug, {}).get("efficacy", 0.1)
    dose = float(config.dose_levels.get(drug, 1.0)) if hasattr(config, "dose_levels") else 1.0
    eff_level = float(config.efficacy_levels.get(drug, 1.0)) if hasattr(config, "efficacy_levels") else 1.0
    return base_eff * dose * eff_level


def compute_synergy_matrix(config: OptimizationConfig):
    """Compute an (N x N) synergy matrix for the selected drugs.

    Uses DEFAULT_SYNERGY base synergy adjusted by subtype factor and dose levels.
    Timing is summarized at the optimal delay (timing factor = 1).
    """
    drugs = list(config.selected_drugs)
    n = len(drugs)
    idx = {d: i for i, d in enumerate(drugs)}
    mat = [[0.0 for _ in range(n)] for _ in range(n)]

    for (d1, d2), syn_data in DEFAULT_SYNERGY.items():
        if d1 not in idx or d2 not in idx:
            continue

        base = float(syn_data.get("base_synergy", 0.0))
        p_weights = syn_data.get("pathway_weights", {})
        subtype_f = sum(p_weights.get(pw, 0.0) * config.subtype_scores.get(pw, 0.0) for pw in p_weights)
        subtype_f = subtype_f if subtype_f > 0 else 1.0

        dose1 = float(config.dose_levels.get(d1, 1.0))
        dose2 = float(config.dose_levels.get(d2, 1.0))

        # Match the optimizer's synergy scaling (binary assumption) but include dose levels.
        val = base * 4.0 * dose1 * dose2 * subtype_f

        i, j = idx[d1], idx[d2]
        mat[i][j] = val
        mat[j][i] = val

    return {"drugs": drugs, "matrix": mat}


def _pair_key(a: str, b: str):
    return (a, b) if a <= b else (b, a)


def _build_toxicity_gram_terms(days: int, decay: float):
    """Precompute sums used for dynamic toxicity penalty with flushing.

    Toxicity state: S_t = sum_{k<=t} decay^(t-k) * daily_tox_k.
    Returns:
      - w_sum[k] = sum_t W[t,k]
      - g[k][k2] = sum_t W[t,k] * W[t,k2]
    """
    g = [[0.0 for _ in range(days)] for _ in range(days)]
    w_sum = [0.0 for _ in range(days)]

    for k in range(days):
        for t in range(k, days):
            w_sum[k] += decay ** (t - k)

    for k in range(days):
        for k2 in range(days):
            m = k if k > k2 else k2
            s = 0.0
            for t in range(m, days):
                s += (decay ** (t - k)) * (decay ** (t - k2))
            g[k][k2] = s

    return w_sum, g


def get_qubo_terms(config: OptimizationConfig):
    """Return raw linear/quadratic coefficient dictionaries used for QUBO construction."""
    drugs = config.selected_drugs
    days = config.days

    budget = config.base_toxicity_budget - 0.5 * (config.patient_profile.get("age", 40) - 40)
    decay = 1.0 - float(getattr(config, "toxicity_flush_rate", 0.0))
    decay = min(max(decay, 0.0), 1.0)

    linear: Dict[str, float] = {}
    quadratic: Dict[Tuple[str, str], float] = {}

    # 1) Efficacy
    for d in drugs:
        eff = get_effective_efficacy(d, config)
        for t in range(days):
            var = f"x_{d}_{t}"
            linear[var] = linear.get(var, 0.0) - config.alpha * eff

    # 2) Dynamic Synergy (pairwise, time dependent)
    for (d1, d2), syn_data in DEFAULT_SYNERGY.items():
        if d1 not in drugs or d2 not in drugs:
            continue

        base = float(syn_data.get("base_synergy", 0.0))
        opt_delay = int(syn_data.get("optimal_delay", 0))
        beta_t = float(syn_data.get("beta", 1.0))
        p_weights = syn_data.get("pathway_weights", {})

        subtype_f = sum(p_weights.get(pw, 0.0) * config.subtype_scores.get(pw, 0.0) for pw in p_weights)
        subtype_f = subtype_f if subtype_f > 0 else 1.0

        dose1 = float(config.dose_levels.get(d1, 1.0))
        dose2 = float(config.dose_levels.get(d2, 1.0))
        dose_factor = 4.0 * dose1 * dose2

        for t1 in range(days):
            for t2 in range(days):
                timing_factor = float(np.exp(-beta_t * abs((t2 - t1) - opt_delay)))
                val = base * dose_factor * timing_factor * subtype_f
                if val == 0:
                    continue

                v1, v2 = f"x_{d1}_{t1}", f"x_{d2}_{t2}"
                if v1 == v2:
                    continue

                key = _pair_key(v1, v2)
                quadratic[key] = quadratic.get(key, 0.0) - config.alpha * val

    # 3) Dynamic toxicity penalty with flushing
    # Minimize: beta * sum_t (S_t - budget)^2
    # where S_t includes exponential carry-over of previous toxicity.
    w_sum, g = _build_toxicity_gram_terms(days=days, decay=decay)

    t_eff_by_drug = {d: get_effective_toxicity(d, config) for d in drugs}

    for d in drugs:
        t_eff = t_eff_by_drug[d]
        for k in range(days):
            var = f"x_{d}_{k}"
            linear[var] = linear.get(var, 0.0) + config.beta * (t_eff * t_eff * g[k][k] - 2.0 * budget * t_eff * w_sum[k])

    for i, d1 in enumerate(drugs):
        t1 = t_eff_by_drug[d1]
        for j, d2 in enumerate(drugs):
            if j < i:
                continue
            t2 = t_eff_by_drug[d2]
            for k in range(days):
                v1 = f"x_{d1}_{k}"
                k2_start = k + 1 if d1 == d2 else 0
                for k2 in range(k2_start, days):
                    v2 = f"x_{d2}_{k2}"
                    if v1 == v2:
                        continue
                    key = _pair_key(v1, v2)
                    quadratic[key] = quadratic.get(key, 0.0) + config.beta * (2.0 * t1 * t2 * g[k][k2])

    # 4) Max drugs per day
    for t in range(days):
        M = config.max_drugs_per_day
        for d in drugs:
            v1 = f"x_{d}_{t}"
            linear[v1] = linear.get(v1, 0.0) + config.lambda_daily * (1 - 2 * M)
        for i, d1 in enumerate(drugs):
            v1 = f"x_{d1}_{t}"
            for d2 in drugs[i + 1:]:
                v2 = f"x_{d2}_{t}"
                key = _pair_key(v1, v2)
                quadratic[key] = quadratic.get(key, 0.0) + config.lambda_daily * 2.0

    # 5) Mutually exclusive
    for (d1, d2) in config.mutually_exclusive_pairs:
        if d1 in drugs and d2 in drugs:
            for t in range(days):
                v1, v2 = f"x_{d1}_{t}", f"x_{d2}_{t}"
                key = _pair_key(v1, v2)
                quadratic[key] = quadratic.get(key, 0.0) + config.gamma

    # 6) Inter-dose gap constraints
    for d, min_gap in config.gap_constraints.items():
        if d in drugs:
            for t in range(days - 1):
                for gap_step in range(1, int(min_gap) + 1):
                    if t + gap_step < days:
                        v1, v2 = f"x_{d}_{t}", f"x_{d}_{t + gap_step}"
                        key = _pair_key(v1, v2)
                        quadratic[key] = quadratic.get(key, 0.0) + config.lambda_gap

    return {
        "linear": linear,
        "quadratic": quadratic,
        "budget": budget,
        "decay": decay,
    }

def build_quadratic_program(config: OptimizationConfig):
    qp = QuadraticProgram()
    drugs = config.selected_drugs
    days = config.days

    # Variables
    for d in drugs:
        for t in range(days):
            qp.binary_var(f"x_{d}_{t}")

    terms = get_qubo_terms(config)
    linear = terms["linear"]
    quadratic = terms["quadratic"]

    # Scale coefficients moderately to prevent numerical issues but preserve parameter differences
    max_lin = max(abs(v) for v in linear.values()) if linear else 1.0
    max_quad = max(abs(v) for v in quadratic.values()) if quadratic else 1.0
    scale = max(max_lin, max_quad)
    if scale > 1e6:
        for k in list(linear.keys()):
            linear[k] /= scale
        for k in list(quadratic.keys()):
            quadratic[k] /= scale

    print(f"[QUBO] Budget={terms['budget']:.2f}, Alpha={config.alpha}, Beta={config.beta}, Flush={getattr(config, 'toxicity_flush_rate', 0.0):.2f}")
    print(f"[QUBO] Max linear coeff={max_lin:.4f}, Max quadratic coeff={max_quad:.4f}")

    qp.minimize(linear=linear, quadratic=quadratic)
    return qp

def _solve_with_numpy(qp):
    from qiskit_optimization.algorithms import MinimumEigenOptimizer
    from qiskit_algorithms import NumPyMinimumEigensolver
    
    num_vars = qp.get_num_vars()
    
    # For small problems, use exact solver (fast and optimal)
    if num_vars <= 14:
        mes = NumPyMinimumEigensolver()
        optimizer = MinimumEigenOptimizer(mes)
        return qp, optimizer.solve(qp)
    
    # For larger problems, use simulated annealing with proper QUBO evaluation
    print(f"[Solver] Problem size {num_vars} exceeds exact threshold. Using simulated annealing...")
    return qp, _simulated_annealing_qubo(qp)

def _simulated_annealing_qubo(qp):
    """Solve QUBO using simulated annealing with proper objective evaluation."""
    import numpy as np
    
    num_vars = qp.get_num_vars()
    
    # Extract linear and quadratic coefficients from the quadratic program
    linear_dict = {}
    quadratic_dict = {}
    
    # Initialize linear terms
    for i, var in enumerate(qp.variables):
        linear_dict[var.name] = 0.0
    
    # Extract coefficients from the objective
    objective = qp.objective
    if objective is not None:
        # Linear terms - these are stored in the objective.linear property
        try:
            if hasattr(objective, 'linear'):
                linear_coeffs = objective.linear
                if hasattr(linear_coeffs, 'to_dict'):
                    linear_dict.update(linear_coeffs.to_dict())
                elif hasattr(linear_coeffs, 'items'):
                    for var_name, coeff in linear_coeffs.items():
                        linear_dict[var_name] = coeff
                elif hasattr(linear_coeffs, '__iter__'):
                    # Array-like access
                    for i, coeff in enumerate(linear_coeffs):
                        if i < len(qp.variables):
                            linear_dict[qp.variables[i].name] = coeff
        except Exception as e:
            print(f"[Warning] Could not extract linear terms: {e}")
        
        # Quadratic terms - these are stored in objective.quadratic
        try:
            if hasattr(objective, 'quadratic'):
                quadratic_coeffs = objective.quadratic
                if hasattr(quadratic_coeffs, 'to_dict'):
                    for (i, j), coeff in quadratic_coeffs.to_dict().items():
                        var_i = qp.variables[i].name
                        var_j = qp.variables[j].name
                        quadratic_dict[(var_i, var_j)] = coeff
                elif hasattr(quadratic_coeffs, 'items'):
                    for (i, j), coeff in quadratic_coeffs.items():
                        var_i = qp.variables[i].name
                        var_j = qp.variables[j].name
                        quadratic_dict[(var_i, var_j)] = coeff
        except Exception as e:
            print(f"[Warning] Could not extract quadratic terms: {e}")
    
    def evaluate_solution(x_binary):
        """Evaluate the FULL QUBO objective including all quadratic and linear terms."""
        obj = 0.0
        
        # Linear terms
        for i, var in enumerate(qp.variables):
            var_name = var.name
            coeff = linear_dict.get(var_name, 0.0)
            obj += coeff * x_binary[i]
        
        # Quadratic terms: coefficient * x_i * x_j for all i,j pairs
        for (var_i, var_j), coeff in quadratic_dict.items():
            # Find indices of these variables
            idx_i = None
            idx_j = None
            for idx, var in enumerate(qp.variables):
                if var.name == var_i:
                    idx_i = idx
                if var.name == var_j:
                    idx_j = idx
            
            if idx_i is not None and idx_j is not None:
                obj += coeff * x_binary[idx_i] * x_binary[idx_j]
        
        return obj
    
    # Start with multiple random initializations to avoid local optima
    best_x = None
    best_energy = float('inf')
    
    # Try multiple random initializations with different sparsity levels
    sparsity_levels = [0.2, 0.3, 0.4, 0.5, 0.6]
    for init_attempt, sparsity in enumerate(sparsity_levels):
        current_x = np.zeros(num_vars, dtype=int)
        for i in range(num_vars):
            if np.random.random() < sparsity:
                current_x[i] = 1
        
        current_energy = evaluate_solution(current_x)
        
        # Simulated annealing parameters
        temperature = 10.0  # Higher initial temperature for better exploration
        cooling_rate = 0.98  # Slower cooling to avoid premature convergence
        sa_iterations = 2000  # More iterations for better convergence
        
        # Run simulated annealing from this initialization
        for iteration in range(sa_iterations):
            # Single bit flip move
            idx = np.random.randint(0, num_vars)
            neighbor_x = current_x.copy()
            neighbor_x[idx] = 1 - neighbor_x[idx]
            neighbor_energy = evaluate_solution(neighbor_x)
            
            # Metropolis criterion
            delta_energy = neighbor_energy - current_energy
            if delta_energy < 0 or (temperature > 0 and np.random.random() < np.exp(-delta_energy / max(temperature, 0.001))):
                current_x = neighbor_x
                current_energy = neighbor_energy
                
                # Track best solution found
                if current_energy < best_energy:
                    best_x = current_x.copy()
                    best_energy = current_energy
            
            # Cool down temperature
            temperature *= cooling_rate
            
            # Early stopping if temperature is very low
            if temperature < 0.0001:
                break
        
        print(f"[SA] Init {init_attempt}: sparsity={sparsity:.1f}, energy={current_energy:.6f}, best_energy={best_energy:.6f}")
    
    # Ensure we have a solution
    if best_x is None:
        best_x = np.zeros(num_vars, dtype=int)
        best_energy = evaluate_solution(best_x)
    
    # Final greedy improvement pass: try flipping each bit
    improved = True
    greedy_iterations = 0
    while improved and greedy_iterations < 100:
        improved = False
        greedy_iterations += 1
        for idx in range(num_vars):
            x_flipped = best_x.copy()
            x_flipped[idx] = 1 - x_flipped[idx]
            flipped_energy = evaluate_solution(x_flipped)
            if flipped_energy < best_energy:
                best_x = x_flipped
                best_energy = flipped_energy
                improved = True
                break
    
    print(f"[SA] Final best energy: {best_energy:.6f}, drugs scheduled: {int(np.sum(best_x))}/{num_vars}")
    class MockResult:
        def __init__(self, x_sol, obj_val):
            self.x = x_sol
            self.fval = obj_val
            self.status = type('Status', (), {'name': 'SUCCESS'})()
    
    return MockResult(best_x, best_energy)

def run_optimization(config: OptimizationConfig):
    qp = build_quadratic_program(config)
    
    _, result = _solve_with_numpy(qp)
    
    schedule = {d: np.zeros(config.days) for d in config.selected_drugs}
    per_day_drugs = {t: [] for t in range(config.days)}
    
    if result and result.status.name == "SUCCESS":
        for i, val in enumerate(result.x):
            if val > 0.5:
                var_name = qp.variables[i].name
                # Parse variable name: format is "x_<drug>_<day>"
                # Handle both "x_A_0" and "x_Drug_A_0" formats
                parts = var_name.split("_")
                if len(parts) == 3:  # "x_A_0"
                    _, d, t = parts
                else:  # "x_Drug_A_0" or similar
                    t = parts[-1]
                    d = "_".join(parts[1:-1])
                
                t = int(t)
                if d in config.selected_drugs:
                    schedule[d][t] = 1
                    per_day_drugs[t].append(d)

    # Hard-enforce gap constraints: if a drug is given on day t,
    # it cannot be given on days t+1..t+min_gap.
    for d, min_gap in (config.gap_constraints or {}).items():
        if d not in schedule:
            continue
        mg = int(min_gap)
        if mg <= 0:
            continue
        for t in range(config.days):
            if schedule[d][t] <= 0.5:
                continue
            for step in range(1, mg + 1):
                tt = t + step
                if tt >= config.days:
                    break
                if schedule[d][tt] > 0.5:
                    schedule[d][tt] = 0
                    if d in per_day_drugs.get(tt, []):
                        per_day_drugs[tt] = [x for x in per_day_drugs[tt] if x != d]
                
    return OptimizationSolution(
        schedule=schedule,
        per_day_drugs=per_day_drugs,
        metrics={"score": result.fval if result else 0.0},
        status=result.status.name if result else "FAILED"
    )
