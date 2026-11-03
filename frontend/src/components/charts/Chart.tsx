import type { ChartType, GroupedResult, ReportResult, TabularResult } from "../../api/analytics";
import { formatCurrency, formatNumber } from "../../lib/records";
import { cx } from "../ui/cx";

// Categorical palette (validated for contrast on white; distinguishable for common colour-vision deficiencies).
export const PALETTE = [
  "#1f6feb",
  "#f59e0b",
  "#10b981",
  "#e11d48",
  "#8b5cf6",
  "#0ea5e9",
  "#f97316",
  "#64748b",
  "#84cc16",
  "#db2777",
];

type Datum = { label: string; value: number; series?: string };

function isMoney(result: GroupedResult, key: string): boolean {
  const field = result.aggregates.find((a) => a.key === key)?.field ?? "";
  return /amount|total|revenue|cost|balance|price|paid|fee/.test(field);
}

export function formatMetric(value: number | null | undefined, money: boolean): string {
  if (value === null || value === undefined) return "—";
  return money ? formatCurrency(value) : formatNumber(value);
}

function compact(value: number, money: boolean): string {
  const abs = Math.abs(value);
  const s =
    abs >= 1e6
      ? `${(value / 1e6).toFixed(1)}M`
      : abs >= 1e3
        ? `${(value / 1e3).toFixed(abs >= 1e4 ? 0 : 1)}k`
        : formatNumber(Math.round(value * 100) / 100);
  return money ? `$${s}` : s;
}

/** Rows of (label, value) from a summary result; matrix results are flattened by series. */
function toData(result: GroupedResult, aggKey: string): { data: Datum[]; series: string[] } {
  if (result.format === "matrix" && result.dimensions.length > 1) {
    const n = result.row_dimensions;
    const series = [...new Set(result.groups.map((g) => g.labels[n] ?? ""))];
    return {
      data: result.groups.map((g) => ({
        label: g.labels.slice(0, n).join(" / "),
        series: g.labels[n] ?? "",
        value: Number(g.values[aggKey] ?? 0),
      })),
      series,
    };
  }
  return {
    data: result.groups.map((g) => ({ label: g.labels.join(" / "), value: Number(g.values[aggKey] ?? 0) })),
    series: [],
  };
}

