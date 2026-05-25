import numpy as np

def expected_bliss_effect(ea, eb):
    return ea + eb - ea * eb

def synergy_score(observed, expected):
    return max(min(observed - expected, 3.0), -3.0)

class GompertzTumorModel:
    def __init__(self, drug_strength=None, drug_toxicity=None, r=0.12, K=1e9, patient_profile=None):
        self.r = r
        self.K = K

        self.drug_strength = {
            "Pembrolizumab": 3.0,
            "Cisplatin": 2.5,
            "Paclitaxel": 3.5,
        }

        self.drug_toxicity = {
            "Pembrolizumab": {"kidney": 0.2, "liver": 0.1, "marrow": 0.4, "immune": 0.1, "vascular": 0.2},
            "Cisplatin": {"kidney": 0.1, "liver": 0.3, "marrow": 0.2, "immune": 0.3, "vascular": 0.1},
            "Paclitaxel": {"kidney": 0.4, "liver": 0.2, "marrow": 0.1, "immune": 0.1, "vascular": 0.2},
        }

        self.patient_profile = patient_profile or {
            "kidney": 1.0,
            "liver": 1.0,
            "marrow": 1.0,
            "immune": 1.0,
            "vascular": 1.0,
            "age": 40
        }

        self.subtype_scores = {
            "BRCA": 0.5,
            "PDL1": 0.5,
            "VEGF": 0.5
        }

        if drug_strength:
            self.drug_strength.update(drug_strength)
        if drug_toxicity:
            self.drug_toxicity.update(drug_toxicity)

        self.schedule = None

    def set_schedule(self, schedule):
        self.schedule = schedule
        
    def set_patient_profile(self, profile, subtype_scores):
        self.patient_profile.update(profile)
        self.subtype_scores.update(subtype_scores)

    def get_effective_toxicity(self, drug):
        tox = self.drug_toxicity.get(drug, {})
        if not tox:
            return 0.0
        effective_tox = 0.0
        for organ, val in tox.items():
            profile_val = self.patient_profile.get(organ, 1.0)
            if profile_val > 0:
                effective_tox += val / profile_val
        return effective_tox
        
    def subtype_factor(self, pathway_weights):
        factor = 0.0
        for pathway, weight in pathway_weights.items():
            factor += weight * self.subtype_scores.get(pathway, 0.0)
        return factor if factor > 0 else 1.0

    def dynamic_synergy(self, drug1, drug2, base_synergy, d1=1.0, d2=1.0, delta_t=0, optimal_delay=0, beta=1.0, pathway_weights=None):
        if pathway_weights is None:
            pathway_weights = {"BRCA": 0.33, "PDL1": 0.33, "VEGF": 0.34}
        
        dose_factor = 4 * d1 * d2
        timing_factor = np.exp(-beta * abs(delta_t - optimal_delay))
        subtype_f = self.subtype_factor(pathway_weights)
        
        return base_synergy * dose_factor * timing_factor * subtype_f

    def drug_effect(self, t):
        if not self.schedule:
            return 0.0

        day = int(t)
        total_kill = 0.0

        active_drugs = []  # list[(drug, dose)]
        for drug in self.schedule:
            if day >= len(self.schedule[drug]):
                continue

            dose = float(self.schedule[drug][day])
            if dose <= 0:
                continue

            active_drugs.append((drug, dose))
            drug_str = self.drug_strength.get(drug, 0.0)
            total_kill += drug_str * dose

        for i, (drug1, dose1) in enumerate(active_drugs):
            for (drug2, dose2) in active_drugs[i + 1:]:
                # Simplified interaction for simulation
                ea = self.drug_strength.get(drug1, 0.0) * dose1
                eb = self.drug_strength.get(drug2, 0.0) * dose2
                expected = expected_bliss_effect(ea, eb)
                observed = ea + eb + 0.1  # Mock observed
                score = synergy_score(observed, expected)
                total_kill += score * 0.1 

        return total_kill

    def gompertz_equation(self, N, t):
        growth = self.r * N * np.log(self.K / N)
        kill = self.drug_effect(t) * N
        return growth - kill

    def gompertz_no_treatment(self, N, t):
        return self.r * N * np.log(self.K / N)
