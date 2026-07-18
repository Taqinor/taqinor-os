import LeadWorkspace from '../../features/crm/workspace/LeadWorkspace'

/* LW13 — LeadForm est devenu un ADAPTATEUR mince vers le LeadWorkspace
   (features/crm/workspace/) : le cockpit 3 zones à moteur `useLeadDraft`
   (autosauvegarde sans perte, rafale J/K, rails identité/contexte). Le
   contrat de props est INCHANGÉ — LeadsPage continue d'ouvrir la fiche
   exactement comme avant (overlay ?lead=, file de rafale `leadsQueue`).
   Ce fichier disparaît en LW40 (les appelants pointeront directement sur
   LeadWorkspace) ; d'ici là il garde l'ancien chemin d'import vivant. */
export default function LeadForm(props) {
  return <LeadWorkspace variant="dialog" {...props} />
}
