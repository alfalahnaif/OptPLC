import {
  Activity,
  BarChart3,
  Beaker,
  Bell,
  Binary,
  Bot,
  Bug,
  ClipboardList,
  Code2,
  FileCode2,
  FileText,
  Folder,
  Gauge,
  GitBranch,
  History,
  Home,
  Plus,
  Settings,
  ShieldCheck,
  Sparkles,
  Workflow
} from "lucide-react";

export const currentProject = {
  id: "PRJ-0421",
  name: "Motor Control - Conveyor M-12",
  domain: "Motor Control",
  owner: "L. Park",
  updated: "2026-05-17",
  standard: "IEC 61131-3",
  runtime: "CODESYS / TwinCAT compatible"
};

export const sidebarSections = [
  {
    label: "Overview",
    items: [
      { title: "Dashboard", href: "/", icon: Home },
      { title: "New Project", href: "/new-project", icon: Plus },
      { title: "Project History", href: "/history", icon: History }
    ]
  },
  {
    label: "Pipeline",
    items: [
      { title: "Requirements", href: "/requirements", icon: ClipboardList },
      { title: "Plan Object", href: "/plan", icon: GitBranch },
      { title: "Agent Workflow", href: "/workflow", icon: Workflow },
      { title: "Generated Code", href: "/code", icon: Code2 },
      { title: "Validation", href: "/validation", icon: ShieldCheck },
      { title: "Debugging", href: "/debugging", icon: Bug },
      { title: "Optimization", href: "/optimization", icon: Sparkles },
      { title: "Metrics", href: "/metrics", icon: BarChart3 },
      { title: "Final Report", href: "/report", icon: FileText }
    ]
  },
  {
    label: "System",
    items: [
      { title: "Benchmark Suite", href: "/benchmark", icon: Beaker },
      { title: "Settings", href: "/settings", icon: Settings }
    ]
  }
] as const;

export const pipelineSteps = [
  { id: "01", title: "Requirements", href: "/requirements" },
  { id: "02", title: "Plan Object", href: "/plan" },
  { id: "03", title: "Agent Workflow", href: "/workflow" },
  { id: "04", title: "Generated Code", href: "/code" },
  { id: "05", title: "Validation", href: "/validation" },
  { id: "06", title: "Debugging", href: "/debugging" },
  { id: "07", title: "Optimization", href: "/optimization" },
  { id: "08", title: "Metrics", href: "/metrics" },
  { id: "09", title: "Final Report", href: "/report" }
] as const;

export const dashboardKpis = [
  { label: "Total projects", value: "24", detail: "5 active", delta: "+12.5%", icon: Folder, tone: "primary" },
  { label: "Verified programs", value: "21 / 24", detail: "first pass plus repaired", delta: "+9.4%", icon: ShieldCheck, tone: "success" },
  { label: "Optimized programs", value: "19 / 21", detail: "validated gains", delta: "+14.2%", icon: Sparkles, tone: "primary" },
  { label: "Avg complexity reduction", value: "34.6%", detail: "last 30 days", delta: "+4.1%", icon: Activity, tone: "info" },
  { label: "Avg maintainability gain", value: "+21.2 pts", detail: "IEC ST score", delta: "+2.8%", icon: Gauge, tone: "success" }
];

export const trendData = [
  { week: "W14", complexity: 18, maintainability: 4 },
  { week: "W15", complexity: 22, maintainability: 7 },
  { week: "W16", complexity: 27, maintainability: 9 },
  { week: "W17", complexity: 25, maintainability: 11 },
  { week: "W18", complexity: 29, maintainability: 14 },
  { week: "W19", complexity: 31, maintainability: 16 },
  { week: "W20", complexity: 34, maintainability: 19 },
  { week: "W21", complexity: 33, maintainability: 22 },
  { week: "W22", complexity: 32, maintainability: 24 },
  { week: "W23", complexity: 38, maintainability: 26 },
  { week: "W24", complexity: 41, maintainability: 28 },
  { week: "W25", complexity: 43, maintainability: 31 }
];

export const serviceStatus = [
  { name: "LLM Provider", detail: "Claude Sonnet 4.5", latency: "412 ms", status: "healthy", icon: Bot },
  { name: "Validator", detail: "MATIEC + nuXmv", latency: "6.1 s", status: "healthy", icon: ShieldCheck },
  { name: "Optimizer", detail: "3-pass pipeline", latency: "11.2 s", status: "healthy", icon: Sparkles },
  { name: "RAG Knowledge", detail: "7 docs, 279k chunks", latency: "88 ms", status: "healthy", icon: Binary }
];

