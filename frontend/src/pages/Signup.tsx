import { Link, useNavigate } from "react-router-dom";
import AuthBrand from "./AuthBrand";

export default function Signup() {
  const navigate = useNavigate();
  return (
    <div className="login-wrap">
      <div className="card login-card">
        <AuthBrand />
        <h2>Create your account</h2>
        <p className="muted">I am a...</p>
        <div className="role-choice">
          <button type="button" className="role-card" onClick={() => navigate("/signup/admin")}>
            <strong>Department Admin</strong>
            <span>Manages a department and approves its nurses</span>
          </button>
          <button type="button" className="role-card" onClick={() => navigate("/signup/nurse")}>
            <strong>Nurse</strong>
            <span>Joins a department to use handovers</span>
          </button>
        </div>
        <p className="muted" style={{ marginTop: 16 }}>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
