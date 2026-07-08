export type AnswerInlineSegment = {
  text: string
  bold: boolean
}

export type AnswerBlock =
  | {
      type: "paragraph"
      segments: AnswerInlineSegment[]
    }
  | {
      type: "list"
      items: AnswerInlineSegment[][]
    }

const citationPattern = /\[(?:\d+\s*(?:,\s*\d+\s*)*)\](?:\s*\[(?:\d+\s*(?:,\s*\d+\s*)*)\])*/g

export function removeNumericCitations(text: string): string {
  return text
    .replace(citationPattern, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\s+([.,;:!?])/g, "$1")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n[ \t]+/g, "\n")
    .trim()
}

export function formatAnswerBlocks(answer: string): AnswerBlock[] {
  const cleanedAnswer = removeNumericCitations(answer)
  const blocks: AnswerBlock[] = []
  const listItems: AnswerInlineSegment[][] = []
  const paragraphLines: string[] = []

  function flushParagraph() {
    if (paragraphLines.length === 0) {
      return
    }
    blocks.push({
      type: "paragraph",
      segments: parseInlineSegments(paragraphLines.join("\n")),
    })
    paragraphLines.length = 0
  }

  function flushList() {
    if (listItems.length === 0) {
      return
    }
    blocks.push({ type: "list", items: [...listItems] })
    listItems.length = 0
  }

  for (const line of cleanedAnswer.split(/\r?\n/)) {
    const trimmedLine = line.trim()
    const bulletMatch = trimmedLine.match(/^[-*]\s+(.+)$/)

    if (!trimmedLine) {
      flushParagraph()
      flushList()
      continue
    }

    if (bulletMatch) {
      flushParagraph()
      listItems.push(parseInlineSegments(normalizeBulletText(bulletMatch[1])))
      continue
    }

    flushList()
    paragraphLines.push(trimmedLine)
  }

  flushParagraph()
  flushList()

  return blocks
}

export function parseInlineSegments(text: string): AnswerInlineSegment[] {
  const segments: AnswerInlineSegment[] = []
  const boldPattern = /\*\*(.+?)\*\*/g
  let cursor = 0
  let match: RegExpExecArray | null

  while ((match = boldPattern.exec(text)) !== null) {
    if (match.index > cursor) {
      segments.push({
        text: stripSingleAsteriskMarkdown(text.slice(cursor, match.index)),
        bold: false,
      })
    }
    segments.push({ text: match[1], bold: true })
    cursor = match.index + match[0].length
  }

  if (cursor < text.length) {
    segments.push({
      text: stripSingleAsteriskMarkdown(text.slice(cursor)),
      bold: false,
    })
  }

  return segments.length > 0 ? segments : [{ text, bold: false }]
}

function normalizeBulletText(text: string): string {
  const boldLead = text.match(/^\*\*(.+?)\*\*\s+(.+)$/)
  if (!boldLead) {
    return text
  }
  return `**${boldLead[1]}** — ${boldLead[2]}`
}

function stripSingleAsteriskMarkdown(text: string): string {
  return text.replace(/\*(.*?)\*/g, "$1")
}
