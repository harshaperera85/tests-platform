// Step-through navigator — two ways to drive the real LinearStrategy end-to-end:
//   • Manual: answer each item; θ/SE are re-estimated after every response via the
//     stateless /preview endpoint (initialize → next_action → record_response →
//     score). Shows a live θ trace.
//   • Simulated examinee: pick a true θ and let the server simulate the whole
//     session (real engine + 2PL model) — a genuine simulated e2e demonstration.
// All data via the generated client; θ/SE are real EAP estimates.
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useSimulateForm } from "../../api/generated/endpoints/forms/forms";
import { useGetPoolItems } from "../../api/generated/endpoints/pool/pool";
import {
  useRespondPreview,
  useScorePreview,
  useStartPreview,
} from "../../api/generated/endpoints/preview/preview";
import type { PoolItem, PreviewStep } from "../../api/generated/model";
import { Alert, Button, Card, Field, Pill, Spinner, TextInput } from "../../components/ui";

type TracePoint = { position: number; theta: number; se: number };

export function SessionNavigatorScreen({
  formId,
  onBack,
}: {
  formId: string;
  onBack: () => void;
}) {
  const [mode, setMode] = useState<"manual" | "sim">("manual");
  const pool = useGetPoolItems();
  const byId = new Map<string, PoolItem>(
    (pool.data?.items ?? []).map((it) => [it.item_id, it]),
  );

  return (
    <div className="space-y-5">
      <Card
        title="Session walkthrough"
        subtitle="Driven by the engine: next_action → record_response → score"
        actions={
          <div className="flex gap-2">
            <Button
              variant={mode === "manual" ? "primary" : "secondary"}
              onClick={() => setMode("manual")}
            >
              Manual
            </Button>
            <Button
              variant={mode === "sim" ? "primary" : "secondary"}
              onClick={() => setMode("sim")}
            >
              Simulated examinee
            </Button>
            <Button variant="ghost" onClick={onBack}>
              ← Back to preview
            </Button>
          </div>
        }
      >
        {mode === "manual" ? (
          <ManualWalk formId={formId} byId={byId} />
        ) : (
          <SimulatedWalk formId={formId} />
        )}
      </Card>
    </div>
  );
}

