export type PublicUser = {
  id: string
  email: string
  role: "ADMIN" | "EDITOR"
  workspaceId: string
}

export type Pagination = {
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export type Material = {
  id: string
  workspaceId: string
  externalCode: string
  name: string
  specification: string
  category: string
  baseUnit: string
  safetyStockQty: number
  leadTimeDays: number
  status: "ACTIVE" | "INACTIVE" | "ARCHIVED"
  createdAt: string
  updatedAt: string
}

export type Supplier = {
  id: string
  workspaceId: string
  externalCode: string
  name: string
  website: string | null
  country: string
  status: "ACTIVE" | "INACTIVE" | "ARCHIVED"
  createdAt: string
  updatedAt: string
}

export type ListEnvelope<T> = {
  data: T[]
  pagination: Pagination
}

export type ImportRowError = {
  row: number
  code: string
  message: string
}

export type ImportResult = {
  jobId: string
  entityType: "MATERIAL" | "SUPPLIER"
  status: "SUCCEEDED" | "SUCCEEDED_WITH_ERRORS" | "FAILED"
  fileName: string
  totalRows: number
  createdRows: number
  failedRows: number
  errors: ImportRowError[]
}

export type WorkspaceView = "dashboard" | "materials" | "suppliers" | "imports"
