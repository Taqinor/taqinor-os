import { createElement } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../../ui'

/* Habillage partagé par la fiche chantier (InstallationDetail) et l'onglet
   « Matériel & BC » (ChantierApprovisionnement) : mêmes classes de carte et de
   tableau, une seule source. Module sans composant : fonctions et constantes. */

/** Carte titrée (icône + titre + action optionnelle) : surface Card du système
    de design. Fonction (pas un composant) : appelée par `Bloc` / `Section`. */
export function carteTitree({ icon: Icon, title, action, children }) {
  return createElement(
    Card,
    null,
    createElement(
      CardHeader,
      { className: 'flex-row items-center justify-between gap-2 space-y-0' },
      createElement(
        CardTitle,
        { className: 'flex items-center gap-2 text-sm' },
        Icon ? createElement(Icon, { className: 'size-4 text-muted-foreground', 'aria-hidden': 'true' }) : null,
        title,
      ),
      action,
    ),
    createElement(CardContent, { className: 'flex flex-col gap-3' }, children),
  )
}

export const TABLEAU_ENVELOPPE = 'overflow-x-auto rounded-lg border border-border'
export const TABLEAU_CLASSE = 'w-full border-collapse text-sm'

const TH_CLASSE = 'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground'

/** `<thead>` d'un tableau à intitulés simples ; `head` = liste de libellés. */
export function enTeteTableau(head) {
  return createElement(
    'thead',
    { className: 'bg-muted/60' },
    createElement(
      'tr',
      null,
      head.map((h, i) => createElement('th', { key: `${h || 'vide'}-${i}`, className: TH_CLASSE }, h)),
    ),
  )
}
