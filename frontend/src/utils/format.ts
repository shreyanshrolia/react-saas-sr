export function formatINR(amount: number): string {
  const a = Number(amount) || 0;
  return `₹${a.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const day = String(d.getDate()).padStart(2, "0");
    const month = d.toLocaleString("en-IN", { month: "short" });
    const year = d.getFullYear();
    return `${day} ${month} ${year}`;
  } catch {
    return iso;
  }
}

export function formatMonth(month: string): string {
  // YYYY-MM
  const [y, m] = month.split("-");
  try {
    const d = new Date(parseInt(y, 10), parseInt(m, 10) - 1, 1);
    return d.toLocaleString("en-IN", { month: "long", year: "numeric" });
  } catch {
    return month;
  }
}

export function currentMonthKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function daysUntil(iso?: string | null): number {
  if (!iso) return 0;
  try {
    const d = new Date(iso).getTime();
    const now = Date.now();
    return Math.max(0, Math.ceil((d - now) / 86400000));
  } catch {
    return 0;
  }
}
