// A-033 History tab — assembled forms for this test (client-side registry until a
// backend list endpoint lands). Each links back to its preview / walkthrough.
import { Link, useParams } from "react-router-dom";

import { Alert, Button, Card, Pill } from "../../../components/ui";
import { useTest } from "../../../lib/testStore";

export function HistoryTab() {
  const { testId } = useParams();
  const test = useTest(testId);
  if (!test) return null;

  return (
    <Card title="History" subtitle="Forms assembled for this test.">
      {test.forms.length === 0 ? (
        <Alert tone="info" title="No forms yet">
          Assemble a form in the Assembly tab.
        </Alert>
      ) : (
        <ul className="divide-y divide-ink-100">
          {test.forms.map((f) => (
            <li key={f.formId} className="flex items-center justify-between py-3 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium text-ink-900">
                  form {f.formId.slice(0, 8)}
                  {f.nForms > 1 ? ` (+${f.nForms - 1} parallel)` : ""}
                </p>
                <p className="text-xs text-ink-400">
                  pool {f.poolId} · job {f.jobId.slice(0, 8)} ·{" "}
                  {new Date(f.createdAt).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Pill tone={f.status === "optimal" ? "ok" : "info"}>{f.status}</Pill>
                <Link to={`/tests/${testId}/assembly?form=${f.formId}`}>
                  <Button variant="secondary">Preview</Button>
                </Link>
                <Link to={`/tests/${testId}/walk/${f.formId}`}>
                  <Button variant="ghost">Walk</Button>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
