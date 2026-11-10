import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, errorMessage, listOrders, uploadOrder } from "./api";

/** Replace fetch with one that answers every call with this status and body. */
function answerWith(status: number, body: unknown) {
  const fetchMock = vi.fn(
    async () => new Response(JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("errorMessage", () => {
  it("uses a plain detail as is", () => {
    expect(errorMessage({ detail: "File is not a PDF" }, 415)).toBe("File is not a PDF");
  });

  it("names the field for each validation error", () => {
    const body = {
      detail: [
        { loc: ["body", "provider_npi"], msg: "Value error, NPI fails the check digit" },
        { loc: ["body", "patient_dob"], msg: "Value error, date must be a YYYY-MM-DD string" },
      ],
    };

    expect(errorMessage(body, 422)).toBe(
      "provider_npi: Value error, NPI fails the check digit; " +
        "patient_dob: Value error, date must be a YYYY-MM-DD string",
    );
  });

  it("falls back to the status code", () => {
    expect(errorMessage(null, 502)).toBe("Request failed (502)");
  });
});

describe("request", () => {
  it("sends the bearer token", async () => {
    const fetchMock = answerWith(200, []);

    await listOrders("token-123");

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer token-123");
  });

  it("throws ApiError with the API's message when refused", async () => {
    answerWith(429, { detail: "Upload limit of 100 per 24 hours reached" });

    const upload = uploadOrder("token-123", new File(["%PDF-"], "order.pdf"));

    await expect(upload).rejects.toEqual(
      new ApiError(429, "Upload limit of 100 per 24 hours reached"),
    );
  });

  it("sends the PDF as multipart form data", async () => {
    const fetchMock = answerWith(201, {});

    await uploadOrder("token-123", new File(["%PDF-"], "order.pdf"));

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url.endsWith("/orders/upload")).toBe(true);
    expect(init.body).toBeInstanceOf(FormData);
  });
});
