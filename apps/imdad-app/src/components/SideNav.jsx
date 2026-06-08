import { NavLink } from "react-router-dom";

export default function SideNav({ admin = false }) {
  const items = admin
    ? [
        { to: "/admin/dashboard", label: "Overview" },
        { to: "/admin/requests", label: "All Requests" }
      ]
    : [
        { to: "/dashboard", label: "Overview" },
        { to: "/profile", label: "Business Profile" }
      ];

  return (
    <aside className="sidenav">
      <h2>{admin ? "Admin Workspace" : "Customer Workspace"}</h2>
      <nav>
        {items.map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? "active" : "") }>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
