import { TriangleAlert } from 'lucide-react'
import { Badge } from '../../../ui'

/* ============================================================================
   AOF101 (2/2) — Marges de robustesse, EN CENTIMÈTRES, avec leur seuil.
   ----------------------------------------------------------------------------
   Le moteur publie `Marges` (`core/calepinage/types.py`) en centimètres —
   `troncon_min_cm` / `bande_min_cm` — parce qu'un calage au MILLIMÈTRE près
   n'est pas exploitable en chantier : personne ne pose une table à 0,3 mm
   d'un obstacle. Ce composant ne calcule RIEN (les deux marges et leurs
   seuils viennent du moteur — `Parametres.marge_troncon_min_m` /
   `marge_bande_min_m`, convertis en cm par l'appelant) ; il compare et
   AFFICHE, seuil à côté de la valeur, toujours.

   **Sous le seuil**, la marge n'est pas un simple avertissement discret :
   c'est un badge d'ALERTE nommé, avec le texte produit gravé du contrat —
   « calage au millimètre — non exploitable en chantier » — parce qu'une
   marge de robustesse trop fine décide, en silence, si le calepinage tiendra
   au relevé d'exécution ou pas.
   ========================================================================== */

const MESSAGE_SOUS_SEUIL = 'calage au millimètre — non exploitable en chantier'

function formatCm(valeur) {
  return Number.isFinite(valeur) ? `${valeur.toFixed(1).replace('.', ',')} cm` : '—'
}

function MargeBadge({ libelle, valeurCm, seuilCm, critique }) {
  if (!Number.isFinite(valeurCm)) return null
  const sousLeSeuil = Number.isFinite(seuilCm) && valeurCm < seuilCm
  return (
    <div
      className="flex flex-col gap-1"
      data-marge-robustesse={libelle}
      data-marge-sous-seuil={sousLeSeuil ? 'true' : 'false'}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">{libelle}</span>
        <Badge tone={sousLeSeuil ? 'danger' : 'success'}>
          {formatCm(valeurCm)}
          {Number.isFinite(seuilCm) && ` (seuil ${formatCm(seuilCm)})`}
        </Badge>
      </div>
      {sousLeSeuil && (
        <p role="alert" className="flex items-center gap-1.5 text-xs font-medium text-destructive">
          <TriangleAlert className="size-3.5 shrink-0" aria-hidden="true" />
          {MESSAGE_SOUS_SEUIL}
        </p>
      )}
      {critique && (
        <p className="text-xs text-muted-foreground">{critique}</p>
      )}
    </div>
  )
}

/**
 * `marges`  = { troncon_min_cm, bande_min_cm, rangee_critique?, obstacle_critique? }
 * `seuils`  = { troncon_min_cm, bande_min_cm }
 */
export function RobustesseBadges({ marges, seuils = {} }) {
  if (!marges) return null
  return (
    <div className="flex flex-wrap gap-4">
      <MargeBadge
        libelle="Marge tronçon"
        valeurCm={marges.troncon_min_cm}
        seuilCm={seuils.troncon_min_cm}
        critique={marges.rangee_critique && `Rangée la plus serrée : ${marges.rangee_critique}`}
      />
      <MargeBadge
        libelle="Marge bande"
        valeurCm={marges.bande_min_cm}
        seuilCm={seuils.bande_min_cm}
        critique={marges.obstacle_critique && `Obstacle le plus proche : ${marges.obstacle_critique}`}
      />
    </div>
  )
}

export default RobustesseBadges
