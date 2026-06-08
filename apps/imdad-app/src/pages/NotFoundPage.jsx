import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main className="notfound">
      <h1>Page Not Found</h1>
      <p>The route does not exist in this app.</p>
      <Link to="/" className="btn primary">Go Home</Link>
    </main>
  );
}
