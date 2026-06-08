import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";

const empty = {
  ownerName: "",
  businessName: "",
  phone: "",
  email: "",
  businessType: "Cafe",
  city: "",
  crNumber: "",
  iban: "",
  googleMapsLink: "",
  samaInfo: ""
};

export default function BusinessProfilePage() {
  const { currentUser } = useAuth();
  const { getProfile, saveProfile } = useData();
  const navigate = useNavigate();
  const [form, setForm] = useState(empty);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const existing = getProfile(currentUser.id);
    if (existing) setForm({ ...empty, ...existing });
  }, [currentUser.id]);

  function onSubmit(e) {
    e.preventDefault();
    const result = saveProfile(currentUser.id, form);
    if (!result.ok) {
      setMessage(result.message);
      return;
    }
    setMessage("Profile saved");
    navigate("/request/new");
  }

  return (
    <DashboardLayout title="Business Profile">
      <form className="form-grid" onSubmit={onSubmit}>
        <article>
          <h3>Business Identity</h3>
          <label>Owner Name</label>
          <input required value={form.ownerName} onChange={(e) => setForm((p) => ({ ...p, ownerName: e.target.value }))} />
          <label>Business Name</label>
          <input required value={form.businessName} onChange={(e) => setForm((p) => ({ ...p, businessName: e.target.value }))} />
          <label>Phone</label>
          <input required value={form.phone} onChange={(e) => setForm((p) => ({ ...p, phone: e.target.value }))} />
          <label>Email</label>
          <input type="email" required value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
        </article>
        <article>
          <h3>Compliance & Banking</h3>
          <label>Business Type (Cafe or Restaurant only)</label>
          <select value={form.businessType} onChange={(e) => setForm((p) => ({ ...p, businessType: e.target.value }))}>
            <option>Cafe</option>
            <option>Restaurant</option>
          </select>
          <label>City</label>
          <input required value={form.city} onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))} />
          <label>CR Number</label>
          <input required value={form.crNumber} onChange={(e) => setForm((p) => ({ ...p, crNumber: e.target.value }))} />
          <label>IBAN</label>
          <input required value={form.iban} onChange={(e) => setForm((p) => ({ ...p, iban: e.target.value }))} />
          <label>Google Maps Link (optional)</label>
          <input value={form.googleMapsLink} onChange={(e) => setForm((p) => ({ ...p, googleMapsLink: e.target.value }))} />
          <label>منصة سما info (optional)</label>
          <input value={form.samaInfo} onChange={(e) => setForm((p) => ({ ...p, samaInfo: e.target.value }))} />
        </article>
        <div className="action-row form-actions-wide">
          {message && <p className="muted">{message}</p>}
          <button className="btn primary" type="submit">Save Profile</button>
        </div>
      </form>
    </DashboardLayout>
  );
}
