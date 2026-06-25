// A-031 Assembly tab — the blueprint editor + assemble + form preview/TIF plot,
// server-backed by the test (PATCH draft + POST assemble). "Walk the form" routes
// to the step-through navigator.
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  useGetTest,
  useListTestForms,
} from "../../../api/generated/endpoints/tests/tests";
import { Card, Spinner } from "../../../components/ui";
import { BlueprintEditorScreen } from "../BlueprintEditorScreen";
import { FormPreviewScreen } from "../FormPreviewScreen";

export function AssemblyTab() {
  const { testId } = useParams();
  const test = useGetTest(testId ?? "", { query: { enabled: Boolean(testId) } });
  const forms = useListTestForms(testId ?? "", { query: { enabled: Boolean(testId) } });
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  if (!testId) return null;
  if (test.isLoading || !test.data) {
    return <Card title="Assembly"><Spinner label="Loading…" /></Card>;
  }

  const list = forms.data ?? [];
  const selectedId = params.get("form") ?? list[0]?.id;
  const selected = list.find((f) => f.id === selectedId);
  // Freeze is derived from form lifecycle (single source of truth): a form past
  // draft freezes blueprint edits + re-assembly until it returns to draft.
  const frozen = list.some((f) => f.lifecycle_state !== "draft");

  return (
    <div className="space-y-6">
      {frozen ? (
        <Card
          title="Blueprint (frozen)"
          subtitle="A form is in review / approved / published. Return it to draft in the Review tab to edit or re-assemble."
        >
          <p className="text-sm text-ink-600">
            Editing and re-assembly are disabled while this test has a form under
            governance review or released.
          </p>
        </Card>
      ) : (
        <BlueprintEditorScreen
          key={testId}
          testId={testId}
          initialName={test.data.name}
          initialPoolId={test.data.pool_id}
          initialBlueprint={test.data.blueprint}
          onAssembled={(formId) => setParams({ form: formId })}
        />
      )}

      {selected && (
        <div className="border-t border-ink-200 pt-6">
          <FormPreviewScreen
            formId={selected.id}
            blueprintId={selected.blueprint_id}
            poolId={selected.pool_id}
            onWalk={() => navigate(`/tests/${testId}/walk/${selected.id}`)}
            onBack={() => setParams({})}
          />
        </div>
      )}
    </div>
  );
}
