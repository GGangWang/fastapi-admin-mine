import { request } from "@utils";

export interface HttpLog {
  id: string;
  started_at: string;
  service: string;
  business?: string;
  operator?: string;
  correlation_id?: string;
  method: string;
  url: string;
  status_code?: number;
  result: string;
  duration_ms: number;
  request_bytes: number;
  response_bytes: number;
  request_headers?: string;
  response_headers?: string;
  request_body_state: string;
  response_body_state: string;
  error?: string;
}
export interface HttpBodyPage {
  text: string;
  offset: number;
  next_offset: number;
  total_bytes: number;
  has_next: boolean;
  state: string;
}
const base = "/system/http-log";
export default {
  months: () => request<ApiResponse<string[]>>({ url: `${base}/months`, method: "get" }),
  list: (params: Record<string, unknown>) =>
    request<ApiResponse<PageResult<HttpLog>>>({ url: `${base}/list`, method: "get", params }),
  detail: (month: string, id: string) =>
    request<ApiResponse<HttpLog>>({ url: `${base}/${month}/${id}`, method: "get" }),
  body: (month: string, id: string, side: string, offset: number) =>
    request<ApiResponse<HttpBodyPage>>({
      url: `${base}/${month}/${id}/body/${side}`,
      method: "get",
      params: { offset },
    }),
  ticket: (month: string, id: string, side: string) =>
    request<ApiResponse<{ ticket: string }>>({
      url: `${base}/${month}/${id}/ticket/${side}`,
      method: "post",
    }),
};
