import { useAuth } from "../../auth/context";
import { Card } from "../../components/ui";

export function PortalHomePage() {
  const { me } = useAuth();
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Hello, {me?.user.name}</h1>
      <Card title="Your client portal is coming soon">
        <p className="text-sm text-slate-600">
          Soon you will be able to follow your visa application, upload documents, sign your service agreement
          and message your migration agent here.
        </p>
      </Card>
    </div>
  );
}
