// A-031..034 Test Editor shell — tab bar + routed tab content, plus the test-level
// status workflow (lock / unlock / duplicate). Server-backed via the generated client.
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";

import {
  getGetTestQueryKey,
  getListTestsQueryKey,
  useDuplicateTest,
  useGetTest,
  useLockTest,
  useUnlockTest,
} from "../../api/generated/endpoints/tests/tests";
import { Alert, Button, Card, Pill, Spinner } from "../../components/ui";

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

  const lock = useLockTest();
  const unlock = useUnlockTest();
  const duplicate = useDuplicateTest();

  function invalidate() {
    if (testId) qc.invalidateQueries({ queryKey: getGetTestQueryKey(testId) });
    qc.invalidateQueries({ queryKey: getListTestsQueryKey() });
  }

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
  const locked = t.status === "locked";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-400">Test editor</p>
          <h2 className="text-2xl font-semibold text-ink-900">{t.name}</h2>
          <p className="flex items-center gap-2 text-sm text-ink-600">
            {t.administration_model} · pool {t.pool_id} · v{t.version} · {t.form_count} form
            {t.form_count === 1 ? "" : "s"}{" "}
            <Pill tone={locked ? "warn" : t.form_count ? "ok" : "neutral"}>{t.status}</Pill>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {locked ? (
            <Button
              variant="secondary"
              onClick={async () => {
                await unlock.mutateAsync({ testId });
                invalidate();
              }}
            >
              Unlock
            </Button>
          ) : (
            <Button
              variant="secondary"
              disabled={t.form_count === 0}
              onClick={async () => {
                await lock.mutateAsync({ testId });
                invalidate();
              }}
            >
              Lock
            </Button>
          )}
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

      {locked && (
        <Alert tone="info" title="This test is locked.">
          Editing and re-assembly are disabled. Unlock to make changes.
        </Alert>
      )}

      <Outlet />
    </div>
  );
}
