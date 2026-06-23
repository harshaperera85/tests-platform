// A-034 Scoring tab — the linear scoring model. Linear fixed-form scores via the
// canonical θ metric (psychometrics): EAP over the answered items. A scored
// walkthrough is reachable once a form is assembled.
import { Link, useParams } from "react-router-dom";

import { Button, Card, Pill } from "../../../components/ui";
import { useTest } from "../../../lib/testStore";

export function ScoringTab() {
  const { testId } = useParams();
  const test = useTest(testId);
  if (!test) return null;
  const latestForm = test.forms[0];

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
        {latestForm ? (
          <Link to={`/tests/${testId}/walk/${latestForm.formId}`}>
            <Button>Open walkthrough →</Button>
          </Link>
        ) : (
          <p className="text-sm text-ink-600">Assemble a form first (Assembly tab).</p>
        )}
      </Card>
    </div>
  );
}
