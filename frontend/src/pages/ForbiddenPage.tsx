import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-semibold">Access denied</h1>
      <p className="mt-2 text-sm text-slate-600">Your role does not have permission to view this page.</p>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-brand-700 hover:underline">
        Go to Home
      </Link>
    </div>
  );
}
