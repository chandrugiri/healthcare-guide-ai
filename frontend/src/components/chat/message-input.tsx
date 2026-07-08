"use client"

import type { KeyboardEvent } from "react"
import { SendHorizontal, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

type MessageInputProps = {
  value: string
  isLoading: boolean
  hasMessages: boolean
  onChange: (value: string) => void
  onSubmit: () => void
  onClear: () => void
}

export function MessageInput({
  value,
  isLoading,
  hasMessages,
  onChange,
  onSubmit,
  onClear,
}: MessageInputProps) {
  const canSubmit = value.trim().length > 0 && !isLoading

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      if (canSubmit) {
        onSubmit()
      }
    }
  }

  return (
    <form
      className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault()
        if (canSubmit) {
          onSubmit()
        }
      }}
    >
      <label className="sr-only" htmlFor="chat-message">
        Ask a general health question
      </label>
      <Textarea
        id="chat-message"
        value={value}
        rows={3}
        disabled={isLoading}
        placeholder="Ask about sleep, symptoms, prevention, healthy habits, or when to seek care..."
        className="max-h-40 min-h-24 resize-none rounded-xl border-slate-200 bg-slate-50 px-3 py-3 text-slate-900 placeholder:text-slate-500 focus-visible:border-teal-700 focus-visible:ring-teal-700/20"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-slate-500">
          Press Enter to send. Press Shift+Enter for a new line.
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={!hasMessages || isLoading}
            className="rounded-xl border-slate-200 text-slate-700"
            onClick={onClear}
          >
            <Trash2 aria-hidden="true" className="size-4" />
            Clear conversation
          </Button>
          <Button
            type="submit"
            disabled={!canSubmit}
            className="rounded-xl bg-teal-700 text-white hover:bg-teal-800"
          >
            <SendHorizontal aria-hidden="true" className="size-4" />
            Send
          </Button>
        </div>
      </div>
    </form>
  )
}
