// Step-through navigator — drives the real LinearStrategy through the thin
// /preview endpoint (initialize → next_action → record_response → score). The
// server is stateless: SessionState round-trips with each call. θ/SE are the
// engine's real EAP estimate, not a client approximation.
import { useEffect, useState } from "react";

import {
  useRespondPreview,
  useScorePreview,
  useStartPreview,
} from "../../api/generated/endpoints/preview/preview";
import type { PreviewStep, ScoreResult } from "../../api/generated/model";
import { Button, Card, Pill } from "../../components/ui";

export function SessionNavigatorScreen({
  formId,
  onBack,
}: {
  formId: string;
  onBack: () => void;
}) {
  const startPreview = useStartPreview();
  const respondPreview = useRespondPreview();
  const scorePreview = useScorePreview();

  const [step, setStep] = useState<PreviewStep | null>(null);
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Start the dry-run once, for this form.
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
    } catch {
      setError("Failed to record the response.");
    }
  }

  async function finish() {
    if (!step) return;
    try {
      setScore(await scorePreview.mutateAsync({ data: { state: step.state } }));
    } catch {
      setError("Scoring failed.");
    }
  }

  if (error) return <Card title="Walkthrough"><Pill tone="warn">{error}</Pill></Card>;
  if (!step) return <Card title="Walkthrough">Starting session…</Card>;

  const total = step.next_action.navigation.total_items ?? null;
  const position = step.state.position ?? 0;
  const done = step.termination.complete;
  const currentItem =
    step.next_action.kind === "present"
      ? String(step.next_action.payload?.item_id ?? "")
      : null;

  return (
    <div className="space-y-5">
      <Card
        title="Session walkthrough"
        subtitle="Driven by the engine: next_action → record_response → score"
        actions={
          <Button variant="secondary" onClick={onBack}>
            ← Back to preview
          </Button>
        }
      >
        <div className="mb-4 flex items-center gap-3">
          <Pill tone="info">
            item {Math.min(position + (done ? 0 : 1), total ?? position)}
            {total ? ` / ${total}` : ""}
          </Pill>
          {step.next_action.navigation.can_review && <Pill>review</Pill>}
          {step.next_action.navigation.can_navigate_back && <Pill>back</Pill>}
          <Pill>{step.next_action.navigation.fixed_length ? "fixed-length" : "adaptive"}</Pill>
        </div>

        {total !== null && (
          <div className="mb-5 h-2 w-full overflow-hidden rounded bg-ink-100">
            <div
              className="h-full bg-brand-500 transition-all"
              style={{ width: `${total ? (position / total) * 100 : 0}%` }}
            />
          </div>
        )}

        {!done && currentItem ? (
          <div className="rounded-lg border border-ink-200 p-5">
            <p className="text-sm text-ink-600">Presenting item</p>
            <p className="mt-1 text-2xl font-semibold text-ink-900">{currentItem}</p>
            <p className="mt-1 text-sm text-ink-400">
              Simulated examinee response (dry run — no real item content):
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
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
            <p className="font-medium text-emerald-800">
              End of form — {step.termination.reason}
            </p>
            <div className="mt-4">
              {score ? (
                <div className="flex flex-wrap items-center gap-4">
                  <div>
                    <p className="text-xs uppercase text-ink-400">θ (EAP, canonical)</p>
                    <p className="text-2xl font-semibold tabular-nums text-ink-900">
                      {score.theta != null ? score.theta.toFixed(3) : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase text-ink-400">SE</p>
                    <p className="text-2xl font-semibold tabular-nums text-ink-900">
                      {score.standard_error != null
                        ? score.standard_error.toFixed(3)
                        : "—"}
                    </p>
                  </div>
                  <Pill tone="ok">scale: {score.scale}</Pill>
                </div>
              ) : (
                <Button onClick={finish} disabled={scorePreview.isPending}>
                  {scorePreview.isPending ? "Scoring…" : "Score session"}
                </Button>
              )}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
