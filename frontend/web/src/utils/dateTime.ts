import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";

dayjs.extend(utc);
dayjs.extend(timezone);

export const DATE_TIME_FORMAT = "YYYY-MM-DD HH:mm:ss";
const WALL_TIME = /^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?$/;

/** API strings are Beijing calendar values; Date/numeric values are instants. */
export function beijingTime(value?: dayjs.ConfigType): dayjs.Dayjs {
  if (typeof value === "string" && WALL_TIME.test(value)) {
    return dayjs.utc(value.replace(" ", "T")).tz("Asia/Shanghai", true);
  }
  return dayjs(value).tz("Asia/Shanghai");
}

export function formatDateTime(value?: dayjs.ConfigType, format = DATE_TIME_FORMAT): string {
  if (value === undefined || value === null || value === "") return "—";
  const parsed = beijingTime(value);
  return parsed.isValid() ? parsed.format(format) : String(value);
}

/** Validate form/calendar values without converting them through the browser zone. */
export function dateTimeFormValue(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value) || formatDateTime(value) !== value) {
    throw new RangeError("时间格式必须为 YYYY-MM-DD HH:mm:ss（北京时间）");
  }
  return value;
}

/** Element Plus uses local Date components; this is a calendar carrier, not an instant. */
export function beijingPickerDate(value: dayjs.ConfigType = new Date()): Date {
  const parts = formatDateTime(value).match(/\d+/g)!.map(Number);
  return new Date(parts[0]!, parts[1]! - 1, parts[2]!, parts[3]!, parts[4]!, parts[5]!);
}
