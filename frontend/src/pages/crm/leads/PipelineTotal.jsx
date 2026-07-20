import { useMemo } from 'react'
import { filterLeads, isPerdu, latestDevisTotal, formatMAD } from '../../../features/crm/stages'
import { STAGE_PROBABILITY } from './views/KanbanView'

// LB51 — le total Pipeline devient un TEXTE discret (blueprint cockpit,
// patron « résumé Pipedrive » à coût vertical zéro) : total MAD des leads
// FILTRÉS non perdus (un perdu compte 0 — mêmes chiffres que les têtes de
// colonnes, critique Fable LB #4), prévisionnel pondéré en INFOBULLE
// (« Prév. » quitte le visible — décision fondateur LB46). Masqué < 1600px
// par CSS (reste lisible dans le panneau Filtres mobile + les en-têtes
// kanban).
export default function PipelineTotal({ leads, filters, myUsername }) {
  const { brut, pondere } = useMemo(() => {
    const pool = filterLeads(leads, filters, { myUsername }).filter((l) => !isPerdu(l))
    return {
      brut: pool.reduce((s, l) => s + latestDevisTotal(l), 0),
      pondere: pool.reduce(
        (s, l) => s + latestDevisTotal(l) * (STAGE_PROBABILITY[l.stage] ?? 0), 0,
      ),
    }
  }, [leads, filters, myUsername])

  return (
    <span
      className="lp-pipeline-total num"
      title={`Prévisionnel pondéré : ${formatMAD(pondere)} (probabilité de conversion par étape)`}
    >
      {formatMAD(brut)}
    </span>
  )
}
