// Client-side test registry (localStorage).
//
// The backend currently exposes no list/update endpoints and no `test` resource
// (only POST + GET-by-id for blueprints/jobs/forms), and Phase 1.6 is frontend-only.
// So a "test" is tracked here: a stable client id + the authoring draft, pointing at
// the immutable blueprints/forms it creates server-side. When a backend `tests`
// resource + list endpoints land, this store is replaced by generated hooks.
import { useSyncExternalStore } from "react";

export type ConstraintDraft = {
  tag_type: string;
  tag_value: string;
  minimum: string;
  maximum: string;
};

export type EditorDraft = {
  name: string;
  poolId: string;
  length: string;
  numForms: string;
  maxUse: string;
  thetaText: string;
  infoText: string;
  tolerance: string;
  method: "minimax" | "maximin";
  constraints: ConstraintDraft[];
};

export type FormRef = {
  formId: string;
  blueprintId: string;
  jobId: string;
  poolId: string;
  status: string;
  nForms: number;
  createdAt: string;
};

export type TestRecord = {
  testId: string;
  name: string;
  createdAt: string;
  poolId: string;
  latestBlueprintId?: string;
  draft?: EditorDraft;
  forms: FormRef[];
};

const KEY = "tests-platform.tests.v1";

let cache: TestRecord[] = load();
const listeners = new Set<() => void>();

function load(): TestRecord[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as TestRecord[]) : [];
  } catch {
    return [];
  }
}

function persist(next: TestRecord[]) {
  cache = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* ignore quota/availability errors */
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function listTests(): TestRecord[] {
  return cache;
}

export function getTest(testId: string): TestRecord | undefined {
  return cache.find((t) => t.testId === testId);
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `t_${Math.abs(Date.now())}_${cache.length}`;
}

export function createTest(init: Partial<TestRecord> = {}): TestRecord {
  const rec: TestRecord = {
    testId: newId(),
    name: init.name ?? "Untitled test",
    createdAt: new Date().toISOString(),
    poolId: init.poolId ?? "demo_mixed",
    draft: init.draft,
    forms: [],
  };
  persist([rec, ...cache]);
  return rec;
}

export function updateTest(testId: string, patch: Partial<TestRecord>): void {
  persist(cache.map((t) => (t.testId === testId ? { ...t, ...patch } : t)));
}

export function deleteTest(testId: string): void {
  persist(cache.filter((t) => t.testId !== testId));
}

export function addForm(testId: string, form: FormRef): void {
  persist(
    cache.map((t) =>
      t.testId === testId
        ? {
            ...t,
            poolId: form.poolId,
            latestBlueprintId: form.blueprintId,
            forms: [form, ...t.forms],
          }
        : t,
    ),
  );
}

export function useTests(): TestRecord[] {
  return useSyncExternalStore(subscribe, listTests, listTests);
}

export function useTest(testId: string | undefined): TestRecord | undefined {
  const tests = useTests();
  return testId ? tests.find((t) => t.testId === testId) : undefined;
}
