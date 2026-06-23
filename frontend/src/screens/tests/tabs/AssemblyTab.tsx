// A-031 Assembly tab — the blueprint editor + assemble + form preview/TIF plot,
// restructured into the tab. Assembling registers an immutable form on the test and
// shows its preview; "Walk the form" routes to the step-through navigator.
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { addForm, updateTest, useTest } from "../../../lib/testStore";
import { BlueprintEditorScreen } from "../BlueprintEditorScreen";
import type { AssembledResult } from "../BlueprintEditorScreen";
import { FormPreviewScreen } from "../FormPreviewScreen";

export function AssemblyTab() {
  const { testId } = useParams();
  const test = useTest(testId);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  if (!testId || !test) return null;

  const selectedId = params.get("form") ?? test.forms[0]?.formId;
  const selected = test.forms.find((f) => f.formId === selectedId);

  function onAssembled(r: AssembledResult) {
    updateTest(testId!, { name: r.draft.name, poolId: r.poolId, draft: r.draft });
    addForm(testId!, {
      formId: r.formId,
      blueprintId: r.blueprintId,
      jobId: r.jobId,
      poolId: r.poolId,
      status: r.status,
      nForms: r.nForms,
      createdAt: new Date().toISOString(),
    });
    setParams({ form: r.formId });
  }

  return (
    <div className="space-y-6">
      <BlueprintEditorScreen
        key={testId}
        initialDraft={test.draft}
        onAssembled={onAssembled}
      />
      {selected && (
        <div className="border-t border-ink-200 pt-6">
          <FormPreviewScreen
            formId={selected.formId}
            blueprintId={selected.blueprintId}
            poolId={selected.poolId}
            onWalk={() => navigate(`/tests/${testId}/walk/${selected.formId}`)}
            onBack={() => setParams({})}
          />
        </div>
      )}
    </div>
  );
}
