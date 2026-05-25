#!/usr/bin/env python3
"""Test if parameter changes affect the QUBO formulation and optimization results."""

from quantum_optimizer import OptimizationConfig, build_quadratic_program, run_optimization
import json

# Test 1: Run with kidney = 1.0 (healthy)
print("\n" + "="*60)
print("TEST 1: Kidney = 1.0 (Healthy)")
print("="*60)

config1 = OptimizationConfig(
    days=14,
    selected_drugs=["Pembrolizumab", "Cisplatin", "Paclitaxel"],
    patient_profile={'kidney': 1.0, 'liver': 1.0, 'marrow': 1.0, 'immune': 1.0, 'vascular': 1.0, 'age': 40},
    alpha=10.0,
    beta=0.1,
    gamma=100.0,
    lambda_daily=50.0,
    lambda_gap=50.0,
    base_toxicity_budget=10.0,
    subtype_scores={'BRCA': 0.5, 'PDL1': 0.5, 'VEGF': 0.5},
    max_drugs_per_day=2
)

qp1 = build_quadratic_program(config1)
result1 = run_optimization(config1)

schedule1_json = json.dumps({
    drug: result1.schedule[drug].tolist() 
    for drug in result1.schedule
}, indent=2)
print(f"Schedule 1: {schedule1_json}")
print(f"Per-day drugs: {result1.per_day_drugs}")
print(f"Total doses: {sum(len(drugs) for drugs in result1.per_day_drugs.values())}")

# Test 2: Run with kidney = 0.3 (damaged)
print("\n" + "="*60)
print("TEST 2: Kidney = 0.3 (Damaged)")
print("="*60)

config2 = OptimizationConfig(
    days=14,
    selected_drugs=["Pembrolizumab", "Cisplatin", "Paclitaxel"],
    patient_profile={'kidney': 0.3, 'liver': 1.0, 'marrow': 1.0, 'immune': 1.0, 'vascular': 1.0, 'age': 40},
    alpha=10.0,
    beta=0.1,
    gamma=100.0,
    lambda_daily=50.0,
    lambda_gap=50.0,
    base_toxicity_budget=10.0,
    subtype_scores={'BRCA': 0.5, 'PDL1': 0.5, 'VEGF': 0.5},
    max_drugs_per_day=2
)

qp2 = build_quadratic_program(config2)
result2 = run_optimization(config2)

schedule2_json = json.dumps({
    drug: result2.schedule[drug].tolist() 
    for drug in result2.schedule
}, indent=2)
print(f"Schedule 2: {schedule2_json}")
print(f"Per-day drugs: {result2.per_day_drugs}")
print(f"Total doses: {sum(len(drugs) for drugs in result2.per_day_drugs.values())}")

# Test 3: Run with max_drugs_per_day = 1
print("\n" + "="*60)
print("TEST 3: Max Drugs Per Day = 1")
print("="*60)

config3 = OptimizationConfig(
    days=14,
    selected_drugs=["Pembrolizumab", "Cisplatin", "Paclitaxel"],
    patient_profile={'kidney': 1.0, 'liver': 1.0, 'marrow': 1.0, 'immune': 1.0, 'vascular': 1.0, 'age': 40},
    alpha=10.0,
    beta=0.1,
    gamma=100.0,
    lambda_daily=50.0,
    lambda_gap=50.0,
    base_toxicity_budget=10.0,
    subtype_scores={'BRCA': 0.5, 'PDL1': 0.5, 'VEGF': 0.5},
    max_drugs_per_day=1
)

qp3 = build_quadratic_program(config3)
result3 = run_optimization(config3)

schedule3_json = json.dumps({
    drug: result3.schedule[drug].tolist() 
    for drug in result3.schedule
}, indent=2)
print(f"Schedule 3: {schedule3_json}")
print(f"Per-day drugs: {result3.per_day_drugs}")
print(f"Total doses: {sum(len(drugs) for drugs in result3.per_day_drugs.values())}")

# Summary
print("\n" + "="*60)
print("SUMMARY - Parameter Sensitivity Test")
print("="*60)
doses1 = sum(len(drugs) for drugs in result1.per_day_drugs.values())
doses2 = sum(len(drugs) for drugs in result2.per_day_drugs.values())
doses3 = sum(len(drugs) for drugs in result3.per_day_drugs.values())

print(f"\nSchedule 1 (kidney=1.0, max=2): {doses1} doses")
print(f"Schedule 2 (kidney=0.3, max=2): {doses2} doses - {'✓ DIFFERENT' if doses1 != doses2 else '✗ SAME (hardcoded)'}")
print(f"Schedule 3 (kidney=1.0, max=1): {doses3} doses - {'✓ DIFFERENT' if doses1 != doses3 else '✗ SAME (hardcoded)'}")

if doses1 == doses2 == doses3:
    print("\n❌ FAILURE: All schedules are identical - parameters are NOT affecting optimization")
else:
    print("\n✅ SUCCESS: Different parameters produce different schedules")
