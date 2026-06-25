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
  useCrossValidateForm,
  useGetForm,
  useGetFormTifCurve,
} from "../../api/generated/endpoints/forms/forms";
import { useGetPoolItems } from "../../api/generated/endpoints/pool/pool";
import type {
  Blueprint,
  CrossValidationResult,
  PoolItem,
} from "../../api/generated/model";
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
  const crossVal = useCrossValidateForm();
  const xval: CrossValidationResult | undefined = crossVal.data;
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
  // maximin has no target — show achieved TIF only (no target curve / gap).
  const isMaximin = curve.data?.method === "maximin";

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
            <Button
              variant="secondary"
              onClick={() => crossVal.mutate({ formId })}
              disabled={crossVal.isPending}
            >
              {crossVal.isPending ? "Validating…" : "Validate against eatATA"}
            </Button>
            <Button onClick={onWalk}>Walk the form →</Button>
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {isMaximin ? (
            <Pill tone="ok">worst-point info = {Math.min(...f.tif.map((p) => p.actual)).toFixed(3)}</Pill>
          ) : (
            <Pill tone={worstGap < 0.5 ? "ok" : "warn"}>
              worst |actual − target| = {worstGap.toFixed(3)}
            </Pill>
          )}
          {curve.data && <Pill tone="info">method: {curve.data.method}</Pill>}
          {!isMaximin && tol != null && <Pill>tolerance ±{tol}</Pill>}
          <span className="text-sm text-ink-600">
            {isMaximin
              ? "Test Information Function (achieved; maximin — no target)"
              : "Test Information Function vs. blueprint target"}
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
                {!isMaximin &&
                  tol != null &&
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
                {!isMaximin && (
                  <Scatter data={targetData} dataKey="target" name="target" fill="#0f172a">
                    {tol != null && <ErrorBar dataKey="tol" stroke="#64748b" width={4} />}
                  </Scatter>
                )}
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="mt-3 overflow-hidden rounded-lg border border-ink-100">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 text-ink-600">
              <tr>
                <th className="px-3 py-1.5 text-left">θ</th>
                {!isMaximin && <th className="px-3 py-1.5 text-right">target</th>}
                <th className="px-3 py-1.5 text-right">actual</th>
                {!isMaximin && <th className="px-3 py-1.5 text-right">gap</th>}
              </tr>
            </thead>
            <tbody>
              {f.tif.map((p) => (
                <tr key={p.theta} className="border-t border-ink-100 tabular-nums">
                  <td className="px-3 py-1.5">{p.theta}</td>
                  {!isMaximin && (
                    <td className="px-3 py-1.5 text-right">{p.target.toFixed(2)}</td>
                  )}
                  <td className="px-3 py-1.5 text-right">{p.actual.toFixed(3)}</td>
                  {!isMaximin && (
                  <td
                    className={`px-3 py-1.5 text-right ${Math.abs(p.gap) < 0.5 ? "text-emerald-700" : "text-amber-700"}`}
                  >
                    {p.gap >= 0 ? "+" : ""}
                    {p.gap.toFixed(3)}
                  </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <ConstraintCheck blueprint={blueprint.data?.blueprint} form={f} byId={byId} />

      {(crossVal.isPending || xval || crossVal.isError) && (
        <CrossValidationPanel
          result={xval}
          loading={crossVal.isPending}
          error={crossVal.isError}
        />
      )}

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
  blueprint,
  form,
  byId,
}: {
  blueprint?: Blueprint | null;
  form: { item_ids: string[] };
  byId: Map<string, PoolItem>;
}) {
  const constraints = blueprint?.content_constraints ?? [];
  if (!constraints.length) return null;
  const length = blueprint?.length ?? form.item_ids.length;

  return (
    <Card title="Content constraints" subtitle="Satisfaction in the assembled form">
      <ul className="space-y-1.5 text-sm">
        {constraints.map((c, i) => {
          // predicates: tags map (cell) or a single tag_type/tag_value (marginal)
          const preds: [string, string][] = c.tags
            ? Object.entries(c.tags)
            : c.tag_type && c.tag_value
              ? [[c.tag_type, c.tag_value]]
              : [];
          const count = form.item_ids.filter((id) => {
            const tags = byId.get(id)?.tags ?? {};
            return preds.every(([k, v]) => tags[k] === v);
          }).length;
          // proportion bounds resolve to counts against the form length
          const resolve = (v: number | null | undefined): number | null =>
            v == null ? null : c.mode === "proportion" ? Math.round(v * length) : v;
          const mn = resolve(c.minimum);
          const mx = resolve(c.maximum);
          const ok = (mn == null || count >= mn) && (mx == null || count <= mx);
          const label = preds.map(([k, v]) => `${k}=${v}`).join(" & ") || "(empty)";
          const unit = c.mode === "proportion" ? " ·prop" : "";
          return (
            <li key={i} className="flex items-center gap-2">
              <Pill tone={ok ? "ok" : "warn"}>{ok ? "✓" : "✗"}</Pill>
              <span className="font-medium text-ink-800">{label}</span>
              <span className="text-ink-600">
                {count} in form (need {mn ?? 0}..{mx ?? "∞"}{unit})
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function CrossValidationPanel({
  result,
  loading,
  error,
}: {
  result?: CrossValidationResult;
  loading: boolean;
  error: boolean;
}) {
  const subtitle =
    "Read-only: solve the same compiled problem with the eatATA R package and compare. " +
    "OR-Tools remains the sole production assembler — the oracle never builds a form.";
  if (loading)
    return (
      <Card title="Cross-validation (eatATA)" subtitle={subtitle}>
        <Spinner label="Solving with eatATA (lpSolve)…" />
      </Card>
    );
  if (error || !result)
    return (
      <Card title="Cross-validation (eatATA)" subtitle={subtitle}>
        <Alert tone="error" title="Cross-validation request failed." />
      </Card>
    );

  if (result.status !== "ok" || !result.comparison) {
    const tone = result.status === "unsupported" ? "info" : "warn";
    const title =
      result.status === "unsupported"
        ? "Not applicable to this blueprint"
        : result.status === "oracle_unavailable"
          ? "Oracle service unavailable"
          : "Oracle could not validate";
    return (
      <Card title="Cross-validation (eatATA)" subtitle={subtitle}>
        <Alert tone={tone} title={title}>
          {result.detail ?? ""}
        </Alert>
      </Card>
    );
  }

  const c = result.comparison;
  const o = result.oracle;
  const agree = c.selection_match && c.objective_within_tolerance !== false;
  return (
    <Card title="Cross-validation (eatATA)" subtitle={subtitle}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Pill tone={agree ? "ok" : "warn"}>
          {agree ? "✓ agreement" : "⚠ divergence"}
        </Pill>
        <Pill tone="info">{result.package}</Pill>
        {o.solver && <Pill>solver: {o.solver}</Pill>}
        {o.solve_time_s != null && <Pill>{o.solve_time_s.toFixed(2)}s</Pill>}
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="rounded-lg border border-ink-100 p-3">
          <div className="font-medium text-ink-800">OR-Tools (CP-SAT) · production</div>
          <div className="mt-1 text-ink-600">
            objective {result.ortools.objective_value?.toFixed(4) ?? "—"}
          </div>
          <div className="text-ink-600">{result.ortools.item_ids.length} items</div>
        </div>
        <div className="rounded-lg border border-ink-100 p-3">
          <div className="font-medium text-ink-800">eatATA (R) · validation</div>
          <div className="mt-1 text-ink-600">
            objective {o.objective_value?.toFixed(4) ?? "—"}
          </div>
          <div className="text-ink-600">{o.item_ids?.length ?? 0} items</div>
        </div>
      </div>

      <ul className="mt-3 space-y-1 text-sm text-ink-700">
        <li>
          <span className="font-medium">Item selection:</span>{" "}
          {c.selection_match
            ? "identical set ✓"
            : `differ — ${c.only_in_ortools.length} only in OR-Tools, ` +
              `${c.only_in_oracle.length} only in eatATA (Jaccard ${c.jaccard.toFixed(3)})`}
        </li>
        <li>
          <span className="font-medium">Objective:</span>{" "}
          |Δ| = {c.objective_abs_diff?.toFixed(5) ?? "—"} ·{" "}
          {c.objective_within_tolerance ? "within" : "outside"} tolerance{" "}
          {c.tolerance.toFixed(5)} <span className="text-ink-400">[{c.tolerance_basis}]</span>
        </li>
        <li>
          <span className="font-medium">Constraints:</span>{" "}
          {c.constraints_satisfied ? "oracle solution feasible ✓" : "not satisfied ✗"}
        </li>
        {!c.selection_match && (c.only_in_ortools.length > 0 || c.only_in_oracle.length > 0) && (
          <li className="text-xs text-ink-500">
            only-OR-Tools: {c.only_in_ortools.join(", ") || "—"} · only-eatATA:{" "}
            {c.only_in_oracle.join(", ") || "—"}
          </li>
        )}
      </ul>
    </Card>
  );
}
