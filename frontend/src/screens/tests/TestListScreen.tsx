// A-030 Test List — landing screen. Lists tests (client-side registry until a
// backend `tests` resource + list endpoint lands), with create + open.
import { Link, useNavigate } from "react-router-dom";

import { Button, Card, Pill } from "../../components/ui";
import { createTest, deleteTest, useTests } from "../../lib/testStore";

export function TestListScreen() {
  const tests = useTests();
  const navigate = useNavigate();

  return (
    <div className="space-y-5">
      <Card
        title="Tests"
        subtitle="Linear fixed-form tests. Drafts are stored in this browser until a backend tests resource is wired."
        actions={
          <Button
            onClick={() => {
              const t = createTest({ name: "Untitled test" });
              navigate(`/tests/${t.testId}/assembly`);
            }}
          >
            + New test
          </Button>
        }
      >
        {tests.length === 0 ? (
          <div className="py-8 text-center text-ink-600">
            <p>No tests yet.</p>
            <p className="mt-1 text-sm text-ink-400">
              Create one, then load a demo scenario in the Assembly tab to assemble a
              form against the simulated bank.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-ink-100">
            {tests.map((t) => (
              <li key={t.testId} className="flex items-center justify-between py-3">
                <Link to={`/tests/${t.testId}/assembly`} className="min-w-0">
                  <p className="truncate font-medium text-ink-900">{t.name}</p>
                  <p className="text-xs text-ink-400">
                    linear · pool {t.poolId} · {t.forms.length} assembled form
                    {t.forms.length === 1 ? "" : "s"} ·{" "}
                    {new Date(t.createdAt).toLocaleString()}
                  </p>
                </Link>
                <div className="flex items-center gap-2">
                  {t.forms.length > 0 ? (
                    <Pill tone="ok">assembled</Pill>
                  ) : (
                    <Pill tone="neutral">draft</Pill>
                  )}
                  <Link to={`/tests/${t.testId}/assembly`}>
                    <Button variant="secondary">Open</Button>
                  </Link>
                  <Button
                    variant="ghost"
                    aria-label={`delete ${t.name}`}
                    onClick={() => deleteTest(t.testId)}
                  >
                    ✕
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
