import { request } from "@utils";

// API 前缀来自分系统包 module_xxx → /xxx
// 对齐 module_example/demo：业务接口固定为 /{prefix}/{module_name}
const API_PATH = "/demo/test_demo_base";

const TestDemoBaseAPI = {
  listTestDemoBase(query: TestDemoBasePageQuery) {
    return request<ApiResponse<PageResult<TestDemoBaseTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailTestDemoBase(query: number) {
    return request<ApiResponse<TestDemoBaseTable>>({
      url: `${API_PATH}/detail/${query}`,
      method: "get",
    });
  },

  createTestDemoBase(body: TestDemoBaseForm) {
    return request<ApiResponse>({
      url: `${API_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  updateTestDemoBase(id: number, body: TestDemoBaseForm) {
    return request<ApiResponse>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: body,
    });
  },

  deleteTestDemoBase(body: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "delete",
      data: body,
    });
  },

  batchTestDemoBase(body: BatchType) {
    return request<ApiResponse>({
      url: `${API_PATH}/status/batch`,
      method: "patch",
      data: body,
    });
  },

  exportTestDemoBase(body: TestDemoBasePageQuery) {
    return request<Blob>({
      url: `${API_PATH}/export`,
      method: "post",
      data: body,
      responseType: "blob",
    });
  },

  downloadTemplateTestDemoBase() {
    return request<Blob>({
      url: `${API_PATH}/download/template`,
      method: "post",
      responseType: "blob",
    });
  },

  importTestDemoBase(body: FormData) {
    return request<ApiResponse>({
      url: `${API_PATH}/import`,
      method: "post",
      data: body,
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },
};

export default TestDemoBaseAPI;

// ------------------------------
// TS 类型声明
// ------------------------------

/** 列表查询参数 */
export interface TestDemoBasePageQuery extends PageQuery, UserByQueryParams {
  user_name?: string;
  user_sex?: number;
}

/** 列表展示项 */
export interface TestDemoBaseTable extends BaseType {
  user_name?: string;
  user_sex?: number;
}

/** 新增/修改表单参数 */
export interface TestDemoBaseForm extends BaseFormType {
  user_name?: string;
  user_sex?: number;
}
