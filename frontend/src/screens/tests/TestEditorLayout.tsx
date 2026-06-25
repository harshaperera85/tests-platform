// A-031..034 Test Editor shell — tab bar + routed tab content + Duplicate. The
// test's status + editability are DERIVED from its forms' lifecycle (no manual
// lock — see the Review tab). Server-backed via the generated client.
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";

import {
  getListTestsQueryKey,
  useDuplicateTest,
  useGetTest,
} from "../../api/generated/endpoints/tests/tests";
import { Alert, Button, Card, Pill, Spinner } from "../../components/ui";

const STATUS_TONE: Record<string, "neutral" | "ok" | "warn" | "info"> = {
  draft: "neutral",
  in_review: "info",
  approved: "warn",
  published: "ok",
};

const TABS = [
  { to: "assembly", id: "A-031", label: "Assembly" },
  { to: "about", id: "A-032", label: "About" },
  { to: "scoring", id: "A-034", label: "Scoring" },
  { to: "history", id: "A-033", label: "History" },
  { to: "review", id: "A-038", label: "Review" },
];

export function TestEditorLayout() {
  const { testId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const test = useGetTest(testId ?? "", { query: { enabled: Boolean(testId) } });

  const duplicate = useDuplicateTest();

  if (test.isLoading) return <Card title="Test editor"><Spinner label="Loading…" /></Card>;
  if (test.isError || !test.data || !testId) {
    return (
      <Card title="Test not found">
        <Alert tone="warn" title="This test could not be loaded." />
        <div className="mt-4">
          <NavLink to="/"><Button variant="secondary">← Back to tests</Button></NavLink>
        </div>
      </Card>
    );
  }

  const t = test.data;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-400">Test editor</p>
          <h2 className="text-2xl font-semibold text-ink-900">{t.name}</h2>
          <p className="flex items-center gap-2 text-sm text-ink-600">
            {t.administration_model} · pool {t.pool_id} · v{t.version} · {t.form_count} form
            {t.form_count === 1 ? "" : "s"}{" "}
            <Pill tone={STATUS_TONE[t.status] ?? "neutral"}>{t.status}</Pill>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={async () => {
              const dup = await duplicate.mutateAsync({ testId });
              qc.invalidateQueries({ queryKey: getListTestsQueryKey() });
              navigate(`/tests/${dup.id}/assembly`);
            }}
          >
            Duplicate
          </Button>
          <NavLink to="/"><Button variant="ghost">All tests</Button></NavLink>
        </div>
      </div>

      <nav className="flex gap-1 border-b border-ink-200">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                isActive
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-ink-600 hover:text-ink-900"
              }`
            }
          >
            <span className="text-ink-400">{tab.id}</span> {tab.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  );
}
