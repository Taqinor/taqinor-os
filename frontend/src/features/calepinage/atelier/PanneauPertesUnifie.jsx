import { useState } from 'react'
import DiagrammePertes from '../production/DiagrammePertes'
import PanneauPertes from './PanneauPertes'

/* ============================================================================
   ACAL396 — « PERTES » ET « POSTES DE PERTES » EN UN PANNEAU (mode guidé).
   Le diagramme au-dessus, l'édition d'un poste dessous. Après chaque poste
   enregistré, la `key` du diagramme change : il se remonte et relit
   `GET resultat/` — le bandeau « simulation périmée » apparaît sans changer
   d'onglet. En expert, les deux onglets d'origine restent.
   ========================================================================== */
export default function PanneauPertesUnifie({ calepinageId = null, lectureSeule = false }) {
  const [relecture, setRelecture] = useState(0)
  return (
    <div data-testid="cal-pertes-unifie" className="flex flex-col gap-4">
      <DiagrammePertes key={relecture} calepinageId={calepinageId} />
      <PanneauPertes calepinageId={calepinageId} lectureSeule={lectureSeule}
        onEnregistre={() => setRelecture((n) => n + 1)} />
    </div>
  )
}
