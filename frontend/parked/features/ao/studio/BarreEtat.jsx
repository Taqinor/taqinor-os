import { Badge } from '../../../ui'
import { formatMetres, pasDeGrille, texteEchelle } from './useViewport'

/* ============================================================================
   AOF74 — Barre d'état basse du canvas en mètres.
   ----------------------------------------------------------------------------
   Se glisse dans le slot `etat` de `StudioShell` (AOF73). Elle AFFICHE, elle ne
   CALCULE pas : `surface`, `perimetre` et `azimut` arrivent en props, produits
   par le propriétaire de la géométrie (moteur/serveur) — la règle « jamais un
   chiffre recalculé côté front » vaut aussi pour une barre d'état. Les seules
   valeurs dérivées ici sont celles de la VUE elle-même (échelle courante,
   position du curseur), qui n'existent que côté écran.

   L'état de calibration est explicite et jamais optimiste : une échelle non
   calibrée se dit, elle ne se devine pas (le contrôle de vraisemblance
   d'AOF71 vit côté serveur ; ici on rend son verdict).
   ========================================================================== */

const CALIBRATION = {
  calibre: { libelle: 'Calibré', tone: 'success' },
  a_confirmer: { libelle: 'Échelle à confirmer', tone: 'warning' },
  non_calibre: { libelle: 'Non calibré', tone: 'danger' },
  sans_objet: { libelle: 'Tracé direct', tone: 'neutral' },
}

function Champ({ libelle, valeur }) {
  return (
    <span className="inline-flex items-baseline gap-1 whitespace-nowrap">
      <span className="text-muted-foreground/80">{libelle}</span>
      <span className="font-medium tabular-nums text-foreground">{valeur}</span>
    </span>
  )
}

export function BarreEtat({
  viewport,
  taille,
  curseur,
  surface,
  perimetre,
  azimut,
  calibration = 'non_calibre',
}) {
  const mesurable = Boolean(viewport) && taille?.largeur > 0 && taille?.hauteur > 0
  const pas = mesurable ? pasDeGrille(viewport, taille) : 1
  const cal = CALIBRATION[calibration] ?? CALIBRATION.non_calibre

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <Champ libelle="Échelle" valeur={mesurable ? texteEchelle(viewport, taille) : '—'} />
      <Champ
        libelle="Curseur"
        valeur={curseur
          ? `x ${formatMetres(curseur.x, pas)} · y ${formatMetres(curseur.y, pas)}`
          : '—'}
      />
      <Champ
        libelle="Surface"
        valeur={Number.isFinite(surface) ? `${surface.toFixed(1).replace('.', ',')} m²` : '—'}
      />
      <Champ
        libelle="Périmètre"
        valeur={Number.isFinite(perimetre) ? formatMetres(perimetre, 0.1) : '—'}
      />
      <Champ
        libelle="Azimut"
        valeur={Number.isFinite(azimut) ? `${Math.round(azimut)}°` : '—'}
      />
      <Badge tone={cal.tone}>{cal.libelle}</Badge>
    </div>
  )
}

export default BarreEtat
