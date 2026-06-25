// A-038..041 — Form lifecycle review/approve/publish surface (cross-model
// governance). SME content review (A-038–040) + Admin/publish (A-041): the form's
// lifecycle state + gate actions, the server-generated form-QA report, and the
// append-only sign-off history. Generated Orval client only (golden rule 5).
import { useState } from "react";
import { useParams } from "react-router-dom";

import { useQueryClient } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getGetFormLifecycleQueryKey,
  getGetFormQaReportQueryKey,
  useGetFormLifecycle,
  useGetFormQaReport,
  useTransitionForm,
} from "../../../api/generated/endpoints/forms/forms";
import { useListTestForms } from "../../../api/generated/endpoints/tests/tests";
import { Alert, Button, Card, Field, Pill, Select, Spinner, TextInput } from "../../../components/ui";

// gate action → label + the role it records (role hook is a permissive stub today)
const ACTIONS: Record<string, { label: string; role: string; comment: boolean }> = {
  submit_for_review: { label: "Submit for review", role: "author", comment: false },
  approve_content: { label: "Approve · content (SME)", role: "content_reviewer", comment: false },
  approve_psychometric: { label: "Approve · psychometric", role: "psychometrician", comment: false },
  publish: { label: "Publish", role: "publisher", comment: false },
  return_to_draft: { label: "Return to draft (reject)", role: "reviewer", comment: true },
  withdraw: { label: "Withdraw (unpublish)", role: "publisher", comment: false },
};

const STATE_TONE: Record<string, "neutral" | "ok" | "warn" | "info"> = {
  draft: "neutral",
  content_review: "info",
  psychometric_review: "info",
  approved: "warn",
  published: "ok",
};

export function ReviewTab() {
  const { testId } = useParams();
  const forms = useListTestForms(testId ?? "", { query: { enabled: Boolean(testId) } });
  const [formId, setFormId] = useState<string>("");
  const selected = formId || forms.data?.[0]?.id || "";

  if (forms.isLoading) return <Card title="Review"><Spinner label="Loading…" /></Card>;
  if (!forms.data || forms.data.length === 0)
    return (
      <Card title="Review" subtitle="Form lifecycle: review → approve → publish.">
        <Alert tone="info" title="No forms yet">Assemble a form first.</Alert>
      </Card>
    );

  return (
    <div className="space-y-5">
      <Card
        title="Form lifecycle"
        subtitle="Review → approve → publish. The form is the unit of governance (cross-model)."
        actions={
          <Select value={selected} onChange={(e) => setFormId(e.target.value)} className="w-56">
            {forms.data.map((f) => (
              <option key={f.id} value={f.id}>
                form {f.id.slice(0, 8)} · {f.lifecycle_state}
              </option>
            ))}
          </Select>
        }
      >
        {selected && <LifecyclePanel formId={selected} />}
      </Card>
      {selected && <QAReport formId={selected} />}
      {selected && <SignoffHistory formId={selected} />}
    </div>
  );
}

