import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { MerchantShell } from "../../components/MerchantShell";
import { RiyalSymbol } from "../../components/RiyalSymbol";
import { supabase } from "../../lib/supabase";
import { api, ApiError } from "../../lib/api";
import { env } from "../../lib/env";
import { useAuth } from "../../hooks/useAuth";
import { useMerchant } from "../../hooks/useMerchant";
import {
  useWizard,
  completenessStatus,
  type DocType,
  type UploadedDoc,
} from "../../stores/wizard";

const DOC_TYPE_LABELS: Record<DocType, string> = {
  bank_statement: "Bank statement",
  financial_statement: "Financial statement",
  pos_data: "POS data",
  invoice: "Invoice",
};

const DOC_TYPE_HELP: Record<DocType, string> = {
  bank_statement: "3+ months of your business bank account activity (PDF).",
  financial_statement: "P&L or balance sheet from your accountant.",
  pos_data: "Export from your POS — Foodics, Rasseed, Loyverse, etc. (CSV).",
  invoice: "The vendor invoice for the asset you're financing.",
};

const CR_PLACEHOLDER = "PENDING";

export function MerchantNewLoan() {
  const navigate = useNavigate();
  const { session, profile } = useAuth();
  const { merchant, loading: merchantLoading, reload: reloadMerchant } = useMerchant();
  const {
    loanId, amount, itemDescription, repaymentMonths, docs, step,
    setAmount, setItemDescription, setRepaymentMonths, setLoanId,
    setStep, addDoc, updateDoc, removeDoc, reset, bindToUser,
  } = useWizard();

  const [submitting, setSubmitting] = useState(false);
  const [creatingMerchant, setCreatingMerchant] = useState(false);
  // Survives React 19 StrictMode remount where `creatingMerchant` state may
  // not have committed before the second effect fires. Without this we'd
  // race-INSERT twice and trip the merchants.user_id UNIQUE constraint.
  const createMerchantFiredRef = useRef(false);

  // Scope the persisted wizard draft to the current user. If localStorage
  // contains another user's draft (same-browser signup), wipe it so we don't
  // try to push this user's docs into another merchant's loan.
  useEffect(() => {
    if (session?.user.id) bindToUser(session.user.id);
  }, [session?.user.id, bindToUser]);

  // First-time merchants: upsert a minimal business profile with defaults
  // so they can apply for a lease immediately. `onConflict: "user_id"` makes
  // this idempotent against StrictMode + remount double-fires. Polish in Profile.
  useEffect(() => {
    if (merchantLoading || merchant || creatingMerchant || !session) return;
    if (createMerchantFiredRef.current) return;
    createMerchantFiredRef.current = true;
    (async () => {
      setCreatingMerchant(true);
      const fallbackName =
        profile?.display_name?.trim() ||
        session.user.email?.split("@")[0]?.toUpperCase() ||
        "My Business";
      const { error } = await supabase.from("merchants").upsert(
        {
          user_id: session.user.id,
          business_name: fallbackName,
          cr_number: CR_PLACEHOLDER,
        },
        { onConflict: "user_id", ignoreDuplicates: true },
      );
      setCreatingMerchant(false);
      if (error) {
        createMerchantFiredRef.current = false; // allow retry
        toast.error(`Couldn't set up business profile: ${error.message}`);
        return;
      }
      reloadMerchant();
    })();
  }, [merchant, merchantLoading, creatingMerchant, session, profile, reloadMerchant]);

  if (merchantLoading || creatingMerchant) {
    return (
      <MerchantShell activeTab="apply">
        <div className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          Setting up&hellip;
        </div>
      </MerchantShell>
    );
  }

  if (!merchant) {
    return (
      <MerchantShell activeTab="apply">
        <div className="bg-white border-[3px] border-black offset-shadow p-8 max-w-xl">
          <h2 className="text-2xl font-black uppercase mb-4">Couldn&apos;t set up your profile</h2>
          <p className="text-on-surface-variant mb-6">
            We hit an error creating your default business profile. Try again or refresh the page.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="bg-primary-container border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift"
          >
            Try again
          </button>
        </div>
      </MerchantShell>
    );
  }

  const needsProfilePolish = merchant.cr_number === CR_PLACEHOLDER;

  const handleStartOver = () => {
    if (!window.confirm("Start a new application? Your current draft will be discarded.")) return;
    reset();
    if (session?.user.id) bindToUser(session.user.id);
  };

  const goToStep = async (next: 1 | 2 | 3) => {
    if (next === 2 && !loanId) {
      // Create the loans row on step 2 entry so we have an ID for the Storage path.
      const { data, error } = await supabase
        .from("loans")
        .insert({
          merchant_id: merchant.id,
          amount_requested: amount,
          item_description: itemDescription || "Unspecified asset",
          profit_rate: 0.15,
          repayment_months: repaymentMonths,
          repayment_frequency: "monthly",
        })
        .select()
        .single();
      if (error) {
        toast.error(`Couldn't create loan: ${error.message}`);
        return;
      }
      setLoanId((data as { id: string }).id);
    }
    setStep(next);
  };

  const handleSubmit = async () => {
    if (!loanId) {
      toast.error("Missing loan ID — restart the wizard");
      return;
    }
    setSubmitting(true);
    try {
      await api.startAnalysis(loanId);
      const finishedLoanId = loanId;
      reset();
      navigate(`/merchant/loans/${finishedLoanId}`, { replace: true });
    } catch (e) {
      const err = e instanceof ApiError ? e : null;
      if (err?.status === 422) {
        const detail = (err.body as { detail?: { missing_all_of?: string[] } } | null)?.detail;
        const missing = detail?.missing_all_of?.join(", ") ?? "required docs";
        toast.error(`Missing: ${missing}`);
      } else {
        toast.error(e instanceof Error ? e.message : "Could not start analysis");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <MerchantShell activeTab="apply">
      {needsProfilePolish && (
        <div className="mb-6 bg-primary-container border-[3px] border-black offset-shadow p-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="font-mono text-xs uppercase tracking-widest">
            Using <b>{merchant.business_name}</b> as your default business. Add your CR number &amp; phone anytime.
          </div>
          <Link
            to="/merchant/profile"
            className="bg-black text-white border-[3px] border-black px-4 py-2 font-mono text-[10px] font-black uppercase tracking-widest hover-lift shrink-0"
          >
            Edit profile →
          </Link>
        </div>
      )}
      <WizardHeader step={step} />
      <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
        <div className="md:col-span-4">
          <WizardSidebar step={step} merchantName={merchant.business_name} />
        </div>
        <div className="md:col-span-8">
          {step === 1 && (
            <Step1
              amount={amount} setAmount={setAmount}
              itemDescription={itemDescription} setItemDescription={setItemDescription}
              repaymentMonths={repaymentMonths} setRepaymentMonths={setRepaymentMonths}
              locked={!!loanId}
              onStartOver={handleStartOver}
              onContinue={() => goToStep(2)}
            />
          )}
          {step === 2 && loanId && (
            <Step2
              merchantId={merchant.id}
              loanId={loanId}
              docs={docs}
              addDoc={addDoc}
              updateDoc={updateDoc}
              removeDoc={removeDoc}
              onBack={() => setStep(1)}
              onContinue={() => setStep(3)}
            />
          )}
          {step === 3 && (
            <Step3
              amount={amount}
              itemDescription={itemDescription}
              repaymentMonths={repaymentMonths}
              docs={docs}
              submitting={submitting}
              onBack={() => setStep(2)}
              onSubmit={handleSubmit}
            />
          )}
        </div>
      </div>
    </MerchantShell>
  );
}

function WizardHeader({ step }: { step: 1 | 2 | 3 }) {
  return (
    <div className="mb-8">
      <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
        <span className="w-8 h-[3px] bg-black" />
        Step {step} of 3 · New lease application
      </div>
      <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">
        {step === 1 && "Configure asset"}
        {step === 2 && "Upload documents"}
        {step === 3 && "Review and submit"}
      </h1>
      <div className="mt-6 h-2 w-full bg-surface-container-high border-[3px] border-black">
        <div
          className="h-full bg-primary-container transition-[width] duration-200"
          style={{ width: `${(step / 3) * 100}%` }}
        />
      </div>
    </div>
  );
}

function WizardSidebar({ step, merchantName }: { step: 1 | 2 | 3; merchantName: string }) {
  const tips: Record<1 | 2 | 3, string[]> = {
    1: [
      "Pick an amount that matches the asset's invoice.",
      "Term affects the monthly payment — shorter = higher per month.",
    ],
    2: [
      "We need: one invoice + one bank statement (or financial statement).",
      "POS data is optional but improves your decision speed.",
      "Drop PDFs, CSVs, or images — up to 50 MB each.",
    ],
    3: [
      "Once you submit, our engine underwrites in about 90 seconds.",
      "You can close this page — we'll email you the outcome.",
    ],
  };

  return (
    <div className="space-y-6">
      <div className="bg-secondary text-white border-[3px] border-black p-6 offset-shadow relative overflow-hidden">
        <div className="font-mono text-[10px] uppercase tracking-widest opacity-80 mb-3">
          Merchant
        </div>
        <div className="font-display text-2xl font-black leading-tight mb-4">{merchantName}</div>
        <div className="pt-4 border-t-[2px] border-white/20 flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">
            Credit line
          </div>
          <div className="font-mono text-lg font-black flex items-baseline gap-1">
            <RiyalSymbol className="h-[0.7em] w-[0.63em] translate-y-[0.05em]" />
            <span>250,000</span>
          </div>
        </div>
      </div>

      <div className="bg-white border-[3px] border-black offset-shadow p-6">
        <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-3">
          Tips for step {step}
        </div>
        <ul className="space-y-2 text-sm text-on-surface-variant">
          {tips[step].map((t, i) => (
            <li key={i} className="flex gap-2">
              <span className="font-mono text-[10px] font-bold pt-1">▶</span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ─── STEP 1 ─────────────────────────────────────────────────────────────── */

function Step1({
  amount, setAmount, itemDescription, setItemDescription, repaymentMonths, setRepaymentMonths,
  locked, onStartOver, onContinue,
}: {
  amount: number;
  setAmount: (n: number) => void;
  itemDescription: string;
  setItemDescription: (s: string) => void;
  repaymentMonths: 6 | 12 | 18;
  setRepaymentMonths: (n: 6 | 12 | 18) => void;
  locked: boolean;
  onStartOver: () => void;
  onContinue: () => void;
}) {
  const monthlyPayment = useMemo(() => {
    // Backend computes final — this is just a display estimate using 15% profit rate.
    const total = amount * 1.15;
    return Math.round(total / repaymentMonths);
  }, [amount, repaymentMonths]);

  const amountValid = amount >= 5000 && amount <= 250000;
  const descValid = itemDescription.trim().length >= 3;
  const canContinue = amountValid && descValid;

  return (
    <div className="bg-white border-[3px] border-black offset-shadow-md p-8 space-y-10">
      {locked && (
        <div className="bg-surface-container-low border-[3px] border-black p-4 flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="font-mono text-[10px] font-black uppercase tracking-widest">
              Terms locked
            </div>
            <div className="text-sm text-on-surface-variant mt-1">
              This application has already been registered. To change amount, asset, or term, start over.
            </div>
          </div>
          <button
            type="button"
            onClick={onStartOver}
            className="bg-error text-white border-[3px] border-black px-4 py-2 font-mono text-[10px] font-black uppercase tracking-widest hover-lift shrink-0"
          >
            Start over
          </button>
        </div>
      )}

      <Field label="Request amount (SAR)">
        <div className={`flex items-center border-[3px] border-black h-24 px-6 transition-colors ${
          locked ? "bg-surface-container-low opacity-70" : "bg-white focus-within:bg-primary-container/10"
        }`}>
          <RiyalSymbol className="h-10 w-9 mr-4 text-on-surface-variant" />
          <input
            type="text"
            inputMode="numeric"
            disabled={locked}
            className="w-full bg-transparent border-none focus:ring-0 font-mono text-5xl md:text-6xl font-black outline-none disabled:cursor-not-allowed"
            value={amount.toLocaleString("en-US")}
            onChange={(e) => {
              const raw = e.target.value.replace(/[^0-9]/g, "");
              if (!raw) return setAmount(0);
              setAmount(Number(raw));
            }}
            aria-invalid={!amountValid}
          />
        </div>
        <div className="mt-2 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
          5,000 – 250,000 SAR
        </div>
      </Field>

      <Field label="Asset description">
        <div className={`border-[3px] border-black p-4 transition-colors ${
          locked ? "bg-surface-container-low opacity-70" : "bg-white focus-within:bg-primary-container/10"
        }`}>
          <input
            type="text"
            disabled={locked}
            className="w-full bg-transparent border-none focus:ring-0 text-xl font-bold outline-none disabled:cursor-not-allowed"
            placeholder="What are you financing?"
            value={itemDescription}
            onChange={(e) => setItemDescription(e.target.value)}
            aria-invalid={!descValid}
          />
        </div>
      </Field>

      <Field label="Pay back term">
        <div className="grid grid-cols-3 gap-0 border-[3px] border-black overflow-hidden">
          {([6, 12, 18] as const).map((m, i, arr) => (
            <button
              key={m}
              onClick={() => !locked && setRepaymentMonths(m)}
              type="button"
              disabled={locked}
              className={`py-4 font-mono font-black text-sm uppercase tracking-widest transition-colors disabled:cursor-not-allowed ${
                i < arr.length - 1 ? "border-r-[3px] border-black" : ""
              } ${
                repaymentMonths === m
                  ? "bg-primary-container text-black"
                  : locked
                    ? "bg-surface-container-low opacity-70"
                    : "bg-white hover:bg-surface-container-high"
              }`}
            >
              {m} months
            </button>
          ))}
        </div>
      </Field>

      <div>
        <div className="flex items-center mb-4">
          <h3 className="font-mono text-xs font-bold uppercase tracking-widest whitespace-nowrap mr-4">
            What you&apos;d pay
          </h3>
          <div className="h-[3px] w-full bg-black" />
        </div>
        <div className="bg-surface-container-low border-[3px] border-black p-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-4">
            <div className="bg-secondary p-3 border-[3px] border-black">
              <span className="material-symbols-outlined text-white">payments</span>
            </div>
            <div>
              <p className="text-2xl font-black flex items-baseline gap-2">
                About <RiyalSymbol className="h-[0.8em] w-[0.72em] translate-y-[0.05em]" />
                <span>{monthlyPayment.toLocaleString("en-US")}</span>
                <span className="text-base font-mono text-on-surface-variant">/ month</span>
              </p>
              <p className="font-mono text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                Estimate · fixed rate · {repaymentMonths} months
              </p>
            </div>
          </div>
          <button
            onClick={onContinue}
            disabled={!canContinue}
            className="w-full md:w-auto bg-primary-container text-black border-[3px] border-black px-8 py-4 font-mono font-black uppercase flex items-center justify-center gap-3 offset-shadow hover-lift disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Continue
            <span className="material-symbols-outlined">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── STEP 2 ─────────────────────────────────────────────────────────────── */

function Step2({
  merchantId, loanId, docs, addDoc, updateDoc, removeDoc, onBack, onContinue,
}: {
  merchantId: string;
  loanId: string;
  docs: UploadedDoc[];
  addDoc: (d: UploadedDoc) => void;
  updateDoc: (localId: string, patch: Partial<UploadedDoc>) => void;
  removeDoc: (localId: string) => void;
  onBack: () => void;
  onContinue: () => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const completeness = completenessStatus(docs);

  /*
   * Upload flow (RLS-aware):
   *   1. Upload once to {merchant_id}/{loan_id}/{doc_type_or_pending}/{uuid}.{ext}
   *   2. Call /documents/classify → returns doc_type + confidence
   *   3. If confidence ≥ 0.55, auto-INSERT documents row (locked)
   *   4. Else wait for user to pick doc_type, then INSERT
   *
   * We NEVER call storage.move() or documents.update() — RLS denies both for merchants.
   * Once the documents row is INSERTed the classification is final; to reclassify the
   * user must remove and re-upload.
   */
  const handleFiles = async (files: File[]) => {
    for (const file of files) {
      const localId = crypto.randomUUID();
      const ext = file.name.split(".").pop() || "bin";
      const uuid = crypto.randomUUID();
      const pendingPath = `${merchantId}/${loanId}/_pending/${uuid}.${ext}`;

      addDoc({
        localId,
        fileName: file.name,
        sizeBytes: file.size,
        storagePath: pendingPath,
        docType: "unknown",
        confidence: null,
        documentId: null,
        status: "uploading",
      });

      try {
        const { error: upErr } = await supabase.storage
          .from(env.STORAGE_BUCKET)
          .upload(pendingPath, file, { upsert: false });
        if (upErr) throw new Error(upErr.message);

        updateDoc(localId, { status: "classifying" });

        const cls = await api.classifyDocument(pendingPath);
        const suggested = cls.doc_type as DocType | "unknown";
        const confidence = cls.confidence ?? 0;

        if (suggested !== "unknown" && confidence >= 0.55) {
          const { data: inserted, error: insErr } = await supabase
            .from("documents")
            .insert({ loan_id: loanId, doc_type: suggested, storage_path: pendingPath })
            .select()
            .single();
          if (insErr) throw new Error(insErr.message);
          updateDoc(localId, {
            docType: suggested,
            confidence,
            documentId: (inserted as { id: string }).id,
            status: "ready",
          });
        } else {
          updateDoc(localId, {
            docType: "unknown",
            confidence,
            status: "ready",
          });
        }
      } catch (e) {
        updateDoc(localId, {
          status: "error",
          error: e instanceof Error ? e.message : "Upload failed",
        });
      }
    }
  };

  /* Only allowed BEFORE the documents row is INSERTed (documentId == null).
     After INSERT, RLS blocks merchants from UPDATE/DELETE — to reclassify the
     user must remove + re-upload. */
  const handleManualClassify = async (doc: UploadedDoc, nextType: DocType) => {
    if (doc.docType === nextType) return;
    if (doc.documentId) {
      toast.info("Classification is locked. Remove and re-upload to change it.");
      return;
    }
    const { data: inserted, error: insErr } = await supabase
      .from("documents")
      .insert({ loan_id: loanId, doc_type: nextType, storage_path: doc.storagePath })
      .select()
      .single();
    if (insErr) {
      toast.error(insErr.message);
      return;
    }
    updateDoc(doc.localId, {
      docType: nextType,
      documentId: (inserted as { id: string }).id,
    });
  };

  const handleRemove = (doc: UploadedDoc) => {
    if (doc.documentId) {
      toast.info("This document is locked on the backend — removing from your submission view only.");
    }
    removeDoc(doc.localId);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) void handleFiles(files);
  };

  return (
    <div className="space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`bg-white border-[3px] border-black p-12 text-center transition-colors ${
          dragging ? "bg-primary-container/20 offset-shadow-md" : "offset-shadow"
        }`}
      >
        <span className="material-symbols-outlined text-5xl">cloud_upload</span>
        <div className="mt-3 text-xl font-black uppercase">Drop your documents here</div>
        <div className="mt-2 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          PDF · CSV · XLS · PNG · JPG · up to 50 MB each
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-6 bg-primary-container border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift"
        >
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept=".pdf,.csv,.xls,.xlsx,.png,.jpg,.jpeg,.json"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) void handleFiles(files);
            e.target.value = "";
          }}
        />
      </div>

      <CompletenessWidget docs={docs} />

      {docs.length > 0 && (
        <div className="space-y-3">
          {docs.map((d) => (
            <DocRow
              key={d.localId}
              doc={d}
              onReclassify={(t) => handleManualClassify(d, t)}
              onRemove={() => handleRemove(d)}
            />
          ))}
        </div>
      )}

      <div className="flex justify-between pt-4">
        <button
          onClick={onBack}
          className="bg-white border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift"
        >
          ← Back
        </button>
        <button
          onClick={onContinue}
          disabled={!completeness.isComplete}
          className="bg-primary-container border-[3px] border-black px-8 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Review submission →
        </button>
      </div>
    </div>
  );
}

function CompletenessWidget({ docs }: { docs: UploadedDoc[] }) {
  const c = completenessStatus(docs);
  return (
    <div
      className={`border-[3px] border-black p-5 flex items-center justify-between ${
        c.isComplete ? "bg-success/10" : "bg-surface-container-low"
      }`}
    >
      <div>
        <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-1">
          {c.isComplete ? "Ready to submit" : "What's still needed"}
        </div>
        {c.isComplete ? (
          <div className="text-on-surface">All required documents uploaded. ✓</div>
        ) : (
          <ul className="text-sm text-on-surface-variant">
            {c.missing.map((m) => (
              <li key={m}>· {m}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex items-center gap-3">
        <Pill ok={c.hasInvoice} label="INVOICE" />
        <Pill ok={c.hasFinancialProof} label="FINANCIAL PROOF" />
      </div>
    </div>
  );
}

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`font-mono text-[10px] font-black uppercase tracking-widest px-3 py-1 border-[3px] border-black ${
        ok ? "bg-success text-white" : "bg-white text-on-surface-variant"
      }`}
    >
      {ok ? "✓ " : "· "}
      {label}
    </span>
  );
}

function DocRow({
  doc, onReclassify, onRemove,
}: {
  doc: UploadedDoc;
  onReclassify: (t: DocType) => void;
  onRemove: () => void;
}) {
  const statusColor =
    doc.status === "ready" ? "bg-success"
    : doc.status === "error" ? "bg-error"
    : "bg-primary-container";

  return (
    <div className="bg-white border-[3px] border-black offset-shadow p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <span className={`w-3 h-3 ${statusColor} ${doc.status !== "ready" && doc.status !== "error" ? "animate-pulse" : ""}`} />
          <div className="min-w-0">
            <div className="font-mono text-sm font-bold truncate">{doc.fileName}</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
              {(doc.sizeBytes / 1024).toFixed(0)} KB ·{" "}
              {doc.status === "uploading" ? "Uploading" :
               doc.status === "classifying" ? "Classifying" :
               doc.status === "error" ? `Error: ${doc.error ?? "unknown"}` :
               doc.docType === "unknown" ? "Needs classification" :
               `${DOC_TYPE_LABELS[doc.docType]} · ${Math.round((doc.confidence ?? 0) * 100)}% confident`}
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={onRemove}
          className="font-mono text-[10px] font-bold uppercase tracking-widest border-[3px] border-black px-3 py-1 hover:bg-error hover:text-white hover:border-error transition-colors shrink-0"
        >
          Remove
        </button>
      </div>

      {doc.docType === "unknown" && doc.status === "ready" && !doc.documentId && (
        <div className="mt-4 pt-4 border-t-[2px] border-dashed border-black/20">
          <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-2">
            What is this document?
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {(Object.keys(DOC_TYPE_LABELS) as DocType[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => onReclassify(t)}
                className="text-left font-mono text-xs font-black uppercase tracking-widest border-[3px] border-black px-3 py-2 bg-white hover:bg-primary-container transition-colors"
                title={DOC_TYPE_HELP[t]}
              >
                {DOC_TYPE_LABELS[t]}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── STEP 3 ─────────────────────────────────────────────────────────────── */

function Step3({
  amount, itemDescription, repaymentMonths, docs, submitting, onBack, onSubmit,
}: {
  amount: number;
  itemDescription: string;
  repaymentMonths: number;
  docs: UploadedDoc[];
  submitting: boolean;
  onBack: () => void;
  onSubmit: () => void;
}) {
  const readyDocs = docs.filter((d) => d.status === "ready" && d.docType !== "unknown");

  return (
    <div className="space-y-6">
      <SummaryPanel label="Amount requested">
        <div className="text-5xl font-black flex items-baseline gap-3">
          <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em]" />
          <span>{amount.toLocaleString("en-US")}</span>
        </div>
        <div className="mt-2 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
          Over {repaymentMonths} months · monthly auto-debit
        </div>
      </SummaryPanel>

      <SummaryPanel label="Asset">
        <div className="text-2xl font-bold">{itemDescription || "Unspecified"}</div>
      </SummaryPanel>

      <SummaryPanel label={`Documents (${readyDocs.length})`}>
        <div className="space-y-2">
          {readyDocs.map((d) => (
            <div key={d.localId} className="flex items-center justify-between font-mono text-xs uppercase tracking-widest">
              <span className="text-on-surface-variant">{DOC_TYPE_LABELS[d.docType as DocType]}</span>
              <span className="text-on-surface truncate max-w-[12rem]">{d.fileName}</span>
            </div>
          ))}
        </div>
      </SummaryPanel>

      <div className="bg-secondary text-white border-[3px] border-black offset-shadow-md p-6">
        <div className="font-mono text-[10px] uppercase tracking-widest opacity-80 mb-3">
          What happens next
        </div>
        <ul className="space-y-2">
          <li>▶ We extract key data from each document (&lt;20s).</li>
          <li>▶ 5 dimensions score your business (&lt;60s).</li>
          <li>▶ You see a decision — approved, denied, or manual review.</li>
        </ul>
        <div className="mt-4 font-mono text-[10px] uppercase tracking-widest opacity-60">
          You can close this page — we&apos;ll email you the outcome.
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button
          onClick={onBack}
          disabled={submitting}
          className="bg-white border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift disabled:opacity-40"
        >
          ← Back
        </button>
        <button
          onClick={onSubmit}
          disabled={submitting}
          className="bg-primary-container border-[3px] border-black px-10 py-4 font-mono font-black uppercase text-base offset-shadow hover-lift disabled:opacity-40 flex items-center gap-3"
        >
          {submitting ? "Starting analysis…" : "Start analysis →"}
        </button>
      </div>
    </div>
  );
}

function SummaryPanel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border-[3px] border-black offset-shadow p-6">
      <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-3">{label}</div>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="relative">
      <label className="absolute -top-3 left-4 bg-white px-2 font-mono text-[10px] font-bold z-10 uppercase">
        {label}
      </label>
      {children}
    </div>
  );
}
