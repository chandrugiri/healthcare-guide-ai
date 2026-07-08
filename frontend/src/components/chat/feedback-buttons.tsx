"use client"

import { ThumbsDown, ThumbsUp } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { FeedbackValue } from "@/lib/chat-types"
import { cn } from "@/lib/utils"

type FeedbackButtonsProps = {
  value?: FeedbackValue
  onChange: (value: FeedbackValue) => void
}

export function FeedbackButtons({ value, onChange }: FeedbackButtonsProps) {
  return (
    <div
      aria-label="Rate assistant response"
      className="flex items-center gap-1.5"
    >
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Mark response as helpful"
        aria-pressed={value === "helpful"}
        className={cn(
          "rounded-full text-slate-500 hover:bg-teal-50 hover:text-teal-800",
          value === "helpful" && "bg-teal-50 text-teal-800"
        )}
        onClick={() => onChange("helpful")}
      >
        <ThumbsUp aria-hidden="true" className="size-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Mark response as not helpful"
        aria-pressed={value === "not-helpful"}
        className={cn(
          "rounded-full text-slate-500 hover:bg-red-50 hover:text-red-800",
          value === "not-helpful" && "bg-red-50 text-red-800"
        )}
        onClick={() => onChange("not-helpful")}
      >
        <ThumbsDown aria-hidden="true" className="size-4" />
      </Button>
    </div>
  )
}
