import type { FieldStatus, OrderStatus } from "../api";

interface StatusBadgeProps {
  status: OrderStatus | FieldStatus;
}

/** Show an order or field status as a coloured label. */
export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`badge ${status}`}>{status.replace("_", " ")}</span>;
}
