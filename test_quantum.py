import unittest
from tumor_model import expected_bliss_effect, synergy_score, GompertzTumorModel
from quantum_optimizer import OptimizationConfig, get_effective_toxicity, build_quadratic_program

class TestQuantumOpt(unittest.TestCase):
    def test_bliss_synergy(self):
        self.assertAlmostEqual(expected_bliss_effect(0.5, 0.5), 0.75)
        self.assertAlmostEqual(synergy_score(0.8, 0.75), 0.05)

    def test_toxicity_calculation(self):
        config = OptimizationConfig(patient_profile={"age": 40, "kidney": 0.5, "liver": 1.0, "marrow": 1.0, "immune": 1.0, "vascular": 1.0})
        # Drug C kidney tox is 0.4. 0.4 / 0.5 = 0.8
        eff_tox = get_effective_toxicity("Drug_C", config)
        self.assertGreater(eff_tox, 0.4) # It should scale up
        
    def test_hamiltonian_assembly(self):
        config = OptimizationConfig(
            days=2, selected_drugs=["Drug_A", "Drug_B"],
            patient_profile={"age": 40}, gap_constraints={"Drug_A": 1}
        )
        qp = build_quadratic_program(config)
        self.assertIsNotNone(qp)
        self.assertEqual(qp.get_num_vars(), 4) # 2 drugs * 2 days
        
if __name__ == '__main__':
    unittest.main()
