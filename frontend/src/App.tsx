// Linear path IA (rebuilt in TS from the platform prototype's screen map):
//   A-031 Test Editor (Assembly) → A-033 Form preview → session walkthrough.
// A lightweight staged flow keeps the dependency surface small (no router).
import { useState } from "react";

import { Pill } from "./components/ui";
import { BlueprintEditorScreen } from "./screens/tests/BlueprintEditorScreen";
import { FormPreviewScreen } from "./screens/tests/FormPreviewScreen";
import { SessionNavigatorScreen } from "./screens/tests/SessionNavigatorScreen";

type Stage =
  | { name: "editor" }
  | { name: "preview"; formId: string; blueprintId: string }
  | { name: "navigate"; formId: string; blueprintId: string };

const STEPS: { id: string; label: string; stage: Stage["name"] }[] = [
  { id: "A-031", label: "Blueprint & assemble", stage: "editor" },
  { id: "A-033", label: "Form preview", stage: "preview" },
  { id: "—", label: "Walkthrough", stage: "navigate" },
];

export default function App() {
  const [stage, setStage] = useState<Stage>({ name: "editor" });

  return (
    <main className="min-h-screen bg-ink-50 text-ink-900">
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Tests Platform</h1>
            <p className="text-sm text-ink-600">Linear fixed-form — Test Editor</p>
          </div>
          <nav className="flex items-center gap-2">
            {STEPS.map((s) => (
              <Pill key={s.label} tone={s.stage === stage.name ? "info" : "neutral"}>
                {s.id} {s.label}
              </Pill>
            ))}
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-8">
        {stage.name === "editor" && (
          <BlueprintEditorScreen
            onAssembled={({ formId, blueprintId }) =>
              setStage({ name: "preview", formId, blueprintId })
            }
          />
        )}
        {stage.name === "preview" && (
          <FormPreviewScreen
            formId={stage.formId}
            blueprintId={stage.blueprintId}
            onWalk={() =>
              setStage({
                name: "navigate",
                formId: stage.formId,
                blueprintId: stage.blueprintId,
              })
            }
            onBack={() => setStage({ name: "editor" })}
          />
        )}
        {stage.name === "navigate" && (
          <SessionNavigatorScreen
            formId={stage.formId}
            onBack={() =>
              setStage({
                name: "preview",
                formId: stage.formId,
                blueprintId: stage.blueprintId,
              })
            }
          />
        )}
      </div>
    </main>
  );
}
