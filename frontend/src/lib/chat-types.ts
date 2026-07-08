export type ChatRole = "user" | "assistant"

export type FeedbackValue = "helpful" | "not-helpful"

export type SourceCitation = {
  id: number
  filename: string
  page: number
  contentType: "text" | "table"
  tableIndex: number | null
  similarityScore: number
  excerpt: string
}

export type ChatMessage = {
  id: string
  role: ChatRole
  content: string
  sources?: SourceCitation[]
  feedback?: FeedbackValue
  isSafetyResponse?: boolean
  isInsufficientEvidence?: boolean
  safetyNotice?: string | null
  requestId?: string
}

export type ChatHistoryMessage = {
  role: ChatRole
  content: string
}

export type ChatRequest = {
  question: string
  history: ChatHistoryMessage[]
}

export type ChatSource = {
  source_id: number
  source_file: string
  page_number: number
  content_type: "text" | "table"
  table_index: number | null
  similarity_score: number
  excerpt: string
}

export type ChatResponse = {
  answer: string
  sources: ChatSource[]
  insufficient_context: boolean
  safety_notice: string | null
  request_id: string
}

export type KnowledgeBaseStatus = {
  label: string
  ready: boolean
  documentCount: number
}
