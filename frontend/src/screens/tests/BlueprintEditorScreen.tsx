// A-031 Test Editor — Assembly tab. Pick a pool, optionally load a scenario, edit
// the blueprint, save the draft, and assemble — all against the server-backed test
// (PATCH /tests/{id}, POST /tests/{id}/assemble). Generated client only (golden
// rule 5).
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { getAssemblyJob } from "../../api/generated/endpoints/assembly-jobs/assembly-jobs";
import { useGenerateBlueprintFromCurriculum } from "../../api/generated/endpoints/blueprints/blueprints";
import { useGenerateLoftSessions } from "../../api/generated/endpoints/loft/loft";
import { useCreateBlueprint } from "../../api/generated/endpoints/blueprints/blueprints";
import { useImportItemBank } from "../../api/generated/endpoints/item-bank/item-bank";
import { useListCurricula } from "../../api/generated/endpoints/curricula/curricula";
import {
  getGetPoolCatalogQueryKey,
  getGetPoolItemsQueryKey,
  useGetPoolCatalog,
  useGetPoolItems,
} from "../../api/generated/endpoints/pool/pool";
import { useListScenarios } from "../../api/generated/endpoints/scenarios/scenarios";
import {
  getGetTestQueryKey,
  getListTestFormsQueryKey,
  getListTestsQueryKey,
  useAssembleTest,
  useUpdateTest,
} from "../../api/generated/endpoints/tests/tests";
import type {
  Blueprint,
  GenerateBlueprintResponse,
  LoftSessionsRead,
  ScenarioRead,
} from "../../api/generated/model";
import { Alert, Button, Card, Field, Pill, Select, Spinner, TextInput } from "../../components/ui";

type Predicate = { tag_type: string; tag_value: string };
type ConstraintRow = {
  // one predicate = marginal; multiple = cross-classified cell (AND)
  predicates: Predicate[];
  minimum: string;
  maximum: string;
  mode: "count" | "proportion";
};
type Method = "minimax" | "maximin";

// The pinned cognitive tag contract (item-factory authored; read-only here).
// Bloom is two-dimensional — never a generic "bloom"; DOK is not tagged upstream yet.
const COGNITIVE_DIMENSIONS: Record<string, string[]> = {
  bloom_process: ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"],
  bloom_knowledge: ["Factual", "Conceptual", "Procedural", "Metacognitive"],
  timss: ["Knowing", "Applying", "Reasoning"],
};

type Fields = {
  length: string;
  numForms: string;
  maxUse: string;
  maxRate: string;
  maxOverlap: string;
  expMax: string;
  expPrefer: boolean;
  expWeight: string;
  hasTarget: boolean;
  thetaText: string;
  infoText: string;
  weightsText: string;
  tolerance: string;
  method: Method;
  hasTcc: boolean;
  tccThetaText: string;
  tccScoresText: string;
  tccTolerance: string;
  constraints: ConstraintRow[];
};

const DEFAULT_FIELDS: Fields = {
  length: "20",
  numForms: "1",
  maxUse: "",
  maxRate: "",
  maxOverlap: "",
  expMax: "",
  expPrefer: false,
  expWeight: "",
  hasTarget: true,
  thetaText: "-1, 0, 1",
  infoText: "8, 11, 8",
  weightsText: "",
  tolerance: "",
  method: "minimax",
  hasTcc: false,
  tccThetaText: "-1, 0, 1",
  tccScoresText: "",
  tccTolerance: "1",
  constraints: [
    { predicates: [{ tag_type: "KC", tag_value: "algebra" }], minimum: "4", maximum: "8", mode: "count" },
    { predicates: [{ tag_type: "KC", tag_value: "geometry" }], minimum: "4", maximum: "", mode: "count" },
    { predicates: [{ tag_type: "Bloom", tag_value: "analyze" }], minimum: "3", maximum: "", mode: "count" },
  ],
};

const parseNums = (text: string): number[] =>
  text.split(",").map((s) => s.trim()).filter(Boolean).map(Number);

