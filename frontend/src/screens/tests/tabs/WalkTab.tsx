// Step-through walkthrough route — the /preview flow as built, reached from the
// editor (Assembly preview, Scoring, or History).
import { useNavigate, useParams } from "react-router-dom";

import { Alert, Card } from "../../../components/ui";
import { useTest } from "../../../lib/testStore";
import { SessionNavigatorScreen } from "../SessionNavigatorScreen";

export function WalkTab() {
  const { testId, formId } = useParams();
  const test = useTest(testId);
  const navigate = useNavigate();
  const form = test?.forms.find((f) => f.formId === formId);

  if (!testId || !formId || !form) {
    return (
      <Card title="Walkthrough">
        <Alert tone="warn" title="Form not found for this test." />
      </Card>
    );
  }

  return (
    <SessionNavigatorScreen
      formId={formId}
      poolId={form.poolId}
      onBack={() => navigate(`/tests/${testId}/assembly?form=${formId}`)}
    />
  );
}
