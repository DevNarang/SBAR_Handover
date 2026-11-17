import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { api, ROLE_LABEL } from "./api";

type NavItem = { to: string; label: string; roles: string[] | null };

const TOP_LINKS: NavItem[] = [
  { to: "/", label: "Dashboard", roles: null },
];

const WORK_LINKS: NavItem[] = [
  { to: "/notifications", label: "Notifications", roles: null },
  { to: "/ward", label: "Ward board", roles: null },
  { to: "/roster", label: "Shift roster", roles: ["hod", "nursing_superintendent", "medical_superintendent", "nursing_supervisor"] },
  { to: "/patients", label: "Patients", roles: null },
  { to: "/escalations", label: "Escalations", roles: null },
  { to: "/tasks", label: "Tasks", roles: null },
  { to: "/protocols", label: "Protocols", roles: null },
  { to: "/reports", label: "Reports", roles: ["hod", "nursing_superintendent", "medical_superintendent", "nursing_supervisor"] },
];

const TAIL_LINKS: NavItem[] = [
  { to: "/approvals", label: "Approvals", roles: ["hod", "nursing_superintendent"] },
  { to: "/audit", label: "Audit", roles: ["hod", "nursing_superintendent", "medical_superintendent", "nursing_supervisor"] },
  { to: "/admin", label: "Wards", roles: ["hod"] },
  { to: "/account", label: "Profile", roles: null },
  { to: "/admin", label: "Admin", roles: ["nursing_superintendent", "medical_superintendent", "nursing_supervisor"] },
];

function visibleLinks(items: NavItem[], role: string) {
  return items.filter((l) => !l.roles || l.roles.includes(role));
}

function NavItems({ items, badges }: { items: NavItem[]; badges: Record<string, number> }) {
  return (
    <>
      {items.map((l) => {
        const count = badges[l.to] || 0;
        return (
          <NavLink key={l.to + l.label} to={l.to} end={l.to === "/"} className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
            <span>{l.label}</span>
            {count > 0 && <span className="nav-count">{count > 99 ? "99+" : count}</span>}
          </NavLink>
        );
      })}
    </>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const stored = localStorage.getItem("sbar_theme");
  const [theme, setTheme] = useState(stored === "dark" ? "dark" : "light");
  const workActive = WORK_LINKS.some((l) => location.pathname === l.to || location.pathname.startsWith(l.to + "/"));
  const [workOpen, setWorkOpen] = useState(workActive);
  const [badges, setBadges] = useState<Record<string, number>>({});

  useEffect(() => {
    if (workActive) setWorkOpen(true);
  }, [workActive]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sbar_theme", theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    async function loadBadges() {
      try {
        const notes = await api.get<{ count: number }>("/notifications/unread-count");
        let approvals = 0;
        if (user?.role === "nursing_superintendent" || user?.role === "hod") {
          const pending = await api.get<{ count: number }>("/approvals/pending-count");
          approvals = pending.count;
        }
        if (!cancelled) {
          setBadges({ "/notifications": notes.count, "/approvals": approvals });
        }
      } catch {
        /* keep last counts */
      }
    }
    void loadBadges();
    const onRefresh = () => void loadBadges();
    window.addEventListener("sbar:badges", onRefresh);
    const timer = window.setInterval(onRefresh, 30000);
    return () => {
      cancelled = true;
      window.removeEventListener("sbar:badges", onRefresh);
      window.clearInterval(timer);
    };
  }, [user?.role, location.pathname]);

  if (!user) return null;
  const top = visibleLinks(TOP_LINKS, user.role);
  const work = visibleLinks(WORK_LINKS, user.role);
  const tail = visibleLinks(TAIL_LINKS, user.role);
  const dark = theme === "dark";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-head">
          <div className="brand">
            <div className="brand-mark">
              <img src="/aiims-bibinagar.png" alt="AIIMS Bibinagar emblem" />
            </div>
            <div>
              <h1>SBAR Handover</h1>
              <p>All India Institute of Medical Sciences (AIIMS) - Bibinagar, Hyderabad</p>
            </div>
          </div>
          <NavLink to="/account" className="user-card">
            <strong>{user.full_name}</strong>
            {ROLE_LABEL[user.role]}
            {user.department ? ` - ${user.department}` : ""}
          </NavLink>
          <button type="button" className="btn sidebar-signout" onClick={logout}>
            Sign out
          </button>
          <label className="theme-toggle">
            <button
              type="button"
              className="switch"
              role="switch"
              aria-checked={dark}
              aria-label="Dark mode"
              onClick={() => setTheme(dark ? "light" : "dark")}
            >
              <span className="knob">
                {dark ? (
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path
                      fill="currentColor"
                      d="M12.4 2.1a7.6 7.6 0 1 0 5.5 13.4 6.4 6.4 0 0 1-8.9-8.9A7.55 7.55 0 0 0 12.4 2.1z"
                    />
                  </svg>
                ) : (
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <circle cx="10" cy="10" r="3.2" fill="currentColor" />
                    <path
                      fill="currentColor"
                      d="M9.2 1.6h1.6v2.6H9.2zm0 14.2h1.6v2.6H9.2zM1.6 9.2h2.6v1.6H1.6zm14.2 0h2.6v1.6h-2.6zM4.1 3.5l1.1-1.1 1.8 1.8-1.1 1.1zm8.9 8.9 1.8 1.8-1.1 1.1-1.8-1.8zm1.8-8.9 1.1 1.1-1.8 1.8-1.1-1.1zM5.9 13.5l1.1 1.1-1.8 1.8-1.1-1.1z"
                    />
                  </svg>
                )}
              </span>
            </button>
          </label>
        </div>
        <nav className="sidebar-nav" aria-label="Main">
          <NavItems items={top} badges={badges} />
          {work.length > 0 && (
            <div className="nav-group">
              <button
                type="button"
                className={"nav-link nav-disclosure" + (workActive ? " active" : "")}
                aria-expanded={workOpen}
                aria-controls="sidebar-work-menu"
                onClick={() => setWorkOpen((open) => !open)}
              >
                <span>Wards & work</span>
                <span className="nav-disclosure-end">
                  {(badges["/notifications"] || 0) > 0 && !workOpen && (
                    <span className="nav-count">{badges["/notifications"] > 99 ? "99+" : badges["/notifications"]}</span>
                  )}
                  <span className={"nav-chevron" + (workOpen ? " open" : "")} aria-hidden="true" />
                </span>
              </button>
              <div id="sidebar-work-menu" className="nav-sub" hidden={!workOpen}>
                <NavItems items={work} badges={badges} />
              </div>
            </div>
          )}
          <NavItems items={tail} badges={badges} />
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
