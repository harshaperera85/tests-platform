// A-034 Scoring tab — the linear scoring model + a scored walkthrough link.
import { Link, useParams } from "react-router-dom";

import { useListTestForms } from "../../../api/generated/endpoints/tests/tests";
import { Button, Card, Pill } from "../../../components/ui";

export function ScoringTab() {
  const { testId } = useParams();
  const forms = useListTestForms(testId ?? "", { query: { enabled: Boolean(testId) } });
  const latest = forms.data?.[0];

  return (
    <div className="space-y-5">
      <Card title="Scoring" subtitle="How a completed linear form is scored.">
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-ink-500">Method</dt>
          <dd><Pill tone="info">EAP</Pill></dd>
          <dt className="text-ink-500">Scale</dt>
          <dd className="text-ink-900">canonical θ (mirt metric, D = 1.702)</dd>
          <dt className="text-ink-500">Model</dt>
          <dd className="text-ink-900">2PL / 3PL Fisher information</dd>
          <dt className="text-ink-500">Standard error</dt>
          <dd className="text-ink-900">posterior SD of θ</dd>
        </dl>
        <p className="mt-4 text-sm text-ink-600">
          θ and SE are computed by the engine via the shared psychometrics layer (the
          single source of truth for the θ metric), not in the browser.
        </p>
      </Card>

      <Card title="Scored walkthrough" subtitle="Drive the engine and watch θ̂ converge.">
        {latest ? (
          <Link to={`/tests/${testId}/walk/${latest.id}`}>
            <Button>Open walkthrough →</Button>
          </Link>
        ) : (
          <p className="text-sm text-ink-600">Assemble a form first (Assembly tab).</p>
        )}
      </Card>
    </div>
  );
}
