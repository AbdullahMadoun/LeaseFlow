import { create } from "zustand";
import { persist } from "zustand/middleware";

export type DocType = "bank_statement" | "financial_statement" | "pos_data" | "invoice";

export type UploadedDoc = {
  localId: string;
  fileName: string;
  sizeBytes: number;
  storagePath: string;
  docType: DocType | "unknown";
  confidence: number | null;
  documentId: string | null;
  status: "uploading" | "classifying" | "ready" | "error";
  error?: string;
};

type WizardState = {
  /** Owner of this draft. If the current session has a different user_id we
   *  reset — otherwise the wizard's persisted loanId + docs leak across
   *  logouts/signups on the same browser (→ RLS 403s). */
  userId: string | null;
  loanId: string | null;
  amount: number;
  itemDescription: string;
  repaymentMonths: 6 | 12 | 18;
  docs: UploadedDoc[];
  step: 1 | 2 | 3;

  setAmount: (n: number) => void;
  setItemDescription: (s: string) => void;
  setRepaymentMonths: (n: 6 | 12 | 18) => void;
  setLoanId: (id: string | null) => void;
  setStep: (s: 1 | 2 | 3) => void;

  addDoc: (d: UploadedDoc) => void;
  updateDoc: (localId: string, patch: Partial<UploadedDoc>) => void;
  removeDoc: (localId: string) => void;
  reset: () => void;
  /** Scope the wizard to a user. If it was bound to a different user, wipe
   *  it first. Safe to call on every NewLoan mount. */
  bindToUser: (userId: string) => void;
};

const INITIAL: Pick<WizardState, "userId" | "loanId" | "amount" | "itemDescription" | "repaymentMonths" | "docs" | "step"> = {
  userId: null,
  loanId: null,
  amount: 50000,
  itemDescription: "",
  repaymentMonths: 12,
  docs: [],
  step: 1,
};

export const useWizard = create<WizardState>()(
  persist(
    (set) => ({
      ...INITIAL,
      setAmount: (n) => set({ amount: n }),
      setItemDescription: (s) => set({ itemDescription: s }),
      setRepaymentMonths: (n) => set({ repaymentMonths: n }),
      setLoanId: (id) => set({ loanId: id }),
      setStep: (step) => set({ step }),
      addDoc: (d) => set((s) => ({ docs: [...s.docs, d] })),
      updateDoc: (localId, patch) =>
        set((s) => ({
          docs: s.docs.map((d) => (d.localId === localId ? { ...d, ...patch } : d)),
        })),
      removeDoc: (localId) => set((s) => ({ docs: s.docs.filter((d) => d.localId !== localId) })),
      reset: () => set(INITIAL),
      bindToUser: (userId) =>
        set((s) => (s.userId === userId ? s : { ...INITIAL, userId })),
    }),
    { name: "leaseflow-wizard" },
  ),
);

export function completenessStatus(docs: UploadedDoc[]): {
  hasInvoice: boolean;
  hasFinancialProof: boolean;
  isComplete: boolean;
  missing: string[];
} {
  const ready = docs.filter((d) => d.status === "ready");
  const hasInvoice = ready.some((d) => d.docType === "invoice");
  const hasFinancialProof = ready.some(
    (d) => d.docType === "bank_statement" || d.docType === "financial_statement",
  );
  const missing: string[] = [];
  if (!hasInvoice) missing.push("Invoice (what you're buying)");
  if (!hasFinancialProof) missing.push("Bank or financial statement");
  return { hasInvoice, hasFinancialProof, isComplete: hasInvoice && hasFinancialProof, missing };
}
