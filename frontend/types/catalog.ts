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

export type SourceSystem = "ERP" | "MES" | "WMS" | "DATABASE" | "FILE" | "OTHER"
export type InternalDataType = "INVENTORY" | "CONSUMPTION" | "DEMAND" | "OPEN_SUPPLY"

export type MaterialReference = {
  id: string
  externalCode: string
  name: string
  baseUnit: string
}

export type InventorySnapshot = {
  id: string
  material: MaterialReference
  locationCode: string
  snapshotAt: string
  onHandQty: number
  availableQty: number
  reservedQty: number
  qualityHoldQty: number
  unit: string
  sourceSystem: SourceSystem
  sourceRecordRef: string
  syncJobId: string
}

export type ConsumptionSnapshot = {
  id: string
  material: MaterialReference
  bucketDate: string
  actualQty: number
  plannedQty: number
  unit: string
  sourceSystem: SourceSystem
  sourceRecordRef: string
  syncJobId: string
}

export type MaterialDemand = {
  id: string
  material: MaterialReference
  requiredAt: string
  requiredQty: number
  unit: string
  sourceType: string
  sourceSystem: SourceSystem
  sourceRecordRef: string
  syncJobId: string
}

export type OpenSupplySnapshot = {
  id: string
  material: MaterialReference
  orderNo: string
  orderLineNo: string
  orderedQty: number
  receivedQty: number
  openQty: number
  unit: string
  expectedAt: string
  status: string
  sourceSystem: SourceSystem
  sourceRecordRef: string
  syncJobId: string
}

export type InternalImportResult = {
  jobId: string
  dataType: InternalDataType
  sourceSystem: SourceSystem
  status: "SUCCEEDED" | "SUCCEEDED_WITH_ERRORS" | "FAILED"
  fileName: string
  totalRows: number
  createdRows: number
  failedRows: number
  errors: ImportRowError[]
  replayed: boolean
}

export type WorkspaceView = "dashboard" | "materials" | "suppliers" | "operations" | "imports"
