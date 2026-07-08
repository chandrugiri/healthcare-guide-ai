"use client"

import { useState } from "react"

import type { ChatMessage, FeedbackValue } from "@/lib/chat-types"
import {
  askMockHealthcareGuide,
  knowledgeBaseStatus,
  suggestedQuestions,
} from "@/lib/mock-api"
import { ChatHeader } from "./chat-header"
import { ErrorBanner } from "./error-banner"
import { MessageInput } from "./message-input"
import { MessageList } from "./message-list"
import { SafetyDisclaimer } from "./safety-disclaimer"
import { WelcomeState } from "./welcome-state"

const requestErrorMessage =
  "Something went wrong while preparing the response. Please try again."

export function ChatShell() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function sendMessage(messageText = input) {
    const trimmedMessage = messageText.trim()

    if (!trimmedMessage || isLoading) {
      return
    }

    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: trimmedMessage,
    }

    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setInput("")
    setError(null)
    setIsLoading(true)

    try {
      const response = await askMockHealthcareGuide({
        message: trimmedMessage,
        history: messages,
      })

      const assistantMessage: ChatMessage = {
        id: createMessageId(),
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        isSafetyResponse: response.isSafetyResponse,
        isInsufficientEvidence: response.isInsufficientEvidence,
      }

      setMessages([...nextMessages, assistantMessage])
    } catch {
      setError(requestErrorMessage)
      setMessages(nextMessages)
    } finally {
      setIsLoading(false)
    }
  }

  function updateFeedback(messageId: string, value: FeedbackValue) {
    setMessages((currentMessages) =>
      currentMessages.map((message) =>
        message.id === messageId ? { ...message, feedback: value } : message
      )
    )
  }

  function clearConversation() {
    setMessages([])
    setInput("")
    setError(null)
  }

  return (
    <div className="flex min-h-dvh flex-col bg-slate-50 text-slate-950">
      <ChatHeader status={knowledgeBaseStatus} />

      <main className="flex min-h-0 flex-1 flex-col">
        {messages.length === 0 && !isLoading ? (
          <WelcomeState
            questions={suggestedQuestions}
            onSelectQuestion={sendMessage}
          />
        ) : (
          <MessageList
            messages={messages}
            isLoading={isLoading}
            onFeedback={updateFeedback}
          />
        )}
      </main>

      <footer className="border-t bg-white/95 px-4 py-4 backdrop-blur sm:px-6">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-3">
          {error && <ErrorBanner message={error} />}
          <MessageInput
            value={input}
            isLoading={isLoading}
            hasMessages={messages.length > 0}
            onChange={setInput}
            onSubmit={() => sendMessage()}
            onClear={clearConversation}
          />
          <SafetyDisclaimer />
        </div>
      </footer>
    </div>
  )
}

function createMessageId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }

  return `message-${Date.now()}-${Math.random().toString(16).slice(2)}`
}