function LifecyclePanel({ formId }: { formId: string }) {
  const qc = useQueryClient();
  const lc = useGetFormLifecycle(formId);
  const transition = useTransitionForm();
  const [actor, setActor] = useState("reviewer@example.com");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (lc.isLoading || !lc.data) return <Spinner label="Loading lifecycle…" />;
  const state = lc.data.state;

  function run(action: string) {
    setError(null);
    const meta = ACTIONS[action];
    transition.mutate(
      {
        formId,
        data: { action, actor, actor_role: meta?.role, comment: comment || undefined },
      },
      {
        onSuccess: () => {
          setComment("");
          qc.invalidateQueries({ queryKey: getGetFormLifecycleQueryKey(formId) });
          qc.invalidateQueries({ queryKey: getGetFormQaReportQueryKey(formId) });
        },
        onError: (e: unknown) =>
          setError(e instanceof Error ? e.message : "Transition failed."),
      },
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-600">state</span>
        <Pill tone={STATE_TONE[state] ?? "neutral"}>{state}</Pill>
        {lc.data.frozen && <Pill tone="warn">frozen · editing/re-assembly disabled</Pill>}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Actor (claimed — not yet authorization-checked)">
          <TextInput value={actor} onChange={(e) => setActor(e.target.value)} />
        </Field>
        <Field label="Comment (required to reject)">
          <TextInput value={comment} placeholder="(optional, except reject)"
            onChange={(e) => setComment(e.target.value)} />
        </Field>
      </div>

      <div className="flex flex-wrap gap-2">
        {lc.data.available_actions.length === 0 && (
          <span className="text-sm text-ink-500">No actions from this state.</span>
        )}
        {lc.data.available_actions.map((a) => {
          const meta = ACTIONS[a];
          const disabled =
            transition.isPending || (meta?.comment && !comment.trim());
          return (
            <Button
              key={a}
              variant={a === "publish" ? "primary" : a === "return_to_draft" ? "ghost" : "secondary"}
              disabled={disabled}
              onClick={() => run(a)}
            >
              {meta?.label ?? a}
              {meta?.role ? ` · ${meta.role}` : ""}
            </Button>
          );
        })}
      </div>
      <p className="text-xs text-ink-400">
        Roles are recorded for provenance; enforcement is a deliberate stub until AuthN/AuthZ.
      </p>
      {error && <Alert tone="error" title="Transition failed">{error}</Alert>}
    </div>
  );
}

function QAReport({ formId }: { formId: string }) {
  const qa = useGetFormQaReport(formId);
  if (qa.isLoading || !qa.data)
    return <Card title="Form-QA report"><Spinner label="Generating QA report…" /></Card>;
  const r = qa.data;
  const seData = r.curve.map((p) => ({ theta: p.theta, se: p.se ?? null }));
  const tccData = r.curve.map((p) => ({ theta: p.theta, tcc: p.tcc }));

  return (
    <Card
      title="Form-QA report"
      subtitle={`Canonical ${r.metric} · ${r.n_items} items · what reviewers sign off on`}
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Pill tone={r.key_balance.imbalanced ? "warn" : "ok"}>
          key balance: {r.key_balance.imbalanced ? "⚠ " : "✓ "}{r.key_balance.note}
        </Pill>
        <Pill tone="info">marginal reliability {r.marginal_reliability.toFixed(3)}</Pill>
        {Object.entries(r.key_balance.counts).map(([k, n]) => (
          <Pill key={k}>{k}: {n}</Pill>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1 text-sm font-medium text-ink-700">Conditional SE — SE(θ)=1/√I(θ)</div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={seData} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="theta" type="number" domain={[-3, 3]} stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Line dataKey="se" stroke="#dc2626" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <div className="mb-1 text-sm font-medium text-ink-700">TCC — expected raw score Σ Pᵢ(θ)</div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tccData} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="theta" type="number" domain={[-3, 3]} stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Line dataKey="tcc" stroke="#4f46e5" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="mb-1 font-medium text-ink-700">Content coverage vs blueprint</div>
          {r.coverage.length === 0 ? (
            <p className="text-ink-400">No content constraints.</p>
          ) : (
            <ul className="space-y-1">
              {r.coverage.map((c) => (
                <li key={c.label} className="flex items-center gap-2">
                  <Pill tone={c.satisfied ? "ok" : "warn"}>{c.satisfied ? "✓" : "✗"}</Pill>
                  <span className="font-medium text-ink-800">{c.label}</span>
                  <span className="text-ink-600">
                    {c.count} (need {c.minimum ?? 0}..{c.maximum ?? "∞"})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <div className="mb-1 font-medium text-ink-700">Actual vs target TIF</div>
          <table className="w-full tabular-nums">
            <thead className="text-ink-500">
              <tr><th className="text-left">θ</th><th className="text-right">target</th><th className="text-right">actual</th></tr>
            </thead>
            <tbody>
              {r.tif_actual_vs_target.map((p) => (
                <tr key={p.theta} className="border-t border-ink-100">
                  <td>{p.theta}</td>
                  <td className="text-right">{p.target.toFixed(2)}</td>
                  <td className="text-right">{p.actual.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <details className="mt-4 text-sm">
        <summary className="cursor-pointer font-medium text-ink-700">Answer key (form order)</summary>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {r.answer_key.map((a) => (
            <span key={a.position} className="rounded bg-ink-50 px-2 py-0.5 text-xs text-ink-700">
              {a.position}.{a.item_id}={a.answer_key ?? "—"}
            </span>
          ))}
        </div>
      </details>
    </Card>
  );
}

function SignoffHistory({ formId }: { formId: string }) {
  const lc = useGetFormLifecycle(formId);
  const events = lc.data?.events ?? [];
  return (
    <Card title="Sign-off history" subtitle="Append-only provenance: who moved this form, when, with what sign-off.">
      {events.length === 0 ? (
        <p className="text-sm text-ink-400">No lifecycle events yet.</p>
      ) : (
        <ol className="space-y-2 text-sm">
          {events.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center gap-2 border-b border-ink-100 pb-2">
              <Pill tone="info">{e.action}</Pill>
              <span className="text-ink-600">{e.from_state} → {e.to_state}</span>
              <span className="font-medium text-ink-800">{e.actor}</span>
              {e.actor_role && <span className="text-ink-500">({e.actor_role})</span>}
              <span className="text-xs text-ink-400">{new Date(e.created_at).toLocaleString()}</span>
              {e.comment && <span className="w-full text-ink-600">“{e.comment}”</span>}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
