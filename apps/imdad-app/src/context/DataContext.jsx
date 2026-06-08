import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { addMonths, safeJsonParse, uid } from "../utils/helpers";

const REQUESTS_KEY = "streamflow_requests";
const PROFILES_KEY = "streamflow_profiles";

const DataContext = createContext(null);

const defaultProfiles = {
  cust_1: {
    ownerName: "Faisal Al-Harbi",
    businessName: "Arabica Corner Cafe",
    phone: "+966501112233",
    email: "user@imdad.sa",
    businessType: "Cafe",
    city: "Riyadh",
    crNumber: "1010456789",
    iban: "SA0380000123456789012345",
    googleMapsLink: "https://maps.google.com/?q=Arabica+Corner+Cafe+Riyadh",
    samaInfo: "Demo profile - SAMA check placeholder",
    updatedAt: new Date().toISOString()
  }
};

const PLAN_OPTIONS = {
  1: { durationMonths: 1, processingFee: 250 },
  3: { durationMonths: 3, processingFee: 680 },
  6: { durationMonths: 6, processingFee: 1200 }
};

function buildDerivedInvoiceDetails(request) {
  const today = new Date();
  const due = new Date();
  due.setDate(today.getDate() + 30);
  const supplierCount = request.documents.supplierInvoice.length || 1;
  const estimatedAmount = 42000 + supplierCount * 500;
  const requestSuffix = request.id.split("_").pop()?.slice(-6) || "000001";

  return {
    supplierName: request.invoiceDetails.supplierName || "Supplier extracted by backend",
    invoiceNumber: request.invoiceDetails.invoiceNumber || `INV-${requestSuffix}`,
    invoiceAmount: request.invoiceDetails.invoiceAmount || String(estimatedAmount),
    invoiceDate: request.invoiceDetails.invoiceDate || today.toISOString().slice(0, 10),
    dueDate: request.invoiceDetails.dueDate || due.toISOString().slice(0, 10),
    supplierIban: request.invoiceDetails.supplierIban || request.businessProfile.iban || "",
    description: request.invoiceDetails.description || "Auto-extracted from uploaded supplier invoice."
  };
}

function createDraftRequest(userId, profile) {
  return {
    id: uid("req"),
    customerId: userId,
    status: "draft",
    createdAt: new Date().toISOString(),
    submittedAt: null,
    decisionAt: null,
    decisionBy: null,
    decisionReason: "",
    businessProfile: profile || {},
    documents: {
      bankStatements: [],
      financialStatements: [],
      supplierInvoice: []
    },
    invoiceDetails: {
      supplierName: "",
      invoiceNumber: "",
      invoiceAmount: "",
      invoiceDate: "",
      dueDate: "",
      supplierIban: "",
      description: ""
    },
    plan: {
      durationMonths: null,
      processingFee: null
    },
    evaluation: {
      bankStatements: { score: null, summary: "", feedback: "" },
      financialStatements: { score: null, summary: "", feedback: "" },
      samaInfo: { score: null, summary: "", feedback: "" },
      googleMapsReview: { score: null, summary: "", feedback: "" }
    },
    paymentPlan: null
  };
}

function buildPaymentPlan(request) {
  const principal = Number(request.invoiceDetails.invoiceAmount || 0);
  const fee = Number(request.plan.processingFee || 0);
  const total = principal + fee;
  const months = Number(request.plan.durationMonths || 0);
  const installmentAmount = months > 0 ? Number((total / months).toFixed(2)) : total;

  let remaining = total;
  const installments = Array.from({ length: months }).map((_, idx) => {
    const dueDate = addMonths(request.invoiceDetails.dueDate || new Date().toISOString().slice(0, 10), idx);
    remaining = Number((remaining - installmentAmount).toFixed(2));
    return {
      id: uid("inst"),
      number: idx + 1,
      amount: installmentAmount,
      dueDate,
      status: "unpaid",
      remainingBalance: Math.max(remaining, 0)
    };
  });

  return recalculatePaymentPlan({
    approvedAmount: principal,
    totalRepayment: total,
    amountPaid: 0,
    remainingBalance: total,
    nextDueDate: installments[0]?.dueDate || null,
    progressPercent: 0,
    installments
  });
}

