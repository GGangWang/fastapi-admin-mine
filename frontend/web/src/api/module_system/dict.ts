import { request } from "@utils";

const API_PATH = "/system/dict";

const DictAPI = {
  getTypes(dict_types: string[], mode: "flat" | "tree" = "flat") {
    return request<ApiResponse<Record<string, DictDataTable[]>>>({
      url: `${API_PATH}/types`,
      method: "post",
      data: { dict_types, mode },
    });
  },
  listNodes(query: DictNodeQuery) {
    return request<ApiResponse<PageResult<DictNode>>>({
      url: `${API_PATH}/nodes`,
      method: "get",
      params: query,
    });
  },
  node(key: DictNodeId) {
    return request<ApiResponse<DictNode>>({
      url: `${API_PATH}/nodes/${encodeURIComponent(key)}`,
      method: "get",
    });
  },
  ancestors(key: DictNodeId) {
    return request<ApiResponse<DictNode[]>>({
      url: `${API_PATH}/nodes/${encodeURIComponent(key)}/ancestors`,
      method: "get",
    });
  },
  saveNode(body: DictNodeWrite, key?: DictNodeId) {
    return request<ApiResponse<DictNode>>({
      url: key === undefined ? `${API_PATH}/nodes` : `${API_PATH}/nodes/${encodeURIComponent(key)}`,
      method: key === undefined ? "post" : "put",
      data: body,
    });
  },
  deleteNodes(keys: DictNodeId[]) {
    return request<ApiResponse>({ url: `${API_PATH}/nodes`, method: "delete", data: keys });
  },
  children(key: DictNodeId) {
    return request<ApiResponse<DictNode[]>>({
      url: `${API_PATH}/children/${encodeURIComponent(key)}`,
      method: "get",
    });
  },
  tree(dictType: string) {
    return request<ApiResponse<DictTreeNode[]>>({
      url: `${API_PATH}/tree/${encodeURIComponent(dictType)}`,
      method: "get",
    });
  },
  refreshCache() {
    return request<ApiResponse>({ url: `${API_PATH}/cache/refresh`, method: "post" });
  },
  exportNodes(query: DictNodeQuery, tree = false) {
    return request<Blob>({
      url: `${API_PATH}/export`,
      method: "post",
      params: { tree },
      data: query,
      responseType: "blob",
    });
  },
  listDictType(query: DictPageQuery) {
    return request<ApiResponse<PageResult<DictTable>>>({
      url: `${API_PATH}/type/list`,
      method: "get",
      params: query,
    });
  },

  optionDictType() {
    return request<ApiResponse<DictTable[]>>({
      url: `${API_PATH}/type/optionselect`,
      method: "get",
    });
  },

  getInitDict(dict_type: string) {
    return request<ApiResponse<DictDataTable[]>>({
      url: `${API_PATH}/data/info/${dict_type}`,
      method: "get",
    });
  },
};

export default DictAPI;

export type DictNodeId = number | string;
export interface DictNodeWrite {
  parent_id: number | null;
  dict_name: string;
  dict_code: string;
  dict_sort: number;
  status: number;
  is_default: boolean;
  css_class?: string | null;
  list_class?: string | null;
  description?: string | null;
}
export interface DictNode extends Omit<BaseType, "id">, Omit<DictNodeWrite, "parent_id"> {
  id: DictNodeId;
  parent_id: DictNodeId | null;
  dict_level: number;
  dict_type: string;
  source: "database" | "enum";
  readonly: boolean;
  has_children: boolean;
}
export interface DictTreeNode extends DictNode {
  children: DictTreeNode[];
}
export interface DictNodeQuery extends PageQuery {
  parent_id?: DictNodeId;
  dict_type?: string;
  dict_name?: string;
  dict_code?: string;
  source?: "database" | "enum";
  status?: number;
}

export interface DictPageQuery extends PageQuery {
  dict_name?: string;
  dict_type?: string;
  status?: number;
}

export interface DictDataPageQuery extends PageQuery {
  dict_label?: string;
  dict_type?: string;
  dict_type_id?: number;
  status?: number;
}

export interface DictTable extends Omit<BaseType, "id"> {
  id?: DictNodeId;
  source?: "database" | "enum";
  readonly?: boolean;
  dict_name?: string;
  dict_type?: string;
  status?: number;
  description?: string;
}

export interface DictForm extends BaseFormType {
  dict_name?: string;
  dict_type?: string;
  status?: number;
  description?: string;
}

export interface DictDataTable extends Omit<BaseType, "id"> {
  children?: DictDataTable[];
  dict_code?: string;
  dict_name?: string;
  id?: DictNodeId;
  source?: "database" | "enum";
  readonly?: boolean;
  dict_sort?: number;
  dict_label?: string;
  dict_value?: string;
  dict_type_id?: DictNodeId;
  dict_type?: string;
  css_class?: string;
  list_class?: string;
  is_default?: boolean;
  status?: number;
  description?: string;
}

export interface DictDataForm extends BaseFormType {
  dict_sort?: number;
  dict_label?: string;
  dict_value?: string;
  dict_type_id?: number;
  dict_type?: string;
  css_class?: string;
  list_class?: string;
  is_default?: boolean;
  status?: number;
  description?: string;
}
