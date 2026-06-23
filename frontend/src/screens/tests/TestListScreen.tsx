// A-030 Test List — landing screen. Server-backed via the generated client.
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import {
  getListTestsQueryKey,
  useCreateTest,
  useDeleteTest,
  useListTests,
} from "../../api/generated/endpoints/tests/tests";
import { Button, Card, Pill, Spinner } from "../../components/ui";

export function TestListScreen() {
  const tests = useListTests();
  const createTest = useCreateTest();
  const deleteTest = useDeleteTest();
  const navigate = useNavigate();
  const qc = useQueryClient();

  async function create() {
    const t = await createTest.mutateAsync({ data: { name: "Untitled test" } });
    qc.invalidateQueries({ queryKey: getListTestsQueryKey() });
    navigate(`/tests/${t.id}/assembly`);
  }

  async function remove(testId: string) {
    await deleteTest.mutateAsync({ testId });
    qc.invalidateQueries({ queryKey: getListTestsQueryKey() });
  }

  return (
    <Card
      title="Tests"
      subtitle="Linear fixed-form tests."
      actions={
        <Button onClick={create} disabled={createTest.isPending}>
          {createTest.isPending ? "Creating…" : "+ New test"}
        </Button>
      }
    >
      {tests.isLoading ? (
        <Spinner label="Loading tests…" />
      ) : !tests.data || tests.data.length === 0 ? (
        <div className="py-8 text-center text-ink-600">
          <p>No tests yet.</p>
          <p className="mt-1 text-sm text-ink-400">
            Create one, then load a demo scenario in the Assembly tab to assemble a form
            against the simulated bank.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-ink-100">
          {tests.data.map((t) => (
            <li key={t.id} className="flex items-center justify-between py-3">
              <Link to={`/tests/${t.id}/assembly`} className="min-w-0">
                <p className="truncate font-medium text-ink-900">{t.name}</p>
                <p className="text-xs text-ink-400">
                  {t.administration_model} · pool {t.pool_id} · {t.form_count} form
                  {t.form_count === 1 ? "" : "s"} · updated{" "}
                  {new Date(t.updated_at).toLocaleString()}
                </p>
              </Link>
              <div className="flex items-center gap-2">
                <Pill tone={t.status === "locked" ? "warn" : t.form_count ? "ok" : "neutral"}>
                  {t.status}
                </Pill>
                <Link to={`/tests/${t.id}/assembly`}>
                  <Button variant="secondary">Open</Button>
                </Link>
                <Button variant="ghost" aria-label={`delete ${t.name}`} onClick={() => remove(t.id)}>
                  ✕
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
