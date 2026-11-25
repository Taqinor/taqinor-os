import { PHRASE_REGLAGES_LECTURE_SEULE } from './useReglagesSociete'

/** D-ACAL-104 — la phrase unique des écrans de réglages de la société lus sans le droit de les changer. */
export default function LectureSeuleSociete() {
  return (
    <p className="text-sm text-muted-foreground" role="note" data-testid="cal-reglages-lecture-seule">
      {PHRASE_REGLAGES_LECTURE_SEULE}
    </p>
  )
}
