import type { ChatRequest, ChatResponse, KnowledgeBaseStatus } from "@/lib/chat-types"

const RESPONSE_DELAY_MS = 650

export const knowledgeBaseStatus: KnowledgeBaseStatus = {
  label: "Knowledge base ready",
  ready: true,
  documentCount: 4,
}

export const suggestedQuestions = [
  "What are some simple ways to improve sleep?",
  "When should I seek medical help for a fever?",
  "How can I maintain a healthy blood pressure?",
  "What are common signs of dehydration?",
] as const

const supportedResponses: Array<{
  match: string[]
  response: ChatResponse
}> = [
  {
    match: ["sleep", "improve sleep", "sleep better", "healthy sleep"],
    response: {
      answer:
        "Simple ways to improve sleep include keeping a consistent sleep and wake schedule, limiting caffeine later in the day, reducing screens close to bedtime, keeping the bedroom cool and dark, and using a calming wind-down routine. Regular daytime movement and morning light exposure can also support a healthier sleep rhythm.",
      sources: [
        {
          id: "sleep-1",
          filename: "healthy-sleep-basics.pdf",
          page: 2,
          excerpt:
            "A consistent schedule, a dark and quiet bedroom, and a predictable wind-down routine can help support better sleep quality.",
        },
        {
          id: "sleep-2",
          filename: "healthy-sleep-basics.pdf",
          page: 4,
          excerpt:
            "Caffeine, bright screens, and irregular bedtimes can make it harder to fall asleep or stay asleep.",
        },
      ],
    },
  },
  {
    match: ["fever", "medical help for a fever", "seek medical help", "high temperature"],
    response: {
      answer:
        "For a fever, seek medical help promptly if it is very high, lasts more than a few days, occurs in a very young infant, or comes with warning signs such as trouble breathing, chest pain, confusion, stiff neck, dehydration, a seizure, or a rash that does not fade when pressed. If symptoms feel severe or urgent, use emergency services.",
      sources: [
        {
          id: "fever-1",
          filename: "fever-self-care-and-warning-signs.pdf",
          page: 2,
          excerpt:
            "Medical advice is recommended for fever with breathing difficulty, confusion, stiff neck, seizure, signs of dehydration, or a non-blanching rash.",
        },
        {
          id: "fever-2",
          filename: "fever-self-care-and-warning-signs.pdf",
          page: 3,
          excerpt:
            "Fever in young infants, fever lasting several days, or very high temperature should be discussed with a qualified healthcare professional.",
        },
      ],
    },
  },
  {
    match: ["blood pressure", "healthy blood pressure", "maintain blood pressure", "hypertension"],
    response: {
      answer:
        "General habits that support healthy blood pressure include regular physical activity, eating a balanced diet with plenty of fruits and vegetables, limiting sodium, avoiding tobacco, moderating alcohol, managing stress, and getting enough sleep. Home blood pressure checks can be useful, but personal targets and medication decisions should be discussed with a qualified healthcare professional.",
      sources: [
        {
          id: "blood-pressure-1",
          filename: "blood-pressure-health-basics.pdf",
          page: 3,
          excerpt:
            "Physical activity, a balanced eating pattern, lower sodium intake, avoiding tobacco, and moderating alcohol can help support healthy blood pressure.",
        },
        {
          id: "blood-pressure-2",
          filename: "blood-pressure-health-basics.pdf",
          page: 5,
          excerpt:
            "People using blood pressure medicine or tracking home readings should review personal goals and treatment decisions with a qualified healthcare professional.",
        },
      ],
    },
  },
  {
    match: ["dehydration", "signs of dehydration", "common signs", "not drinking enough"],
    response: {
      answer:
        "Common signs of dehydration can include thirst, dry mouth, dark urine, urinating less often, tiredness, dizziness, headache, and muscle cramps. Seek medical help urgently if there is confusion, fainting, inability to keep fluids down, very little or no urination, or signs of dehydration in an infant, older adult, or someone with a serious illness.",
      sources: [
        {
          id: "dehydration-1",
          filename: "dehydration-signs-and-prevention.pdf",
          page: 2,
          excerpt:
            "Thirst, dry mouth, dark urine, reduced urination, fatigue, dizziness, and headache are common signs that fluid intake may be too low.",
        },
        {
          id: "dehydration-2",
          filename: "dehydration-signs-and-prevention.pdf",
          page: 4,
          excerpt:
            "Confusion, fainting, inability to keep fluids down, or very little urination can require urgent medical assessment.",
        },
      ],
    },
  },
]

const medicalAdvicePattern =
  /\b(diagnos(?:e|is)|medication|dosage|dose|prescrib(?:e|ing)|treatment decision|clinical decision|should i take|should they take|change meds|change medication|stop taking)\b/i

const greetingPattern =
  /^\s*(hi|hello|hey|good morning|good afternoon|good evening)\b[!.?\s]*$/i

const greetingResponse: ChatResponse = {
  answer:
    "Hello! I'm Healthcare Guide AI. You can ask me general questions about health, wellbeing, prevention, common symptoms, or when to seek medical help. How can I help today?",
  sources: [],
}

const safetyResponse: ChatResponse = {
  answer:
    "I can provide general health information only. I cannot diagnose conditions, recommend medication changes, or make treatment decisions. Please speak with a qualified healthcare professional for personal medical advice. If symptoms may be urgent or severe, contact emergency services or the appropriate urgent-care service.",
  isSafetyResponse: true,
  sources: [
    {
      id: "safety-1",
      filename: "medical-safety-disclaimer.pdf",
      page: 1,
      excerpt:
        "The assistant provides general health information and must not be used to diagnose conditions, adjust medication, or make treatment decisions.",
    },
  ],
}

const insufficientEvidenceResponse: ChatResponse = {
  answer:
    "I don't have enough information to answer that confidently. Please try rephrasing your question or ask about a general healthcare topic.",
  isInsufficientEvidence: true,
  sources: [],
}

export async function askMockHealthcareGuide({
  message,
}: ChatRequest): Promise<ChatResponse> {
  await delay(RESPONSE_DELAY_MS)

  const normalizedMessage = message.toLowerCase()

  if (greetingPattern.test(message)) {
    return greetingResponse
  }

  if (medicalAdvicePattern.test(message)) {
    return safetyResponse
  }

  const match = supportedResponses.find(({ match: keywords }) =>
    keywords.some((keyword) => normalizedMessage.includes(keyword))
  )

  return match?.response ?? insufficientEvidenceResponse
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
