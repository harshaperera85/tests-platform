// A-033 History tab — forms assembled for this test (server-backed).
import { Link, useParams } from "react-router-dom";

import { useListTestForms } from "../../../api/generated/endpoints/tests/tests";
import { Alert, Button, Card, Pill, Spinner } from "../../../components/ui";

export function HistoryTab() {
  const { testId } = useParams();
  const forms = useListTestForms(testId ?? "", { query: { enabled: Boolean(testId) } });

  return (
    <Card title="History" subtitle="Forms assembled for this test.">
      {forms.isLoading ? (
        <Spinner label="Loading…" />
      ) : !forms.data || forms.data.length === 0 ? (
        <Alert tone="info" title="No forms yet">
          Assemble a form in the Assembly tab.
        </Alert>
      ) : (
        <ul className="divide-y divide-ink-100">
          {forms.data.map((f) => (
            <li key={f.id} className="flex items-center justify-between py-3 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium text-ink-900">
                  form {f.id.slice(0, 8)} · {f.n_items} items
                </p>
                <p className="text-xs text-ink-400">
                  pool {f.pool_id} · job {f.assembly_job_id.slice(0, 8)} ·{" "}
                  {new Date(f.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Pill
                  tone={
                    f.lifecycle_state === "published"
                      ? "ok"
                      : f.lifecycle_state === "draft"
                        ? "neutral"
                        : "info"
                  }
                >
                  {f.lifecycle_state}
                </Pill>
                <Link to={`/tests/${testId}/assembly?form=${f.id}`}>
                  <Button variant="secondary">Preview</Button>
                </Link>
                <Link to={`/tests/${testId}/review`}>
                  <Button variant="ghost">Review</Button>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
