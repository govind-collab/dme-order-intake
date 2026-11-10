/**
 * Logic for showing and fixing order fields: pairing each saved value with its reading.
 */

import type { FieldName, FieldReport, Order, OrderChanges } from "./api";

/** One order field as the review table shows it. */
export interface FieldView {
  name: FieldName;
  label: string;
  /** The checked value stored on the order, or null when nothing passed. */
  saved: string | null;
  /** What the document said, or null for orders typed in by hand. */
  report: FieldReport | null;
}

/** The order fields in the order a reviewer reads them. */
export const FIELDS: { name: FieldName; label: string }[] = [
  { name: "patient_first_name", label: "Patient first name" },
  { name: "patient_last_name", label: "Patient last name" },
  { name: "patient_dob", label: "Date of birth" },
  { name: "provider_name", label: "Ordering provider" },
  { name: "provider_npi", label: "Provider NPI" },
];

/** Return one view per field, pairing the saved value with what the document said. */
export function fieldViews(order: Order): FieldView[] {
  return FIELDS.map(({ name, label }) => ({
    name,
    label,
    saved: order[name],
    report: order.field_report?.[name] ?? null,
  }));
}

/** Return the change for one field typed in by hand; an empty box clears the field. */
export function fieldChange(name: FieldName, text: string): OrderChanges {
  const value = text.trim();
  return { [name]: value === "" ? null : value };
}

/** Return the patient's saved name for lists and headings, or a placeholder. */
export function patientName(order: Order): string {
  const name = [order.patient_first_name, order.patient_last_name].filter(Boolean).join(" ");
  return name || "Name not saved";
}
