// Read-only item-pool viewer — browse the simulated bank(s): IRT params, tags, and
// synthetic content. Lets you see the demo data behind assembly.
import { useState } from "react";

import { useGetPoolCatalog, useGetPoolItems } from "../../api/generated/endpoints/pool/pool";
import { Card, Pill, Select, Spinner, TextInput } from "../../components/ui";

export function PoolBrowserScreen() {
  const catalog = useGetPoolCatalog();
  const [poolId, setPoolId] = useState("demo_mixed");
  const [q, setQ] = useState("");
  const pool = useGetPoolItems({ pool_id: poolId });

  const items = pool.data?.items ?? [];
  const needle = q.trim().toLowerCase();
  const shown = needle
    ? items.filter((it) => {
        const hay = [
          it.item_id,
          it.stem ?? "",
          ...Object.values(it.tags ?? {}),
        ]
          .join(" ")
          .toLowerCase();
        return hay.includes(needle);
      })
    : items;

  return (
    <Card
      title="Item pools (simulated)"
      subtitle="Browse the calibrated demo bank — IRT params, tags, and synthetic content."
      actions={
        <Select value={poolId} onChange={(e) => setPoolId(e.target.value)} className="w-64">
          {(catalog.data?.pools ?? []).map((p) => (
            <option key={p.pool_id} value={p.pool_id}>
              {p.title} — {p.n_items} items
            </option>
          ))}
        </Select>
      }
    >
      {pool.isLoading || !pool.data ? (
        <Spinner label="Loading pool…" />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Pill tone="info">{pool.data.model}</Pill>
            <Pill>{pool.data.n_items} items</Pill>
            {Object.entries(pool.data.tag_summary?.domain ?? {}).map(([d, n]) => (
              <Pill key={d} tone="neutral">{d}: {n}</Pill>
            ))}
            <TextInput
              className="ml-auto w-64"
              placeholder="filter by id / stem / tag…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <p className="mb-2 text-xs text-ink-400">
            showing {shown.length} of {items.length}
            {pool.data.provenance ? ` · ${pool.data.provenance}` : ""}
          </p>
          <div className="max-h-[28rem] overflow-auto rounded-lg border border-ink-100">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-ink-50 text-ink-600">
                <tr>
                  <th className="px-3 py-1.5 text-left">item</th>
                  <th className="px-3 py-1.5 text-right">a</th>
                  <th className="px-3 py-1.5 text-right">d</th>
                  <th className="px-3 py-1.5 text-right" title="difficulty b = -d/a">b</th>
                  <th className="px-3 py-1.5 text-right">c</th>
                  <th className="px-3 py-1.5 text-left">KC</th>
                  <th className="px-3 py-1.5 text-left">Bloom</th>
                  <th className="px-3 py-1.5 text-left">domain</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((it) => (
                  <tr key={it.item_id} className="border-t border-ink-100 tabular-nums">
                    <td className="px-3 py-1.5 font-medium">{it.item_id}</td>
                    <td className="px-3 py-1.5 text-right">{it.a}</td>
                    <td className="px-3 py-1.5 text-right">{it.d}</td>
                    <td className="px-3 py-1.5 text-right">{it.b.toFixed(3)}</td>
                    <td className="px-3 py-1.5 text-right">{it.c}</td>
                    <td className="px-3 py-1.5">{it.tags?.KC ?? "—"}</td>
                    <td className="px-3 py-1.5">{it.tags?.Bloom ?? "—"}</td>
                    <td className="px-3 py-1.5">{it.tags?.domain ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
