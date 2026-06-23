// /tests/new — create a fresh test and drop into its Assembly tab.
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { useCreateTest } from "../../api/generated/endpoints/tests/tests";
import { Alert, Card, Spinner } from "../../components/ui";

export function NewTestScreen() {
  const navigate = useNavigate();
  const createTest = useCreateTest();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // guard StrictMode double-invoke
    started.current = true;
    createTest
      .mutateAsync({ data: { name: "Untitled test" } })
      .then((t) => navigate(`/tests/${t.id}/assembly`, { replace: true }))
      .catch(() => {
        /* surfaced below */
      });
  }, [createTest, navigate]);

  return (
    <Card title="New test">
      {createTest.isError ? (
        <Alert tone="error" title="Could not create the test." />
      ) : (
        <Spinner label="Creating…" />
      )}
    </Card>
  );
}
