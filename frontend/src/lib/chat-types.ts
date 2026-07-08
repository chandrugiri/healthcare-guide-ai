export type ChatRole = "user" | "assistant"

export type FeedbackValue = "helpful" | "not-helpful"

export type SourceCitation = {
  id: string
  filename: string
  page: number
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
}

export type ChatRequest = {
  message: string
  history: ChatMessage[]
}

export type ChatResponse = {
  answer: string
  sources: SourceCitation[]
  isSafetyResponse?: boolean
  isInsufficientEvidence?: boolean
}

export type KnowledgeBaseStatus = {
  label: string
  ready: boolean
  documentCount: number
}
