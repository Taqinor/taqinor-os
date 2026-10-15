import { Button, EmptyState } from '../../../../ui'

/* État vide d'une vue de leads à DEUX paliers : `totalLeads === 0` (vraiment
   aucun lead) reçoit le coach illustré (VX40) ; « filtré à 0 » garde l'icône
   et un CTA « Effacer les filtres » réel quand le parent le fournit.
   `actionAucun` : CTA du palier « aucun lead du tout » (création/import). */
export default function EtatVideVueLeads({
  totalLeads, onClearFilters, icon, title, descriptionAucun, descriptionFiltre,
  actionAucun = null,
}) {
  const aucunDuTout = totalLeads != null && totalLeads === 0
  if (aucunDuTout) {
    return (
      <EmptyState illustrated title={title} description={descriptionAucun} action={actionAucun} />
    )
  }
  return (
    <EmptyState
      icon={icon}
      title={title}
      description={descriptionFiltre}
      action={onClearFilters ? (
        <Button type="button" variant="outline" size="sm" onClick={onClearFilters}>
          Effacer les filtres
        </Button>
      ) : null}
    />
  )
}