export const projects = [
  { name: "Motor Control - Conveyor M-12", id: "PRJ-0421", domain: "Motor Control", updated: "2026-05-17", iterations: 3, delta: "-41.7%", status: "optimized" },
  { name: "Tank Level Control - T-204", id: "PRJ-0418", domain: "Process Control", updated: "2026-05-15", iterations: 4, delta: "-36.2%", status: "optimized" },
  { name: "Intersection 17 Traffic Signal", id: "PRJ-0415", domain: "Traffic Control", updated: "2026-05-12", iterations: 2, delta: "-28.9%", status: "verified" },
  { name: "Safety Interlock - Press P-3", id: "PRJ-0410", domain: "Safety Interlocks", updated: "2026-05-08", iterations: 5, delta: "-47.4%", status: "optimized" },
  { name: "Batch Reactor Sequence R-1", id: "PRJ-0407", domain: "Sequential Batch", updated: "2026-05-03", iterations: 5, delta: "-", status: "failed" }
];

export const domainYield = [
  { domain: "Motor Control", value: 92, color: "bg-emerald-700" },
  { domain: "Process Control", value: 84, color: "bg-blue-700" },
  { domain: "Traffic Control", value: 88, color: "bg-emerald-700" },
  { domain: "Safety Interlocks", value: 78, color: "bg-blue-700" },
  { domain: "Sequential Batch", value: 71, color: "bg-amber-700" }
];

export const requirement = {
  text:
    "Control a three-phase motor on conveyor M-12. The operator starts the motor via the Start pushbutton when the Stop pushbutton is not pressed. Pressing Stop or activating the Emergency Stop must immediately de-energize the motor. After an Emergency Stop or thermal overload event, the motor must NOT restart automatically. The operator must acknowledge the fault using the Reset pushbutton before a new Start command is accepted. Fault and Ready lamps must indicate state.",
  constraints: [
    "Motor must not auto-restart after Emergency Stop",
    "E-Stop input is NC (Normally Closed); broken wire triggers fault",
    "Reset requires explicit operator action",
    "Fault lamp must reflect latched fault, not transient signal"
  ],
  performanceTargets: {
    scanTimeMs: 5,
    cyclomaticComplexity: 8,
    maintainability: 75,
    maxIterations: 5
  }
};

export const planObject = {
  projectId: "PRJ-0421",
  agent: "PlanningAgent/v1.4",
  generatedAt: "2026-05-17T09:42:18Z",
  inputs: [
    { name: "Start_PB", type: "BOOL", source: "DI-04", description: "Momentary start pushbutton" },
    { name: "Stop_PB", type: "BOOL", source: "DI-05", description: "Momentary stop pushbutton, NC" },
    { name: "E_Stop", type: "BOOL", source: "DI-06", description: "Emergency stop, NC, hardwired safety relay" },
    { name: "Overload", type: "BOOL", source: "DI-07", description: "Thermal overload relay contact" },
    { name: "Reset_PB", type: "BOOL", source: "DI-08", description: "Operator fault acknowledgement" }
  ],
  outputs: [
    { name: "Motor_Run", type: "BOOL", address: "DO-01", description: "Motor contactor coil" },
    { name: "Fault_Lamp", type: "BOOL", address: "DO-02", description: "Fault indicator red" },
    { name: "Ready_Lamp", type: "BOOL", address: "DO-03", description: "Ready indicator green" }
  ],
  logicRules: [
    "Start latch held until Stop, fault, or de-energize",
    "Any safety event sets latched Fault_State",
    "Fault_State only cleared by Reset_PB while sources are clear",
    "Motor_Run is gated by NOT Fault_State"
  ],
  safetyConstraints: requirement.constraints,
  scope: {
    standard: "IEC 61131-3",
    edition: "3rd ed. (2013)",
    language: "Structured Text",
    runtime: "CODESYS / TwinCAT compatible"
  }
};

export const generatedStructuredText = `(*========================
  M01_Motor_Controller - patched after validation feedback
  Target: IEC 61131-3 Structured Text
  Generated by: Code Generation Agent - iter 2
  Patch: Reset_PB + Fault_State, prevent auto-restart after E-Stop
========================*)

PROGRAM Motor_Controller
VAR_INPUT
    Start_PB    : BOOL;
    Stop_PB     : BOOL;
    E_Stop      : BOOL;  (* NC, hardwired *)
    Overload    : BOOL;
    Reset_PB    : BOOL;  (* Operator acknowledgement *)
END_VAR
VAR_OUTPUT
    Motor_Run   : BOOL;
    Fault_Lamp  : BOOL;
    Ready_Lamp  : BOOL;
END_VAR
VAR
    Run_Cmd       : BOOL;
    Fault_State   : BOOL;
    EStop_Active  : BOOL;
END_VAR

(* Safety sensing *)
EStop_Active := NOT E_Stop;

(* Latch fault on any safety event; require explicit reset *)
IF EStop_Active OR Overload THEN
    Fault_State := TRUE;
    Run_Cmd := FALSE;
END_IF;

IF Fault_State AND Reset_PB AND NOT EStop_Active AND NOT Overload THEN
    Fault_State := FALSE;
END_IF;

(* Start/stop, gated by fault state *)
IF Start_PB AND NOT Stop_PB AND NOT Fault_State THEN
    Run_Cmd := TRUE;
END_IF;

IF Stop_PB OR Fault_State THEN
    Run_Cmd := FALSE;
END_IF;

(* Outputs *)
Motor_Run := Run_Cmd AND NOT Fault_State;
Fault_Lamp := Fault_State;
Ready_Lamp := NOT Fault_State AND NOT Motor_Run;

END_PROGRAM`;

