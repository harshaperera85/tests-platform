// A-031..034 Test Editor shell — tab bar + routed tab content. A "test" here is the
// client-side record; tabs read it by id from the store.
import { NavLink, Outlet, useParams } from "react-router-dom";

import { Alert, Button, Card } from "../../components/ui";
import { useTest } from "../../lib/testStore";

const TABS = [
  { to: "assembly", id: "A-031", label: "Assembly" },
  { to: "about", id: "A-032", label: "About" },
  { to: "scoring", id: "A-034", label: "Scoring" },
  { to: "history", id: "A-033", label: "History" },
];

export function TestEditorLayout() {
  const { testId } = useParams();
  const test = useTest(testId);

  if (!test) {
    return (
      <Card title="Test not found">
        <Alert tone="warn" title="This test isn't in your browser registry.">
          It may have been created in another browser or cleared.
        </Alert>
        <div className="mt-4">
          <NavLink to="/">
            <Button variant="secondary">← Back to tests</Button>
          </NavLink>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-400">Test editor</p>
          <h2 className="text-2xl font-semibold text-ink-900">{test.name}</h2>
          <p className="text-sm text-ink-600">
            linear · pool {test.poolId} · {test.forms.length} assembled form
            {test.forms.length === 1 ? "" : "s"}
          </p>
        </div>
        <NavLink to="/">
          <Button variant="ghost">All tests</Button>
        </NavLink>
      </div>

      <nav className="flex gap-1 border-b border-ink-200">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              `-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                isActive
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-ink-600 hover:text-ink-900"
              }`
            }
          >
            <span className="text-ink-400">{t.id}</span> {t.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  );
}
