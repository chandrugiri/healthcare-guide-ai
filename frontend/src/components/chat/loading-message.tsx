import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"

export function LoadingMessage() {
  return (
    <div className="flex gap-3" aria-label="Assistant is preparing a response">
      <Avatar className="bg-teal-700 text-white" size="sm">
        <AvatarFallback className="bg-teal-700 text-xs font-semibold text-white">
          AI
        </AvatarFallback>
      </Avatar>
      <div className="w-full max-w-2xl rounded-2xl rounded-tl-md border border-slate-200 bg-white p-4 shadow-sm">
        <div className="space-y-2">
          <Skeleton className="h-3 w-5/6 bg-slate-200" />
          <Skeleton className="h-3 w-2/3 bg-slate-200" />
          <Skeleton className="h-3 w-1/2 bg-slate-200" />
        </div>
      </div>
    </div>
  )
}
