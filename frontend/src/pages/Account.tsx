import { useState } from "react";
import { api } from "../api";
import PasswordField from "../PasswordField";
import { notify, notifyError } from "../notify";

export default function Account() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  return (
    <>
      <div className="topbar">
        <h2>Password</h2>
      </div>
      <form
        className="card"
        style={{ maxWidth: 480 }}
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
    </>
  );
}
