import type { Order } from "../api";
import { patientName } from "../fields";
import { StatusBadge } from "./StatusBadge";

interface OrderListProps {
  orders: Order[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** List the reviewer's orders, newest first, with their status. */
export function OrderList({ orders, selectedId, onSelect }: OrderListProps) {
  if (orders.length === 0) {
    return <p className="muted">No orders yet.</p>;
  }
  return (
    <ul className="order-list">
      {orders.map((order) => (
        <li key={order.id}>
          <button
            type="button"
            className={order.id === selectedId ? "order selected" : "order"}
            onClick={() => onSelect(order.id)}
          >
            <span>{patientName(order)}</span>
            <StatusBadge status={order.status} />
            <small className="muted">
              {order.source} · {new Date(order.created_at).toLocaleString()}
            </small>
          </button>
        </li>
      ))}
    </ul>
  );
}
