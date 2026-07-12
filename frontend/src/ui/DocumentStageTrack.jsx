import { Check } from 'lucide-react'

// VX141 — `StatusPill` est un fait ISOLÉ (point + badge) : rien ne visualise
// la CHAÎNE brouillon→envoyé→accepté→BC→facturé→chantier — un devis accepté
// sans BC n'était signalé qu'en texte. `<DocumentStageTrack>` pose une piste
// horizontale de puces reliées : franchies cochées (vert), courante remplie
// (primaire), bloquée en rouge, à venir neutre.
//
// Strictement la couche STATUTS DOCUMENT (règle CLAUDE.md #4 — brouillon/
// envoyé/accepté/refusé/expiré + BC/facture/chantier) ; jamais les stages
// STAGES.py (règle #2, funnel CRM lead) — les deux couches ne se mélangent
// JAMAIS. Aucune clé de stage CRM n'est importée ici.
//
// @param {{key:string, label:string}[]} stages  Piste ordonnée (5-6 puces).
// @param {string}   current   Clé de la puce ATTEINTE la plus avancée ; les
//                             puces avant elle sont « franchies », elle-même
//                             est « courante », les suivantes sont « à venir ».
// @param {string[]} blocked   Clés de puces en anomalie (ex : BC annulé après
//                             acceptation) — priment sur franchie/courante,
//                             rendues en rouge.
export default function DocumentStageTrack({ stages, current, blocked = [], className = '' }) {
  if (!Array.isArray(stages) || stages.length === 0) return null
  const currentIndex = stages.findIndex(s => s.key === current)

  // NB a11y — pas de libellé caché PAR PUCE : les libellés (« Envoyé »,
  // « Accepté »…) dupliqueraient le texte déjà rendu par le `StatusPill`
  // voisin et casseraient un `getByText('Envoyé')` existant (ambiguïté 2
  // correspondances). Un seul résumé accessible porte toute la piste ; le
  // détail par puce reste au survol (`title`), la couleur/coche restent
  // purement visuelles (déjà doublées par la position + l'icône ✓).
  const summary = stages
    .map(s => `${s.label}${blocked.includes(s.key) ? ' (bloqué)' : ''}`)
    .join(' → ')

  return (
    <div
      className={`flex flex-wrap items-center gap-0.5 ${className}`}
      role="img"
      aria-label={`Parcours du document : ${summary} — étape actuelle : ${stages[currentIndex]?.label ?? '—'}`}
    >
      {stages.map((s, i) => {
        const isBlocked = blocked.includes(s.key)
        const state = isBlocked
          ? 'blocked'
          : currentIndex < 0
            ? 'pending'
            : i < currentIndex ? 'done' : i === currentIndex ? 'current' : 'pending'
        const dotClass = state === 'done'
          ? 'border-success bg-success text-success-foreground'
          : state === 'current'
            ? 'border-primary bg-primary text-primary-foreground'
            : state === 'blocked'
              ? 'border-destructive bg-destructive text-destructive-foreground'
              : 'border-border bg-muted text-transparent'
        const connectorClass = (i < currentIndex && !isBlocked) ? 'bg-success' : 'bg-border'
        return (
          <div key={s.key} aria-hidden="true" className="flex items-center gap-0.5">
            <span
              className={`flex size-3.5 shrink-0 items-center justify-center rounded-full border ${dotClass}`}
              title={`${s.label}${state === 'blocked' ? ' — bloqué' : ''}`}
            >
              {state === 'done' && <Check className="size-2.5" strokeWidth={3} />}
            </span>
            {i < stages.length - 1 && (
              <span className={`h-px w-3 shrink-0 ${connectorClass}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