export const optimizedStructuredText = `(*========================
  M01_Motor_Controller - optimized
  Passes: Structural Simplification, Logic Compaction,
          Maintainability Enhancement
  Revalidation: PASSED
========================*)

PROGRAM Motor_Controller
VAR_INPUT
    Start_PB    : BOOL;
    Stop_PB     : BOOL;
    E_Stop      : BOOL;  (* NC, hardwired *)
    Overload    : BOOL;
    Reset_PB    : BOOL;
END_VAR
VAR_OUTPUT
    Motor_Run   : BOOL;
    Fault_Lamp  : BOOL;
    Ready_Lamp  : BOOL;
END_VAR
VAR
    Run_Cmd     : BOOL;
    Fault_State : BOOL;
END_VAR

IF (NOT E_Stop) OR Overload THEN
    Fault_State := TRUE;
ELSIF Reset_PB THEN
    Fault_State := FALSE;
END_IF;

Run_Cmd := (Run_Cmd OR Start_PB) AND NOT Stop_PB AND NOT Fault_State;

Motor_Run := Run_Cmd;
Fault_Lamp := Fault_State;
Ready_Lamp := NOT Fault_State AND NOT Motor_Run;

END_PROGRAM`;

export const workflowEvents = [
  { agent: "Planning Agent", status: "completed", iter: 1, input: "Natural-language requirement", output: "Plan Object: 5 inputs, 3 outputs, 4 safety constraints", duration: "4.2 s", icon: GitBranch },
  { agent: "Code Generation Agent", status: "completed", iter: 1, input: "Plan Object - iter 1", output: "ST source: 38 LOC, syntax OK", duration: "6.8 s", icon: FileCode2 },
  { agent: "Validation Agent", status: "failed", iter: 1, input: "ST source - iter 1", output: "1 syntax pass, 1 formal violation (SC1)", duration: "9.1 s", icon: ShieldCheck },
  { agent: "Debugging Agent", status: "completed", iter: 1, input: "Counterexample trace", output: "Patch advice: introduce Reset_PB + Fault_State latch", duration: "5.4 s", icon: Bug },
  { agent: "Code Generation Agent", status: "completed", iter: 2, input: "Plan Object + patch advice", output: "ST source: 47 LOC, syntax OK", duration: "5.9 s", icon: FileCode2 },
  { agent: "Validation Agent", status: "completed", iter: 2, input: "ST source - iter 2", output: "All safety properties hold - CSR 100%", duration: "8.7 s", icon: ShieldCheck },
  { agent: "Optimization Agent", status: "completed", iter: 1, input: "Verified ST - iter 2", output: "3/3 passes applied, revalidation PASS", duration: "11.2 s", icon: Sparkles }
];

export const sessionLog = [
  ["09:42:14", "INFO", "Planning", "Session start - project PRJ-0421"],
  ["09:42:18", "INFO", "Planning", "Plan Object emitted (2.1 KB)"],
  ["09:42:22", "INFO", "CodeGen", "RAG retrieval: 7 documents, top-k=5"],
  ["09:42:26", "INFO", "CodeGen", "Generated ST: 38 LOC - iter 1"],
  ["09:42:31", "INFO", "Validation", "MATIEC syntax check: PASS"],
  ["09:42:37", "WARN", "Validation", "Property no_auto_restart_after_estop: VIOLATED"],
  ["09:42:38", "ERROR", "Validation", "Counterexample emitted (8 steps)"],
  ["09:42:44", "INFO", "Debugging", "Patch advice ready - 4 changes"],
  ["09:42:49", "INFO", "CodeGen", "Regenerated ST: 47 LOC - iter 2"],
  ["09:42:58", "INFO", "Validation", "All 4 properties VERIFIED - iter 2"],
  ["09:43:01", "INFO", "Optimization", "Pass 1/3 Structural Simplification applied"],
  ["09:43:04", "INFO", "Optimization", "Pass 2/3 Logic Compaction applied"],
  ["09:43:08", "INFO", "Optimization", "Pass 3/3 Maintainability Enhancement applied"]
];

