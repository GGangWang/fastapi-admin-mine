import { request } from "@utils";

// ==================== 操作日志 ====================

const OP_API = "/system/log/operation";

const OperationLogAPI = {
  months() {
    return request<ApiResponse<string[]>>({ url: `${OP_API}/months`, method: "get" });
  },
  list(query: OperationLogPageQuery) {
    return request<ApiResponse<PageResult<OperationLogTable>>>({
      url: `${OP_API}/list`,
      method: "get",
      params: query,
    });
  },

  detail(id: string, month: string) {
    return request<ApiResponse<OperationLogTable>>({
      url: `${OP_API}/detail/${id}`,
      params: { month },
      method: "get",
    });
  },

  delete(body: string[], month: string) {
    return request<ApiResponse>({
      url: `${OP_API}/delete`,
      method: "delete",
      params: { month },
      data: body,
    });
  },

  export(query: OperationLogPageQuery) {
    return request<Blob>({
      url: `${OP_API}/export`,
      params: { month: query.month },
      method: "post",
      data: query,
      responseType: "blob",
    });
  },
};

export default OperationLogAPI;

export interface OperationLogPageQuery extends PageQuery, UserByQueryParams {
  month: string;
  order_by?: string;
  request_path?: string;
  request_method?: string;
  username?: string;
  status?: number;
  request_ip?: string;
}

export interface OperationLogTable {
  id: string;
  username: string;
  status?: number;
  description?: string;
  request_path: string;
  request_method: string;
  request_payload?: Record<string, unknown> | string;
  response_code: number;
  response_json?: Record<string, unknown> | string;
  process_time?: string;
  created_time?: string;
  request_ip?: string;
}

// ==================== 登录日志 ====================

const LOGIN_API = "/system/log/login";

export const LoginLogAPI = {
  months() {
    return request<ApiResponse<string[]>>({ url: `${LOGIN_API}/months`, method: "get" });
  },
  list(query: LoginLogPageQuery) {
    return request<ApiResponse<PageResult<LoginLogTable>>>({
      url: `${LOGIN_API}/list`,
      method: "get",
      params: query,
    });
  },

  detail(id: string, month: string) {
    return request<ApiResponse<LoginLogTable>>({
      url: `${LOGIN_API}/detail/${id}`,
      params: { month },
      method: "get",
    });
  },

  delete(body: string[], month: string) {
    return request<ApiResponse>({
      url: `${LOGIN_API}/delete`,
      method: "delete",
      params: { month },
      data: body,
    });
  },
};

export interface LoginLogPageQuery extends PageQuery, UserByQueryParams {
  month: string;
  order_by?: string;
  username?: string;
  status?: number;
}

export interface LoginLogTable {
  id: string;
  username: string;
  status: number;
  login_ip?: string;
  login_location?: string;
  request_os?: string;
  request_browser?: string;
  msg?: string;
  created_time?: string;
}
