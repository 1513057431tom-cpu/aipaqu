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

export type SignalType = "PRICE" | "SPECIFICATION" | "AVAILABILITY" | "LEAD_TIME" | "SUPPLIER_EVENT"

export type MonitoringSource = {
  id: string
  name: string
  targetUrl: string
  allowedDomain: string
  scheduleMinutes: number
  signalType: SignalType
  materialId: string | null
  supplierId: string | null
  extractionSelector: string
  status: "ACTIVE" | "PAUSED"
  lastCollectedAt: string | null
  lastCollectionStatus: "SUCCEEDED" | "FAILED" | "WAITING_HUMAN" | null
  createdAt: string
  updatedAt: string
}

export type CollectionJob = {
  id: string
  sourceId: string
  status: "SUCCEEDED" | "FAILED" | "WAITING_HUMAN"
  startedAt: string
  finishedAt: string
  statusCode: number | null
  documentId: string | null
  contentChanged: boolean
  errorCode: string | null
  errorMessage: string | null
}

export type EvidenceDocument = {
  id: string
  sourceId: string
  collectionJobId: string
  finalUrl: string
  statusCode: number
  contentType: string
  title: string
  extractedText: string
  contentDigest: string
  previousContentDigest: string | null
  changed: boolean
  collectedAt: string
}

export type ExternalSignal = {
  id: string
  sourceId: string
  documentId: string
  signalType: SignalType
  materialId: string | null
  supplierId: string | null
  occurredAt: string
  observedAt: string
  previousValue: string
  currentValue: string
  confidence: number
  evidenceRef: string
  reviewStatus: "PENDING" | "CONFIRMED" | "DISMISSED"
  reviewedBy: string | null
  reviewedAt: string | null
}

export type CollectionResult = {
  job: CollectionJob
  document: EvidenceDocument | null
  signal: ExternalSignal | null
}

export type WorkspaceView =
  | "dashboard"
  | "materials"
  | "suppliers"
  | "operations"
  | "imports"
  | "monitoring"
  | "signals"
