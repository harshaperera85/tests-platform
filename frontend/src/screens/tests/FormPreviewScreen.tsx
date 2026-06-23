// A-033 Form preview — assembled items + a smooth actual-vs-target TIF plot, item
// metadata from the simulated bank, and content-constraint satisfaction. All data
// via the generated client (golden rule 5); TIF curve is server-computed on the
// canonical metric (golden rule 4).
import {
  CartesianGrid,
  ComposedChart,
  ErrorBar,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useGetBlueprint } from "../../api/generated/endpoints/blueprints/blueprints";
import {
  useGetForm,
  useGetFormTifCurve,
} from "../../api/generated/endpoints/forms/forms";
import { useGetPoolItems } from "../../api/generated/endpoints/pool/pool";
import type { PoolItem } from "../../api/generated/model";
import { Alert, Button, Card, Pill, Spinner } from "../../components/ui";

export function FormPreviewScreen({
  formId,
  blueprintId,
  poolId,
  onWalk,
  onBack,
}: {
  formId: string;
  blueprintId: string;
  poolId: string;
  onWalk: () => void;
  onBack?: () => void;
}) {
  const form = useGetForm(formId);
  const curve = useGetFormTifCurve(formId, { theta_min: -3, theta_max: 3, n: 61 });
  const blueprint = useGetBlueprint(blueprintId, {
    query: { enabled: Boolean(blueprintId) },
  });
  const pool = useGetPoolItems({ pool_id: poolId });

  if (form.isLoading) return <Card title="Form preview"><Spinner label="Loading form…" /></Card>;
  if (form.isError || !form.data)
    return (
      <Card title="Form preview">
        <Alert tone="error" title={`Could not load form ${formId}.`} />
      </Card>
    );

  const f = form.data;
  const byId = new Map<string, PoolItem>(
    (pool.data?.items ?? []).map((it) => [it.item_id, it]),
  );
  const worstGap = Math.max(...f.tif.map((p) => Math.abs(p.gap)));
  const tol = curve.data?.tolerance ?? null;

  const actualData = (curve.data?.curve ?? []).map((p) => ({
    theta: Number(p.theta.toFixed(3)),
    actual: Number(p.actual.toFixed(4)),
  }));
  const targetData = f.tif.map((p) => ({
    theta: p.theta,
    target: p.target,
    tol: tol ?? 0,
  }));

  return (
    <div className="space-y-5">
      <Card
        title="Form preview"
        subtitle={`Form ${f.id.slice(0, 8)} · ${f.item_ids.length} items · status ${f.status}`}
        actions={
          <div className="flex gap-2">
            {onBack && (
              <Button variant="secondary" onClick={onBack}>← Back</Button>
            )}
            <Button onClick={onWalk}>Walk the form →</Button>
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Pill tone={worstGap < 0.5 ? "ok" : "warn"}>
            worst |actual − target| = {worstGap.toFixed(3)}
          </Pill>
          {curve.data && <Pill tone="info">method: {curve.data.method}</Pill>}
          {tol != null && <Pill>tolerance ±{tol}</Pill>}
          <span className="text-sm text-ink-600">
            Test Information Function vs. blueprint target
          </span>
        </div>
        <div className="h-72 w-full">
          {curve.isLoading ? (
            <Spinner label="Computing TIF curve…" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="theta"
                  type="number"
                  domain={[-3, 3]}
                  allowDuplicatedCategory={false}
                  label={{ value: "θ", position: "insideBottom", offset: -8 }}
                  stroke="#94a3b8"
                />
                <YAxis
                  label={{ value: "information", angle: -90, position: "insideLeft" }}
                  stroke="#94a3b8"
                />
                <Tooltip />
                <Legend />
                {tol != null &&
                  targetData.map((t) => (
                    <ReferenceArea
                      key={t.theta}
                      x1={t.theta - 0.06}
                      x2={t.theta + 0.06}
                      y1={Math.max(0, t.target - t.tol)}
                      y2={t.target + t.tol}
                      fill="#94a3b8"
                      fillOpacity={0.15}
                      ifOverflow="extendDomain"
                    />
                  ))}
                <Line
                  data={actualData}
                  dataKey="actual"
                  name="actual TIF"
                  stroke="#4f46e5"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <Scatter data={targetData} dataKey="target" name="target" fill="#0f172a">
                  {tol != null && <ErrorBar dataKey="tol" stroke="#64748b" width={4} />}
                </Scatter>
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="mt-3 overflow-hidden rounded-lg border border-ink-100">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 text-ink-600">
              <tr>
                <th className="px-3 py-1.5 text-left">θ</th>
                <th className="px-3 py-1.5 text-right">target</th>
                <th className="px-3 py-1.5 text-right">actual</th>
                <th className="px-3 py-1.5 text-right">gap</th>
              </tr>
            </thead>
            <tbody>
              {f.tif.map((p) => (
                <tr key={p.theta} className="border-t border-ink-100 tabular-nums">
                  <td className="px-3 py-1.5">{p.theta}</td>
                  <td className="px-3 py-1.5 text-right">{p.target.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right">{p.actual.toFixed(3)}</td>
                  <td
                    className={`px-3 py-1.5 text-right ${Math.abs(p.gap) < 0.5 ? "text-emerald-700" : "text-amber-700"}`}
                  >
                    {p.gap >= 0 ? "+" : ""}
                    {p.gap.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <ConstraintCheck blueprintSpec={blueprint.data?.blueprint} form={f} byId={byId} />

      <Card
        title="Assembled items"
        subtitle="Fixed linear order · simulated bank content"
      >
        <ol className="space-y-1 text-sm text-ink-800">
          {f.item_ids.map((id, i) => {
            const it = byId.get(id);
            return (
              <li key={id} className="flex gap-2">
                <span className="w-6 shrink-0 text-right text-ink-400 tabular-nums">
                  {i + 1}.
                </span>
                <span className="w-14 shrink-0 font-medium">{id}</span>
                <span className="truncate text-ink-600">
                  {it?.stem ?? "—"}
                  {it && (
                    <span className="ml-2 text-ink-400">
                      (a={it.a}, b={it.b}, {it.tags?.KC}/{it.tags?.Bloom})
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
      </Card>
    </div>
  );
}

function ConstraintCheck({
  blueprintSpec,
  form,
  byId,
}: {
  blueprintSpec?: {
    content_constraints?: {
      tag_type: string;
      tag_value: string;
      minimum?: number | null;
      maximum?: number | null;
    }[];
  };
  form: { item_ids: string[] };
  byId: Map<string, PoolItem>;
}) {
  const constraints = blueprintSpec?.content_constraints ?? [];
  if (!constraints.length) return null;

  return (
    <Card title="Content constraints" subtitle="Satisfaction in the assembled form">
      <ul className="space-y-1.5 text-sm">
        {constraints.map((c, i) => {
          const count = form.item_ids.filter(
            (id) => byId.get(id)?.tags?.[c.tag_type] === c.tag_value,
          ).length;
          const okMin = c.minimum == null || count >= c.minimum;
          const okMax = c.maximum == null || count <= c.maximum;
          const ok = okMin && okMax;
          const bounds = `${c.minimum ?? 0}..${c.maximum ?? "∞"}`;
          return (
            <li key={i} className="flex items-center gap-2">
              <Pill tone={ok ? "ok" : "warn"}>{ok ? "✓" : "✗"}</Pill>
              <span className="font-medium text-ink-800">
                {c.tag_type}={c.tag_value}
              </span>
              <span className="text-ink-600">
                {count} in form (need {bounds})
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
