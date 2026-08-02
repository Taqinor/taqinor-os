import { useMemo } from 'react'
import { Button } from '../../../ui'

/* ============================================================================
   AOF96 — Graphe « compte vs largeur d'allée » + PLATEAU GRATUIT.
   ----------------------------------------------------------------------------
   RÈGLE PRODUIT GRAVÉE (en-tête du Groupe AOF) : **ne jamais publier l'allée
   minimale quand une allée large est gratuite.** Le cas réel du bâtiment C le
   montre — le compte reste identique (314) de 0,60 m à 1,94 m : poser 0,60
   revient à jeter 1,90 m de circulation de maintenance pour rien.

   L'écueil est que cette information soit une DÉCOUVERTE (il faut penser à
   tester d'autres largeurs). Ici c'est une AFFORDANCE : le plateau est
   surligné et un bouton applique en un clic la plus grande largeur gratuite.

   Le graphe est un rendu, pas un calcul : les points, les bornes du plateau,
   les libellés et le libellé du bouton viennent tous du moteur. Les seules
   opérations faites ici transforment une valeur en PIXEL (fonction `echelle`,
   paramètres anonymes) — de la géométrie d'affichage, pas une grandeur métier
   (garde de code AOF94).

   ── Contrat de charge utile ───────────────────────────────────────────────
   graphe = {
     points: [{ largeur_m, compte, texte_largeur, texte_compte }],
     plateau?: { debut_m, fin_m, texte_debut, texte_fin, resume,
                 largeur_offerte_m, libelle_bouton },
   }
   ========================================================================== */

// Nom accessible du graphe. Il reste STABLE : le résumé du plateau est une
// légende VISIBLE (le `<p data-plateau-resume>` sous le graphe), il ne doit pas
// être répété comme nom de l'image — sinon un lecteur d'écran l'énonce deux
// fois, et le même texte apparaît en double dans le document.
const NOM_GRAPHE = "Compte de modules selon la largeur d'allée"

const L = 320
const H = 140
const MARGE_G = 8
const MARGE_D = 8
const MARGE_H = 10
const MARGE_B = 22

// Valeur → pixel. Paramètres volontairement anonymes : cette fonction ne sait
// pas ce qu'elle projette, elle ne dérive donc aucune grandeur métier.
function echelle(valeur, min, max, debut, fin) {
  if (!Number.isFinite(valeur) || max === min) return debut
  return debut + ((valeur - min) * (fin - debut)) / (max - min)
}

export default function AlleeGratuiteChart({ graphe, onAppliquer, perime = false }) {
  const points = useMemo(() => (graphe?.points || []).filter((p) => Number.isFinite(p.largeur_m)), [graphe])

  const geometrie = useMemo(() => {
    if (points.length === 0) return null
    const abscisses = points.map((p) => p.largeur_m)
    const ordonnees = points.map((p) => p.compte)
    const xMin = Math.min(...abscisses)
    const xMax = Math.max(...abscisses)
    const yMin = Math.min(...ordonnees)
    const yMax = Math.max(...ordonnees)
    const px = (valeur) => echelle(valeur, xMin, xMax, MARGE_G, L - MARGE_D)
    const py = (valeur) => echelle(valeur, yMin, yMax, H - MARGE_B, MARGE_H)
    return {
      px,
      py,
      trace: points.map((p) => `${px(p.largeur_m)},${py(p.compte)}`).join(' '),
    }
  }, [points])

  if (!geometrie) return null

  const plateau = graphe.plateau
  const { px, py } = geometrie

  return (
    <div className="flex flex-col gap-2" data-graphe="allee-gratuite">
      <svg
        viewBox={`0 0 ${L} ${H}`}
        role="img"
        aria-label={NOM_GRAPHE}
        className="w-full rounded-md border border-border bg-card"
      >
        <title>{NOM_GRAPHE}</title>

        {/* Plateau GRATUIT : la bande où le compte ne bouge pas. */}
        {plateau && (
          <rect
            data-plateau="gratuit"
            x={px(plateau.debut_m)}
            y={MARGE_H}
            width={px(plateau.fin_m) - px(plateau.debut_m)}
            height={H - MARGE_B - MARGE_H}
            className="fill-success/15 stroke-success"
            strokeWidth={1}
          />
        )}

        <polyline
          data-item="courbe"
          points={geometrie.trace}
          className="fill-none stroke-primary"
          strokeWidth={2}
        />

        {points.map((p) => (
          <circle
            key={p.texte_largeur ?? p.largeur_m}
            data-item="point"
            data-largeur={p.texte_largeur}
            data-compte={p.texte_compte}
            cx={px(p.largeur_m)}
            cy={py(p.compte)}
            r={2.5}
            className="fill-primary"
          />
        ))}

        {/* Bornes du plateau : textes SERVEUR, jamais un nombre reformaté ici. */}
        {plateau?.texte_debut && (
          <text x={px(plateau.debut_m)} y={H - 6} textAnchor="middle" className="fill-muted-foreground text-[9px]">
            {plateau.texte_debut}
          </text>
        )}
        {plateau?.texte_fin && (
          <text x={px(plateau.fin_m)} y={H - 6} textAnchor="middle" className="fill-muted-foreground text-[9px]">
            {plateau.texte_fin}
          </text>
        )}
      </svg>

      {plateau?.resume && (
        <p className="text-xs text-muted-foreground" data-plateau-resume="">{plateau.resume}</p>
      )}

      {plateau?.libelle_bouton && (
        <Button
          size="sm"
          variant="outline"
          disabled={perime}
          data-action="appliquer-allee-gratuite"
          onClick={() => onAppliquer?.(plateau.largeur_offerte_m)}
        >
          {plateau.libelle_bouton}
        </Button>
      )}
    </div>
  )
}
