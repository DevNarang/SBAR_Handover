import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./Layout";
import Login from "./pages/Login";
import ResetPassword from "./pages/ResetPassword";
import Signup from "./pages/Signup";
import SignupAdmin from "./pages/SignupAdmin";
import SignupNurse from "./pages/SignupNurse";
import Awaiting from "./pages/Awaiting";
import Approvals from "./pages/Approvals";
import Dashboard from "./pages/Dashboard";
import WardBoard from "./pages/WardBoard";
import HandoverForm from "./pages/HandoverForm";
import Patients from "./pages/Patients";
import Escalations from "./pages/Escalations";
import Tasks from "./pages/Tasks";
import Protocols from "./pages/Protocols";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";
import Admin from "./pages/Admin";
import Roster from "./pages/Roster";
import Notifications from "./pages/Notifications";
import Account from "./pages/Account";
import { ToastHost } from "./notify";
import type { ReactNode } from "react";

function Guard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted" style={{ padding: 24 }}>Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/signup/admin" element={<SignupAdmin />} />
          <Route path="/signup/nurse" element={<SignupNurse />} />
          <Route path="/awaiting" element={<Awaiting />} />
          <Route
            path="/"
            element={
              <Guard>
                <Layout />
              </Guard>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="ward" element={<WardBoard />} />
            <Route path="handover/:id" element={<HandoverForm />} />
            <Route path="patients" element={<Patients />} />
            <Route path="escalations" element={<Escalations />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="protocols" element={<Protocols />} />
            <Route path="reports" element={<Reports />} />
            <Route path="audit" element={<Audit />} />
            <Route path="admin" element={<Admin />} />
            <Route path="approvals" element={<Approvals />} />
            <Route path="roster" element={<Roster />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="account" element={<Account />} />
          </Route>
        </Routes>
        <ToastHost />
      </BrowserRouter>
    </AuthProvider>
  );
}
