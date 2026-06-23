// A-032 About tab — test identity + blueprint summary (read from the server-backed
// test draft).
import { useParams } from "react-router-dom";

import { useGetTest } from "../../../api/generated/endpoints/tests/tests";
import { Alert, Card, Pill, Spinner } from "../../../components/ui";

export function AboutTab() {
  const { testId } = useParams();
  const test = useGetTest(testId ?? "", { query: { enabled: Boolean(testId) } });

  if (test.isLoading || !test.data) return <Card title="About"><Spinner /></Card>;
  const t = test.data;
  const bp = t.blueprint;

  return (
    <div className="space-y-5">
      <Card title="About" subtitle="Test identity and administration model.">
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-ink-500">Name</dt>
          <dd className="font-medium text-ink-900">{t.name}</dd>
          <dt className="text-ink-500">Administration model</dt>
          <dd><Pill tone="info">{t.administration_model}</Pill></dd>
          <dt className="text-ink-500">Item pool</dt>
          <dd className="text-ink-900">{t.pool_id}</dd>
          <dt className="text-ink-500">Status</dt>
          <dd><Pill tone={t.status === "locked" ? "warn" : "neutral"}>{t.status}</Pill></dd>
          <dt className="text-ink-500">Version</dt>
          <dd className="text-ink-900">v{t.version}</dd>
          <dt className="text-ink-500">Created</dt>
          <dd className="text-ink-900">{new Date(t.created_at).toLocaleString()}</dd>
        </dl>
      </Card>

      <Card title="Blueprint summary" subtitle="The current saved draft.">
        {!bp ? (
          <Alert tone="info" title="No blueprint yet">
            Edit and save a blueprint in the Assembly tab.
          </Alert>
        ) : (
          <dl className="grid grid-cols-2 gap-y-3 text-sm">
            <dt className="text-ink-500">Length</dt>
            <dd className="text-ink-900">{bp.length} items</dd>
            <dt className="text-ink-500">Parallel forms</dt>
            <dd className="text-ink-900">{bp.num_forms ?? 1}</dd>
            <dt className="text-ink-500">Exposure</dt>
            <dd className="text-ink-900">
              {bp.exposure_target?.max_use_per_item != null
                ? `max ${bp.exposure_target.max_use_per_item} use/item`
                : "none"}
            </dd>
            <dt className="text-ink-500">Content constraints</dt>
            <dd className="text-ink-900">{(bp.content_constraints ?? []).length}</dd>
            <dt className="text-ink-500">TIF target (θ)</dt>
            <dd className="text-ink-900">{bp.statistical_target.theta_points.join(", ")}</dd>
            <dt className="text-ink-500">TIF method</dt>
            <dd className="text-ink-900">{bp.statistical_target.method ?? "minimax"}</dd>
          </dl>
        )}
      </Card>
    </div>
  );
}