export const validation = {
  iteration: 2,
  properties: 4,
  syntax: "MATIEC 0.7",
  solver: "nuXmv 2.0",
  totalTime: "7.4 s",
  checks: [
    "Tokenization OK",
    "Type checks pass for all declarations",
    "POU structure conforms to IEC 61131-3"
  ],
  counterexample: [
    { t: 0, start: false, estop: true, overload: false, reset: false, motor: false },
    { t: 1, start: true, estop: true, overload: false, reset: false, motor: true },
    { t: 2, start: false, estop: false, overload: false, reset: false, motor: false },
    { t: 3, start: false, estop: true, overload: false, reset: false, motor: true }
  ]
};

export const optimizationPasses = [
  { name: "Structural Simplification", status: "completed", description: "Collapsed nested IF chains into a single guarded expression. Removed unused EStop_Active intermediate.", loc: [47, 39], cc: [9, 6] },
  { name: "Logic Compaction", status: "completed", description: "Converted two latch patterns to compact assignment form. Lifted fault and run command into single-expression form.", loc: [39, 34], cc: [6, 5] },
  { name: "Maintainability Enhancement", status: "completed", description: "Renamed locals for clarity, grouped output assignments, regenerated section comments, aligned VAR columns.", loc: [34, 33], cc: [5, 4] }
];

export const metricsCards = [
  { label: "Lines of code", before: 47, after: 33, suffix: "LOC", delta: "+29.8%" },
  { label: "Cyclomatic complexity", before: 9, after: 4, suffix: "", delta: "+55.6%" },
  { label: "Maintainability index", before: 68, after: 89, suffix: "/100", delta: "+30.9%" },
  { label: "Estimated scan time", before: 4.1, after: 2.4, suffix: "ms", delta: "+41.5%" },
  { label: "Iteration count", before: 2, after: 2, suffix: "", delta: "unchanged" },
  { label: "Verification rate", before: 75, after: 100, suffix: "%", delta: "+33.3%" }
];

export const comparisonData = [
  { metric: "LOC", before: 47, after: 33 },
  { metric: "CC", before: 9, after: 4 },
  { metric: "MI / 100", before: 68, after: 89 },
  { metric: "Scan (ms x10)", before: 41, after: 24 },
  { metric: "VR %", before: 75, after: 100 }
];

export const qualityRadar = [
  { subject: "Maintainability", before: 68, after: 89 },
  { subject: "Verifiability", before: 76, after: 96 },
  { subject: "Compactness", before: 54, after: 84 },
  { subject: "Simplicity", before: 61, after: 90 },
  { subject: "Determinism", before: 82, after: 94 },
  { subject: "Readability", before: 72, after: 88 }
];

export const benchmarkCases = [
  { id: "B-001", name: "Motor start/stop with E-stop", domain: "Motor Control", complexity: "Medium", status: "passed", time: "24.3 s", gain: "41.7%" },
  { id: "B-002", name: "Two-pump alternation", domain: "Process Control", complexity: "Medium", status: "passed", time: "28.9 s", gain: "32.4%" },
  { id: "B-003", name: "Tank high-high trip", domain: "Safety Interlocks", complexity: "Simple", status: "passed", time: "18.1 s", gain: "27.8%" },
  { id: "B-004", name: "Traffic light pedestrian phase", domain: "Traffic Control", complexity: "Medium", status: "passed", time: "31.0 s", gain: "29.1%" },
  { id: "B-005", name: "Batch fill-heat-agitate-drain", domain: "Sequential Batch", complexity: "Complex", status: "warning", time: "49.6 s", gain: "18.6%" },
  { id: "B-006", name: "Compressor permissive chain", domain: "Motor Control", complexity: "Complex", status: "passed", time: "37.8 s", gain: "45.3%" }
];

export const settingsGroups = [
  { title: "Planning Agent", rows: [["Plan schema", "plan_object.v1.4"], ["Max requirement tokens", "4,000"], ["I/O extraction mode", "strict"]] },
  { title: "Validation Agent", rows: [["Syntax checker", "MATIEC 0.7"], ["Formal solver", "nuXmv 2.0"], ["Counterexample depth", "12 steps"]] },
  { title: "Optimization Agent", rows: [["Pass budget", "3"], ["Rollback on regression", "enabled"], ["Maintainability floor", "75"]] }
];

export const headerActions = [
  { label: "Notifications", icon: Bell },
  { label: "System activity", icon: Activity }
];

export type Status = "optimized" | "verified" | "failed" | "completed" | "healthy" | "passed" | "warning";
