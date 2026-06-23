// A-031 Test Editor — Assembly tab. Pick a simulated item pool, optionally load a
// named demo scenario, edit the blueprint (content + TIF target + length + parallel
// forms/exposure), and assemble. Inline validation, clear success/warning/error
// states, tag-availability hints. All API calls go through generated hooks (golden
// rule 5).
import { useState } from "react";

import { useCreateAssemblyJob } from "../../api/generated/endpoints/assembly-jobs/assembly-jobs";
import { useCreateBlueprint } from "../../api/generated/endpoints/blueprints/blueprints";
import { useGetPoolCatalog, useGetPoolItems } from "../../api/generated/endpoints/pool/pool";
import { useListScenarios } from "../../api/generated/endpoints/scenarios/scenarios";
import type { Blueprint, ScenarioRead } from "../../api/generated/model";
import { Alert, Button, Card, Field, Pill, Select, Spinner, TextInput } from "../../components/ui";

type ConstraintRow = {
  tag_type: string;
  tag_value: string;
  minimum: string;
  maximum: string;
};
type Method = "minimax" | "maximin";

const DEFAULT_CONSTRAINTS: ConstraintRow[] = [
  { tag_type: "KC", tag_value: "algebra", minimum: "4", maximum: "8" },
  { tag_type: "KC", tag_value: "geometry", minimum: "4", maximum: "" },
  { tag_type: "Bloom", tag_value: "analyze", minimum: "3", maximum: "" },
];

const parseNums = (text: string): number[] =>
  text.split(",").map((s) => s.trim()).filter(Boolean).map(Number);

