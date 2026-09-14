import type { AnalysisResult, AnalysisSignal } from "@/lib/api-contracts";

type DomainProfile = {
  label: string;
  inputs: AnalysisSignal[];
  outputSignals: AnalysisSignal[];
  internalSignals: AnalysisSignal[];
  confidence: number;
};

const DOMAIN_PROFILES: Record<"motor" | "sequential-batch", DomainProfile> = {
  motor: {
    label: "Motor Control",
    confidence: 0.92,
    inputs: [
      { name: "Start_PB", type: "BOOL" },
      { name: "Stop_PB", type: "BOOL" },
      { name: "Emergency_Stop", type: "BOOL" },
      { name: "Overload", type: "BOOL" },
      { name: "Reset_PB", type: "BOOL" }
    ],
    outputSignals: [
      { name: "Motor_Run", type: "BOOL" },
      { name: "Fault_Lamp", type: "BOOL" },
      { name: "Ready_Lamp", type: "BOOL" }
    ],
    internalSignals: [{ name: "Fault_State", type: "BOOL" }]
  },
  "sequential-batch": {
    label: "Sequential Batch",
    confidence: 0.92,
    inputs: [
      { name: "Start_PB", type: "BOOL" },
      { name: "Emergency_Stop", type: "BOOL" },
      { name: "Abort_PB", type: "BOOL" },
      { name: "Reset_PB", type: "BOOL" },
      { name: "High_Level", type: "BOOL" },
      { name: "Low_Level", type: "BOOL" },
      { name: "Mix_Timer_Done", type: "BOOL" }
    ],
    outputSignals: [
      { name: "Fill_Valve", type: "BOOL" },
      { name: "Mixer_Motor", type: "BOOL" },
      { name: "Drain_Valve", type: "BOOL" },
      { name: "Batch_Complete", type: "BOOL" }
    ],
    internalSignals: [
      { name: "Step_State", type: "INT" },
      { name: "Fault_State", type: "BOOL" }
    ]
  }
};

export function deriveRequirementAnalysisPreview({
  projectDomain,
  requirementText,
  safetyConstraints
}: {
  projectDomain: string;
  requirementText: string;
  safetyConstraints: string[];
}): AnalysisResult {
  const key = requirementText.toLowerCase();
  const normalizedDomain = normalizeDomain(projectDomain) ?? normalizeDomain(key);
  const profile = normalizedDomain ? DOMAIN_PROFILES[normalizedDomain] : null;
  const domain = profile?.label ?? "Generic";
  const inputSignals = profile?.inputs.filter((signal) => isInputExplicitlyMentioned(key, signal.name, domain)) ?? [];
  const outputSignals = profile?.outputSignals.filter((signal) => isOutputExplicitlyMentioned(key, signal.name, domain)) ?? [];
  const suggestedInternals = profile?.internalSignals ?? [];
  const signalCount = inputSignals.length + outputSignals.length + suggestedInternals.length;
  const confidence = signalCount >= 5 ? 0.92 : signalCount >= 3 ? 0.72 : 0.55;

  return {
    domain,
    confidence: profile?.confidence ?? confidence,
    inferred_inputs: dedupeSignals(inputSignals),
    suggested_outputs: dedupeSignals(outputSignals),
    suggested_internals: dedupeSignals(suggestedInternals),
    safety_constraints: [...safetyConstraints],
    suggested_constraints: generateSafetyConstraintSuggestions(requirementText),
    source: "heuristic"
  };
}

function dedupeSignals(signals: AnalysisSignal[]) {
  return signals.filter((item, index, source) => source.findIndex((candidate) => candidate.name === item.name) === index);
}

function includesAny(text: string, keys: string[]) {
  return keys.some((item) => text.includes(item));
}

function normalizeDomain(text: string): "motor" | "sequential-batch" | null {
  const key = text.toLowerCase();
  if (key.includes("sequential batch") || key.includes("batch reactor") || key.includes("batch process")) {
    return "sequential-batch";
  }
  if (key.includes("motor control") || key.includes("conveyor") || key.includes("motor")) {
    return "motor";
  }
  return null;
}

function isInputExplicitlyMentioned(text: string, inputName: string, domain: string) {
  const hints: Record<string, string[]> = {
    Start_PB: ["start_pb", "start pushbutton", "start push button", "operator start", "start command", "start"],
    Stop_PB: ["stop_pb", "stop pushbutton", "stop push button", "stop command", "stop"],
    Emergency_Stop: ["emergency stop", "e-stop", "e_stop", "estop"],
    Overload: ["overload", "thermal overload"],
    Reset_PB: ["reset_pb", "fault reset", "reset"],
    Abort_PB: ["abort_pb", "abort"],
    High_Level: ["high level", "fill complete", "high_level"],
    Low_Level: ["low level", "drain complete", "low_level"],
    Mix_Timer_Done: ["mix timer", "timer done", "mix_timer_done"]
  };

  if (domain === "Sequential Batch") {
    const sequentialOnlyInputs = ["Start_PB", "Emergency_Stop", "Abort_PB", "Reset_PB", "High_Level", "Low_Level", "Mix_Timer_Done"];
    if (!sequentialOnlyInputs.includes(inputName)) return false;
  }

  const inputHints = hints[inputName] ?? [];
  return includesAny(text, inputHints);
}

function isOutputExplicitlyMentioned(text: string, outputName: string, domain: string) {
  const outputHints: Record<string, string[]> = {
    Motor_Run: ["motor_run", "motor run", "run output", "contactor"],
    Fault_Lamp: ["fault lamp", "fault_lamp", "fault indicator"],
    Ready_Lamp: ["ready lamp", "ready_lamp", "ready indicator"],
    Fill_Valve: ["fill valve", "fill_valve"],
    Mixer_Motor: ["mixer motor", "mixer_motor"],
    Drain_Valve: ["drain valve", "drain_valve"],
    Batch_Complete: ["batch complete", "batch_complete"]
  };

  if (domain === "Sequential Batch") {
    const sequentialOutputs = ["Fill_Valve", "Mixer_Motor", "Drain_Valve", "Batch_Complete"];
    if (!sequentialOutputs.includes(outputName)) {
      return false;
    }
  }

  if (outputName === "Motor_Run" && domain !== "Motor Control") {
    return false;
  }

  const hints = outputHints[outputName] ?? [];
  return includesAny(text, hints);
}

function generateSafetyConstraintSuggestions(text: string): string[] {
  const key = text.toLowerCase();
  const suggestions: string[] = [];
  if (key.includes("emergency stop") || key.includes("e-stop") || key.includes("e_stop")) {
    suggestions.push("Motor_Run must be FALSE when Emergency_Stop is active.");
  }
  if (key.includes("overload")) {
    suggestions.push("Motor_Run must be FALSE when Overload is active.");
  }
  if (key.includes("reset") || key.includes("fault")) {
    suggestions.push("Motor must not restart automatically after fault until Reset_PB is pressed.");
  }
  if (key.includes("guard door")) {
    suggestions.push("Actuator output must be FALSE when Guard_Door_Open is active.");
  }
  if (key.includes("tank high level") || key.includes("high level")) {
    suggestions.push("Pump must stop when High_Level is active.");
  }
  return suggestions;
}
