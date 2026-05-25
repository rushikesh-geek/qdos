import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from quantum_optimizer import OptimizationConfig, run_optimization, get_effective_toxicity, DEFAULT_DRUG_LIBRARY
from schedule_input import generate_standard_schedule_for_drugs
from simulator import TumorSimulator

st.set_page_config(page_title="Q-DOS: Quantum Drug Optimization System", layout="wide")

st.title("?? Q-DOS: Quantum Drug Optimization System")
st.markdown("Optimize cancer drug schedules using dynamic synergy and organ-specific toxicity constraints via Quantum formulation.")

# Sidebar Settings
st.sidebar.header("Patient Profile")
age = st.sidebar.slider("Age", 18, 100, 40)
st.sidebar.subheader("Organ Function (0.0=Failure, 1.0=Normal)")
kidney = st.sidebar.slider("Kidney", 0.1, 1.0, 1.0)
liver = st.sidebar.slider("Liver", 0.1, 1.0, 1.0)
marrow = st.sidebar.slider("Bone Marrow", 0.1, 1.0, 1.0)
immune = st.sidebar.slider("Immune System", 0.1, 1.0, 1.0)
vascular = st.sidebar.slider("Vascular", 0.1, 1.0, 1.0)

st.sidebar.header("Tumor Subtype")
brca = st.sidebar.slider("BRCA Score", 0.0, 1.0, 0.5)
pdl1 = st.sidebar.slider("PD-L1 Score", 0.0, 1.0, 0.5)
vegf = st.sidebar.slider("VEGF Score", 0.0, 1.0, 0.5)

st.sidebar.header("Treatment Constraints")
max_drugs = st.sidebar.number_input("Max Drugs / Day", 1, 5, 2)
base_budget = st.sidebar.number_input("Base Toxicity Budget", 5.0, 50.0, 10.0)

if st.button("Run Quantum Optimization"):
    with st.spinner("Compiling QUBO & Solving..."):
        selected_drugs = ["Pembrolizumab", "Cisplatin", "Paclitaxel"]
        patient_profile = {"age": age, "kidney": kidney, "liver": liver, "marrow": marrow, "immune": immune, "vascular": vascular}
        config = OptimizationConfig(
            days=14,
            selected_drugs=selected_drugs,
            patient_profile=patient_profile,
            subtype_scores={"BRCA": brca, "PDL1": pdl1, "VEGF": vegf},
            mutually_exclusive_pairs=[("Drug_B", "Drug_C")],
            gap_constraints={"Drug_A": 1},
            max_drugs_per_day=max_drugs,
            base_toxicity_budget=base_budget
        )
        
        # 1. Run Optimization
        print(f"\n[App] Running optimization with kidney={kidney:.2f}, liver={liver:.2f}, marrow={marrow:.2f}, age={age}")
        solution = run_optimization(config)
        st.success(f"Optimization Complete! Status: {solution.status}")
        print(f"[App] Q-DOS scheduled {sum(len(drugs) for drugs in solution.per_day_drugs.values())} drug doses")
        print(f"[App] Q-DOS schedule: {solution.per_day_drugs}")
        
        # 2. Generate Standard Schedule
        standard_schedule = generate_standard_schedule_for_drugs(selected_drugs, 14)
        
        # 3. Run Simulations
        simulator = TumorSimulator(
            days=14,
            patient_profile=patient_profile,
            subtype_scores=config.subtype_scores
        )
        
        t_notx, pop_notx = simulator.simulate_no_treatment()
        t_standard, pop_standard = simulator.simulate_treatment(standard_schedule)
        t_tx, pop_tx = simulator.simulate_treatment(solution.schedule)
        
        # 4. Calculate Toxicity (only when drugs are actually scheduled)
        tox_qdos = np.zeros(14)
        tox_standard = np.zeros(14)
        
        for drug in selected_drugs:
            t_eff = get_effective_toxicity(drug, config)
            
            for t in range(14):
                # Only add toxicity if drug is actually scheduled on this day
                if solution.schedule[drug][t] > 0.5:
                    tox_qdos[t] += t_eff
                if standard_schedule[drug][t] > 0.5:
                    tox_standard[t] += t_eff
        
        cum_tox_qdos = np.cumsum(tox_qdos)
        cum_tox_standard = np.cumsum(tox_standard)
        
        # 5. Display Metrics
        budget = base_budget - 0.5 * (age - 40)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            tumor_reduction = ((pop_notx[0] - pop_tx[-1]) / pop_notx[0] * 100) if pop_notx[0] > 0 else 0
            st.metric("Tumor Reduction %", f"{tumor_reduction:.1f}%")
        with col2:
            st.metric("Q-DOS Toxicity", f"{cum_tox_qdos[-1]:.2f}")
        with col3:
            st.metric("Std Toxicity", f"{cum_tox_standard[-1]:.2f}")
        with col4:
            st.metric("Budget", f"{budget:.2f}")
        
        # 6. Plot 1: Tumor Growth
        st.subheader("1. Tumor Cell Population Over Time")
        fig_tumor = go.Figure()
        fig_tumor.add_trace(go.Scatter(x=t_notx, y=pop_notx, mode='lines', name='No Treatment', line=dict(color='gray', dash='dash')))
        fig_tumor.add_trace(go.Scatter(x=t_standard, y=pop_standard, mode='lines', name='Standard Care', line=dict(color='orange')))
        fig_tumor.add_trace(go.Scatter(x=t_tx, y=pop_tx, mode='lines', name='Q-DOS Optimized', line=dict(color='green', width=3)))
        fig_tumor.update_layout(title="Tumor Growth Comparison", xaxis_title="Days", yaxis_title="Number of Cells", height=400)
        st.plotly_chart(fig_tumor, use_container_width=True)
        
        # 7. Plot 2: Toxicity
        st.subheader("2. Cumulative Toxicity Over Time")
        fig_tox = go.Figure()
        fig_tox.add_trace(go.Scatter(x=list(range(14)), y=cum_tox_standard.tolist(), mode='lines+markers', name='Standard Schedule', line=dict(color='orange')))
        fig_tox.add_trace(go.Scatter(x=list(range(14)), y=cum_tox_qdos.tolist(), mode='lines+markers', name='Q-DOS Schedule', line=dict(color='red')))
        fig_tox.add_hline(y=budget, line_dash="dash", line_color="darkred", annotation_text=f"Safety Threshold ({budget:.1f})", annotation_position="right")
        fig_tox.update_layout(title="Toxicity Management", xaxis_title="Days", yaxis_title="Cumulative Toxicity", height=400)
        st.plotly_chart(fig_tox, use_container_width=True)
        
        # 8. Plot 3: Schedule Heatmap
        st.subheader("3. Treatment Schedule Heatmap")
        schedule_matrix = np.array([solution.schedule[drug] for drug in selected_drugs])
        fig_heat = go.Figure(data=go.Heatmap(z=schedule_matrix, x=[f"D{i+1}" for i in range(14)], y=selected_drugs, colorscale="Blues"))
        fig_heat.update_layout(title="Q-DOS Drug Schedule (1=Administered)", xaxis_title="Days", yaxis_title="Drugs", height=300)
        st.plotly_chart(fig_heat, use_container_width=True)
        
        # 9. Display Schedule
        st.subheader("Generated Schedule")
        st.json(solution.per_day_drugs)
