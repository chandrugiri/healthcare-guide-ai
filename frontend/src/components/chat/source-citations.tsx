"use client"

import { useMemo, useState } from "react"
import { ChevronDown, ExternalLink, FileText } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import type { SourceCitation } from "@/lib/chat-types"
import { getSourceMetadata } from "@/lib/source-metadata"
import { cn } from "@/lib/utils"

type SourceCitationsProps = {
  sources: SourceCitation[]
}

type GroupedSource = {
  filename: string
  title: string
  officialUrl: string | null
  publisher: string | null
  pages: number[]
  passages: Array<{
    key: string
    page: number
    excerpt: string
  }>
}

export function SourceCitations({ sources }: SourceCitationsProps) {
  const [open, setOpen] = useState(false)
  const groupedSources = useMemo(() => groupSources(sources), [sources])

  if (groupedSources.length === 0) {
    return null
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <section
        className="mt-4 rounded-xl border border-slate-200 bg-slate-50"
        aria-label="Information sources"
      >
        <CollapsibleTrigger
          aria-expanded={open}
          className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left outline-none transition hover:bg-slate-100 focus-visible:ring-3 focus-visible:ring-teal-700/20"
        >
          <span className="flex min-w-0 items-center gap-2">
            <FileText
              aria-hidden="true"
              className="size-4 shrink-0 text-teal-700"
            />
            <span className="text-xs font-medium uppercase tracking-normal text-slate-500">
              Information sources
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-500">
              {groupedSources.length}
            </span>
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
          <div className="space-y-2 border-t border-slate-200 px-3 py-3">
            {groupedSources.map((source) => (
              <GroupedSourceItem key={source.filename} source={source} />
            ))}
          </div>
        </CollapsibleContent>
      </section>
    </Collapsible>
  )
}

function GroupedSourceItem({ source }: { source: GroupedSource }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {source.officialUrl ? (
            <a
              href={source.officialUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ${source.title} in a new tab`}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-teal-800 underline-offset-2 hover:underline"
            >
              <span>{source.title}</span>
              <ExternalLink aria-hidden="true" className="size-3.5 shrink-0" />
            </a>
          ) : (
            <p className="text-sm font-medium text-slate-800">{source.title}</p>
          )}
          {source.publisher && (
            <p className="mt-0.5 text-xs text-slate-500">{source.publisher}</p>
          )}
        </div>
        <p className="shrink-0 text-xs text-slate-500">
          {formatPages(source.pages)}
        </p>
      </div>

      <div className="mt-3 space-y-2">
        {source.passages.map((passage) => (
          <SupportingPassage key={passage.key} passage={passage} />
        ))}
      </div>
    </div>
  )
}

function SupportingPassage({
  passage,
}: {
  passage: { page: number; excerpt: string }
}) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        aria-expanded={open}
        aria-label={`View supporting passage from page ${passage.page}`}
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 outline-none transition hover:bg-slate-50 focus-visible:ring-3 focus-visible:ring-teal-700/20"
      >
        View supporting passage
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "size-3.5 transition-transform",
            open && "rotate-180"
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-600">
          {passage.excerpt}
        </p>
      </CollapsibleContent>
    </Collapsible>
  )
}

function groupSources(sources: SourceCitation[]): GroupedSource[] {
  const groups = new Map<string, GroupedSource>()

  for (const source of sources) {
    const metadata = getSourceMetadata(source.filename)
    const existing = groups.get(source.filename)
    const group =
      existing ??
      ({
        filename: source.filename,
        title: metadata.title,
        officialUrl: metadata.officialUrl,
        publisher: metadata.publisher,
        pages: [],
        passages: [],
      } satisfies GroupedSource)

    if (!group.pages.includes(source.page)) {
      group.pages.push(source.page)
    }

    group.passages.push({
      key: `${source.id}-${source.page}-${group.passages.length}`,
      page: source.page,
      excerpt: source.excerpt,
    })

    groups.set(source.filename, group)
  }

  return Array.from(groups.values()).map((source) => ({
    ...source,
    pages: [...source.pages].sort((left, right) => left - right),
  }))
}

function formatPages(pages: number[]) {
  if (pages.length === 1) {
    return `Page ${pages[0]}`
  }

  return `Pages ${pages.join(", ")}`
}
