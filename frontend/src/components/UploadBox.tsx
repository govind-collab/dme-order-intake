import { useState } from "react";

import { messageOf, uploadOrder, type Order } from "../api";

interface UploadBoxProps {
  token: string;
  /** Called with the order the API created from the PDF. */
  onUploaded: (order: Order) => void;
}

/** Take a PDF by drag and drop or file picker and upload it as a new order. */
export function UploadBox({ token, onUploaded }: UploadBoxProps) {
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(file: File | undefined) {
    if (!file || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onUploaded(await uploadOrder(token, file));
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className={dragging ? "dropzone dragging" : "dropzone"}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        void send(event.dataTransfer.files[0]);
      }}
    >
      <p>{busy ? "Reading the PDF, this takes a few seconds…" : "Drop an order PDF here"}</p>
      <label className="button">
        Choose a PDF
        <input
          type="file"
          accept="application/pdf"
          hidden
          disabled={busy}
          onChange={(event) => {
            void send(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
