import { X } from 'lucide-react'
import { accord } from '../lib/textes'

/* ============================================================================
   TCH45 — Barre de sélection (actions en lot) : posée au bas de l'écran quand au moins une
   ligne est sélectionnée (appui long → Sélectionner, `x`, Ctrl/⌘+clic). Elle remplace le
   bouton flottant tant qu'elle est là. Les actions sont les routes de `taches/lot/` :
   Déplacer · Quand · Priorité · Terminer · Supprimer (`lot` : deplacer, planifier, prioriser,
   terminer, supprimer). Le nombre est annoncé (`role=status`) à chaque changement.
   Aucune touche seule ne fait disparaître une ligne : Supprimer demande l'action explicite.
   ========================================================================== */

const ACTIONS_LOT = [
  { code: 'deplacer', libelle: 'Déplacer' },
  { code: 'planifier', libelle: 'Quand' },
  { code: 'prioriser', libelle: 'Priorité' },
  { code: 'terminer', libelle: 'Terminer' },
  { code: 'supprimer', libelle: 'Supprimer' },
]

export default function BarreSelection({ n = 0, actions = ACTIONS_LOT, onAction, onFermer }) {
  if (n <= 0) return null
  return (
    <div className="barre-selection" role="toolbar" aria-label="Actions sur la sélection">
      <span className="compte chiffres" role="status">{accord(n, 'sélectionnée')}</span>
      {actions.map(({ code, libelle }) => (
        <button key={code} type="button" className="bouton" onClick={() => onAction?.(code)}>{libelle}</button>
      ))}
      <button type="button" className="bouton-icone" aria-label="Annuler la sélection" onClick={onFermer}>
        <X className="i" aria-hidden="true" />
      </button>
    </div>
  )
}
