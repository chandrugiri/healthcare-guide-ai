"use client"

import { useEffect, useRef } from "react"

import { ScrollArea } from "@/components/ui/scroll-area"
import type { ChatMessage as ChatMessageType, FeedbackValue } from "@/lib/chat-types"
import { ChatMessage } from "./chat-message"
import { LoadingMessage } from "./loading-message"

type MessageListProps = {
  messages: ChatMessageType[]
  isLoading: boolean
  onFeedback: (messageId: string, value: FeedbackValue) => void
}

export function MessageList({
  messages,
  isLoading,
  onFeedback,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" })
  }, [messages, isLoading])

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-6 sm:px-6">
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            onFeedback={onFeedback}
          />
        ))}
        {isLoading && <LoadingMessage />}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
