// Small, typed UI primitives shared by the Tests screens. Token-driven (see
// tailwind.config.js). Intentionally minimal — no component library dependency.
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

export function Card({
  title,
  subtitle,
  children,
  actions,
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-ink-200 bg-white shadow-sm">
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-ink-100 px-5 py-4">
          <div>
            {title && <h2 className="text-lg font-semibold text-ink-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-ink-600">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
};

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  const styles: Record<string, string> = {
    primary:
      "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-ink-200 disabled:text-ink-400",
    secondary:
      "border border-ink-200 bg-white text-ink-800 hover:bg-ink-50 disabled:text-ink-400",
    ghost: "text-brand-600 hover:bg-brand-50 disabled:text-ink-400",
  };
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink-800">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-400">{hint}</span>}
    </label>
  );
}

const inputCls =
  "mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-sm text-ink-900 outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={inputCls} {...props} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={inputCls} {...props} />;
}

export function Pill({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "info";
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    neutral: "bg-ink-100 text-ink-600",
    ok: "bg-emerald-100 text-emerald-800",
    warn: "bg-amber-100 text-amber-800",
    info: "bg-brand-100 text-brand-700",
  };
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Alert({
  tone,
  title,
  children,
}: {
  tone: "error" | "warn" | "info";
  title: string;
  children?: ReactNode;
}) {
  const tones: Record<string, string> = {
    error: "border-rose-200 bg-rose-50 text-rose-800",
    warn: "border-amber-200 bg-amber-50 text-amber-800",
    info: "border-brand-200 bg-brand-50 text-brand-700",
  };
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${tones[tone]}`} role="alert">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 text-[13px] opacity-90">{children}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-600">
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-ink-200 border-t-brand-600"
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
