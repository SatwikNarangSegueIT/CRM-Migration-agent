import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { dataApi, type DryRun, type ImportAnalysis, type ImportJob } from "../api/data";
import { controlClass } from "../components/record/FieldInput";
import { UploadIcon } from "../components/icons";
import { Alert, Badge, Button, Card, PageHeader, Spinner } from "../components/ui";
import { cx } from "../components/ui/cx";
import { formatDateTimeValue, useObjects } from "../lib/records";
import { API_BASE } from "../api/client";

type Step = 1 | 2 | 3 | 4;

/** CSV import wizard: choose object -> upload -> map columns & duplicate rule -> dry run -> import. */
export function ImportPage() {
  const [params] = useSearchParams();
  const objects = useObjects();
  const [step, setStep] = useState<Step>(1);
  const [object, setObject] = useState(params.get("object") ?? "");
  const [fileName, setFileName] = useState("");
  const [csv, setCsv] = useState("");
  const [analysis, setAnalysis] = useState<ImportAnalysis | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [matchField, setMatchField] = useState("");
  const [duplicateAction, setDuplicateAction] = useState<"skip" | "update" | "create">("skip");
  const [dry, setDry] = useState<DryRun | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const jobs = useQuery({ queryKey: ["imports"], queryFn: ({ signal }) => dataApi.jobs(signal) });

  const analyze = useMutation({
    mutationFn: () => dataApi.analyze(object, csv),
    onSuccess: (a) => {
      setAnalysis(a);
      setMapping(a.suggested_mapping);
      setMatchField(
        a.match_fields.find((f) => Object.values(a.suggested_mapping).includes(f) && f !== "name") ?? "",
      );
      setStep(3);
    },
  });
  const input = () => ({
    object_api_name: object,
    file_name: fileName,
    csv,
    mapping: Object.fromEntries(Object.entries(mapping).filter(([, v]) => v)),
    match_field: matchField || null,
    duplicate_action: duplicateAction,
  });
  const dryRun = useMutation({
    mutationFn: () => dataApi.dryRun(input()),
    onSuccess: (d) => {
      setDry(d);
      setStep(4);
    },
  });
  const start = useMutation({
    mutationFn: () => dataApi.start(input()),
    onSuccess: (j) => {
      setJob(j);
      void jobs.refetch();
    },
  });
  const creatable = (objects.data ?? []).filter((o) => o.access.create && !o.is_detail_only);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Import Data"
        subtitle="Bring in records from a CSV file. Validation, field security and duplicate rules apply exactly as for manual entry."
        icon={<UploadIcon size={22} className="text-brand-700" />}
      />
      <ol className="flex flex-wrap gap-2 text-sm" aria-label="Steps">
        {["Object", "Upload", "Map fields", "Review & import"].map((label, i) => (
          <li
            key={label}
            aria-current={step === i + 1 ? "step" : undefined}
            className={cx(
              "rounded-full px-3 py-1",
              step === i + 1
                ? "bg-brand-700 text-white"
                : step > i + 1
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-slate-200 text-slate-600",
            )}
          >
            {i + 1}. {label}
          </li>
        ))}
      </ol>
      <Card>
        {step === 1 && (
          <div className="max-w-md space-y-3">
            <label htmlFor="import-object" className="block text-sm font-medium text-slate-700">
              What are you importing?
            </label>
            <select
              id="import-object"
              className={controlClass(false)}
              value={object}
              onChange={(e) => setObject(e.target.value)}
            >
              <option value="">Choose an object…</option>
              {creatable.map((o) => (
                <option key={o.api_name} value={o.api_name}>
                  {o.plural_label}
                </option>
              ))}
            </select>
            <Button disabled={!object} onClick={() => setStep(2)}>
              Next
            </Button>
          </div>
        )}
        {step === 2 && (
          <div className="max-w-lg space-y-3">
            <label htmlFor="import-file" className="block text-sm font-medium text-slate-700">
              CSV file (UTF-8, first row = column headings, up to 10 MB)
            </label>
            <input
              id="import-file"
              type="file"
              accept=".csv,text/csv"
              className="block text-sm"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                setFileName(f.name);
                setCsv(await f.text());
              }}
            />
            {analyze.isError && <Alert tone="error">{errorMessage(analyze.error)}</Alert>}
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button disabled={!csv} loading={analyze.isPending} onClick={() => analyze.mutate()}>
                Next
              </Button>
            </div>
          </div>
        )}
        {step === 3 && analysis && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              {analysis.row_count} rows in {fileName}. Columns were matched to fields by name; adjust as
              needed.
            </p>
            <table className="min-w-full max-w-3xl text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-600">
                  <th scope="col" className="py-2 pr-4">
                    CSV column
                  </th>
                  <th scope="col" className="py-2 pr-4">
                    Sample
                  </th>
                  <th scope="col" className="py-2">
                    Field
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {analysis.headers.map((h) => (
                  <tr key={h}>
                    <td className="py-2 pr-4 font-medium">{h}</td>
                    <td className="max-w-[16rem] truncate py-2 pr-4 text-slate-500">
                      {analysis.sample[0]?.[h]}
                    </td>
                    <td className="py-2">
                      <select
                        aria-label={`Field for ${h}`}
                        className={controlClass(false, "w-64")}
                        value={mapping[h] ?? ""}
                        onChange={(e) => setMapping({ ...mapping, [h]: e.target.value })}
                      >
                        <option value="">Don't import</option>
                        {analysis.fields.map((f) => (
                          <option key={f.api_name} value={f.api_name}>
                            {f.label}
                            {f.required ? " *" : ""}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="grid max-w-2xl gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="match-field" className="block text-sm font-medium text-slate-700">
                  Find duplicates by
                </label>
                <select
                  id="match-field"
                  className={controlClass(false, "mt-1")}
                  value={matchField}
                  onChange={(e) => setMatchField(e.target.value)}
                >
                  <option value="">Don't check (always create)</option>
                  {analysis.match_fields
                    .filter((f) => Object.values(mapping).includes(f))
                    .map((f) => (
                      <option key={f} value={f}>
                        {analysis.fields.find((x) => x.api_name === f)?.label ?? f}
                      </option>
                    ))}
                </select>
              </div>
              {matchField && (
                <div>
                  <label htmlFor="dup-action" className="block text-sm font-medium text-slate-700">
                    When a match is found
                  </label>
                  <select
                    id="dup-action"
                    className={controlClass(false, "mt-1")}
                    value={duplicateAction}
                    onChange={(e) => setDuplicateAction(e.target.value as typeof duplicateAction)}
                  >
                    <option value="skip">Skip the row</option>
                    <option value="update">Update the existing record</option>
                    <option value="create">Create anyway</option>
                  </select>
                </div>
              )}
            </div>
            {dryRun.isError && <Alert tone="error">{errorMessage(dryRun.error)}</Alert>}
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button loading={dryRun.isPending} onClick={() => dryRun.mutate()}>
                Preview (dry run)
              </Button>
            </div>
          </div>
        )}
        {step === 4 && dry && (
          <div className="space-y-4">
            {!job ? (
              <>
                <div className="flex flex-wrap gap-2 text-sm">
                  <Badge tone="green">{dry.created} to create</Badge>
                  <Badge tone="blue">{dry.updated} to update</Badge>
                  <Badge tone="gray">{dry.skipped} skipped</Badge>
                  <Badge tone={dry.errors ? "red" : "gray"}>{dry.errors} with errors</Badge>
                </div>
                {dry.error_rows.length > 0 && (
                  <div className="max-h-48 overflow-y-auto rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                    {dry.error_rows.slice(0, 50).map((e) => (
                      <p key={e.row}>
                        Row {e.row}: {e.message}
                      </p>
                    ))}
                  </div>
                )}
                <p className="text-sm text-slate-600">
                  Nothing has been saved yet. Rows with errors are skipped when you import.
                </p>
                {start.isError && <Alert tone="error">{errorMessage(start.error)}</Alert>}
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => setStep(3)}>
                    Back
                  </Button>
                  <Button
                    loading={start.isPending}
                    onClick={() => start.mutate()}
                    disabled={dry.created + dry.updated === 0}
                  >
                    Import {dry.created + dry.updated} record(s)
                  </Button>
                </div>
              </>
            ) : (
              <Alert
                tone={job.status === "failed" ? "error" : "success"}
                title={
                  job.status === "completed"
                    ? "Import complete"
                    : job.status === "failed"
                      ? "Import failed"
                      : "Import started"
                }
              >
                {job.status === "completed"
                  ? `${job.created} created, ${job.updated} updated, ${job.skipped} skipped, ${job.errors} errors.`
                  : job.status === "pending" || job.status === "running"
                    ? "Large files run in the background; check the history below."
                    : null}
                <div className="mt-2 flex gap-3">
                  <Link to={`/o/${object}`} className="text-brand-700 hover:underline">
                    Go to {object}
                  </Link>
                  {job.errors > 0 && (
                    <a
                      href={`${API_BASE}/imports/${job.id}/errors.csv`}
                      className="text-brand-700 hover:underline"
                    >
                      Download error file
                    </a>
                  )}
                </div>
              </Alert>
            )}
          </div>
        )}
      </Card>
      <Card>
        <h2 className="mb-2 font-semibold text-slate-900">Import history</h2>
        {jobs.isPending ? (
          <Spinner label="Loading" />
        ) : (jobs.data ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">No imports yet.</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-600">
                <th className="py-1.5">File</th>
                <th>Object</th>
                <th>Status</th>
                <th>Created</th>
                <th>Updated</th>
                <th>Errors</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {jobs.data!.map((j) => (
                <tr key={j.id}>
                  <td className="py-1.5">{j.file_name}</td>
                  <td>{j.object_api_name}</td>
                  <td>
                    <Badge
                      tone={j.status === "completed" ? "green" : j.status === "failed" ? "red" : "amber"}
                    >
                      {j.status}
                    </Badge>
                  </td>
                  <td>{j.created}</td>
                  <td>{j.updated}</td>
                  <td>
                    {j.errors ? (
                      <a
                        href={`${API_BASE}/imports/${j.id}/errors.csv`}
                        className="text-brand-700 hover:underline"
                      >
                        {j.errors}
                      </a>
                    ) : (
                      0
                    )}
                  </td>
                  <td>{formatDateTimeValue(j.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