function ThetaTrace({
  data,
  trueTheta,
}: {
  data: TracePoint[];
  trueTheta?: number;
}) {
  if (data.length === 0) return null;
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="position"
            type="number"
            domain={[0, "dataMax"]}
            allowDecimals={false}
            label={{ value: "items answered", position: "insideBottom", offset: -8 }}
            stroke="#94a3b8"
          />
          <YAxis
            domain={[-3, 3]}
            label={{ value: "θ̂", angle: -90, position: "insideLeft" }}
            stroke="#94a3b8"
          />
          <Tooltip />
          {trueTheta != null && (
            <ReferenceLine y={trueTheta} stroke="#0f172a" strokeDasharray="5 4" />
          )}
          <Line
            type="monotone"
            dataKey="theta"
            name="θ̂ (EAP)"
            stroke="#4f46e5"
            strokeWidth={2}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ManualWalk({
  formId,
  byId,
}: {
  formId: string;
  byId: Map<string, PoolItem>;
}) {
  const startPreview = useStartPreview();
  const respondPreview = useRespondPreview();
  const scorePreview = useScorePreview();

  const [step, setStep] = useState<PreviewStep | null>(null);
  const [trace, setTrace] = useState<TracePoint[]>([]);
  const [theta, setTheta] = useState<number | null>(null);
  const [se, setSe] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    startPreview
      .mutateAsync({ data: { form_id: formId } })
      .then((s) => !cancelled && setStep(s))
      .catch(() => !cancelled && setError("Could not start the preview session."));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formId]);

  async function answer(correct: 0 | 1) {
    if (!step) return;
    const itemId = String(step.next_action.payload?.item_id ?? "");
    try {
      const next = await respondPreview.mutateAsync({
        data: { state: step.state, item_id: itemId, correct },
      });
      setStep(next);
      const score = await scorePreview.mutateAsync({ data: { state: next.state } });
      if (score.theta != null && score.standard_error != null) {
        setTheta(score.theta);
        setSe(score.standard_error);
        setTrace((t) => [
          ...t,
          { position: next.state.position ?? t.length + 1, theta: score.theta!, se: score.standard_error! },
        ]);
      }
    } catch {
      setError("Failed to record/score the response.");
    }
  }

  if (error) return <Alert tone="error" title={error} />;
  if (!step) return <Spinner label="Starting session…" />;

  const total = step.next_action.navigation.total_items ?? null;
  const position = step.state.position ?? 0;
  const done = step.termination.complete;
  const currentId =
    step.next_action.kind === "present"
      ? String(step.next_action.payload?.item_id ?? "")
      : null;
  const currentItem = currentId ? byId.get(currentId) : undefined;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Pill tone="info">
          item {Math.min(position + (done ? 0 : 1), total ?? position)}
          {total ? ` / ${total}` : ""}
        </Pill>
        {theta != null && <Pill tone="ok">θ̂ {theta.toFixed(3)}</Pill>}
        {se != null && <Pill>SE {se.toFixed(3)}</Pill>}
        {step.next_action.navigation.fixed_length && <Pill>fixed-length</Pill>}
      </div>

      {total !== null && (
        <div className="mb-5 h-2 w-full overflow-hidden rounded bg-ink-100">
          <div
            className="h-full bg-brand-500 transition-all"
            style={{ width: `${total ? (position / total) * 100 : 0}%` }}
          />
        </div>
      )}

      {!done && currentId ? (
        <div className="rounded-lg border border-ink-200 p-5">
          <p className="text-sm text-ink-600">Presenting item {currentId}</p>
          <p className="mt-1 text-lg font-medium text-ink-900">
            {currentItem?.stem ?? "(simulated item)"}
          </p>
          <p className="mt-1 text-sm text-ink-400">
            Simulate the examinee's response (dry run):
          </p>
          <div className="mt-4 flex gap-3">
            <Button onClick={() => answer(1)} disabled={respondPreview.isPending}>
              Answer correct
            </Button>
            <Button
              variant="secondary"
              onClick={() => answer(0)}
              disabled={respondPreview.isPending}
            >
              Answer incorrect
            </Button>
          </div>
        </div>
      ) : (
        <Alert tone="info" title={`End of form — ${step.termination.reason}`}>
          Final θ̂ {theta?.toFixed(3) ?? "—"} · SE {se?.toFixed(3) ?? "—"} (EAP, canonical)
        </Alert>
      )}

      {trace.length > 0 && (
        <div className="mt-5">
          <p className="mb-1 text-sm font-medium text-ink-800">θ̂ trace</p>
          <ThetaTrace data={trace} />
        </div>
      )}
    </div>
  );
}

function SimulatedWalk({ formId }: { formId: string }) {
  const [thetaText, setThetaText] = useState("0.8");
  const [seedText, setSeedText] = useState("1");
  const trueTheta = Number(thetaText);
  const seed = Number(seedText) || 0;

  const sim = useSimulateForm(
    formId,
    { theta: trueTheta, seed },
    { query: { enabled: false } },
  );

  const trace: TracePoint[] =
    sim.data?.trace
      .filter((s) => s.theta != null && s.standard_error != null)
      .map((s) => ({
        position: s.position,
        theta: s.theta as number,
        se: s.standard_error as number,
      })) ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-end gap-4">
        <Field label="True θ">
          <TextInput
            type="number"
            step="0.1"
            value={thetaText}
            onChange={(e) => setThetaText(e.target.value)}
          />
        </Field>
        <Field label="Seed">
          <TextInput
            type="number"
            value={seedText}
            onChange={(e) => setSeedText(e.target.value)}
          />
        </Field>
        <Button
          onClick={() => sim.refetch()}
          disabled={sim.isFetching || Number.isNaN(trueTheta)}
        >
          {sim.isFetching ? "Simulating…" : "Run simulated examinee"}
        </Button>
        {sim.isFetching && <Spinner />}
      </div>

      {sim.isError && (
        <div className="mt-4">
          <Alert tone="error" title="Simulation failed" />
        </div>
      )}

      {sim.data && (
        <div className="mt-5">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <Pill tone="info">true θ {sim.data.true_theta}</Pill>
            <Pill tone="ok">final θ̂ {sim.data.final_theta?.toFixed(3) ?? "—"}</Pill>
            <Pill>SE {sim.data.final_standard_error?.toFixed(3) ?? "—"}</Pill>
            <Pill>{sim.data.n_items} items</Pill>
          </div>
          <p className="mb-1 text-sm font-medium text-ink-800">
            θ̂ converging toward the true θ (dashed)
          </p>
          <ThetaTrace data={trace} trueTheta={sim.data.true_theta} />
        </div>
      )}
    </div>
  );
}