function recalculatePaymentPlan(plan) {
  const paidCount = plan.installments.filter((installment) => installment.status === "paid").length;
  const amountPaid = Number(
    plan.installments
      .filter((installment) => installment.status === "paid")
      .reduce((sum, installment) => sum + Number(installment.amount || 0), 0)
      .toFixed(2)
  );
  const remainingBalance = Number(Math.max(plan.totalRepayment - amountPaid, 0).toFixed(2));
  const nextDueDate = plan.installments.find((installment) => installment.status !== "paid")?.dueDate || null;

  return {
    ...plan,
    amountPaid,
    remainingBalance,
    nextDueDate,
    progressPercent: plan.installments.length ? Math.round((paidCount / plan.installments.length) * 100) : 0
  };
}

export function DataProvider({ children }) {
  const [profiles, setProfiles] = useState(() => safeJsonParse(localStorage.getItem(PROFILES_KEY), defaultProfiles));
  const [requests, setRequests] = useState(() => safeJsonParse(localStorage.getItem(REQUESTS_KEY), []));

  useEffect(() => {
    if (!profiles.cust_1) {
      setProfiles((prev) => ({ ...defaultProfiles, ...prev }));
    }
  }, [profiles]);

  useEffect(() => {
    localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
  }, [profiles]);

  useEffect(() => {
    localStorage.setItem(REQUESTS_KEY, JSON.stringify(requests));
  }, [requests]);

  useEffect(() => {
    const latestCustomerRequest = [...requests]
      .filter((request) => request.customerId === "cust_1" && request.status !== "draft")
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))[0];

    if (!latestCustomerRequest || latestCustomerRequest.status === "approved") {
      return;
    }

    setRequests((prev) =>
      prev.map((request) =>
        request.id === latestCustomerRequest.id
          ? {
              ...request,
              status: "approved",
              decisionBy: "admin_1",
              decisionAt: new Date().toISOString(),
              decisionReason: "Approved for demo preview",
              paymentPlan: buildPaymentPlan(request)
            }
          : request
      )
    );
  }, [requests]);

  const byId = useMemo(() => Object.fromEntries(requests.map((r) => [r.id, r])), [requests]);

  function saveProfile(userId, profile) {
    if (!["Cafe", "Restaurant"].includes(profile.businessType)) {
      return { ok: false, message: "Only Cafe and Restaurant are eligible" };
    }
    setProfiles((prev) => ({ ...prev, [userId]: { ...profile, updatedAt: new Date().toISOString() } }));
    return { ok: true };
  }

  function getProfile(userId) {
    return profiles[userId] || null;
  }

  function getOrCreateDraft(userId) {
    const existing = requests.find((r) => r.customerId === userId && r.status === "draft");
    if (existing) return existing;
    return createDraftRequest(userId, getProfile(userId));
  }

  function updateDraft(userId, patch) {
    let requestId = null;
    setRequests((prev) => {
      const draft = prev.find((r) => r.customerId === userId && r.status === "draft");
      if (!draft) {
        const created = createDraftRequest(userId, profiles[userId] || {});
        requestId = created.id;
        return [
          ...prev,
          {
            ...created,
            ...patch,
            businessProfile: { ...created.businessProfile, ...(patch.businessProfile || {}) },
            documents: { ...created.documents, ...(patch.documents || {}) },
            invoiceDetails: { ...created.invoiceDetails, ...(patch.invoiceDetails || {}) },
            plan: { ...created.plan, ...(patch.plan || {}) }
          }
        ];
      }

      requestId = draft.id;
      return prev.map((r) =>
        r.id === draft.id
          ? {
              ...r,
              ...patch,
              businessProfile: { ...r.businessProfile, ...(patch.businessProfile || {}) },
              documents: { ...r.documents, ...(patch.documents || {}) },
              invoiceDetails: { ...r.invoiceDetails, ...(patch.invoiceDetails || {}) },
              plan: { ...r.plan, ...(patch.plan || {}) }
            }
          : r
      );
    });
    return requestId;
  }

  function selectPlan(userId, durationMonths) {
    const chosen = PLAN_OPTIONS[durationMonths];
    if (!chosen) return { ok: false, message: "Invalid plan" };
    updateDraft(userId, { plan: chosen });
    return { ok: true };
  }

  function submitDraft(userId) {
    const draft = getOrCreateDraft(userId);
    const requiredDocs = draft.documents.bankStatements.length && draft.documents.financialStatements.length && draft.documents.supplierInvoice.length;
    if (!requiredDocs) return { ok: false, message: "All required documents must be uploaded" };
    if (!draft.plan.durationMonths) return { ok: false, message: "Select a repayment plan" };
    const derivedInvoiceDetails = buildDerivedInvoiceDetails({
      ...draft,
      businessProfile: getProfile(userId) || draft.businessProfile
    });

    setRequests((prev) =>
      prev.map((r) =>
        r.id === draft.id
          ? {
              ...r,
              status: "under_review",
              submittedAt: new Date().toISOString(),
              businessProfile: getProfile(userId) || r.businessProfile,
              invoiceDetails: derivedInvoiceDetails
            }
          : r
      )
    );
    return { ok: true, requestId: draft.id };
  }

  function listUserRequests(userId) {
    return requests.filter((r) => r.customerId === userId).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  function listAdminRequests() {
    return requests
      .filter((r) => r.status !== "draft")
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  function getRequest(id) {
    return byId[id] || null;
  }

  function updateEvaluation(requestId, evaluation) {
    setRequests((prev) => prev.map((r) => (r.id === requestId ? { ...r, evaluation } : r)));
  }

  function approveRequest(requestId, adminId, reason) {
    const target = byId[requestId];
    if (!target) return { ok: false, message: "Request not found" };
    const paymentPlan = buildPaymentPlan(target);

    setRequests((prev) =>
      prev.map((r) =>
        r.id === requestId
          ? {
              ...r,
              status: "approved",
              decisionBy: adminId,
              decisionAt: new Date().toISOString(),
              decisionReason: reason || "Approved after admin review",
              paymentPlan
            }
          : r
      )
    );
    return { ok: true };
  }

  function rejectRequest(requestId, adminId, reason) {
    const target = byId[requestId];
    if (!target) return { ok: false, message: "Request not found" };
    if (target.status === "approved") return { ok: false, message: "Approved requests cannot be rejected" };

    setRequests((prev) =>
      prev.map((r) =>
        r.id === requestId
          ? {
              ...r,
              status: "rejected",
              decisionBy: adminId,
              decisionAt: new Date().toISOString(),
              decisionReason: reason || "Rejected after admin review"
            }
          : r
      )
    );
    return { ok: true };
  }

  function payInstallment(requestId, installmentId) {
    const target = byId[requestId];
    if (!target || !target.paymentPlan) return { ok: false, message: "Payment plan not found" };

    const alreadyPaid = target.paymentPlan.installments.find((installment) => installment.id === installmentId)?.status === "paid";
    if (alreadyPaid) return { ok: false, message: "Installment already paid" };

    setRequests((prev) =>
      prev.map((request) => {
        if (request.id !== requestId || !request.paymentPlan) {
          return request;
        }

        const installments = request.paymentPlan.installments.map((installment) =>
          installment.id === installmentId
            ? { ...installment, status: "paid" }
            : installment
        );
        const nextPlan = recalculatePaymentPlan({
          ...request.paymentPlan,
          installments
        });
        const nextStatus = nextPlan.remainingBalance === 0
          ? "paid"
          : request.status === "approved" || request.status === "repaying" || request.status === "paid"
            ? "repaying"
            : request.status;

        return {
          ...request,
          status: nextStatus,
          paymentPlan: nextPlan
        };
      })
    );

    return { ok: true };
  }

  return (
    <DataContext.Provider
      value={{
        saveProfile,
        getProfile,
        getOrCreateDraft,
        updateDraft,
        selectPlan,
        submitDraft,
        listUserRequests,
        listAdminRequests,
        getRequest,
        updateEvaluation,
        approveRequest,
        rejectRequest,
        payInstallment
      }}
    >
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error("useData must be used inside DataProvider");
  return ctx;
}
