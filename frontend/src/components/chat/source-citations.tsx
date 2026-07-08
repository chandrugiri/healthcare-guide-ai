"use client"

import { useState } from "react"
import { ChevronDown, FileText } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import type { SourceCitation } from "@/lib/chat-types"
import { cn } from "@/lib/utils"

type SourceCitationsProps = {
  sources: SourceCitation[]
}

export function SourceCitations({ sources }: SourceCitationsProps) {
  if (sources.length === 0) {
    return null
  }

  return (
    <div className="mt-4 space-y-2" aria-label="Source citations">
      <p className="text-xs font-medium uppercase tracking-normal text-slate-500">
        Sources
      </p>
      <div className="space-y-2">
        {sources.map((source) => (
          <SourceCitationItem key={source.id} source={source} />
        ))}
      </div>
    </div>
  )
}

function SourceCitationItem({ source }: { source: SourceCitation }) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="rounded-xl border border-slate-200 bg-slate-50">
        <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm text-slate-700 outline-none transition hover:bg-slate-100 focus-visible:ring-3 focus-visible:ring-teal-700/20">
          <span className="flex min-w-0 items-center gap-2">
            <FileText
              aria-hidden="true"
              className="size-4 shrink-0 text-teal-700"
            />
            <span className="truncate font-medium">{source.filename}</span>
            <span className="shrink-0 text-slate-500">page {source.page}</span>
          </span>
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "size-4 shrink-0 text-slate-500 transition-transform",
              open && "rotate-180"
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <p className="border-t border-slate-200 px-3 py-3 text-sm leading-6 text-slate-600">
            {source.excerpt}
          </p>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
}
