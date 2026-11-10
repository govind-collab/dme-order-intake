import { useEffect, useState } from "react";

import { listOrders, messageOf, type Order } from "../api";
import { OrderDetail } from "./OrderDetail";
import { OrderList } from "./OrderList";
import { UploadBox } from "./UploadBox";

interface WorkspaceProps {
  token: string;
  onSignOut: () => void;
}

/** Show the upload box, the reviewer's orders and the selected order side by side. */
export function Workspace({ token, onSignOut }: WorkspaceProps) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listOrders(token)
      .then(setOrders)
      .catch((error: unknown) => setError(messageOf(error)));
  }, [token]);

  const selected = orders.find((order) => order.id === selectedId) ?? null;

  function addOrder(order: Order) {
    setOrders((current) => [order, ...current]);
    setSelectedId(order.id);
  }

  function replaceOrder(order: Order) {
    setOrders((current) => current.map((each) => (each.id === order.id ? order : each)));
  }

  function removeOrder(id: string) {
    setOrders((current) => current.filter((order) => order.id !== id));
    setSelectedId(null);
  }

  return (
    <div className="workspace">
      <header className="topbar">
        <h1>DME order intake</h1>
        <button type="button" className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="columns">
        <aside>
          <UploadBox token={token} onUploaded={addOrder} />
          <OrderList orders={orders} selectedId={selectedId} onSelect={setSelectedId} />
        </aside>
        <main>
          {selected ? (
            <OrderDetail
              key={selected.id}
              token={token}
              order={selected}
              onChanged={replaceOrder}
              onDeleted={removeOrder}
            />
          ) : (
            <p className="muted">Upload a PDF or pick an order to review it.</p>
          )}
        </main>
      </div>
    </div>
  );
}
