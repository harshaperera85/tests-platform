// A-032 About tab — test identity + blueprint summary (read from the latest
// assembled blueprint via the generated client).
import { useParams } from "react-router-dom";

import { useGetBlueprint } from "../../../api/generated/endpoints/blueprints/blueprints";
import { Alert, Card, Pill } from "../../../components/ui";
import { useTest } from "../../../lib/testStore";

export function AboutTab() {
  const { testId } = useParams();
  const test = useTest(testId);
  const bpId = test?.latestBlueprintId;
  const bp = useGetBlueprint(bpId ?? "", { query: { enabled: Boolean(bpId) } });

  if (!test) return null;

  return (
    <div className="space-y-5">
      <Card title="About" subtitle="Test identity and administration model.">
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-ink-500">Name</dt>
          <dd className="font-medium text-ink-900">{test.name}</dd>
          <dt className="text-ink-500">Administration model</dt>
          <dd><Pill tone="info">linear</Pill></dd>
          <dt className="text-ink-500">Item pool</dt>
          <dd className="text-ink-900">{test.poolId}</dd>
          <dt className="text-ink-500">Status</dt>
          <dd>{test.forms.length ? <Pill tone="ok">assembled</Pill> : <Pill>draft</Pill>}</dd>
          <dt className="text-ink-500">Created</dt>
          <dd className="text-ink-900">{new Date(test.createdAt).toLocaleString()}</dd>
        </dl>
      </Card>

      <Card title="Blueprint summary" subtitle="From the latest assembled blueprint.">
        {!bpId ? (
          <Alert tone="info" title="No blueprint yet">
            Assemble a form in the Assembly tab to populate this summary.
          </Alert>
        ) : bp.isLoading ? (
          <p className="text-sm text-ink-600">Loading…</p>
        ) : bp.data ? (
          <dl className="grid grid-cols-2 gap-y-3 text-sm">
            <dt className="text-ink-500">Length</dt>
            <dd className="text-ink-900">{bp.data.blueprint.length} items</dd>
            <dt className="text-ink-500">Parallel forms</dt>
            <dd className="text-ink-900">{bp.data.blueprint.num_forms ?? 1}</dd>
            <dt className="text-ink-500">Exposure</dt>
            <dd className="text-ink-900">
              {bp.data.blueprint.exposure_target?.max_use_per_item != null
                ? `max ${bp.data.blueprint.exposure_target.max_use_per_item} use/item`
                : "none"}
            </dd>
            <dt className="text-ink-500">Content constraints</dt>
            <dd className="text-ink-900">
              {(bp.data.blueprint.content_constraints ?? []).length}
            </dd>
            <dt className="text-ink-500">TIF target (θ)</dt>
            <dd className="text-ink-900">
              {bp.data.blueprint.statistical_target.theta_points.join(", ")}
            </dd>
            <dt className="text-ink-500">TIF method</dt>
            <dd className="text-ink-900">
              {bp.data.blueprint.statistical_target.method ?? "minimax"}
            </dd>
          </dl>
        ) : (
          <Alert tone="warn" title="Could not load the blueprint." />
        )}
      </Card>
    </div>
  );
}
