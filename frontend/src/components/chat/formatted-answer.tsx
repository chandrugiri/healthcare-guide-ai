import { formatAnswerBlocks } from "@/lib/answer-formatting"

type FormattedAnswerProps = {
  answer: string
}

export function FormattedAnswer({ answer }: FormattedAnswerProps) {
  const blocks = formatAnswerBlocks(answer)

  return (
    <div className="space-y-3">
      {blocks.map((block, index) => {
        if (block.type === "list") {
          return (
            <ul key={index} className="list-disc space-y-2 pl-5">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  <InlineSegments segments={item} />
                </li>
              ))}
            </ul>
          )
        }

        return (
          <p key={index} className="whitespace-pre-wrap">
            <InlineSegments segments={block.segments} />
          </p>
        )
      })}
    </div>
  )
}

function InlineSegments({
  segments,
}: {
  segments: Array<{ text: string; bold: boolean }>
}) {
  return (
    <>
      {segments.map((segment, index) =>
        segment.bold ? (
          <strong key={index} className="font-semibold">
            {segment.text}
          </strong>
        ) : (
          <span key={index}>{segment.text}</span>
        )
      )}
    </>
  )
}
