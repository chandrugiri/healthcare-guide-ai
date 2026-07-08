"use client"

import { Bot, UserRound } from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import type { ChatMessage as ChatMessageType, FeedbackValue } from "@/lib/chat-types"
import { cn } from "@/lib/utils"
import { FeedbackButtons } from "./feedback-buttons"
import { SourceCitations } from "./source-citations"

type ChatMessageProps = {
  message: ChatMessageType
  onFeedback: (messageId: string, value: FeedbackValue) => void
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const isUser = message.role === "user"

  return (
    <article
      className={cn("flex gap-3", isUser && "justify-end")}
      aria-label={isUser ? "User message" : "Assistant message"}
    >
      {!isUser && (
        <Avatar className="bg-teal-700 text-white" size="sm">
          <AvatarFallback className="bg-teal-700 text-xs font-semibold text-white">
            <Bot aria-hidden="true" className="size-3.5" />
          </AvatarFallback>
        </Avatar>
      )}

      <div
        className={cn(
          "max-w-[min(42rem,calc(100%-3rem))] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm",
          isUser
            ? "rounded-tr-md bg-teal-700 text-white"
            : "rounded-tl-md border border-slate-200 bg-white text-slate-800",
          message.isSafetyResponse && "border-amber-200 bg-amber-50 text-amber-950",
          message.isInsufficientEvidence &&
            "border-slate-200 bg-slate-50 text-slate-700"
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {!isUser && <SourceCitations sources={message.sources ?? []} />}

        {!isUser && (
          <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-200 pt-3">
            <span className="text-xs text-slate-500">Was this helpful?</span>
            <FeedbackButtons
              value={message.feedback}
              onChange={(value) => onFeedback(message.id, value)}
            />
          </div>
        )}
      </div>

      {isUser && (
        <Avatar className="bg-slate-900 text-white" size="sm">
          <AvatarFallback className="bg-slate-900 text-xs font-semibold text-white">
            <UserRound aria-hidden="true" className="size-3.5" />
          </AvatarFallback>
        </Avatar>
      )}
    </article>
  )
}
