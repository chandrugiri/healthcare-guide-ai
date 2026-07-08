export type SourceMetadata = {
  title: string
  officialUrl: string | null
  publisher: string | null
}

export const SOURCE_METADATA: Record<string, SourceMetadata> = {
  "01-sleep-hygiene.pdf": {
    title: "Sleep hygiene guidance",
    officialUrl:
      "https://www.uhs.nhs.uk/Media/UHS-website-2019/Patientinformation/Other/Sleep-hygiene-3276-PIL.pdf",
    publisher: "University Hospital Southampton NHS Foundation Trust",
  },
  "02-heart-health.pdf": {
    title: "British Heart Foundation heart health guidance",
    officialUrl:
      "https://www.bhf.org.uk/-/media/files/information-and-support/publications/healthy-eating-and-exercise/understanding-your-heart-health-his4a6-0624.pdf?rev=36b7e5904cee4511b3a182ae468ce71f",
    publisher: "British Heart Foundation",
  },
  "03-high-blood-pressure.pdf": {
    title: "British Heart Foundation blood pressure guidance",
    officialUrl:
      "https://www.bhf.org.uk/informationsupport/publications/risk-factors/understanding-high-blood-pressure",
    publisher: "British Heart Foundation",
  },
  "04-healthy-eating.pdf": {
    title: "Healthy eating guidance",
    officialUrl: null,
    publisher: null,
  },
  "05-dehydration.pdf": {
    title: "Dehydration guidance",
    officialUrl:
      "https://www.wchc.nhs.uk/resources/hydration-information-leaflet/",
    publisher: "Wirral Community Health and Care NHS Foundation Trust",
  },
  "06-physical-activity.pdf": {
    title: "WHO physical activity guidance",
    officialUrl:
      "https://www.who.int/publications/i/item/9789240015128",
    publisher: "World Health Organization",
  },
}

export function getSourceMetadata(filename: string): SourceMetadata {
  return (
    SOURCE_METADATA[filename] ?? {
      title: "Healthcare guidance source",
      officialUrl: null,
      publisher: null,
    }
  )
}
