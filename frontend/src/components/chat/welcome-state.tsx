import { MessageSquareText } from "lucide-react"

import { Button } from "@/components/ui/button"

type WelcomeStateProps = {
  questions: readonly string[]
  onSelectQuestion: (question: string) => void
}

export function WelcomeState({ questions, onSelectQuestion }: WelcomeStateProps) {
  return (
    <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-4 py-10 text-center sm:px-6">
      <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-teal-700 text-white shadow-sm">
        <MessageSquareText aria-hidden="true" className="size-6" />
      </div>
      <h2 className="mt-5 text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
        How can I help with your health question?
      </h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
        Ask about common health topics, healthy habits, symptoms, prevention,
        and when to seek professional care.
      </p>

      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {questions.map((question) => (
          <Button
            key={question}
            type="button"
            variant="outline"
            className="h-auto min-h-16 justify-start rounded-xl border-slate-200 bg-white px-4 py-4 text-left text-sm leading-5 text-slate-800 shadow-sm hover:border-teal-200 hover:bg-teal-50 hover:text-teal-950"
            onClick={() => onSelectQuestion(question)}
          >
            {question}
          </Button>
        ))}
      </div>
    </section>
  )
}
