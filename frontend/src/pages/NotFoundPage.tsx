import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-slate-600">The page you are looking for does not exist.</p>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-brand-700 hover:underline">
        Go to Home
      </Link>
    </div>
  );
}
