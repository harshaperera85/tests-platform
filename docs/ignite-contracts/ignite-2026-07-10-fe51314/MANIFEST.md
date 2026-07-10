# Ignite contract pack — 2026-07-10 @ fe51314

Cut from harshaperera85/cat-platform commit `fe51314` on 2026-07-10.
Destination: `tests-platform/docs/ignite-contracts/ignite-2026-07-10-fe51314/`
(copy the whole directory; do not merge into an older pack).

| File | What it is |
|---|---|
| openapi-snapshot.json | Full Ignite OpenAPI spec (CI-gated byte-identical to live) |
| test-config.schema.json | TestConfig JSON Schema — the shape the CAT module brings in the merge (incl. blueprint_binding) |
| blueprint-binding.schema.json | The consumption contract for tests-platform blueprints (BP-MODES-1 §5) |
| item-create.schema.json | Item ingest contract incl. the tags dimension map (unit/kc/complicator + bloom_process/bloom_knowledge/timss) |
| session-public.schema.json | Session surface incl. blueprint_conformance record (BP-MODES-1 §3.5) |
| bp-cat-verification-report.md | §7 verification evidence (merge-gate document) |
| simulation-lane-conventions.md | Lane semantics (C1–C5) + shared verification-report format — binds both platforms |
| BUILDLOG.md | Full build history at this commit |
| vendored-blueprint-schema.sha256 | Hash of the tests-platform Blueprint schema Ignite is built against — compare with yours to detect drift |

Spec of record: docs/design/blueprint-delivery-mode-semantics.md (BP-MODES-1),
canonical copy in tests-platform/docs/.
