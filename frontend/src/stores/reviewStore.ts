import { create } from "zustand";

export interface EditableLineItem {
  line_item_id?: string;
  product_name?: string;
  sku?: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface ReviewFormState {
  po_number: string;
  customer: string;
  gst_no: string;
  ship_to: string;
  address_1: string;
  address_2: string;
  city: string;
  state: string;
  country: string;
  zip: string;
  line_items: EditableLineItem[];
  total_amount: number;
}

interface ReviewState {
  runId: string | null;
  isEditMode: boolean;
  selectedLineItemId: string | null;
  auditorNote: string;
  isConfirmDialogOpen: boolean;
  confirmAction: "approve" | "reject" | null;
  form: ReviewFormState | null;
  isLoading: boolean;
  setRunId: (runId: string | null) => void;
  setIsEditMode: (isEditMode: boolean) => void;
  setSelectedLineItemId: (id: string | null) => void;
  setAuditorNote: (note: string) => void;
  setIsConfirmDialogOpen: (open: boolean) => void;
  setConfirmAction: (action: "approve" | "reject" | null) => void;
  setForm: (form: ReviewFormState | null) => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

export const useReviewStore = create<ReviewState>((set) => ({
  runId: null,
  isEditMode: false,
  selectedLineItemId: null,
  auditorNote: "",
  isConfirmDialogOpen: false,
  confirmAction: null,
  form: null,
  isLoading: false,

  setRunId: (runId) => set({ runId }),
  setIsEditMode: (isEditMode) => set({ isEditMode }),
  setSelectedLineItemId: (id) => set({ selectedLineItemId: id }),
  setAuditorNote: (auditorNote) => set({ auditorNote }),
  setIsConfirmDialogOpen: (open) => set({ isConfirmDialogOpen: open }),
  setConfirmAction: (confirmAction) => set({ confirmAction }),
  setForm: (form) => set({ form }),
  setLoading: (isLoading) => set({ isLoading }),
  reset: () =>
    set({
      runId: null,
      isEditMode: false,
      selectedLineItemId: null,
      auditorNote: "",
      isConfirmDialogOpen: false,
      confirmAction: null,
      form: null,
      isLoading: false,
    }),
}));