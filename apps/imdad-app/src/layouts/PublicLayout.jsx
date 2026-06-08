import TopNav from "../components/TopNav";

export default function PublicLayout({ title, children }) {
  return (
    <div>
      <TopNav title={title} />
      <main className="page public">{children}</main>
    </div>
  );
}
