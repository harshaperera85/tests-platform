// /tests/new — create a fresh test record and drop into its Assembly tab.
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { Card, Spinner } from "../../components/ui";
import { createTest } from "../../lib/testStore";

export function NewTestScreen() {
  const navigate = useNavigate();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return; // guard StrictMode double-invoke
    done.current = true;
    const t = createTest({ name: "Untitled test" });
    navigate(`/tests/${t.testId}/assembly`, { replace: true });
  }, [navigate]);

  return (
    <Card title="New test">
      <Spinner label="Creating…" />
    </Card>
  );
}
