import type {
  ChatHistoryMessage,
  ChatRequest,
  ChatResponse,
  KnowledgeBaseStatus,
} from "@/lib/chat-types"

const REQUEST_TIMEOUT_MS = 30_000

export const knowledgeBaseStatus: KnowledgeBaseStatus = {
  label: "Knowledge base ready",
  ready: true,
  documentCount: 4,
}

export const suggestedQuestions = [
  "What are some simple ways to improve sleep?",
  "When should I seek medical help for a fever?",
  "How can I maintain a healthy blood pressure?",
  "What are common signs of dehydration?",
] as const

export class ChatApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number
  ) {
    super(message)
    this.name = "ChatApiError"
  }
}

export async function askHealthcareGuide(
  request: ChatRequest
): Promise<ChatResponse> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL

  if (!apiBaseUrl) {
    throw new ChatApiError("Backend URL is not configured.")
  }

  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new ChatApiError(await friendlyErrorMessage(response), response.status)
    }

    return (await response.json()) as ChatResponse
  } catch (error) {
    if (error instanceof ChatApiError) {
      throw error
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ChatApiError(
        "The request timed out. Please check that the backend is running and try again."
      )
    }
    throw new ChatApiError(
      "Unable to reach the backend. Please make sure the FastAPI server is running."
    )
  } finally {
    window.clearTimeout(timeoutId)
  }
}

export function toBackendHistory(
  messages: Array<{ role: string; content: string }>
): ChatHistoryMessage[] {
  return messages
    .filter(
      (message): message is ChatHistoryMessage =>
        (message.role === "user" || message.role === "assistant") &&
        message.content.trim().length > 0
    )
    .slice(-6)
    .map((message) => ({
      role: message.role,
      content: message.content,
    }))
}

async function friendlyErrorMessage(response: Response) {
  if (response.status === 503) {
    return "The healthcare guide is temporarily unavailable. Please try again shortly."
  }

  if (response.status === 422) {
    return "Please check your question and try again."
  }

  return "Something went wrong while preparing the response. Please try again."
}
