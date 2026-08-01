// APX31 — Avancement de checklist : UN composant, deux panneaux.
// ----------------------------------------------------------------------------
// État vérifié : `pages/sav/TicketChecklistPanel.jsx` affichait « X/Y points »
// en TEXTE PLAT, alors que `pages/installations/ChantierChecklist.jsx` avait
// déjà la bonne idée — une `Progress` + le pourcentage. Deux écrans de
// checklist, deux réponses différentes à la même question (« où en suis-je ? »).
//
// Ce composant factorise la bonne version pour les DEUX : barre de progression
// tonalisée (verte à 100 %) + le compte « X/Y » lisible. Il est PUREMENT
// présentationnel — il ne connaît ni ticket ni chantier, seulement deux
// nombres — donc rien n'empêche un troisième écran de checklist de l'adopter.
//
// Accessibilité : `Progress` porte déjà le rôle/les bornes ARIA ; le compte est
// rendu en TEXTE à côté, jamais seulement dans la couleur de la barre.
import { cn } from '../lib/cn'
import { Progress } from './Progress'

/**
 * ChecklistProgress — avancement d'une checklist.
 *
 * @param {object} props
 * @param {number} props.done   nombre de points cochés
 * @param {number} props.total  nombre total de points
 * @param {string} [props.noun='point']  nom au singulier de l'unité comptée
 *   (« point » côté SAV, « étape » côté chantier) — le pluriel est dérivé.
 * @param {'count'|'percent'|'both'} [props.show='both']  ce qui accompagne la
 *   barre : le compte « 3/8 », le pourcentage, ou les deux.
 * @param {number} [props.percent]  pourcentage IMPOSÉ, quand il est calculé
 *   ailleurs — le chantier reçoit son `completion` du serveur (qui peut
 *   pondérer autrement qu'un simple done/total) : adopter ce composant ne doit
 *   PAS changer le nombre qu'il affichait. Omis = dérivé de done/total.
 */
export function ChecklistProgress({
  done, total, noun = 'point', show = 'both', percent: percentImpose, className,
}) {
  const totalSafe = Number.isFinite(total) && total > 0 ? total : 0
  const doneSafe = Math.min(Math.max(Number(done) || 0, 0), totalSafe)
  // Une checklist vide n'a pas d'avancement à montrer (et 0/0 n'a pas de sens).
  if (!totalSafe && percentImpose == null) return null
  const percent = percentImpose != null
    ? Math.max(0, Math.min(100, Math.round(Number(percentImpose) || 0)))
    : Math.round((doneSafe / totalSafe) * 100)
  const complet = percent === 100
  const pluriel = totalSafe > 1 ? 's' : ''

  const compte = totalSafe ? `${doneSafe}/${totalSafe} ${noun}${pluriel}` : `${percent}%`
  const libelle = show === 'count' ? compte
    : show === 'percent' ? `${percent}%`
      : `${compte} · ${percent}%`

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <Progress
        value={percent}
        tone={complet ? 'success' : 'primary'}
        className="flex-1"
        aria-label={`Avancement : ${compte}`}
      />
      <span className={cn(
        'shrink-0 text-sm font-semibold tabular-nums',
        complet ? 'text-success' : 'text-muted-foreground',
      )}
      >
        {libelle}
      </span>
    </div>
  )
}

export default ChecklistProgress