const numOrUndef = (s: string): number | undefined => {
  if (s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isNaN(n) ? undefined : n;
};

function fieldsFromBlueprint(bp: Blueprint): Fields {
  const t = bp.statistical_target;
  return {
    length: String(bp.length),
    numForms: String(bp.num_forms ?? 1),
    maxUse:
      bp.exposure_target?.max_use_per_item != null
        ? String(bp.exposure_target.max_use_per_item)
        : "",
    expMax:
      bp.exposure_feedback?.max_cumulative != null
        ? String(bp.exposure_feedback.max_cumulative)
        : "",
    expPrefer: Boolean(bp.exposure_feedback?.prefer_underused),
    expWeight:
      bp.exposure_feedback?.underuse_weight
        ? String(bp.exposure_feedback.underuse_weight)
        : "",
    maxRate:
      bp.exposure_target?.max_exposure_rate != null
        ? String(bp.exposure_target.max_exposure_rate)
        : "",
    maxOverlap:
      bp.exposure_target?.max_pairwise_overlap != null
        ? String(bp.exposure_target.max_pairwise_overlap)
        : "",
    // content-only blueprints (BP-MODES-1) carry no statistical_target — blank fields
    hasTarget: t != null,
    thetaText: (t?.theta_points ?? []).join(", "),
    infoText: (t?.target_info ?? []).join(", "),
    weightsText: (t?.weights ?? []).join(", "),
    tolerance: t?.tolerance != null ? String(t.tolerance) : "",
    method: (t?.method as Method) ?? "minimax",
    hasTcc: bp.tcc_target != null,
    tccThetaText: (bp.tcc_target?.theta_points ?? []).join(", "),
    tccScoresText: (bp.tcc_target?.target_scores ?? []).join(", "),
    tccTolerance:
      bp.tcc_target?.tolerance != null ? String(bp.tcc_target.tolerance) : "1",
    constraints: (bp.content_constraints ?? []).map((c) => {
      const predicates: Predicate[] = c.tags
        ? Object.entries(c.tags).map(([tag_type, tag_value]) => ({ tag_type, tag_value }))
        : [{ tag_type: c.tag_type ?? "", tag_value: c.tag_value ?? "" }];
      return {
        predicates,
        minimum: c.minimum != null ? String(c.minimum) : "",
        maximum: c.maximum != null ? String(c.maximum) : "",
        mode: (c.mode as "count" | "proportion") ?? "count",
      };
    }),
  };
}

export function BlueprintEditorScreen({
  testId,
  initialName,
  initialPoolId,
  initialBlueprint,
  onAssembled,
}: {
  testId: string;
  initialName: string;
  initialPoolId: string;
  initialBlueprint?: Blueprint | null;
  onAssembled: (formId: string) => void;
}) {
  const base = initialBlueprint ? fieldsFromBlueprint(initialBlueprint) : DEFAULT_FIELDS;
  const [name, setName] = useState(initialName);
  const [poolId, setPoolId] = useState(initialPoolId);
  const [length, setLength] = useState(base.length);
  const [numForms, setNumForms] = useState(base.numForms);
  const [maxUse, setMaxUse] = useState(base.maxUse);
  const [maxRate, setMaxRate] = useState(base.maxRate);
  const [maxOverlap, setMaxOverlap] = useState(base.maxOverlap);
  const [expMax, setExpMax] = useState(base.expMax);
  const [expPrefer, setExpPrefer] = useState(base.expPrefer);
  const [expWeight, setExpWeight] = useState(base.expWeight);
  const [constraints, setConstraints] = useState<ConstraintRow[]>(base.constraints);
  const [hasTarget, setHasTarget] = useState(base.hasTarget);
  const [thetaText, setThetaText] = useState(base.thetaText);
  const [infoText, setInfoText] = useState(base.infoText);
  const [weightsText, setWeightsText] = useState(base.weightsText);
  const [tolerance, setTolerance] = useState(base.tolerance);
  const [method, setMethod] = useState<Method>(base.method);
  const [hasTcc, setHasTcc] = useState(base.hasTcc);
  const [tccThetaText, setTccThetaText] = useState(base.tccThetaText);
  const [tccScoresText, setTccScoresText] = useState(base.tccScoresText);
  const [tccTolerance, setTccTolerance] = useState(base.tccTolerance);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [infeasible, setInfeasible] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [polling, setPolling] = useState(false);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  // --- Generate from curriculum (BP-MODES-1 §6) ---
  const curricula = useListCurricula();
  const generateBp = useGenerateBlueprintFromCurriculum();
  const [genCourseId, setGenCourseId] = useState("");
  const [genTestType, setGenTestType] = useState<
    "unit_quiz" | "mid_course" | "end_of_course" | "cumulative_final"
  >("cumulative_final");
  const [genUnitId, setGenUnitId] = useState("");
  const [genLength, setGenLength] = useState("20");
  const [genDim, setGenDim] = useState("");
  const [genShares, setGenShares] = useState<Record<string, string>>({});
  const [genResult, setGenResult] = useState<GenerateBlueprintResponse | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  // --- LOFT session preview (BP-MODES-1 §4) ---
  const loftSessions = useGenerateLoftSessions();
  const createBlueprintRow = useCreateBlueprint();
  const [loftN, setLoftN] = useState("10");
  const [loftEngine, setLoftEngine] = useState<
    "random_constrained" | "cp_sat" | "pregenerated"
  >("random_constrained");
  const [loftResult, setLoftResult] = useState<LoftSessionsRead | null>(null);
  const [loftError, setLoftError] = useState<string | null>(null);

  // --- import affordances: bank upload + blueprint-JSON paste ---
  const importBank = useImportItemBank();
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [importErr, setImportErr] = useState<string | null>(null);
  const [showJsonPaste, setShowJsonPaste] = useState(false);
  const [jsonText, setJsonText] = useState("");
  const [jsonErr, setJsonErr] = useState<string | null>(null);

  const qc = useQueryClient();
  const catalog = useGetPoolCatalog();
  const scenarios = useListScenarios();
  const pool = useGetPoolItems({ pool_id: poolId });
  const updateTest = useUpdateTest();
  const assembleTest = useAssembleTest();
  const busy = updateTest.isPending || assembleTest.isPending || polling;

  const theta = parseNums(thetaText);
  const info = parseNums(infoText);
  const weights = parseNums(weightsText);
  const len = Number(length);
  const nForms = Number(numForms);
  const isMinimax = method === "minimax";
  const errors: Record<string, string> = {};
  if (!Number.isInteger(len) || len <= 0) errors.length = "Length must be a positive integer.";
  if (!Number.isInteger(nForms) || nForms <= 0) errors.numForms = "Forms must be ≥ 1.";
  // content-only blueprint (BP-MODES-1 §2.1): no TIF fields to validate at all.
  if (hasTarget) {
    if (theta.length === 0) errors.theta = "Enter at least one θ point.";
    // maximin has no target: target_info/tolerance/weights are not validated/required.
    if (isMinimax) {
      if (info.length !== theta.length) errors.info = "Target info count must match θ points.";
      if (info.some((v) => Number.isNaN(v) || v < 0)) errors.info = "Target info must be ≥ 0.";
      if (weights.length > 0) {
        if (weights.length !== theta.length) errors.weights = "Weights count must match θ points.";
        else if (weights.some((w) => Number.isNaN(w) || w <= 0)) errors.weights = "Weights must be > 0.";
      }
    }
  }
  const tccTheta = parseNums(tccThetaText);
  const tccScores = parseNums(tccScoresText);
  if (hasTcc) {
    if (tccTheta.length === 0) errors.tccTheta = "Enter at least one θ point.";
    if (tccScores.length !== tccTheta.length)
      errors.tccScores = "Score count must match θ points.";
    else if (tccScores.some((v) => Number.isNaN(v) || v < 0 || v > len))
      errors.tccScores = "Scores must be in [0, length].";
    const tccTolNum = numOrUndef(tccTolerance);
    if (tccTolNum == null || tccTolNum <= 0)
      errors.tccTolerance = "The TCC band is hard — a tolerance > 0 is required.";
  }
  const rateNum = numOrUndef(maxRate);
  if (rateNum != null && (rateNum <= 0 || rateNum > 1)) errors.maxRate = "Rate must be in (0, 1].";
  // Live availability: how many pool items match a constraint's predicate(s).
  const poolItems = pool.data?.items ?? [];
  const availFor = (preds: Predicate[]): number | null => {
    const valid = preds.filter((p) => p.tag_type && p.tag_value);
    if (!valid.length || !pool.data) return null;
    return poolItems.filter((it) =>
      valid.every((p) => (it.tags ?? {})[p.tag_type] === p.tag_value),
    ).length;
  };
  const lenOk = Number.isInteger(len) && len > 0;
  const resolveCount = (v: number | undefined, mode: "count" | "proportion") =>
    v == null ? null : mode === "proportion" ? Math.round(v * len) : v;

  // per-row matching-item count, for the live hint
  const constraintAvail: (number | null)[] = [];
  constraints.forEach((c, i) => {
    const mn = numOrUndef(c.minimum);
    const mx = numOrUndef(c.maximum);
    const hasPred = c.predicates.some((p) => p.tag_type && p.tag_value);
    const avail = availFor(c.predicates);
    constraintAvail[i] = avail;
    if (!hasPred) errors[`c${i}`] = "set a tag type and value";
    else if (mn == null && mx == null) errors[`c${i}`] = "set a min and/or max";
    else if (mn != null && mx != null && mn > mx) errors[`c${i}`] = "min > max";
    else if (c.mode === "proportion") {
      if ([mn, mx].some((v) => v != null && (v < 0 || v > 1)))
        errors[`c${i}`] = "proportions must be 0–1";
    } else if ([mn, mx].some((v) => v != null && !Number.isInteger(v))) {
      errors[`c${i}`] = "counts must be whole numbers";
    } else if (mn != null && mn > len) {
      errors[`c${i}`] = `min ${mn} > length ${len}`;
    }
    // Dynamic feasibility: a resolved minimum can't exceed the matching items
    // in the pool (catches over-asks early — esp. thin cross-classified cells).
    if (!errors[`c${i}`] && lenOk && avail != null) {
      const rmin = resolveCount(mn, c.mode);
      if (rmin != null && rmin > avail) {
        errors[`c${i}`] =
          `needs ${rmin} but only ${avail} item${avail === 1 ? "" : "s"} in ` +
          `'${poolId}' match — loosen this or pick a broader tag`;
      }
    }
  });
  const valid = Object.keys(errors).length === 0;

  function applyFields(f: Fields, bpName: string) {
    setName(bpName);
    setLength(f.length);
    setNumForms(f.numForms);
    setMaxUse(f.maxUse);
    setMaxRate(f.maxRate);
    setMaxOverlap(f.maxOverlap);
    setExpMax(f.expMax);
    setExpPrefer(f.expPrefer);
    setExpWeight(f.expWeight);
    setHasTarget(f.hasTarget);
    setThetaText(f.thetaText);
    setInfoText(f.infoText);
    setWeightsText(f.weightsText);
    setMethod(f.method);
    setTolerance(f.tolerance);
    setHasTcc(f.hasTcc);
    setTccThetaText(f.tccThetaText);
    setTccScoresText(f.tccScoresText);
    setTccTolerance(f.tccTolerance);
    setConstraints(f.constraints);
    setInfeasible(null);
    setSubmitError(null);
    setWarnings([]);
  }

  function applyScenario(s: ScenarioRead) {
    setPoolId(s.pool_id);
    applyFields(fieldsFromBlueprint(s.blueprint), s.blueprint.name ?? "scenario");
  }

  async function generateFromCurriculum() {
    setGenError(null);
    setGenResult(null);
    const distribution: Record<string, number> = {};
    for (const [value, share] of Object.entries(genShares)) {
      const n = Number(share);
      if (share.trim() !== "" && !Number.isNaN(n) && n > 0) distribution[value] = n;
    }
    try {
      const res = await generateBp.mutateAsync({
        data: {
          course_id: genCourseId,
          test_type: genTestType,
          unit_id: genTestType === "unit_quiz" ? genUnitId || undefined : undefined,
          length: Number(genLength),
          pool_id: poolId,
          ...(genDim && Object.keys(distribution).length
            ? {
                cognitive_profile: {
                  dimension: genDim as "bloom_process" | "bloom_knowledge" | "timss",
                  distribution,
                },
              }
            : {}),
        },
      });
      setGenResult(res);
      // load the generated blueprint into the editor for review; save is explicit
      applyFields(
        fieldsFromBlueprint(res.blueprint),
        res.blueprint.name ?? "generated-blueprint",
      );
    } catch (e) {
      const detail = (
        e as { response?: { data?: { detail?: unknown } } }
      )?.response?.data?.detail;
      setGenError(
        typeof detail === "string"
          ? detail
          : e instanceof Error
            ? e.message
            : "Generation failed.",
      );
    }
  }

  function updateConstraint(i: number, patch: Partial<ConstraintRow>) {
    setConstraints((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function updatePredicate(ci: number, pi: number, patch: Partial<Predicate>) {
    setConstraints((rows) =>
      rows.map((r, idx) =>
        idx === ci
          ? { ...r, predicates: r.predicates.map((p, j) => (j === pi ? { ...p, ...patch } : p)) }
          : r,
      ),
    );
  }

  function addPredicate(ci: number) {
    setConstraints((rows) =>
      rows.map((r, idx) =>
        idx === ci ? { ...r, predicates: [...r.predicates, { tag_type: "", tag_value: "" }] } : r,
      ),
    );
  }

  function removePredicate(ci: number, pi: number) {
    setConstraints((rows) =>
      rows.map((r, idx) =>
        idx === ci ? { ...r, predicates: r.predicates.filter((_, j) => j !== pi) } : r,
      ),
    );
  }

  function buildBlueprint(): Blueprint {
    const maxUseNum = numOrUndef(maxUse);
    const rate = numOrUndef(maxRate);
    const overlap = numOrUndef(maxOverlap);
    const exposure =
      maxUseNum != null || rate != null || overlap != null
        ? {
            max_use_per_item: maxUseNum,
            max_exposure_rate: rate,
            max_pairwise_overlap: overlap,
          }
        : undefined;
    // opt-in longitudinal exposure feedback (default-off): only sent when configured
    const expMaxNum = numOrUndef(expMax);
    const expWeightNum = numOrUndef(expWeight);
    const exposureFeedback =
      expMaxNum != null || (expPrefer && (expWeightNum ?? 0) > 0)
        ? {
            count_contexts: ["published"],
            max_cumulative: expMaxNum,
            prefer_underused: expPrefer,
            underuse_weight: expPrefer ? (expWeightNum ?? 0) : 0,
          }
        : undefined;
    // weights apply to minimax only; omit when empty or all 1 (== unweighted)
    const weightsClean =
      isMinimax && weights.length === theta.length && weights.some((w) => w !== 1)
        ? weights
        : undefined;
    return {
      name,
      length: len,
      num_forms: nForms,
      // content-only (BP-MODES-1 A1): omit the target — fixed-form assembly is then
      // feasibility-only (no TIF objective) and still reports realized TIF.
      statistical_target: hasTarget
        ? {
            theta_points: theta,
            target_info: info,
            method,
            tolerance: isMinimax ? numOrUndef(tolerance) : undefined,
            weights: weightsClean,
          }
        : null,
      // G4: expected-score (TCC) band — hard constraint, tolerance required
      tcc_target: hasTcc
        ? {
            theta_points: tccTheta,
            target_scores: tccScores,
            tolerance: numOrUndef(tccTolerance) ?? 1,
          }
        : null,
      exposure_target: exposure,
      exposure_feedback: exposureFeedback,
      content_constraints: constraints
        .map((c) => {
          const preds = c.predicates.filter((p) => p.tag_type && p.tag_value);
          if (preds.length === 0) return null;
          const bounds = {
            minimum: numOrUndef(c.minimum),
            maximum: numOrUndef(c.maximum),
            mode: c.mode,
          };
          // one predicate → marginal; many → cross-classified cell (tags map)
          return preds.length === 1
            ? { ...bounds, tag_type: preds[0].tag_type, tag_value: preds[0].tag_value }
            : {
                ...bounds,
                tags: Object.fromEntries(preds.map((p) => [p.tag_type, p.tag_value])),
              };
        })
        .filter((c): c is NonNullable<typeof c> => c !== null),
    };
  }

  async function uploadBankFile(file: File) {
    setImportErr(null);
    setImportMsg(null);
    try {
      const doc = JSON.parse(await file.text());
      const report = await importBank.mutateAsync({ data: doc });
      // pools are dynamic now — refresh every pool-derived cache immediately
      qc.invalidateQueries({ queryKey: getGetPoolCatalogQueryKey() });
      qc.invalidateQueries({ queryKey: getGetPoolItemsQueryKey() });
      const bits = [
        `${report.n_items} items`,
        `${report.n_administrable} administrable`,
        report.pool_id ? `pool '${report.pool_id}'` : null,
        report.field_pool_id ? `field pool '${report.field_pool_id}'` : null,
      ].filter(Boolean);
      setImportMsg(`Imported bank '${report.bank_id}': ${bits.join(" · ")}${
        report.warnings.length ? ` · ${report.warnings.length} warning(s)` : ""
      }`);
      if (report.pool_id) setPoolId(report.pool_id);
    } catch (e) {
      const detail = (
        e as { response?: { data?: { detail?: unknown } } }
      )?.response?.data?.detail;
      setImportErr(
        typeof detail === "string"
          ? detail
          : e instanceof Error
            ? e.message
            : "Import failed.",
      );
    }
  }

  function applyPastedBlueprint() {
    setJsonErr(null);
    try {
      const bp = JSON.parse(jsonText) as Blueprint;
      if (typeof bp.length !== "number") {
        throw new Error("not a blueprint document (missing numeric 'length')");
      }
      applyFields(fieldsFromBlueprint(bp), bp.name ?? "imported-blueprint");
      setShowJsonPaste(false);
      setJsonText("");
    } catch (e) {
      setJsonErr(e instanceof Error ? e.message : "Invalid JSON.");
    }
  }

  async function previewLoftSessions() {
    setLoftError(null);
    setLoftResult(null);
    try {
      // snapshot the current editor state as a blueprint row, then draw sessions
      const row = await createBlueprintRow.mutateAsync({ data: buildBlueprint() });
      const res = await loftSessions.mutateAsync({
        data: {
          blueprint_id: row.id,
          pool_id: poolId,
          n_sessions: Number(loftN) || 10,
          seed: 0,
          engine: loftEngine,
          // engine (c): this test's PUBLISHED forms are the pre-generated pool
          test_id: loftEngine === "pregenerated" ? testId : undefined,
        },
      });
      setLoftResult(res);
    } catch (e) {
      const detail = (
        e as { response?: { data?: { detail?: unknown } } }
      )?.response?.data?.detail;
      setLoftError(
        typeof detail === "string"
          ? detail
          : e instanceof Error
            ? e.message
            : "LOFT preview failed.",
      );
    }
  }

  async function persistDraft() {
    await updateTest.mutateAsync({
      testId,
      data: { name, pool_id: poolId, blueprint: buildBlueprint() },
    });
    qc.invalidateQueries({ queryKey: getGetTestQueryKey(testId) });
    qc.invalidateQueries({ queryKey: getListTestsQueryKey() });
  }

  async function saveDraft() {
    setSubmitError(null);
    try {
      await persistDraft();
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Save failed.");
    }
  }

  async function assemble() {
    setSubmitError(null);
    setInfeasible(null);
    setWarnings([]);
    try {
      await persistDraft();
      let job = await assembleTest.mutateAsync({
        testId,
        data: { strategy: "mip", seed: 0, time_limit_s: 12 },
      });
      // Async path: the API returns a queued job; poll until the worker finishes.
      setPolling(true);
      let tries = 0;
      while ((job.status === "queued" || job.status === "running") && tries < 200) {
        setJobStatus(job.status);
        await new Promise((r) => setTimeout(r, 700));
        tries += 1;
        job = await getAssemblyJob(job.id);
      }
      setPolling(false);
      setJobStatus(null);

      setWarnings(job.warnings ?? []);
      // Distinguish the terminal outcomes: still-running (timed out polling),
      // engine error, infeasible, vs success.
      if (job.status === "queued" || job.status === "running") {
        setSubmitError(
          "Assembly is taking longer than expected — it's still running. Check the " +
            "History tab in a moment for the result.",
        );
        return;
      }
      if (job.status === "error") {
        setSubmitError(`Assembly failed: ${job.error ?? "engine error"}.`);
        return;
      }
      const formIds = job.form_ids ?? [];
      if (!formIds.length || (job.status !== "optimal" && job.status !== "feasible")) {
        setInfeasible(
          hasTarget
            ? `Assembly ${job.status}: no feasible form for these constraints + TIF target on ` +
              `pool '${poolId}'. Loosen a constraint, lower the target, or reduce forms.`
            : `Assembly ${job.status}: no feasible form for these content constraints on ` +
              `pool '${poolId}'. Loosen a constraint or reduce forms.`,
        );
        return;
      }
      qc.invalidateQueries({ queryKey: getListTestFormsQueryKey(testId) });
      qc.invalidateQueries({ queryKey: getGetTestQueryKey(testId) });
      qc.invalidateQueries({ queryKey: getListTestsQueryKey() });
      onAssembled(formIds[0]);
    } catch (e) {
      setPolling(false);
      setJobStatus(null);
      setSubmitError(e instanceof Error ? e.message : "Assembly request failed.");
    }
  }

  const tagSummary = pool.data?.tag_summary;

  return (
    <div className="space-y-5">
      <Card
        title="Pool & scenario"
        subtitle="Choose a simulated bank, or load a named demo scenario to populate the blueprint."
      >
        <div className="grid grid-cols-2 gap-4">
          <Field label="Item pool">
            <Select value={poolId} onChange={(e) => setPoolId(e.target.value)}>
              {(catalog.data?.pools ?? []).map((p) => (
                <option key={p.pool_id} value={p.pool_id}>
                  {p.title} — {p.n_items} items{p.n_3pl ? ` (${p.n_3pl} 3PL)` : ""}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Demo scenario">
            <Select
              value=""
              onChange={(e) => {
                const s = (scenarios.data ?? []).find((x) => x.scenario_id === e.target.value);
                if (s) applyScenario(s);
              }}
            >
              <option value="">— load a scenario —</option>
              {(scenarios.data ?? []).map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>
                  {s.title}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {pool.data && (
          <p className="mt-3 text-xs text-ink-400">
            {pool.data.simulated ? "Simulated bank" : "Bank"}: {pool.data.n_items} items
            {tagSummary?.domain && " · domains " + Object.keys(tagSummary.domain).join(", ")}
          </p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-ink-100 pt-3">
          <label className="cursor-pointer text-sm text-brand-600 hover:underline">
            {importBank.isPending ? "Importing…" : "Import item bank (JSON export)…"}
            <input
              type="file"
              accept="application/json,.json"
              className="hidden"
              disabled={importBank.isPending}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadBankFile(f);
                e.target.value = "";
              }}
            />
          </label>
          <Button variant="ghost" onClick={() => setShowJsonPaste((v) => !v)}>
            {showJsonPaste ? "Cancel paste" : "Paste blueprint JSON…"}
          </Button>
        </div>
        {importMsg && <Alert tone="info" title="Bank imported">{importMsg}</Alert>}
        {importErr && <Alert tone="error" title="Import failed">{importErr}</Alert>}
        {showJsonPaste && (
          <div className="mt-3 space-y-2">
            <textarea
              className="h-40 w-full rounded-lg border border-ink-200 p-2 font-mono text-xs"
              placeholder='{"length": 20, "content_constraints": [...], ...}'
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
            />
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={applyPastedBlueprint}>
                Load into editor
              </Button>
              <span className="text-xs text-ink-400">
                validates on save/assemble; ids and tags are used verbatim
              </span>
            </div>
            {jsonErr && <Alert tone="error" title="Invalid blueprint JSON">{jsonErr}</Alert>}
          </div>
        )}
      </Card>

      <Card
        title="Generate from curriculum"
        subtitle="Derive a blueprint from an item-factory course: pick the course, test type, and length; optionally add an authored cognitive profile. The result loads into the editor below for review — saving stays explicit."
      >
        <div className="grid grid-cols-4 items-end gap-4">
          <Field label="Course">
            <Select value={genCourseId} onChange={(e) => { setGenCourseId(e.target.value); setGenUnitId(""); }}>
              <option value="">— pick a course —</option>
              {(curricula.data ?? []).map((c) => (
                <option key={c.course_id} value={c.course_id}>
                  {c.course_name ?? c.course_id} — {c.n_units} units, {c.n_kcs} KCs
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Test type" hint="quiz → LOFT-bound; others → CAT-bound">
            <Select value={genTestType}
              onChange={(e) =>
                setGenTestType(e.target.value as typeof genTestType)
              }>
              <option value="unit_quiz">Unit quiz (one unit)</option>
              <option value="mid_course">Mid-course (first-half units)</option>
              <option value="end_of_course">End-of-course (second-half units)</option>
              <option value="cumulative_final">Cumulative final (all units)</option>
            </Select>
          </Field>
          {genTestType === "unit_quiz" && (
            <Field label="Unit">
              <Select value={genUnitId} onChange={(e) => setGenUnitId(e.target.value)}>
                <option value="">— pick a unit —</option>
                {(curricula.data ?? [])
                  .find((c) => c.course_id === genCourseId)
                  ?.units.map((u) => (
                    <option key={u.unit_id} value={u.unit_id}>
                      {u.name ?? u.unit_id}
                    </option>
                  ))}
              </Select>
            </Field>
          )}
          <Field label="Length">
            <TextInput type="number" min={1} value={genLength}
              onChange={(e) => setGenLength(e.target.value)} />
          </Field>
          <Field label="Cognitive profile" hint="authored, not derived from curriculum">
            <Select value={genDim}
              onChange={(e) => { setGenDim(e.target.value); setGenShares({}); }}>
              <option value="">(none)</option>
              {Object.keys(COGNITIVE_DIMENSIONS).map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </Select>
          </Field>
        </div>
        {genDim && (
          <div className="mt-3 flex flex-wrap items-end gap-3">
            {COGNITIVE_DIMENSIONS[genDim].map((v) => (
              <Field key={v} label={v}>
                <TextInput type="number" min={0} max={1} step="0.05" className="w-24"
                  value={genShares[v] ?? ""} placeholder="share"
                  onChange={(e) => setGenShares((s) => ({ ...s, [v]: e.target.value }))} />
              </Field>
            ))}
            <span className="pb-2 text-xs text-ink-400">shares must sum to 1</span>
          </div>
        )}
        <div className="mt-3 flex items-center gap-3">
          <Button
            onClick={generateFromCurriculum}
            disabled={!genCourseId || generateBp.isPending ||
              (genTestType === "unit_quiz" && !genUnitId)}
          >
            {generateBp.isPending ? "Generating…" : "Generate blueprint"}
          </Button>
          {genResult && (
            <Pill tone={genResult.feasible ? "ok" : "warn"}>
              {genResult.feasible
                ? `feasible on '${poolId}'`
                : `${genResult.issues.length} feasibility issue(s) on '${poolId}'`}
            </Pill>
          )}
        </div>
        {genError && <Alert tone="error" title="Generation failed">{genError}</Alert>}
        {genResult && (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-ink-500">
              {genResult.shares.map((s) =>
                `${s.label ?? s.key}: ${s.count}`).join(" · ")} (Σ ={" "}
              {genResult.shares.reduce((a, s) => a + s.count, 0)})
              {(genResult.imputed_fraction ?? 0) > 0 && (
                <span className="text-amber-700">
                  {" "}· {Math.round((genResult.imputed_fraction ?? 0) * 100)}% of
                  dimension counts imputed (§6.1) — weights are estimates
                </span>
              )}
            </p>
            {!genResult.feasible && (
              <Alert tone="warn" title="Feasibility issues vs the selected pool">
                <ul className="list-disc pl-4">
                  {genResult.issues.map((i, k) => <li key={k}>{i.message}</li>)}
                </ul>
              </Alert>
            )}
            {genResult.warnings.length > 0 && (
              <Alert tone="info" title="Generator notes">
                <ul className="list-disc pl-4">
                  {genResult.warnings.map((w, k) => <li key={k}>{w}</li>)}
                </ul>
              </Alert>
            )}
          </div>
        )}
      </Card>

      <Card title="Blueprint" subtitle="Name, length, parallel forms, and exposure.">
        <div className="grid grid-cols-4 gap-4">
          <Field label="Name">
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Length" hint={errors.length}>
            <TextInput type="number" min={1} value={length} aria-invalid={Boolean(errors.length)}
              onChange={(e) => setLength(e.target.value)} />
          </Field>
          <Field label="Parallel forms" hint={errors.numForms}>
            <TextInput type="number" min={1} value={numForms} aria-invalid={Boolean(errors.numForms)}
              onChange={(e) => setNumForms(e.target.value)} />
          </Field>
          <Field label="Max use / item" hint="exposure count (optional)">
            <TextInput type="number" min={1} value={maxUse} placeholder="(none)"
              onChange={(e) => setMaxUse(e.target.value)} />
          </Field>
          <Field label="Max exposure rate" hint={errors.maxRate ?? "0–1; → ceil(rate × forms)"}>
            <TextInput type="number" min={0} max={1} step="0.05" value={maxRate}
              placeholder="(none)" aria-invalid={Boolean(errors.maxRate)}
              onChange={(e) => setMaxRate(e.target.value)} />
          </Field>
          <Field label="Max pairwise overlap" hint="items shared by any 2 forms">
            <TextInput type="number" min={0} value={maxOverlap} placeholder="(none)"
              onChange={(e) => setMaxOverlap(e.target.value)} />
          </Field>
        </div>
        <p className="mt-2 text-xs text-ink-400">
          Exposure/overlap apply across parallel forms (Parallel forms ≥ 2). Rate assumes
          uniform form administration; a raw “Max use / item” overrides the rate.
        </p>
      </Card>

      <Card
        title="Longitudinal exposure feedback (opt-in)"
        subtitle="Use cumulative item usage across past assemblies/publications to constrain selection. Default off — leave blank to keep assembly unchanged."
      >
        <div className="grid grid-cols-3 items-end gap-4">
          <Field label="Max cumulative use" hint="exclude items used ≥ this (published)">
            <TextInput type="number" min={1} value={expMax} placeholder="(none)"
              onChange={(e) => setExpMax(e.target.value)} />
          </Field>
          <Field label="Prefer under-used">
            <label className="mt-1 flex items-center gap-2 text-sm text-ink-700">
              <input type="checkbox" checked={expPrefer}
                onChange={(e) => setExpPrefer(e.target.checked)} />
              bias toward under-utilized items
            </label>
          </Field>
          <Field label="Under-use weight" hint="info-units per use; 0 = off">
            <TextInput type="number" min={0} step="0.1" value={expWeight} placeholder="0"
              disabled={!expPrefer}
              onChange={(e) => setExpWeight(e.target.value)} />
          </Field>
        </div>
        <p className="mt-2 text-xs text-ink-400">
          Longitudinal (across administrations), distinct from the within-batch overlap/rate
          above and from CAT administration-time exposure. Counts <em>published</em> usage.
        </p>
      </Card>

      <Card
        title="Content constraints"
        subtitle="Bound items by tag. One tag = marginal; '+ AND tag' = a content × cognitive cell. Count or proportion per row."
        actions={
          <Button
            variant="secondary"
            onClick={() =>
              setConstraints((r) => [
                ...r,
                { predicates: [{ tag_type: "", tag_value: "" }], minimum: "", maximum: "", mode: "count" },
              ])
            }
          >
            + Add constraint
          </Button>
        }
      >
        <div className="space-y-3">
          {constraints.map((c, i) => (
            <div key={i} className="rounded-lg border border-ink-200 p-3">
              <div className="space-y-2">
                {c.predicates.map((p, pi) => (
                  <div key={pi} className="flex items-center gap-2">
                    <span className="w-10 text-xs text-ink-400">{pi === 0 ? "where" : "AND"}</span>
                    <TextInput
                      className="flex-1"
                      value={p.tag_type}
                      placeholder="KC"
                      onChange={(e) => updatePredicate(i, pi, { tag_type: e.target.value })}
                    />
                    <span className="text-ink-400">=</span>
                    <TextInput
                      className="flex-1"
                      value={p.tag_value}
                      placeholder="algebra"
                      onChange={(e) => updatePredicate(i, pi, { tag_value: e.target.value })}
                    />
                    {c.predicates.length > 1 && (
                      <Button variant="ghost" aria-label="remove tag" onClick={() => removePredicate(i, pi)}>
                        ✕
                      </Button>
                    )}
                  </div>
                ))}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Button variant="ghost" onClick={() => addPredicate(i)}>
                  + AND tag
                </Button>
                <span className="ml-2 text-xs text-ink-400">min</span>
                <input
                  type="number"
                  className="w-20 rounded border border-ink-200 px-2 py-1 text-sm"
                  value={c.minimum}
                  aria-invalid={Boolean(errors[`c${i}`])}
                  onChange={(e) => updateConstraint(i, { minimum: e.target.value })}
                />
                <span className="text-xs text-ink-400">max</span>
                <input
                  type="number"
                  className="w-20 rounded border border-ink-200 px-2 py-1 text-sm"
                  value={c.maximum}
                  aria-invalid={Boolean(errors[`c${i}`])}
                  onChange={(e) => updateConstraint(i, { maximum: e.target.value })}
                />
                <Select
                  className="w-36"
                  value={c.mode}
                  onChange={(e) =>
                    updateConstraint(i, { mode: e.target.value as "count" | "proportion" })
                  }
                >
                  <option value="count">count</option>
                  <option value="proportion">proportion</option>
                </Select>
                {constraintAvail[i] != null && (
                  <span
                    className={`text-xs ${errors[`c${i}`] ? "text-rose-600" : "text-ink-400"}`}
                    title="items in the selected pool matching this constraint"
                  >
                    {constraintAvail[i]} match in pool
                  </span>
                )}
                <Button
                  variant="ghost"
                  aria-label={`remove constraint ${i + 1}`}
                  className="ml-auto"
                  onClick={() => setConstraints((rows) => rows.filter((_, idx) => idx !== i))}
                >
                  Remove
                </Button>
              </div>
              {errors[`c${i}`] && (
                <p className="mt-1 text-xs text-rose-600">{errors[`c${i}`]}</p>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Card
        title="Statistical target (TIF)"
        subtitle="Target test information at θ points — what makes forms psychometrically parallel."
      >
        <label className="mb-3 flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={hasTarget}
            onChange={(e) => {
              setHasTarget(e.target.checked);
              // re-enabling on a content-only blueprint: start from sensible defaults
              if (e.target.checked && thetaText.trim() === "") {
                setThetaText(DEFAULT_FIELDS.thetaText);
                setInfoText(DEFAULT_FIELDS.infoText);
              }
            }}
          />
          set a statistical (TIF) target
        </label>
        {hasTarget ? (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Method">
              <Select value={method} onChange={(e) => setMethod(e.target.value as Method)}>
                <option value="minimax">minimax (match target)</option>
                <option value="maximin">maximin (maximize worst point)</option>
              </Select>
            </Field>
            <Field label="Theta points" hint={errors.theta ?? "comma-separated"}>
              <TextInput value={thetaText} aria-invalid={Boolean(errors.theta)}
                onChange={(e) => setThetaText(e.target.value)} />
            </Field>
            {isMinimax ? (
              <>
                <Field label="Target info" hint={errors.info ?? "comma-separated, same length"}>
                  <TextInput value={infoText} aria-invalid={Boolean(errors.info)}
                    onChange={(e) => setInfoText(e.target.value)} />
                </Field>
                <Field label="Weights" hint={errors.weights ?? "per-θ, default 1; raise to protect a θ"}>
                  <TextInput value={weightsText} placeholder="1, 1, 1"
                    aria-invalid={Boolean(errors.weights)}
                    onChange={(e) => setWeightsText(e.target.value)} />
                </Field>
                <Field label="Tolerance" hint="optional absolute band">
                  <TextInput type="number" value={tolerance} placeholder="(none)"
                    onChange={(e) => setTolerance(e.target.value)} />
                </Field>
              </>
            ) : (
              <div className="col-span-2 rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-500">
                <span className="font-medium text-ink-700">maximin</span> maximizes information at
                the worst θ point — there is no target, so target-info, weights, and tolerance
                don’t apply. The preview shows the achieved TIF only.
              </div>
            )}
          </div>
        ) : (
          // authoring-time notice per BP-MODES-1 §2.1: legal, but say what it gives up.
          <Alert tone="info" title="Content-only blueprint">
            No TIF target: assembly is <em>feasibility-only</em> — items are selected to
            satisfy the content, enemy, length, and exposure constraints with no
            information objective. Forms are parallel in <em>content only</em>, not
            statistically; realized TIF is still computed and reported. Fine for
            low-stakes forms — set a target when score comparability across forms
            matters.
          </Alert>
        )}
      </Card>

      <Card
        title="Expected-score band (TCC)"
        subtitle="Hard band on TCC(θ) = Σ Pᵢ(θ) — score comparability across forms/sessions (stronger than the TIF precision band). Enforced by CP-SAT assembly and every LOFT engine."
      >
        <label className="mb-3 flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={hasTcc}
            onChange={(e) => setHasTcc(e.target.checked)}
          />
          set an expected-score (TCC) band
        </label>
        {hasTcc && (
          <div className="grid grid-cols-3 gap-4">
            <Field label="Theta points" hint={errors.tccTheta ?? "comma-separated"}>
              <TextInput value={tccThetaText} aria-invalid={Boolean(errors.tccTheta)}
                onChange={(e) => setTccThetaText(e.target.value)} />
            </Field>
            <Field label="Target scores"
              hint={errors.tccScores ?? "expected score per θ, ≤ length"}>
              <TextInput value={tccScoresText} placeholder="6, 10, 14"
                aria-invalid={Boolean(errors.tccScores)}
                onChange={(e) => setTccScoresText(e.target.value)} />
            </Field>
            <Field label="Tolerance"
              hint={errors.tccTolerance ?? "required — the band is hard"}>
              <TextInput type="number" value={tccTolerance}
                aria-invalid={Boolean(errors.tccTolerance)}
                onChange={(e) => setTccTolerance(e.target.value)} />
            </Field>
          </div>
        )}
      </Card>

      <Card
        title="LOFT session preview (§4)"
        subtitle="Draw unique conforming forms per session from this blueprint: TIF tolerance band as hard acceptance, running exposure-rate cap, conformance record per session. LOFT-bound blueprints need a tolerance on the target."
      >
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Sessions">
            <TextInput type="number" min={1} max={500} className="w-24"
              value={loftN} onChange={(e) => setLoftN(e.target.value)} />
          </Field>
          <Field
            label="Engine"
            hint="random search · per-session CP-SAT · draw from this test's published forms"
          >
            <Select value={loftEngine}
              onChange={(e) =>
                setLoftEngine(e.target.value as typeof loftEngine)
              }>
              <option value="random_constrained">randomized search</option>
              <option value="cp_sat">CP-SAT (band as hard constraints)</option>
              <option value="pregenerated">
                pre-generated pool (published forms)
              </option>
            </Select>
          </Field>
          <Button variant="secondary" onClick={previewLoftSessions}
            disabled={!valid || loftSessions.isPending}>
            {loftSessions.isPending ? "Drawing sessions…" : "Draw LOFT sessions"}
          </Button>
          {loftResult && (
            <Pill tone="ok">
              {loftResult.n_sessions} sessions · {loftResult.n_distinct_forms} distinct
              forms{loftResult.n_pool_forms != null &&
                ` (pool of ${loftResult.n_pool_forms} published)`} · max rate{" "}
              {loftResult.max_empirical_rate.toFixed(2)} · 100% conformant
            </Pill>
          )}
        </div>
        {loftError && (
          <Alert tone="error" title="LOFT session generation failed">{loftError}</Alert>
        )}
        {loftResult && loftResult.warnings.length > 0 && (
          <Alert tone="info" title="LOFT notes">
            <ul className="list-disc pl-4">
              {loftResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </Alert>
        )}
      </Card>

      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Button onClick={assemble} disabled={busy || !valid}>
            {assembleTest.isPending || polling ? "Assembling…" : "Assemble form"}
          </Button>
          <Button variant="secondary" onClick={saveDraft} disabled={busy || !valid}>
            Save draft
          </Button>
          {(assembleTest.isPending || polling) && (
            <Spinner label={jobStatus ? `OR-Tools CP-SAT solving… (${jobStatus})` : "Queuing…"} />
          )}
          {updateTest.isPending && !assembleTest.isPending && !polling && (
            <Spinner label="Saving…" />
          )}
          {!busy && savedAt && <Pill tone="ok">saved {savedAt}</Pill>}
          {!valid && !busy && <Pill tone="warn">Fix the highlighted fields</Pill>}
        </div>
        {infeasible && <Alert tone="warn" title="Infeasible blueprint">{infeasible}</Alert>}
        {submitError && <Alert tone="error" title="Request failed">{submitError}</Alert>}
        {warnings.length > 0 && (
          <Alert tone="info" title="Assembly warnings">
            <ul className="list-disc pl-4">
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </Alert>
        )}
      </div>
    </div>
  );
}
