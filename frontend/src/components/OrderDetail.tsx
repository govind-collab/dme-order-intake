import { useState } from "react";

import { deleteOrder, messageOf, updateOrder, type FieldName, type Order } from "../api";
import { fieldChange, fieldViews, patientName } from "../fields";
import { FieldRow } from "./FieldRow";
import { StatusBadge } from "./StatusBadge";

interface OrderDetailProps {
  token: string;
  order: Order;
  /** Called with the order as the API returned it after a field was fixed. */
  onChanged: (order: Order) => void;
  onDeleted: (id: string) => void;
}

/** Show one order field by field, saved value next to what was read, with fix and delete. */
export function OrderDetail({ token, order, onChanged, onDeleted }: OrderDetailProps) {
  const [error, setError] = useState<string | null>(null);

  async function saveField(name: FieldName, text: string): Promise<boolean> {
    try {
      onChanged(await updateOrder(token, order.id, fieldChange(name, text)));
      setError(null);
      return true;
    } catch (error) {
      setError(messageOf(error));
      return false;
    }
  }

  async function remove() {
    if (!window.confirm("Delete this order? This cannot be undone.")) {
      return;
    }
    try {
      await deleteOrder(token, order.id);
      onDeleted(order.id);
    } catch (error) {
      setError(messageOf(error));
    }
  }

  return (
    <section className="detail">
      <header>
        <h2>{patientName(order)}</h2>
        <StatusBadge status={order.status} />
        <button type="button" className="danger" onClick={() => void remove()}>
          Delete order
        </button>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <table className="fields">
        <thead>
          <tr>
            <th>Field</th>
            <th>Saved on the order</th>
            <th>Read from the document</th>
            <th>Check</th>
            <th>Page</th>
            <th>Quote</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {fieldViews(order).map((view) => (
            <FieldRow key={view.name} view={view} onSave={(text) => saveField(view.name, text)} />
          ))}
        </tbody>
      </table>
      {order.source === "manual" && (
        <p className="muted">Typed in by hand, so there is no document reading to compare.</p>
      )}
    </section>
  );
}
