import TopNav from "../components/TopNav";

export default function DashboardLayout({ title, children }) {
  return (
    <div>
      <TopNav title={title} />
      <main className="page dashboard">{children}</main>
    </div>
  );
}