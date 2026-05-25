import matplotlib.pyplot as plt

from quantum_optimizer import OptimizationConfig, run_optimization
from schedule_input import generate_standard_schedule_for_drugs
from simulator import TumorSimulator


def _build_drug_strength_map(profiles):
    return {
        drug: min(2.5, max(0.2, profile["efficacy"] / 4.0))
        for drug, profile in profiles.items()
    }


def _build_demo_config(days):
    selected_drugs = ["Drug_A", "Drug_B", "Drug_C"]
    return OptimizationConfig(
        days=days,
        selected_drugs=selected_drugs,
        efficacy={"Drug_A": 5.0, "Drug_B": 4.4, "Drug_C": 6.0},
        toxicity={"Drug_A": 2.0, "Drug_B": 1.7, "Drug_C": 2.4},
        toxicity_budget=18.0,
        alpha=1.0,
        beta=1.0,
        gamma=100.0,
        clearance_rate=0.3,
        qaoa_reps=2,
        use_qiskit=True,
    )


def main():
    print("\n===== QDOS Tumor Validation Engine =====")

    days = 30
    config = _build_demo_config(days)
    solution = run_optimization(config)

    print("\nOPTIMIZED SCHEDULE")
    for day, drugs in solution.per_day_drugs.items():
        label = ", ".join(drugs) if drugs else "Rest"
        print(f"Day {day + 1}: {label}")

    standard_schedule = generate_standard_schedule_for_drugs(config.selected_drugs, days)

    optimized_sim = TumorSimulator(
        solution.schedule,
        drug_strength=_build_drug_strength_map(solution.resolved_profiles),
        drug_toxicity={drug: profile["toxicity"] for drug, profile in solution.resolved_profiles.items()},
    )
    standard_sim = TumorSimulator(
        standard_schedule,
        drug_strength=_build_drug_strength_map(solution.resolved_profiles),
        drug_toxicity={drug: profile["toxicity"] for drug, profile in solution.resolved_profiles.items()},
    )

    tumor_optimized = optimized_sim.run_with_treatment()
    tumor_standard = standard_sim.run_with_treatment()
    tumor_no_treatment = optimized_sim.run_without_treatment()
    tox_optimized = optimized_sim.calculate_toxicity()
    tox_standard = standard_sim.calculate_toxicity()
    time = optimized_sim.time

    final_size, reduction = optimized_sim.calculate_statistics(tumor_optimized)

    print("\nSimulation Results")
    print("Initial Tumor Size:", optimized_sim.initial_tumor_size)
    print("Final Tumor Size:", final_size)
    print("Tumor Reduction %:", reduction)
    print("Objective Score:", solution.metrics["objective_score"])

    plt.figure()
    plt.plot(time, tumor_no_treatment, label="No Treatment")
    plt.plot(time, tumor_standard, label="Standard Care")
    plt.plot(time, tumor_optimized, label="Optimized Schedule")
    plt.xlabel("Time (Days)")
    plt.ylabel("Tumor Size")
    plt.title("Tumor Growth Simulation")
    plt.legend()
    plt.show()

    plt.figure()
    plt.plot(range(days), tox_standard, label="Standard Toxicity")
    plt.plot(range(days), tox_optimized, label="Optimized Toxicity")
    plt.xlabel("Time (Days)")
    plt.ylabel("Cumulative Toxicity")
    plt.title("Toxicity Accumulation")
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()