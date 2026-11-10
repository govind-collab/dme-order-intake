import { describe, expect, it } from "vitest";

import type { FieldReport, Order } from "./api";
import { fieldChange, fieldViews, patientName } from "./fields";

const okReport = (value: string): FieldReport => ({
  status: "ok",
  value_as_read: value,
  reason: null,
  page: 1,
  quote: value,
});

const uploaded: Order = {
  id: "order-1",
  status: "needs_review",
  source: "upload",
  patient_first_name: "Ada",
  patient_last_name: "Lovelace",
  patient_dob: "1985-12-10",
  provider_name: "Grace Hopper",
  provider_npi: null,
  field_report: {
    patient_first_name: okReport("Ada"),
    patient_last_name: okReport("Lovelace"),
    patient_dob: okReport("12/10/1985"),
    provider_name: okReport("Grace Hopper"),
    provider_npi: {
      status: "invalid",
      value_as_read: "1234567890",
      reason: "NPI fails the check digit",
      page: 1,
      quote: "NPI: 1234567890",
    },
  },
  created_at: "2026-11-10T20:00:00Z",
  updated_at: "2026-11-10T20:00:00Z",
};

describe("fieldViews", () => {
  it("pairs a refused value with what the document said", () => {
    const npi = fieldViews(uploaded).find((view) => view.name === "provider_npi");

    expect(npi?.saved).toBeNull();
    expect(npi?.report?.value_as_read).toBe("1234567890");
    expect(npi?.report?.reason).toBe("NPI fails the check digit");
  });

  it("lists all five fields in reading order", () => {
    expect(fieldViews(uploaded).map((view) => view.name)).toEqual([
      "patient_first_name",
      "patient_last_name",
      "patient_dob",
      "provider_name",
      "provider_npi",
    ]);
  });

  it("has no reading for an order typed in by hand", () => {
    const manual: Order = { ...uploaded, source: "manual", field_report: null };

    expect(fieldViews(manual).every((view) => view.report === null)).toBe(true);
  });
});

describe("fieldChange", () => {
  it("trims the typed value", () => {
    expect(fieldChange("provider_npi", " 1234567893 ")).toEqual({ provider_npi: "1234567893" });
  });

  it("clears the field when the box is empty", () => {
    expect(fieldChange("patient_dob", "   ")).toEqual({ patient_dob: null });
  });
});

describe("patientName", () => {
  it("joins the saved parts of the name", () => {
    expect(patientName({ ...uploaded, patient_last_name: null })).toBe("Ada");
  });

  it("says when no name was saved", () => {
    expect(patientName({ ...uploaded, patient_first_name: null, patient_last_name: null })).toBe(
      "Name not saved",
    );
  });
});
