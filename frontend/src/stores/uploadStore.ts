import { create } from "zustand";

export type UploadPhase = "IDLE" | "SELECTED" | "UPLOADING" | "PROCESSING" | "COMPLETED" | "FAILED";
export type StepperStep = "upload" | "extract" | "verify" | "sale";

interface UploadState {
  phase: UploadPhase;
  file: File | null;
  error: string | null;
  runId: string | null;
  activeStep: StepperStep;
  setPhase: (phase: UploadPhase) => void;
  setFile: (file: File | null) => void;
  setError: (error: string | null) => void;
  setRunId: (runId: string | null) => void;
  setActiveStep: (step: StepperStep) => void;
  reset: () => void;
  resetToSelect: () => void;
}

export const useUploadStore = create<UploadState>((set) => ({
  phase: "IDLE",
  file: null,
  error: null,
  runId: null,
  activeStep: "upload",

  setPhase: (phase) => set({ phase }),
  setFile: (file) => set({ file }),
  setError: (error) => set({ error }),
  setRunId: (runId) => set({ runId }),
  setActiveStep: (activeStep) => set({ activeStep }),
  reset: () =>
    set({
      phase: "IDLE",
      file: null,
      error: null,
      runId: null,
      activeStep: "upload",
    }),
  resetToSelect: () =>
    set({
      phase: "IDLE",
      file: null,
      error: null,
      runId: null,
      activeStep: "upload",
    }),
}));