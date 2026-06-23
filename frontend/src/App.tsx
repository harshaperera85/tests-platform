// Linear-path IA (rebuilt in TS from the platform prototype's screen map):
//   A-030 Test List → A-031..034 Test Editor tabs (Assembly / About / Scoring /
//   History) → step-through walkthrough. Real routes via react-router.
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { NewTestScreen } from "./screens/tests/NewTestScreen";
import { TestEditorLayout } from "./screens/tests/TestEditorLayout";
import { TestListScreen } from "./screens/tests/TestListScreen";
import { AboutTab } from "./screens/tests/tabs/AboutTab";
import { AssemblyTab } from "./screens/tests/tabs/AssemblyTab";
import { HistoryTab } from "./screens/tests/tabs/HistoryTab";
import { ScoringTab } from "./screens/tests/tabs/ScoringTab";
import { WalkTab } from "./screens/tests/tabs/WalkTab";

export default function App() {
  return (
    <div className="min-h-screen bg-ink-50 text-ink-900">
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="block">
            <h1 className="text-xl font-semibold tracking-tight">Tests Platform</h1>
            <p className="text-sm text-ink-600">Linear fixed-form authoring</p>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <ErrorBoundary>
        <Routes>
          <Route path="/" element={<TestListScreen />} />
          <Route path="/tests/new" element={<NewTestScreen />} />
          <Route path="/tests/:testId" element={<TestEditorLayout />}>
            <Route index element={<Navigate to="assembly" replace />} />
            <Route path="assembly" element={<AssemblyTab />} />
            <Route path="about" element={<AboutTab />} />
            <Route path="scoring" element={<ScoringTab />} />
            <Route path="history" element={<HistoryTab />} />
            <Route path="walk/:formId" element={<WalkTab />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}
