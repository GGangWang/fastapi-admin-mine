import { afterEach, describe, expect, it, vi } from "vitest";
import {
  beijingPickerDate,
  beijingTime,
  dateTimeFormValue,
  formatDateTime,
} from "@/utils/dateTime";

afterEach(() => vi.unstubAllEnvs());

describe.each(["UTC", "Asia/Shanghai", "America/New_York"])("Beijing contract in %s", (zone) => {
  it("preserves API calendar values and converts source instants", () => {
    vi.stubEnv("TZ", zone);
    expect(formatDateTime("2026-11-01 00:00:00")).toBe("2026-11-01 00:00:00");
    expect(formatDateTime(new Date("2026-10-31T16:00:00Z"))).toBe("2026-11-01 00:00:00");
    expect(formatDateTime(Date.parse("2026-12-31T16:00:00Z"))).toBe("2027-01-01 00:00:00");
    expect(beijingTime(new Date("2026-10-31T16:00:00Z")).format("YYYYMM")).toBe("202611");
    const picker = beijingPickerDate(new Date("2026-10-31T16:00:00Z"));
    expect([picker.getFullYear(), picker.getMonth(), picker.getDate(), picker.getHours()]).toEqual([
      2026, 10, 1, 0,
    ]);
    expect(dateTimeFormValue("2026-11-01 00:00:00")).toBe("2026-11-01 00:00:00");
  });
});

it.each([
  "2026-10-16T02:00:00Z",
  "2026-10-16T10:00:00+08:00",
  "2026-10-16 10:00:00.123",
  "2026-02-29 00:00:00",
  "1792101600",
])("rejects non-contract form value %s", (value) => {
  expect(() => dateTimeFormValue(value)).toThrow(RangeError);
});

it("keeps missing fields empty", () => {
  expect(formatDateTime(null)).toBe("—");
  expect(formatDateTime(undefined)).toBe("—");
  expect(formatDateTime(0)).toBe("1970-01-01 08:00:00");
});
