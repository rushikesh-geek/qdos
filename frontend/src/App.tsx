import { useState } from 'react';
import axios from 'axios';
import PlotlyPlot from 'react-plotly.js';
const Plot: any = (PlotlyPlot as any).default || PlotlyPlot;
import { Shield, Target, Activity, Settings2, Sliders, Activity as ActivityIcon } from 'lucide-react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const ORGAN_ORDER = ["kidney", "liver", "marrow", "immune", "vascular"];

function buildDayLabels(days: number) {
  const tickvals = Array.from({ length: days }, (_, i) => i);
  const ticktext = tickvals.map((i) => `<b>${i + 1} day</b>`);
  const plain = tickvals.map((i) => `${i + 1} day`);
  return { tickvals, ticktext, plain };
}

function buildScheduleHeatmap(schedule: Record<string, number[]>, drugs: string[], days: number) {
  return drugs.map((drug) =>
    Array.from({ length: days }, (_, day) => Number(schedule?.[drug]?.[day] ?? 0))
  );
}

function buildOrganBurden(organToxicity: Record<string, number[]>) {
  return ORGAN_ORDER.map((organ) => {
    const series = organToxicity?.[organ] ?? [];
    return series.length > 0 ? series[series.length - 1] : 0;
  });
}

function App() {
  const [patientData, setPatientData] = useState({
    age: 40,
    days: 14,
    dt: 1.0,
    selected_drugs: ["Pembrolizumab", "Cisplatin", "Paclitaxel"],
    patient_profile: {
      kidney: 1.0,
      liver: 1.0,
      marrow: 1.0,
      immune: 1.0,
      vascular: 1.0
    },
    subtype_scores: {
      BRCA: 0.5,
      PDL1: 0.5,
      VEGF: 0.5
    },
    mutually_exclusive_pairs: [["Cisplatin", "Paclitaxel"]],
    gap_constraints: {"Pembrolizumab": 1, "Cisplatin": 0, "Paclitaxel": 0},
    dose_levels: {"Pembrolizumab": 1.0, "Cisplatin": 1.0, "Paclitaxel": 1.0},
    efficacy_levels: {"Pembrolizumab": 1.0, "Cisplatin": 1.0, "Paclitaxel": 1.0},
    toxicity_levels: {"Pembrolizumab": 1.0, "Cisplatin": 1.0, "Paclitaxel": 1.0},
    max_drugs_per_day: 2,
    base_toxicity_budget: 10.0,
    toxicity_weight: 0.1,
    toxicity_flush_rate: 0.0
  });

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedDrugs = results?.solution?.schedule ? Object.keys(results.solution.schedule) : patientData.selected_drugs;
  const scheduleHeatmap = results ? buildScheduleHeatmap(results.solution.schedule, selectedDrugs, patientData.days) : [];
  const organBurden = results ? buildOrganBurden(results.charts.organ_toxicity || {}) : [];
  const standardTumor = results?.charts?.tumor_standard ?? [];
  const noTreatmentTumor = results?.charts?.tumor_no_treatment ?? results?.charts?.tumor_std ?? [];
  const qdosTumor = results?.charts?.tumor_qdos ?? [];
  const standardToxicity = results?.charts?.tox_standard ?? [];
  const qdosToxicity = results?.charts?.tox_qdos ?? [];
  const dayLabels = buildDayLabels(patientData.days);
  const tumorReductionPercent =
    noTreatmentTumor.length > 0 && qdosTumor.length > 0
      ? (((noTreatmentTumor[0] - qdosTumor[qdosTumor.length - 1]) / noTreatmentTumor[0]) * 100)
      : 0;

  const availableDrugOptions = ["Pembrolizumab", "Cisplatin", "Paclitaxel", "Doxorubicin"];

  const handleSimulate = async () => {
    if (!patientData.selected_drugs || patientData.selected_drugs.length === 0) {
      setError("No drugs selected. Pick at least one drug in the Drug Library.");
      setResults(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await axios.post(`${API_URL}/api/simulate`, patientData);
      if (resp.data.error) {
         setError(resp.data.error);
         setResults(null);
      } else {
        setResults(resp.data);
      }
    } catch (e: any) {
      setError(e.message || "Simulation Failed. Is the backend running?");
      setResults(null);
    }
    setLoading(false);
  };

  const handleDrugToggle = (drug: string) => {
    const newDrugs = patientData.selected_drugs.includes(drug)
      ? patientData.selected_drugs.filter(d => d !== drug)
      : [...patientData.selected_drugs, drug];

    const newGap = { ...(patientData as any).gap_constraints };
    const newDose = { ...(patientData as any).dose_levels };
    const newEff = { ...(patientData as any).efficacy_levels };
    const newTox = { ...(patientData as any).toxicity_levels };
    if (newDrugs.includes(drug)) {
      if (newGap[drug] === undefined) newGap[drug] = 0;
      if (newDose[drug] === undefined) newDose[drug] = 1.0;
      if (newEff[drug] === undefined) newEff[drug] = 1.0;
      if (newTox[drug] === undefined) newTox[drug] = 1.0;
    } else {
      delete newGap[drug];
      delete newDose[drug];
      delete newEff[drug];
      delete newTox[drug];
    }

    setPatientData({
      ...patientData,
      selected_drugs: newDrugs,
      gap_constraints: newGap,
      dose_levels: newDose,
      efficacy_levels: newEff,
      toxicity_levels: newTox,
    });
  };

  const handleGapChange = (drug: string, value: string) => {
    setPatientData({
      ...patientData,
      gap_constraints: {
        ...(patientData as any).gap_constraints,
        [drug]: Number(value)
      }
    });
  };

  const handleDoseChange = (drug: string, value: string) => {
    setPatientData({
      ...patientData,
      dose_levels: {
        ...(patientData as any).dose_levels,
        [drug]: Number(value)
      }
    });
  };

  const handleDrugEfficacyChange = (drug: string, value: string) => {
    setPatientData({
      ...patientData,
      efficacy_levels: {
        ...(patientData as any).efficacy_levels,
        [drug]: Number(value)
      }
    });
  };

  const handleDrugToxicityChange = (drug: string, value: string) => {
    setPatientData({
      ...patientData,
      toxicity_levels: {
        ...(patientData as any).toxicity_levels,
        [drug]: Number(value)
      }
    });
  };

  const handleProfileChange = (organ: string, value: string) => {
    setPatientData({
      ...patientData,
      patient_profile: {
        ...patientData.patient_profile,
        [organ]: Number(value)
      }
    });
  }
  
  const handleSubtypeChange = (pathway: string, value: string) => {
    setPatientData({
      ...patientData,
      subtype_scores: {
        ...patientData.subtype_scores,
        [pathway]: Number(value)
      }
    });
  }

  return (
    <div className="min-h-screen bg-[#E6EEF5] text-slate-700 font-sans p-4 md:p-8">
      <div className="max-w-[1400px] mx-auto flex flex-col xl:flex-row gap-8">
        
        {/* Sidebar */}
        <div className="w-full xl:w-[450px] shrink-0 bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-8 h-fit border border-white/60">
          <div className="flex items-center gap-4 mb-4 pb-4 border-b border-slate-300/40">
            <div className="p-3 bg-indigo-500 text-white rounded-2xl shadow-[inset_2px_2px_4px_#3730a3,inset_-2px_-2px_4px_#818cf8]">
               <ActivityIcon size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-slate-800">Q-DOS</h1>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Quantum Solver</p>
            </div>
          </div>

          <div className="space-y-6">
            <div className="space-y-3">
              <h3 className="flex items-center gap-2 font-black text-slate-700 uppercase text-xs tracking-widest bg-[#E6EEF5] shadow-[inset_2px_2px_4px_#c4cacf,inset_-2px_-2px_4px_#ffffff] px-4 py-2 rounded-xl w-fit">
                <Target size={14} className="text-indigo-500" /> Patient Params
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <Input label="Age(Yrs)" type="number" value={patientData.age} onChange={(v:any) => setPatientData({...patientData, age: Number(v)})} />
                <Input label="Horizon" type="number" value={patientData.days} onChange={(v:any) => setPatientData({...patientData, days: Number(v)})} />
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 pt-2">
                <Slider label="Budget" min={1.0} max={25.0} step={1.0} value={patientData.base_toxicity_budget} onChange={(v:any) => setPatientData({...patientData, base_toxicity_budget: Number(v)})} />
                <Slider label="Tox weight (penalty)" min={0.0} max={2.0} step={0.05} value={(patientData as any).toxicity_weight} onChange={(v:any) => setPatientData({...patientData, toxicity_weight: Number(v)})} />
                <Slider label="Clearance" min={0.0} max={1.0} step={0.05} value={(patientData as any).toxicity_flush_rate} onChange={(v:any) => setPatientData({...patientData, toxicity_flush_rate: Number(v)})} />
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="flex items-center gap-2 font-black text-slate-700 uppercase text-xs tracking-widest bg-[#E6EEF5] shadow-[inset_2px_2px_4px_#c4cacf,inset_-2px_-2px_4px_#ffffff] px-4 py-2 rounded-xl w-fit">
                Organ Profile (0.1-1.0)
              </h3>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                 <Slider label="Kidney" min={0.1} max={1.0} step={0.1} value={patientData.patient_profile.kidney} onChange={(v:any) => handleProfileChange("kidney", v)} />
                 <Slider label="Liver" min={0.1} max={1.0} step={0.1} value={patientData.patient_profile.liver} onChange={(v:any) => handleProfileChange("liver", v)} />
                 <Slider label="Marrow" min={0.1} max={1.0} step={0.1} value={patientData.patient_profile.marrow} onChange={(v:any) => handleProfileChange("marrow", v)} />
                 <Slider label="Immune" min={0.1} max={1.0} step={0.1} value={patientData.patient_profile.immune} onChange={(v:any) => handleProfileChange("immune", v)} />
                 <Slider label="Vascular" min={0.1} max={1.0} step={0.1} value={patientData.patient_profile.vascular} onChange={(v:any) => handleProfileChange("vascular", v)} />
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="flex items-center gap-2 font-black text-slate-700 uppercase text-xs tracking-widest bg-[#E6EEF5] shadow-[inset_2px_2px_4px_#c4cacf,inset_-2px_-2px_4px_#ffffff] px-4 py-2 rounded-xl w-fit">
                Tumor Subtype
              </h3>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                 <Slider label="BRCA" min={0.0} max={1.0} step={0.1} value={patientData.subtype_scores.BRCA} onChange={(v:any) => handleSubtypeChange("BRCA", v)} />
                 <Slider label="PDL1" min={0.0} max={1.0} step={0.1} value={patientData.subtype_scores.PDL1} onChange={(v:any) => handleSubtypeChange("PDL1", v)} />
                 <Slider label="VEGF" min={0.0} max={1.0} step={0.1} value={patientData.subtype_scores.VEGF} onChange={(v:any) => handleSubtypeChange("VEGF", v)} />
                 <Input label="Max Drugs/Day" type="number" value={patientData.max_drugs_per_day} onChange={(v:any) => setPatientData({...patientData, max_drugs_per_day: Number(v)})} />
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="flex items-center gap-2 font-black text-slate-700 uppercase text-xs tracking-widest bg-[#E6EEF5] shadow-[inset_2px_2px_4px_#c4cacf,inset_-2px_-2px_4px_#ffffff] px-4 py-2 rounded-xl w-fit">
                <Shield size={14} className="text-indigo-500" /> Drug Library
              </h3>
              <div className="flex flex-wrap gap-2">
                {availableDrugOptions.map(drug => (
                  <button
                    key={drug}
                    onClick={() => handleDrugToggle(drug)}
                    className={cn(
                      "px-3 py-1.5 text-xs font-bold rounded-xl transition-all",
                      patientData.selected_drugs.includes(drug)
                        ? "bg-indigo-500 text-white shadow-[inset_2px_2px_4px_#3730a3,inset_-2px_-2px_4px_#818cf8]"
                        : "bg-[#E6EEF5] text-slate-600 shadow-[4px_4px_8px_#c4cacf,-4px_-4px_8px_#ffffff] hover:shadow-[inset_2px_2px_4px_#c4cacf,inset_-2px_-2px_4px_#ffffff]"
                    )}
                  >
                    {drug}
                  </button>
                ))}
              </div>

              <div className="mt-4 space-y-3">
                <h4 className="text-[9px] font-black text-slate-500 uppercase tracking-widest px-2">Dose level + gap days</h4>
                <div className="space-y-3">
                  {patientData.selected_drugs.map((drug) => (
                    <div key={drug} className="bg-[#E6EEF5] rounded-2xl p-3 shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff]">
                      <div className="text-xs font-black text-slate-700 mb-2">{drug}</div>
                      <div className="grid grid-cols-2 gap-3">
                        <Slider
                          label="Dose"
                          min={0.0}
                          max={1.0}
                          step={0.05}
                          value={Number((patientData as any).dose_levels?.[drug] ?? 1.0)}
                          onChange={(v: any) => handleDoseChange(drug, v)}
                        />
                        <Slider
                          label="Gap days"
                          min={0}
                          max={7}
                          step={1}
                          value={Number((patientData as any).gap_constraints?.[drug] ?? 0)}
                          onChange={(v: any) => handleGapChange(drug, v)}
                        />
                        <Slider
                          label="Efficacy"
                          min={0.0}
                          max={2.0}
                          step={0.05}
                          value={Number((patientData as any).efficacy_levels?.[drug] ?? 1.0)}
                          onChange={(v: any) => handleDrugEfficacyChange(drug, v)}
                        />
                        <Slider
                          label="Toxicity"
                          min={0.0}
                          max={2.0}
                          step={0.05}
                          value={Number((patientData as any).toxicity_levels?.[drug] ?? 1.0)}
                          onChange={(v: any) => handleDrugToxicityChange(drug, v)}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-2">
              <button
                 onClick={handleSimulate}
                 disabled={loading}
                 className="w-full py-4 bg-indigo-500 text-white font-black rounded-2xl shadow-[6px_6px_12px_#c4cacf,-6px_-6px_12px_#ffffff] transition-all transform active:translate-y-1 active:shadow-[inset_4px_4px_8px_#3730a3,inset_-4px_-4px_8px_#818cf8] uppercase tracking-[0.15em] text-sm hover:bg-indigo-400 flex justify-center items-center gap-3 disabled:opacity-50"
              >
                {loading ? <ActivityIcon className="animate-spin" /> : <ActivityIcon className="group-hover:scale-110 transition-transform" /> }
                {loading ? "Computing..." : "Run Quantum Solver"}
              </button>
            </div>
            
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col gap-6 min-w-0">
           {error && (
             <div className="p-6 bg-[#E6EEF5] text-red-600 rounded-3xl shadow-[inset_6px_6px_12px_#c4cacf,inset_-6px_-6px_12px_#ffffff] border border-red-200/50 font-bold flex items-center gap-3">
               <div className="p-2 bg-red-100 rounded-full"><Activity size={20}/></div>
               {error}
             </div>
           )}

           {!results && !error && !loading && (
             <div className="flex-1 flex flex-col items-center justify-center p-12 bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl border border-white/60 text-slate-400 min-h-[600px]">
                <div className="p-6 rounded-3xl shadow-[inset_6px_6px_12px_#c4cacf,inset_-6px_-6px_12px_#ffffff] mb-6">
                  <Settings2 size={64} className="text-indigo-400/50" />
                </div>
                <h2 className="text-2xl font-black text-slate-600 mb-2">Awaiting Parameters</h2>
                <p className="text-sm font-medium text-center max-w-sm leading-relaxed">Configure the explicit constraints and subtype scores, then run the solver to generate a personalized multidrug regimen.</p>
             </div>
           )}

           {results && (
             <>
               {(() => {
                 const sch = results?.solution?.schedule;
                 const keys = sch ? Object.keys(sch) : [];
                 const anyDose = keys.some((d: string) => (sch[d] || []).some((v: any) => Number(v) > 0));
                 if (keys.length > 0 && !anyDose) {
                   return (
                     <div className="p-6 bg-[#E6EEF5] text-slate-600 rounded-3xl shadow-[inset_6px_6px_12px_#c4cacf,inset_-6px_-6px_12px_#ffffff] border border-white/60 font-bold">
                       No doses were scheduled. Try lowering tox weight (penalty) or increasing budget.
                     </div>
                   );
                 }
                 return null;
               })()}

               <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <MetricBox label="Objective Energy (lower is better)" value={results.solution.metrics.objective_score.toFixed(2)} />
                 <MetricBox label="Total Toxicity" value={results.solution.metrics.total_toxicity.toFixed(2)} />
                 <MetricBox label="Tumor Reduction" value={`${tumorReductionPercent.toFixed(1)}%`} />
                 <MetricBox label="Treatment Days" value={patientData.days} />
               </div>

               <div className="bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-6 border border-white/60">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 shadow-inner">
                      <Target size={16} />
                    </div>
                    <h3 className="font-black text-slate-700 uppercase tracking-widest text-sm">Optimized Schedule</h3>
                  </div>
                  
                  <ScheduleTable solution={results.solution} days={patientData.days} maxSlots={patientData.max_drugs_per_day} />
               </div>
               
               <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                 <div className="bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-6 border border-white/60 overflow-hidden flex flex-col h-[400px]">
                   <div className="flex items-center gap-3 mb-4">
                      <div className="w-8 h-8 rounded-full bg-rose-100 flex items-center justify-center text-rose-600 shadow-inner">
                        <ActivityIcon size={16} />
                      </div>
                      <h3 className="font-black text-slate-700 uppercase tracking-widest text-sm">Toxicity Limit</h3>
                   </div>
                   <div className="flex-1 w-full bg-[#E6EEF5] rounded-2xl shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] p-2 flex items-center justify-center overflow-hidden">
                     <Plot
                        data={[
                          {
                            x: results.charts.t_days,
                                y: standardToxicity,
                                type: 'scatter',
                                mode: 'lines+markers',
                                fill: 'tozeroy',
                                name: 'Standard Schedule',
                                line: {color: '#94a3b8', width: 2, dash: 'dash'},
                                fillcolor: 'rgba(148, 163, 184, 0.15)'
                              },
                              {
                                x: results.charts.t_days,
                                y: qdosToxicity,
                            type: 'scatter',
                            mode: 'lines+markers',
                            fill: 'tozeroy',
                            name: 'Toxicity Burden (Q-DOS)',
                            line: {color: '#ef4444', width: 2},
                            fillcolor: 'rgba(239, 68, 68, 0.2)'
                          },
                          {
                             x: [0, patientData.days - 1],
                             y: [results.charts.budget, results.charts.budget],
                             mode: 'lines',
                             name: 'Safety Threshold',
                             line: {color: '#dc2626', width: 2, dash: 'dot'}
                          }
                        ]}
                        layout={{
                          autosize: true,
                          margin: {l:40, r:20, t:20, b:40},
                          paper_bgcolor: 'rgba(0,0,0,0)',
                          plot_bgcolor: 'rgba(0,0,0,0)',
                          xaxis: {title: {text: '<b>Days</b>'}, tickvals: dayLabels.tickvals, ticktext: dayLabels.ticktext},
                          yaxis: {title: {text: '<b>Toxicity Burden</b>'}},
                          showlegend: false
                        }}
                        useResizeHandler={true}
                        style={{width: '100%', height: '100%'}}
                     />
                   </div>
                 </div>

                 <div className="bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-6 border border-white/60 flex flex-col h-[400px]">
                   <div className="flex items-center gap-3 mb-4">
                      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 shadow-inner">
                        <Shield size={16} />
                      </div>
                      <h3 className="font-black text-slate-700 uppercase tracking-widest text-sm">Tumor Size Reduction</h3>
                   </div>
                   <div className="flex-1 w-full bg-[#E6EEF5] rounded-2xl shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] p-2 flex justify-center items-center overflow-hidden">
                     <Plot
                        data={[
                          {
                            x: results.charts.t_days,
                            y: noTreatmentTumor,
                            type: 'scatter',
                            mode: 'lines+markers',
                            name: 'No Treatment',
                            line: {color: '#94a3b8', width: 2, dash: 'dash'},
                            marker: {symbol: 'circle', size: 4}
                          },
                          {
                            x: results.charts.t_days,
                            y: standardTumor,
                            type: 'scatter',
                            mode: 'lines+markers',
                            name: 'Standard Schedule',
                            line: {color: '#f59e0b', width: 2},
                            marker: {symbol: 'square', size: 5}
                          },
                          {
                            x: results.charts.t_days,
                            y: results.charts.tumor_qdos,
                            type: 'scatter',
                            mode: 'lines+markers',
                            name: 'Q-DOS Optimized',
                            line: {color: '#10b981', width: 3},
                            marker: {symbol: 'diamond', size: 6}
                          }
                        ]}
                        layout={{
                          autosize: true,
                          margin: {l:40, r:20, t:20, b:40},
                          paper_bgcolor: 'rgba(0,0,0,0)',
                          plot_bgcolor: 'rgba(0,0,0,0)',
                          xaxis: {title: {text: '<b>Days</b>'}, tickvals: dayLabels.tickvals, ticktext: dayLabels.ticktext},
                          yaxis: {title: {text: '<b>Size (#)</b>'}},
                          legend: {orientation: 'h', y: 1.1, x: 0}
                        }}
                        useResizeHandler={true}
                        style={{width: '100%', height: '100%'}}
                     />
                   </div>
                 </div>
               </div>

               <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                 <div className="bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-6 border border-white/60 flex flex-col h-[420px]">
                   <div className="flex items-center gap-3 mb-4">
                      <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 shadow-inner">
                        <Sliders size={16} />
                      </div>
                      <h3 className="font-black text-slate-700 uppercase tracking-widest text-sm">Schedule Heatmap</h3>
                   </div>
                   <div className="flex-1 w-full bg-[#E6EEF5] rounded-2xl shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] p-2 flex items-center justify-center overflow-hidden">
                     <Plot
                        data={[
                          {
                            z: scheduleHeatmap,
                            x: dayLabels.plain,
                            y: selectedDrugs,
                            type: 'heatmap',
                            colorscale: [[0, '#e2e8f0'], [1, '#4f46e5']],
                            showscale: false,
                            hovertemplate: '%{x}<br>%{y}: %{z}<extra></extra>'
                          }
                        ]}
                        layout={{
                          autosize: true,
                          margin: {l:80, r:20, t:20, b:40},
                          paper_bgcolor: 'rgba(0,0,0,0)',
                          plot_bgcolor: 'rgba(0,0,0,0)',
                          xaxis: {title: {text: '<b>Days</b>'}, tickvals: dayLabels.plain, ticktext: dayLabels.ticktext, tickfont: {size: 10}},
                          yaxis: {title: {text: '<b>Drugs</b>'}, autorange: 'reversed'},
                        }}
                        useResizeHandler={true}
                        style={{width: '100%', height: '100%'}}
                     />
                   </div>
                 </div>

                 <div className="bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-6 border border-white/60 flex flex-col h-[420px]">
                   <div className="flex items-center gap-3 mb-4">
                      <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 shadow-inner">
                        <Target size={16} />
                      </div>
                      <h3 className="font-black text-slate-700 uppercase tracking-widest text-sm">Organ Burden</h3>
                   </div>
                   <div className="flex-1 w-full bg-[#E6EEF5] rounded-2xl shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] p-2 flex items-center justify-center overflow-hidden">
                     <Plot
                        data={[
                          {
                            x: organBurden,
                            y: ["Kidney", "Liver", "Marrow", "Immune", "Vascular"],
                            type: 'bar',
                            orientation: 'h',
                            marker: {color: ['#ef4444', '#f97316', '#eab308', '#3b82f6', '#8b5cf6']}
                          }
                        ]}
                        layout={{
                          autosize: true,
                          margin: {l:90, r:20, t:20, b:30},
                          paper_bgcolor: 'rgba(0,0,0,0)',
                          plot_bgcolor: 'rgba(0,0,0,0)',
                          xaxis: {title: {text: '<b>Organ Toxicity Burden</b>'}},
                          yaxis: {
                            title: '',
                            tickvals: ["Kidney", "Liver", "Marrow", "Immune", "Vascular"],
                            ticktext: ["<b>Kidney</b>", "<b>Liver</b>", "<b>Marrow</b>", "<b>Immune</b>", "<b>Vascular</b>"],
                          },
                        }}
                        useResizeHandler={true}
                        style={{width: '100%', height: '100%'}}
                     />
                   </div>
                 </div>
               </div>

               {(results?.model?.synergy_matrix || results?.model?.energy_vector) && (
                 <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                   <div className="bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-6 border border-white/60 flex flex-col h-[420px]">
                     <div className="flex items-center gap-3 mb-4">
                       <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 shadow-inner">
                         <Sliders size={16} />
                       </div>
                       <h3 className="font-black text-slate-700 uppercase tracking-widest text-sm">Synergy Matrix</h3>
                     </div>
                     <div className="flex-1 w-full bg-[#E6EEF5] rounded-2xl shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] p-2 flex items-center justify-center overflow-hidden">
                       <Plot
                         data={[
                           {
                             z: results.model.synergy_matrix.matrix,
                             x: results.model.synergy_matrix.drugs,
                             y: results.model.synergy_matrix.drugs,
                             type: 'heatmap',
                             colorscale: [[0, '#ef4444'], [0.5, '#e2e8f0'], [1, '#10b981']],
                             zmid: 0,
                             showscale: false,
                             hovertemplate: '%{y} → %{x}<br>Synergy: %{z:.3f}<extra></extra>'
                           }
                         ]}
                         layout={{
                           autosize: true,
                           margin: { l: 90, r: 20, t: 20, b: 70 },
                           paper_bgcolor: 'rgba(0,0,0,0)',
                           plot_bgcolor: 'rgba(0,0,0,0)',
                           xaxis: {
                             title: { text: '<b>Drug</b>' },
                             tickangle: -30,
                             tickvals: results.model.synergy_matrix.drugs,
                             ticktext: (results.model.synergy_matrix.drugs as string[]).map((d: string) => `<b>${d}</b>`),
                           },
                           yaxis: {
                             title: { text: '<b>Drug</b>' },
                             autorange: 'reversed',
                             tickvals: results.model.synergy_matrix.drugs,
                             ticktext: (results.model.synergy_matrix.drugs as string[]).map((d: string) => `<b>${d}</b>`),
                           },
                         }}
                         useResizeHandler={true}
                         style={{ width: '100%', height: '100%' }}
                       />
                     </div>
                   </div>

                   <div className="bg-[#E6EEF5] shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] rounded-4xl p-6 border border-white/60 flex flex-col h-[420px]">
                     <div className="flex items-center gap-3 mb-4">
                       <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 shadow-inner">
                         <Target size={16} />
                       </div>
                       <h3 className="font-black text-slate-700 uppercase tracking-widest text-sm">Energy Vector</h3>
                     </div>
                     <div className="flex-1 w-full bg-[#E6EEF5] rounded-2xl shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] p-2 flex items-center justify-center overflow-hidden">
                       {(() => {
                         const ev = results.model.energy_vector || {};
                         const drugs = Object.keys(ev);
                         const energies = drugs.map((d) => (ev[d] || []).reduce((a: number, b: number) => a + Number(b || 0), 0));
                         return (
                           <Plot
                             data={[
                               {
                                 x: drugs,
                                 y: energies,
                                 type: 'bar',
                                 marker: { color: '#4f46e5' },
                                 hovertemplate: '%{x}<br>Energy: %{y:.3f}<extra></extra>'
                               }
                             ]}
                             layout={{
                               autosize: true,
                               margin: { l: 60, r: 20, t: 20, b: 70 },
                               paper_bgcolor: 'rgba(0,0,0,0)',
                               plot_bgcolor: 'rgba(0,0,0,0)',
                               xaxis: { title: { text: '<b>Drug</b>' }, tickangle: -30, tickvals: drugs, ticktext: drugs.map((d: string) => `<b>${d}</b>`) },
                               yaxis: { title: { text: '<b>Energy</b>' } },
                             }}
                             useResizeHandler={true}
                             style={{ width: '100%', height: '100%' }}
                           />
                         );
                       })()}
                     </div>
                   </div>
                 </div>
               )}
             </>
           )}
        </div>

      </div>
    </div>
  );
}

// Subcomponents

function Input({ label, value, onChange, ...props }: any) {
  return (
    <div className={props.className}>
      <label className="block text-[9px] font-black text-slate-500 uppercase tracking-widest pl-2 mb-1">{label}</label>
      <input
        {...props}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-[#E6EEF5] rounded-xl px-3 py-2 text-sm shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] focus:outline-none focus:ring-2 focus:ring-indigo-400 font-bold text-slate-700 transition-all border-none"
      />
    </div>
  );
}

function Slider({ label, value, onChange, ...props }: any) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1 px-2">
        <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest">{label}</label>
        <span className="text-[10px] font-black text-indigo-500 bg-[#E6EEF5] px-1.5 py-0.5 rounded shadow-[inset_2px_2px_4px_#c4cacf,inset_-2px_-2px_4px_#ffffff]">{value}</span>
      </div>
      <input
        type="range"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        {...props}
        className="w-full h-2 bg-[#E6EEF5] rounded-full appearance-none shadow-[inset_3px_3px_6px_#c4cacf,inset_-3px_-3px_6px_#ffffff] accent-indigo-500 cursor-pointer"
      />
    </div>
  );
}

function MetricBox({ label, value }: { label: string, value: string | number }) {
  return (
    <div className="bg-[#E6EEF5] rounded-4xl p-4 shadow-[8px_8px_16px_#c4cacf,-8px_-8px_16px_#ffffff] border border-white/60 flex flex-col items-center justify-center text-center">
       <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">{label}</span>
       <span className="text-3xl font-black text-indigo-600 drop-shadow-sm">{value}</span>
    </div>
  );
}

function ScheduleTable({ solution, days, maxSlots }: { solution: any, days: number, maxSlots: number }) {
  if (!solution) return null;

  const binarySchedule = solution?.schedule ?? {};

  const rows = Array.from({ length: days }, (_, day) => {
    const drugsOnDay = Object.keys(binarySchedule).filter((drug) => Number(binarySchedule[drug]?.[day] ?? 0) > 0);
    return { day, drugsOnDay };
  });

  const slots = Array.from({ length: Math.max(1, maxSlots) }, (_, i) => i);

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full text-left border-separate border-spacing-y-2">
        <thead>
          <tr>
            <th className="text-[9px] font-black text-slate-500 uppercase tracking-widest px-3 py-2">Day</th>
            {slots.map((i) => (
              <th key={i} className="text-[9px] font-black text-slate-500 uppercase tracking-widest px-3 py-2">Drug {i + 1}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ day, drugsOnDay }) => (
            <tr key={day} className="bg-[#E6EEF5] shadow-[inset_4px_4px_8px_#c4cacf,inset_-4px_-4px_8px_#ffffff] rounded-2xl">
              <td className="px-3 py-3 font-black text-slate-700 whitespace-nowrap">{day + 1} day</td>
              {slots.map((slot) => (
                <td key={slot} className="px-3 py-3 font-bold text-slate-600 whitespace-nowrap">
                  {drugsOnDay[slot] ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