function BarChart({
  data,
  series,
  money,
  horizontal,
  title,
}: {
  data: Datum[];
  series: string[];
  money: boolean;
  horizontal: boolean;
  title: string;
}) {
  const labels = [...new Set(data.map((d) => d.label))];
  const keys = series.length ? series : [""];
  const value = (label: string, s: string) =>
    data.filter((d) => d.label === label && (d.series ?? "") === s).reduce((a, d) => a + d.value, 0);
  const totals = labels.map((l) => keys.reduce((a, s) => a + value(l, s), 0));
  const max = Math.max(1, ...totals);
  if (horizontal) {
    return (
      <div role="img" aria-label={title} className="space-y-1.5">
        {labels.map((l, i) => (
          <div key={l} className="grid grid-cols-[minmax(6rem,30%)_1fr_auto] items-center gap-2 text-xs">
            <span className="truncate text-slate-700" title={l}>
              {l}
            </span>
            <div className="flex h-5 overflow-hidden rounded bg-slate-100">
              {keys.map((s, j) => {
                const v = value(l, s);
                return v > 0 ? (
                  <div
                    key={s}
                    title={`${l}${s ? ` · ${s}` : ""}: ${formatMetric(v, money)}`}
                    style={{
                      width: `${(v / max) * 100}%`,
                      backgroundColor: PALETTE[(series.length ? j : 0) % PALETTE.length],
                    }}
                  />
                ) : null;
              })}
            </div>
            <span className="tabular-nums text-slate-900">{compact(totals[i]!, money)}</span>
          </div>
        ))}
      </div>
    );
  }
  const h = 180;
  const bw = Math.max(12, Math.min(48, 560 / Math.max(labels.length, 1) - 12));
  const width = Math.max(320, labels.length * (bw + 16) + 40);
  return (
    <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${h + 48}`} className="h-auto w-full">
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={36} x2={width} y1={h - t * h + 8} y2={h - t * h + 8} stroke="#e2e8f0" />
          <text x={32} y={h - t * h + 12} textAnchor="end" fontSize="10" fill="#64748b">
            {compact(max * t, money)}
          </text>
        </g>
      ))}
      {labels.map((l, i) => {
        let y = h + 8;
        const x = 44 + i * (bw + 16);
        return (
          <g key={l}>
            {keys.map((s, j) => {
              const v = value(l, s);
              const bh = (v / max) * h;
              y -= bh;
              return (
                <rect
                  key={s}
                  x={x}
                  y={y}
                  width={bw}
                  height={Math.max(bh, 0)}
                  rx={2}
                  fill={PALETTE[(series.length ? j : 0) % PALETTE.length]}
                >
                  <title>{`${l}${s ? ` · ${s}` : ""}: ${formatMetric(v, money)}`}</title>
                </rect>
              );
            })}
            <text x={x + bw / 2} y={h + 24} textAnchor="middle" fontSize="10" fill="#334155">
              {l.length > 12 ? `${l.slice(0, 11)}…` : l}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function LineChart({ data, money, title }: { data: Datum[]; money: boolean; title: string }) {
  const h = 160;
  const width = 560;
  const max = Math.max(1, ...data.map((d) => d.value));
  const step = data.length > 1 ? (width - 60) / (data.length - 1) : 0;
  const pts = data.map((d, i) => [44 + i * step, h - (d.value / max) * h + 8] as const);
  return (
    <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${h + 40}`} className="h-auto w-full">
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={40} x2={width} y1={h - t * h + 8} y2={h - t * h + 8} stroke="#e2e8f0" />
          <text x={36} y={h - t * h + 12} textAnchor="end" fontSize="10" fill="#64748b">
            {compact(max * t, money)}
          </text>
        </g>
      ))}
      <polyline
        fill="none"
        stroke={PALETTE[0]}
        strokeWidth={2}
        points={pts.map((p) => p.join(",")).join(" ")}
      />
      {pts.map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r={3.5} fill={PALETTE[0]}>
            <title>{`${data[i]!.label}: ${formatMetric(data[i]!.value, money)}`}</title>
          </circle>
          {(data.length <= 12 || i % Math.ceil(data.length / 12) === 0) && (
            <text x={x} y={h + 26} textAnchor="middle" fontSize="10" fill="#334155">
              {data[i]!.label.slice(0, 10)}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

function Donut({ data, money, title }: { data: Datum[]; money: boolean; title: string }) {
  const total = data.reduce((a, d) => a + d.value, 0) || 1;
  const r = 60;
  // Start angle of each slice (cumulative), computed up front so the map below is pure.
  const starts: number[] = [];
  let acc = -Math.PI / 2;
  for (const d of data) {
    starts.push(acc);
    acc += (d.value / total) * Math.PI * 2;
  }
  const arcs = data.map((d, i) => {
    const a = (d.value / total) * Math.PI * 2;
    const start = starts[i]!;
    const x1 = 80 + r * Math.cos(start);
    const y1 = 80 + r * Math.sin(start);
    const x2 = 80 + r * Math.cos(start + a);
    const y2 = 80 + r * Math.sin(start + a);
    const large = a > Math.PI ? 1 : 0;
    const path =
      data.length === 1
        ? `M 80 20 A 60 60 0 1 1 79.99 20`
        : `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
    return { d: path, color: PALETTE[i % PALETTE.length]!, datum: d };
  });
  return (
    <div className="flex flex-wrap items-center gap-4">
      <svg role="img" aria-label={title} viewBox="0 0 160 160" className="h-40 w-40 flex-none">
        {arcs.map((a) => (
          <path key={a.datum.label} d={a.d} fill="none" stroke={a.color} strokeWidth={22}>
            <title>{`${a.datum.label}: ${formatMetric(a.datum.value, money)}`}</title>
          </path>
        ))}
        <text x={80} y={78} textAnchor="middle" fontSize="18" fontWeight="600" fill="#0f172a">
          {compact(total, money)}
        </text>
        <text x={80} y={96} textAnchor="middle" fontSize="10" fill="#64748b">
          Total
        </text>
      </svg>
      <Legend data={data} money={money} />
    </div>
  );
}

function Legend({ data, money }: { data: Datum[]; money: boolean }) {
  return (
    <ul className="min-w-0 flex-1 space-y-1 text-xs">
      {data.map((d, i) => (
        <li key={d.label} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 flex-none rounded-sm"
            style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
          />
          <span className="truncate text-slate-700">{d.label}</span>
          <span className="ml-auto tabular-nums text-slate-900">{formatMetric(d.value, money)}</span>
        </li>
      ))}
    </ul>
  );
}

function Funnel({ data, money, title }: { data: Datum[]; money: boolean; title: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div role="img" aria-label={title} className="space-y-1">
      {data.map((d, i) => (
        <div key={d.label} className="flex items-center gap-2 text-xs">
          <span className="w-28 truncate text-right text-slate-700" title={d.label}>
            {d.label}
          </span>
          <div className="flex flex-1 justify-center">
            <div
              className="flex h-6 items-center justify-center rounded text-[11px] font-semibold text-white"
              title={`${d.label}: ${formatMetric(d.value, money)}`}
              style={{
                width: `${Math.max(8, (d.value / max) * 100)}%`,
                backgroundColor: PALETTE[i % PALETTE.length],
              }}
            >
              {compact(d.value, money)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ResultTable({ result, max = 1000 }: { result: ReportResult; max?: number }) {
  if (result.format === "tabular") {
    const r = result as TabularResult & ReportResult;
    return (
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
              {r.columns.map((c) => (
                <th key={c.key} scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {r.rows.slice(0, max).map((row) => (
              <tr key={row.id}>
                {row.cells.map((c, i) => {
                  const type = r.columns[i]?.type;
                  const text =
                    type === "currency"
                      ? formatCurrency(c.value)
                      : type === "number" || type === "percent"
                        ? formatNumber(c.value)
                        : c.label;
                  return (
                    <td
                      key={i}
                      className={cx(
                        "px-3 py-1.5",
                        ["currency", "number", "percent"].includes(type ?? "") && "text-right tabular-nums",
                      )}
                    >
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  const g = result as GroupedResult & ReportResult;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
            {g.dimensions.map((d) => (
              <th key={d.key} scope="col" className="px-3 py-2 font-semibold">
                {d.label}
              </th>
            ))}
            {g.aggregates.map((a) => (
              <th key={a.key} scope="col" className="px-3 py-2 text-right font-semibold">
                {a.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {g.groups.slice(0, max).map((row, i) => (
            <tr key={i}>
              {row.labels.map((l, j) => (
                <td key={j} className="px-3 py-1.5">
                  {l}
                </td>
              ))}
              {g.aggregates.map((a) => (
                <td key={a.key} className="px-3 py-1.5 text-right tabular-nums">
                  {formatMetric(row.values[a.key], isMoney(g, a.key))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-slate-300 font-semibold">
            <td className="px-3 py-1.5" colSpan={g.dimensions.length}>
              Grand total
            </td>
            {g.aggregates.map((a) => (
              <td key={a.key} className="px-3 py-1.5 text-right tabular-nums">
                {formatMetric(g.totals[a.key], isMoney(g, a.key))}
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/** Chart for a report result. Summary/matrix results chart their last aggregate (usually the value), else count. */
export function Chart({ result, type, title }: { result: ReportResult; type?: ChartType; title: string }) {
  const chart =
    type ?? (result.format !== "tabular" ? (result as GroupedResult).chart?.type : undefined) ?? "table";
  if (result.format === "tabular" || chart === "table") {
    if (chart === "kpi" && result.format === "tabular") {
      const t = result as TabularResult;
      const key = Object.keys(t.totals).find((k) => k !== "count") ?? "count";
      return (
        <Kpi
          value={t.totals[key] ?? 0}
          money={key !== "count"}
          label={key === "count" ? "Records" : "Total"}
        />
      );
    }
    return <ResultTable result={result} max={chart === "table" ? 10 : 1000} />;
  }
  const g = result as GroupedResult;
  if (g.groups.length === 0)
    return <p className="py-6 text-center text-sm text-slate-500">No data for this period.</p>;
  const agg = g.aggregates[g.aggregates.length - 1]!;
  const money = isMoney(g, agg.key);
  const { data, series } = toData(g, agg.key);
  switch (chart) {
    case "kpi":
      return <Kpi value={g.totals[agg.key] ?? 0} money={money} label={agg.label} />;
    case "donut":
      return <Donut data={data} money={money} title={title} />;
    case "funnel":
      return <Funnel data={data} money={money} title={title} />;
    case "line":
      return <LineChart data={data} money={money} title={title} />;
    case "bar":
      return <BarChart data={data} series={series} money={money} horizontal title={title} />;
    default:
      return (
        <div>
          <BarChart data={data} series={series} money={money} horizontal={false} title={title} />
          {series.length > 0 && (
            <Legend
              data={series.map((s) => ({
                label: s,
                value: data.filter((d) => d.series === s).reduce((a, d) => a + d.value, 0),
              }))}
              money={money}
            />
          )}
        </div>
      );
  }
}

function Kpi({ value, money, label }: { value: number | null; money: boolean; label: string }) {
  return (
    <div className="py-4 text-center">
      <p className="text-3xl font-bold tabular-nums text-slate-900">{formatMetric(value, money)}</p>
      <p className="mt-1 text-xs text-slate-500">{label}</p>
    </div>
  );
}
