import { useEffect, useState } from "react";
import { api, ROLE_LABEL } from "../api";
import { useAuth } from "../auth";
import PasswordField from "../PasswordField";
import { notify, notifyError } from "../notify";

export default function Account() {
  const { user, reloadUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [mobile, setMobile] = useState(user?.mobile || "");
  const [designation, setDesignation] = useState(user?.designation || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  useEffect(() => {
    setFullName(user?.full_name || "");
    setMobile(user?.mobile || "");
    setDesignation(user?.designation || "");
  }, [user]);

  if (!user) return null;

  return (
    <>
      <div className="topbar">
        <div>
          <h2>Profile</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {ROLE_LABEL[user.role] || user.role} · {user.employee_id}
          </p>
        </div>
      </div>
      <div className="grid cards">
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api.patch("/auth/profile", {
                full_name: fullName,
                mobile,
                designation,
              });
              await reloadUser();
              notify("Profile updated", "Your details were saved.");
            } catch (err) {
              notifyError("Could not update profile", err instanceof Error ? err.message : "Try again.");
            }
          }}
        >
          <h3>Your details</h3>
          <div className="field">
            <label>Full name</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Email</label>
            <input value={user.email} disabled />
          </div>
          <div className="field">
            <label>Employee ID</label>
            <input value={user.employee_id} disabled />
          </div>
          <div className="field">
            <label>Role</label>
            <input value={ROLE_LABEL[user.role] || user.role} disabled />
          </div>
          <div className="field">
            <label>Department</label>
            <input value={user.department || "—"} disabled />
          </div>
          <div className="field">
            <label>Wards</label>
            <input
              value={
                user.ward_names?.length
                  ? user.ward_names.join(", ")
                  : ["nursing_superintendent", "medical_superintendent", "nursing_supervisor"].includes(user.role)
                    ? "All wards"
                    : "None assigned"
              }
              disabled
            />
          </div>
          <div className="field">
            <label>Designation</label>
            <input value={designation} onChange={(e) => setDesignation(e.target.value)} />
          </div>
          <div className="field">
            <label>Mobile</label>
            <input value={mobile} onChange={(e) => setMobile(e.target.value)} />
          </div>
          <button className="btn primary">Save profile</button>
        </form>
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            if (newPassword !== confirm) {
              notifyError("Passwords do not match", "Type the new password the same way in both boxes.");
              return;
            }
            try {
              await api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
              setCurrentPassword("");
              setNewPassword("");
              setConfirm("");
              notify("Password updated", "Use the new password the next time you sign in.");
            } catch (err) {
              notifyError("Could not update password", err instanceof Error ? err.message : "Try again.");
            }
          }}
        >
          <h3>Password</h3>
          <div className="field">
            <label>Current password</label>
            <PasswordField value={currentPassword} onChange={setCurrentPassword} required autoComplete="current-password" />
          </div>
          <div className="field">
            <label>New password</label>
            <PasswordField value={newPassword} onChange={setNewPassword} required minLength={8} autoComplete="new-password" />
          </div>
          <div className="field">
            <label>Confirm new password</label>
            <PasswordField value={confirm} onChange={setConfirm} required minLength={8} autoComplete="new-password" />
          </div>
          <button className="btn primary">Save password</button>
        </form>
      </div>
    </>
  );
}
