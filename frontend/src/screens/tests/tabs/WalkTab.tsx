// Step-through walkthrough route — the /preview flow as built, reached from the
// editor (Assembly preview, Scoring, or History).
import { useNavigate, useParams } from "react-router-dom";

import { useListTestForms } from "../../../api/generated/endpoints/tests/tests";
import { Alert, Card, Spinner } from "../../../components/ui";
import { SessionNavigatorScreen } from "../SessionNavigatorScreen";

export function WalkTab() {
  const { testId, formId } = useParams();
  const forms = useListTestForms(testId ?? "", { query: { enabled: Boolean(testId) } });
  const navigate = useNavigate();

  if (forms.isLoading) return <Card title="Walkthrough"><Spinner /></Card>;
  const form = forms.data?.find((f) => f.id === formId);
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
      poolId={form.pool_id}
      onBack={() => navigate(`/tests/${testId}/assembly?form=${formId}`)}
    />
  );
}
