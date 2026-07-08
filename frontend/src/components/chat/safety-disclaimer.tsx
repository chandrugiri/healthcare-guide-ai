import { AlertTriangle } from "lucide-react"

export function SafetyDisclaimer() {
  return (
    <section
      aria-label="Medical safety disclaimer"
      className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950"
    >
      <div className="flex gap-3">
        <AlertTriangle
          aria-hidden="true"
          className="mt-0.5 size-4 shrink-0 text-amber-700"
        />
        <p>
          Healthcare Guide AI provides general health information only. It does
          not diagnose conditions, recommend treatment decisions, or change
          medications. For personal medical advice, contact a qualified
          healthcare professional.
        </p>
      </div>
    </section>
  )
}
