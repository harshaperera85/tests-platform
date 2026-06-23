// A-031 Test Editor — Assembly tab. Edit a blueprint (content constraints + TIF
// target + length) and assemble a linear form via the generated client. All API
// calls go through Orval-generated hooks (CLAUDE.md golden rule 5).
import { useState } from "react";

import { useCreateAssemblyJob } from "../../api/generated/endpoints/assembly-jobs/assembly-jobs";
import { useCreateBlueprint } from "../../api/generated/endpoints/blueprints/blueprints";
import type { Blueprint } from "../../api/generated/model";
import { Button, Card, Field, Pill, Select, TextInput } from "../../components/ui";

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

function parseNums(text: string): number[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .map(Number);
}

function numOrUndef(s: string): number | undefined {
  if (s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isNaN(n) ? undefined : n;
}

export function BlueprintEditorScreen({
  onAssembled,
}: {
  onAssembled: (args: { formId: string; blueprintId: string }) => void;
}) {
  const [name, setName] = useState("linear-demo");
  const [length, setLength] = useState("20");
  const [constraints, setConstraints] = useState<ConstraintRow[]>(DEFAULT_CONSTRAINTS);
  const [thetaText, setThetaText] = useState("-1, 0, 1");
  const [infoText, setInfoText] = useState("8, 11, 8");
  const [tolerance, setTolerance] = useState("");
  const [method, setMethod] = useState<Method>("minimax");
  const [error, setError] = useState<string | null>(null);

  const createBlueprint = useCreateBlueprint();
  const createJob = useCreateAssemblyJob();
  const busy = createBlueprint.isPending || createJob.isPending;

  function updateConstraint(i: number, patch: Partial<ConstraintRow>) {
    setConstraints((rows) =>
      rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)),
    );
  }

  function buildBlueprint(): Blueprint {
    const theta = parseNums(thetaText);
    const info = parseNums(infoText);
    if (theta.length === 0 || theta.length !== info.length) {
      throw new Error("Theta points and target info must be non-empty, equal-length lists.");
    }
    const len = Number(length);
    if (!Number.isInteger(len) || len <= 0) throw new Error("Length must be a positive integer.");

    return {
      name,
      length: len,
      statistical_target: {
        theta_points: theta,
        target_info: info,
        method,
        tolerance: numOrUndef(tolerance),
      },
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
    setError(null);
    try {
      const blueprint = buildBlueprint();
      const created = await createBlueprint.mutateAsync({ data: blueprint });
      const job = await createJob.mutateAsync({
        data: { blueprint_id: created.id, strategy: "mip", time_limit_s: 8 },
      });
      const formIds = job.form_ids ?? [];
      if (!formIds.length || (job.status !== "optimal" && job.status !== "feasible")) {
        setError(`Assembly ${job.status}: no feasible form. Loosen constraints or TIF target.`);
        return;
      }
      onAssembled({ formId: formIds[0], blueprintId: created.id });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assembly failed.");
    }
  }

  return (
    <div className="space-y-5">
      <Card
        title="Blueprint"
        subtitle="Content constraints + statistical (TIF) target — the spec the assembly engine solves."
      >
        <div className="grid grid-cols-2 gap-4">
          <Field label="Name">
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Length (items per form)">
            <TextInput
              type="number"
              min={1}
              value={length}
              onChange={(e) => setLength(e.target.value)}
            />
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
              setConstraints((r) => [
                ...r,
                { tag_type: "", tag_value: "", minimum: "", maximum: "" },
              ])
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
                <TextInput
                  value={c.tag_type}
                  placeholder="KC"
                  onChange={(e) => updateConstraint(i, { tag_type: e.target.value })}
                />
              </div>
              <div className="col-span-4">
                <TextInput
                  value={c.tag_value}
                  placeholder="algebra"
                  onChange={(e) => updateConstraint(i, { tag_value: e.target.value })}
                />
              </div>
              <div className="col-span-2">
                <TextInput
                  type="number"
                  value={c.minimum}
                  onChange={(e) => updateConstraint(i, { minimum: e.target.value })}
                />
              </div>
              <div className="col-span-2">
                <TextInput
                  type="number"
                  value={c.maximum}
                  onChange={(e) => updateConstraint(i, { maximum: e.target.value })}
                />
              </div>
              <div className="col-span-1 text-right">
                <Button
                  variant="ghost"
                  aria-label="remove"
                  onClick={() =>
                    setConstraints((rows) => rows.filter((_, idx) => idx !== i))
                  }
                >
                  ✕
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card
        title="Statistical target (TIF)"
        subtitle="Target test information at theta points — what makes forms psychometrically parallel."
      >
        <div className="grid grid-cols-2 gap-4">
          <Field label="Theta points" hint="comma-separated">
            <TextInput value={thetaText} onChange={(e) => setThetaText(e.target.value)} />
          </Field>
          <Field label="Target info" hint="comma-separated, same length">
            <TextInput value={infoText} onChange={(e) => setInfoText(e.target.value)} />
          </Field>
          <Field label="Method">
            <Select value={method} onChange={(e) => setMethod(e.target.value as Method)}>
              <option value="minimax">minimax (match target)</option>
              <option value="maximin">maximin (maximize worst point)</option>
            </Select>
          </Field>
          <Field label="Tolerance" hint="optional absolute band">
            <TextInput
              type="number"
              value={tolerance}
              placeholder="(none)"
              onChange={(e) => setTolerance(e.target.value)}
            />
          </Field>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={assemble} disabled={busy}>
          {busy ? "Assembling…" : "Assemble form"}
        </Button>
        {busy && <Pill tone="info">OR-Tools CP-SAT solving…</Pill>}
        {error && <Pill tone="warn">{error}</Pill>}
      </div>
    </div>
  );
}
