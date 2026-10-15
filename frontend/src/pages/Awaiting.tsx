import { Link, useLocation } from "react-router-dom";
import AuthBrand from "./AuthBrand";

type State = {
  code?: string;
  queue?: string;
  submitted_at?: string;
  reason?: string;
  message?: string;
};

export default function Awaiting() {
  const { state } = useLocation();
  const data = (state || {}) as State;
  const rejected = data.code === "rejected";
  const reviewer = data.queue === "department_admin" ? "your department Admin" : "the Super Admin";

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <AuthBrand />
        <h2>{rejected ? "Request rejected" : "Request submitted"}</h2>
        {!rejected ? (
          <p className="muted">Your request is with {reviewer}.</p>
        ) : (
          <p className="error">{data.reason || "Contact your administrator."}</p>
        )}
        <ol className="approval-steps">
          <li className={!rejected ? "done" : ""}>Submitted</li>
          <li className={!rejected ? "current" : ""}>Under review</li>
          <li>Access granted</li>
        </ol>
        {rejected && <p className="muted">Contact your administrator if you believe this is a mistake.</p>}
        {!rejected && <p className="muted">You will be notified in the app once a decision is made. Email alerts are not sent yet.</p>}
        <p className="muted" style={{ marginTop: 16 }}>
          <Link to="/login">Back to login</Link>
        </p>
      </div>
    </div>
  );
}
