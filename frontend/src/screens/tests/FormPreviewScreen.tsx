// A-033 Form preview — assembled item order + the actual-vs-target TIF plot
// (Recharts). Reads the form via the generated client.
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useGetForm } from "../../api/generated/endpoints/forms/forms";
import { Button, Card, Pill } from "../../components/ui";

export function FormPreviewScreen({
  formId,
  onWalk,
  onBack,
}: {
  formId: string;
  onWalk: () => void;
  onBack: () => void;
}) {
  const { data: form, isLoading, isError } = useGetForm(formId);

  if (isLoading) return <Card title="Form preview">Loading…</Card>;
  if (isError || !form)
    return (
      <Card title="Form preview">
        <Pill tone="warn">Could not load form {formId}.</Pill>
      </Card>
    );

  const chartData = form.tif.map((p) => ({
    theta: p.theta,
    target: Number(p.target.toFixed(3)),
    actual: Number(p.actual.toFixed(3)),
  }));
  const worstGap = Math.max(...form.tif.map((p) => Math.abs(p.gap)));

  return (
    <div className="space-y-5">
      <Card
        title="Form preview"
        subtitle={`Form ${form.id.slice(0, 8)} · ${form.item_ids.length} items · status ${form.status}`}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onBack}>
              ← Edit blueprint
            </Button>
            <Button onClick={onWalk}>Walk the form →</Button>
          </div>
        }
      >
        <div className="mb-3 flex items-center gap-2">
          <Pill tone={worstGap < 0.5 ? "ok" : "warn"}>
            worst |actual − target| = {worstGap.toFixed(3)}
          </Pill>
          <span className="text-sm text-ink-600">
            Test Information Function vs. blueprint target
          </span>
        </div>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="theta"
                type="number"
                label={{ value: "θ", position: "insideBottom", offset: -8 }}
                stroke="#94a3b8"
              />
              <YAxis
                label={{ value: "information", angle: -90, position: "insideLeft" }}
                stroke="#94a3b8"
              />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="target"
                name="target"
                stroke="#94a3b8"
                strokeDasharray="5 4"
                dot={{ r: 3 }}
              />
              <Line
                type="monotone"
                dataKey="actual"
                name="actual"
                stroke="#4f46e5"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="Assembled items" subtitle="Fixed linear order">
        <ol className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm text-ink-800 sm:grid-cols-3">
          {form.item_ids.map((id, i) => (
            <li key={id} className="flex gap-2 tabular-nums">
              <span className="w-6 text-right text-ink-400">{i + 1}.</span>
              <span className="font-medium">{id}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