const numOrUndef = (s: string): number | undefined => {
  if (s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isNaN(n) ? undefined : n;
};

export function BlueprintEditorScreen({
  onAssembled,
}: {
  onAssembled: (args: { formId: string; blueprintId: string; poolId: string }) => void;
}) {
  const [poolId, setPoolId] = useState("demo_mixed");
  const [name, setName] = useState("linear-demo");
  const [length, setLength] = useState("20");
  const [numForms, setNumForms] = useState("1");
  const [maxUse, setMaxUse] = useState("");
  const [constraints, setConstraints] = useState<ConstraintRow[]>(DEFAULT_CONSTRAINTS);
  const [thetaText, setThetaText] = useState("-1, 0, 1");
  const [infoText, setInfoText] = useState("8, 11, 8");
  const [tolerance, setTolerance] = useState("");
  const [method, setMethod] = useState<Method>("minimax");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [infeasible, setInfeasible] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const catalog = useGetPoolCatalog();
  const scenarios = useListScenarios();
  const pool = useGetPoolItems({ pool_id: poolId });
  const createBlueprint = useCreateBlueprint();
  const createJob = useCreateAssemblyJob();
  const busy = createBlueprint.isPending || createJob.isPending;

  // --- inline validation ---
  const theta = parseNums(thetaText);
  const info = parseNums(infoText);
  const len = Number(length);
  const nForms = Number(numForms);
  const errors: Record<string, string> = {};
  if (!Number.isInteger(len) || len <= 0) errors.length = "Length must be a positive integer.";
  if (!Number.isInteger(nForms) || nForms <= 0) errors.numForms = "Forms must be ≥ 1.";
  if (theta.length === 0) errors.theta = "Enter at least one θ point.";
  if (info.length !== theta.length) errors.info = "Target info count must match θ points.";
  if (info.some((v) => Number.isNaN(v) || v < 0)) errors.info = "Target info must be ≥ 0.";
  constraints.forEach((c, i) => {
    const mn = numOrUndef(c.minimum);
    const mx = numOrUndef(c.maximum);
    if (mn != null && mx != null && mn > mx) errors[`c${i}`] = "min > max";
    if (mn != null && mn > len) errors[`c${i}`] = `min ${mn} > length ${len}`;
  });
  const valid = Object.keys(errors).length === 0;

  function applyScenario(s: ScenarioRead) {
    const bp = s.blueprint;
    setPoolId(s.pool_id);
    setName(bp.name ?? "scenario");
    setLength(String(bp.length));
    setNumForms(String(bp.num_forms ?? 1));
    setMaxUse(
      bp.exposure_target?.max_use_per_item != null
        ? String(bp.exposure_target.max_use_per_item)
        : "",
    );
    setThetaText((bp.statistical_target.theta_points ?? []).join(", "));
    setInfoText((bp.statistical_target.target_info ?? []).join(", "));
    setMethod((bp.statistical_target.method as Method) ?? "minimax");
    setTolerance(
      bp.statistical_target.tolerance != null ? String(bp.statistical_target.tolerance) : "",
    );
    setConstraints(
      (bp.content_constraints ?? []).map((c) => ({
        tag_type: c.tag_type,
        tag_value: c.tag_value,
        minimum: c.minimum != null ? String(c.minimum) : "",
        maximum: c.maximum != null ? String(c.maximum) : "",
      })),
    );
    setInfeasible(null);
    setSubmitError(null);
    setWarnings([]);
  }

  function updateConstraint(i: number, patch: Partial<ConstraintRow>) {
    setConstraints((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function buildBlueprint(): Blueprint {
    const maxUseNum = numOrUndef(maxUse);
    return {
      name,
      length: len,
      num_forms: nForms,
      statistical_target: {
        theta_points: theta,
        target_info: info,
        method,
        tolerance: numOrUndef(tolerance),
      },
      exposure_target: maxUseNum != null ? { max_use_per_item: maxUseNum } : undefined,
      content_constraints: constraints
        .filter((c) => c.tag_type && c.tag_value)
        .map((c) => ({
          tag_type: c.tag_type,
          tag_value: c.tag_value,
          minimum: numOrUndef(c.minimum),
          maximum: numOrUndef(c.maximum),
        })),
    };
  }

  async function assemble() {
    setSubmitError(null);
    setInfeasible(null);
    setWarnings([]);
    try {
      const created = await createBlueprint.mutateAsync({ data: buildBlueprint() });
      const job = await createJob.mutateAsync({
        data: { blueprint_id: created.id, pool_id: poolId, strategy: "mip", time_limit_s: 12 },
      });
      setWarnings(job.warnings ?? []);
      const formIds = job.form_ids ?? [];
      if (!formIds.length || (job.status !== "optimal" && job.status !== "feasible")) {
        setInfeasible(
          `Assembly ${job.status}: no feasible form for these constraints + TIF target on ` +
            `pool '${poolId}'. Loosen a constraint, lower the target, or reduce forms.`,
        );
        return;
      }
      onAssembled({ formId: formIds[0], blueprintId: created.id, poolId });
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Assembly request failed.");
    }
  }

  const tagSummary = pool.data?.tag_summary;

  return (
    <div className="space-y-5">
      <Card
        title="Pool & scenario"
        subtitle="Choose a simulated bank, or load a named demo scenario to populate the blueprint."
      >
        <div className="grid grid-cols-2 gap-4">
          <Field label="Item pool">
            <Select value={poolId} onChange={(e) => setPoolId(e.target.value)}>
              {(catalog.data?.pools ?? []).map((p) => (
                <option key={p.pool_id} value={p.pool_id}>
                  {p.title} — {p.n_items} items{p.n_3pl ? ` (${p.n_3pl} 3PL)` : ""}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Demo scenario">
            <Select
              value=""
              onChange={(e) => {
                const s = (scenarios.data ?? []).find(
                  (x) => x.scenario_id === e.target.value,
                );
                if (s) applyScenario(s);
              }}
            >
              <option value="">— load a scenario —</option>
              {(scenarios.data ?? []).map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>
                  {s.title}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {pool.data && (
          <p className="mt-3 text-xs text-ink-400">
            {pool.data.simulated ? "Simulated bank" : "Bank"}: {pool.data.n_items} items
            {tagSummary?.domain &&
              " · domains " + Object.keys(tagSummary.domain).join(", ")}
            {tagSummary?.KC && " · KC " + Object.entries(tagSummary.KC).map(([k, v]) => `${k}:${v}`).join(", ")}
          </p>
        )}
      </Card>

      <Card title="Blueprint" subtitle="Length, parallel forms, and exposure.">
        <div className="grid grid-cols-4 gap-4">
          <Field label="Name">
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Length" hint={errors.length}>
            <TextInput type="number" min={1} value={length}
              aria-invalid={Boolean(errors.length)}
              onChange={(e) => setLength(e.target.value)} />
          </Field>
          <Field label="Parallel forms" hint={errors.numForms}>
            <TextInput type="number" min={1} value={numForms}
              aria-invalid={Boolean(errors.numForms)}
              onChange={(e) => setNumForms(e.target.value)} />
          </Field>
          <Field label="Max use / item" hint="exposure (optional)">
            <TextInput type="number" min={1} value={maxUse} placeholder="(none)"
              onChange={(e) => setMaxUse(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card
        title="Content constraints"
        subtitle="Min/max item counts by tag (KC, Bloom, TIMSS, domain)."
        actions={
          <Button
            variant="secondary"
            onClick={() =>
              setConstraints((r) => [...r, { tag_type: "", tag_value: "", minimum: "", maximum: "" }])
            }
          >
            + Add
          </Button>
        }
      >
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-2 text-xs font-medium text-ink-400">
            <span className="col-span-3">Tag type</span>
            <span className="col-span-4">Tag value</span>
            <span className="col-span-2">Min</span>
            <span className="col-span-2">Max</span>
            <span className="col-span-1" />
          </div>
          {constraints.map((c, i) => (
            <div key={i} className="grid grid-cols-12 items-center gap-2">
              <div className="col-span-3">
                <TextInput value={c.tag_type} placeholder="KC"
                  onChange={(e) => updateConstraint(i, { tag_type: e.target.value })} />
              </div>
              <div className="col-span-4">
                <TextInput value={c.tag_value} placeholder="algebra"
                  onChange={(e) => updateConstraint(i, { tag_value: e.target.value })} />
              </div>
              <div className="col-span-2">
                <TextInput type="number" value={c.minimum} aria-invalid={Boolean(errors[`c${i}`])}
                  onChange={(e) => updateConstraint(i, { minimum: e.target.value })} />
              </div>
              <div className="col-span-2">
                <TextInput type="number" value={c.maximum} aria-invalid={Boolean(errors[`c${i}`])}
                  onChange={(e) => updateConstraint(i, { maximum: e.target.value })} />
              </div>
              <div className="col-span-1 text-right">
                <Button variant="ghost" aria-label={`remove constraint ${i + 1}`}
                  onClick={() => setConstraints((rows) => rows.filter((_, idx) => idx !== i))}>
                  ✕
                </Button>
              </div>
              {errors[`c${i}`] && (
                <span className="col-span-12 text-xs text-rose-600">{errors[`c${i}`]}</span>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Card
        title="Statistical target (TIF)"
        subtitle="Target test information at θ points — what makes forms psychometrically parallel."
      >
        <div className="grid grid-cols-2 gap-4">
          <Field label="Theta points" hint={errors.theta ?? "comma-separated"}>
            <TextInput value={thetaText} aria-invalid={Boolean(errors.theta)}
              onChange={(e) => setThetaText(e.target.value)} />
          </Field>
          <Field label="Target info" hint={errors.info ?? "comma-separated, same length"}>
            <TextInput value={infoText} aria-invalid={Boolean(errors.info)}
              onChange={(e) => setInfoText(e.target.value)} />
          </Field>
          <Field label="Method">
            <Select value={method} onChange={(e) => setMethod(e.target.value as Method)}>
              <option value="minimax">minimax (match target)</option>
              <option value="maximin">maximin (maximize worst point)</option>
            </Select>
          </Field>
          <Field label="Tolerance" hint="optional absolute band">
            <TextInput type="number" value={tolerance} placeholder="(none)"
              onChange={(e) => setTolerance(e.target.value)} />
          </Field>
        </div>
      </Card>

      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Button onClick={assemble} disabled={busy || !valid}>
            {busy ? "Assembling…" : "Assemble form"}
          </Button>
          {busy && <Spinner label="OR-Tools CP-SAT solving…" />}
          {!valid && !busy && <Pill tone="warn">Fix the highlighted fields</Pill>}
        </div>
        {infeasible && <Alert tone="warn" title="Infeasible blueprint">{infeasible}</Alert>}
        {submitError && <Alert tone="error" title="Request failed">{submitError}</Alert>}
        {warnings.length > 0 && (
          <Alert tone="info" title="Assembly warnings">
            <ul className="list-disc pl-4">
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </Alert>
        )}
      </div>
    </div>
  );
}
