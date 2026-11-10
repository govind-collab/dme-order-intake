import { useState, type FormEvent } from "react";

import type { FieldView } from "../fields";
import { StatusBadge } from "./StatusBadge";

interface FieldRowProps {
  view: FieldView;
  /** Saves the typed text; resolves to true when the API accepted it. */
  onSave: (text: string) => Promise<boolean>;
}

/** Show one field's saved value, reading, check, page and quote, with an inline fix form. */
export function FieldRow({ view, onSave }: FieldRowProps) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const { label, saved, report } = view;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (await onSave(text)) {
      setEditing(false);
    }
  }

  return (
    <tr>
      <th scope="row">{label}</th>
      <td>
        {editing ? (
          <form className="fix" onSubmit={handleSubmit}>
            <input
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={view.name === "patient_dob" ? "YYYY-MM-DD" : "empty clears the field"}
              aria-label={`New ${label}`}
            />
            <button type="submit">Save</button>
            <button type="button" className="secondary" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </form>
        ) : (
          (saved ?? <span className="muted">not saved</span>)
        )}
      </td>
      <td>{report?.value_as_read ?? "—"}</td>
      <td>
        {report ? <StatusBadge status={report.status} /> : "—"}
        {report?.reason && <div className="reason">{report.reason}</div>}
      </td>
      <td>{report?.page ?? "—"}</td>
      <td className="quote">{report?.quote ?? "—"}</td>
      <td>
        {!editing && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setText(saved ?? "");
              setEditing(true);
            }}
          >
            Fix
          </button>
        )}
      </td>
    </tr>
  );
}
