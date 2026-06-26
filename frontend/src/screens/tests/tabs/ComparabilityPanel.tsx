// L2b — cross-form comparability / equating-evidence report. Overlaid TIF (+target
// + divergence flags), conditional SE, and TCC/expected-score across a set of forms,
// with a pass/flag summary. Consulted at the psychometric-review gate alongside the
// per-form QA report. Comparability evidence only — NOT response-data equating.
// Recharts + generated Orval client (golden rule 5).
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCompareForms } from "../../../api/generated/endpoints/forms/forms";
import { Alert, Button, Card, Pill, Spinner } from "../../../components/ui";

const COLORS = ["#4f46e5", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2"];
const short = (id: string) => id.slice(0, 8);

export function ComparabilityPanel({ formIds }: { formIds: string[] }) {
  const compare = useCompareForms();
  const r = compare.data;

  if (formIds.length < 2)
    return (
      <Card title="Cross-form comparability" subtitle="Across-forms equating evidence.">
        <Alert tone="info" title="Need at least two forms">
          Assemble two or more forms (e.g. parallel forms) to compare them.
        </Alert>
      </Card>
    );

  const diverged = r ? r.dispersion.filter((d) => d.diverged) : [];

  return (
    <Card
      title="Cross-form comparability (equating evidence)"
      subtitle="Do these forms match by design on the canonical D=1 IRT scale? (Not response-data equating.)"
      actions={
        <Button
          onClick={() =>
            compare.mutate({ data: { form_ids: formIds, tolerance: 1.0, score_tolerance: 1.0 } })
          }
          disabled={compare.isPending}
        >
          {compare.isPending ? "Computing…" : r ? "Recompute" : "Run comparability report"}
        </Button>
      }
    >
      {compare.isPending && <Spinner label="Comparing forms…" />}
      {compare.isError && <Alert tone="error" title="Comparability request failed." />}
      {!r && !compare.isPending && (
        <p className="text-sm text-ink-500">
          Compares {formIds.length} forms’ TIF, conditional SE, and expected score (TCC).
        </p>
      )}

      {r && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone={r.passed ? "ok" : "warn"}>
              {r.passed ? "✓ comparable (within tolerance)" : "⚠ divergence flagged"}
            </Pill>
            <Pill tone="info">{r.n_forms} forms</Pill>
            <Pill>max TIF Δ {r.max_tif_deviation.toFixed(2)} @ θ={r.max_tif_deviation_theta}</Pill>
            <Pill>
              max score Δ {r.max_expected_score_diff.toFixed(2)} @ θ=
              {r.max_expected_score_diff_theta}
            </Pill>
          </div>

          {r.flags.length > 0 && (
            <Alert tone="warn" title="Forms diverge beyond tolerance">
              <ul className="list-disc pl-4">
                {r.flags.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </Alert>
          )}

          <Overlay
            title="Test Information (TIF) — overlay vs. common target"
            r={r}
            dataKey="tif"
            divergedDots={diverged.map((d) => ({ theta: d.theta, y: d.tif_max }))}
            target={r.target.map((t) => ({ theta: t.theta, target: t.target }))}
          />
          <div className="grid grid-cols-2 gap-4">
            <Overlay title="Conditional SE — SE(θ)=1/√I" r={r} dataKey="se" />
            <Overlay title="Expected score — TCC(θ)=Σ Pᵢ(θ)" r={r} dataKey="tcc" />
          </div>

          <table className="w-full text-sm tabular-nums">
            <thead className="text-ink-500">
              <tr>
                <th className="text-left">form</th>
                <th className="text-right">items</th>
                <th className="text-right">reliability</th>
                <th className="text-right">mean info</th>
                <th className="text-right">peak info</th>
                <th className="text-right">peak θ</th>
              </tr>
            </thead>
            <tbody>
              {r.forms.map((f, i) => (
                <tr key={f.form_id} className="border-t border-ink-100">
                  <td className="py-1">
                    <span
                      className="mr-2 inline-block h-2 w-2 rounded-full"
                      style={{ background: COLORS[i % COLORS.length] }}
                    />
                    {short(f.form_id)}
                  </td>
                  <td className="text-right">{f.n_items}</td>
                  <td className="text-right">{f.marginal_reliability.toFixed(3)}</td>
                  <td className="text-right">{f.mean_information.toFixed(2)}</td>
                  <td className="text-right">{f.peak_information.toFixed(2)}</td>
                  <td className="text-right">{f.peak_theta}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="text-xs text-ink-400">{r.scope_note}</p>
        </div>
      )}
    </Card>
  );
}

type ReportLike = {
  forms: { form_id: string; curve: { theta: number; tif: number; se: number | null; tcc: number }[] }[];
};

function Overlay({
  title,
  r,
  dataKey,
  divergedDots,
  target,
}: {
  title: string;
  r: ReportLike;
  dataKey: "tif" | "se" | "tcc";
  divergedDots?: { theta: number; y: number }[];
  target?: { theta: number; target: number }[];
}) {
  return (
    <div>
      <div className="mb-1 text-sm font-medium text-ink-700">{title}</div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="theta" type="number" domain={[-3, 3]} stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip />
            <Legend />
            {r.forms.map((f, i) => (
              <Line
                key={f.form_id}
                data={f.curve}
                dataKey={dataKey}
                name={short(f.form_id)}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
            {target && target.length > 0 && (
              <Scatter data={target} dataKey="target" name="target" fill="#0f172a" />
            )}
            {divergedDots?.map((d) => (
              <ReferenceDot
                key={d.theta}
                x={d.theta}
                y={d.y}
                r={5}
                fill="#dc2626"
                stroke="none"
                ifOverflow="extendDomain"
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
