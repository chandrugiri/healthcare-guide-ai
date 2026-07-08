import { CheckCircle2, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import type { KnowledgeBaseStatus } from "@/lib/chat-types"

type ChatHeaderProps = {
  status: KnowledgeBaseStatus
}

export function ChatHeader({ status }: ChatHeaderProps) {
  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-teal-700 text-white">
            <ShieldCheck aria-hidden="true" className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-normal text-slate-950 sm:text-2xl">
              Healthcare Guide AI
            </h1>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              General healthcare information with safety-minded guidance
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
          <Badge
            variant="outline"
            className="h-7 gap-1.5 rounded-full border-teal-200 bg-teal-50 px-3 text-teal-800"
          >
            <CheckCircle2 aria-hidden="true" className="size-3.5" />
            {status.label}
          </Badge>
          <Separator
            orientation="vertical"
            className="hidden h-5 bg-slate-200 sm:block"
          />
          <span>{status.documentCount} verified documents indexed</span>
        </div>
      </div>
    </header>
  )
}
