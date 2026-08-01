/* AOF85 — `Cote` : la primitive de cotation, rendue COMME SUR UN PLAN.
   ----------------------------------------------------------------------------
   Vocabulaire repris du `dim` de la planche imprimée (`dessin.py`) : deux lignes
   d'attache perpendiculaires, une ligne de cote entre elles, une double flèche,
   et le texte orienté le long de la cote (horizontal pour un axe X, tourné d'un
   quart de tour pour un axe Y).

   LISIBILITÉ À TOUS LES ZOOMS. Le dessin vit dans un groupe SVG mis à l'échelle
   (`pixelsParMetre`) : si le texte et les flèches étaient exprimés en mètres, ils
   grossiraient avec le plan et deviendraient illisibles ou monstrueux. Toutes les
   dimensions « de papier » (corps du texte, longueur des flèches, débord des
   lignes d'attache) sont donc divisées par `pixelsParMetre` — elles restent
   constantes À L'ÉCRAN quel que soit le zoom.

   COULEUR = PROVENANCE. Le trait et le texte prennent le token de provenance
   (AOF9 : `--ao-provenance-mesure|-confirmer|-deduit|-devine`, dont les valeurs
   d'impression sont le bleu mesuré, l'orange à confirmer et le gris plan/déduit).
   Aucun hexadécimal en dur ici : la planche imprimée et l'écran doivent parler
   de la même couleur, et c'est le token qui les tient ensemble. */

// Repli `currentColor` : tant que les tokens AOF9 ne sont pas chargés, la cote
// reste visible dans la couleur du texte courant plutôt que de disparaître.
function couleurProvenance(provenance) {
  const cle = ['mesure', 'confirmer', 'deduit', 'devine'].includes(provenance)
    ? provenance
    : 'mesure'
  return `var(--ao-provenance-${cle}, currentColor)`
}

// Dimensions « de papier », en pixels écran (converties en unités du plan).
const CORPS_TEXTE_PX = 11
const FLECHE_PX = 7
const DEBORD_ATTACHE_PX = 6
const TRAIT_PX = 1

export default function Cote({
  x1,
  y1,
  x2,
  y2,
  valeur,
  libelle,
  provenance = 'mesure',
  axe = 'x',
  decalage = 0,
  pixelsParMetre = 1,
  unite = 'm',
}) {
  const k = Number(pixelsParMetre) > 0 ? Number(pixelsParMetre) : 1
  const corps = CORPS_TEXTE_PX / k
  const fleche = FLECHE_PX / k
  const debord = DEBORD_ATTACHE_PX / k
  const trait = TRAIT_PX / k
  const couleur = couleurProvenance(provenance)

  // Décalage perpendiculaire : vers le haut pour un axe X, vers la droite pour
  // un axe Y — la convention de lecture d'un plan.
  const horizontal = axe === 'x'
  const dx = horizontal ? 0 : decalage
  const dy = horizontal ? decalage : 0

  const ax = x1 + dx
  const ay = y1 + dy
  const bx = x2 + dx
  const by = y2 + dy
  const mx = (ax + bx) / 2
  const my = (ay + by) / 2

  const texte =
    libelle ?? `${Number(valeur).toFixed(2).replace('.', ',')}${unite ? ` ${unite}` : ''}`

  return (
    <g
      className="ao-cote"
      data-ao-cote
      data-ao-cote-provenance={provenance}
      data-ao-cote-axe={axe}
      stroke={couleur}
      fill="none"
      strokeWidth={trait}
    >
      {/* Lignes d'attache : du point relevé jusqu'au-delà de la ligne de cote. */}
      <line
        x1={x1}
        y1={y1}
        x2={ax + (horizontal ? 0 : Math.sign(decalage) * debord)}
        y2={ay + (horizontal ? Math.sign(decalage) * debord : 0)}
        className="ao-cote-attache"
      />
      <line
        x1={x2}
        y1={y2}
        x2={bx + (horizontal ? 0 : Math.sign(decalage) * debord)}
        y2={by + (horizontal ? Math.sign(decalage) * debord : 0)}
        className="ao-cote-attache"
      />

      {/* Ligne de cote. */}
      <line x1={ax} y1={ay} x2={bx} y2={by} className="ao-cote-ligne" />

      {/* Double flèche, une à chaque extrémité. */}
      {horizontal ? (
        <>
          <polyline points={`${ax + fleche},${ay - fleche / 2} ${ax},${ay} ${ax + fleche},${ay + fleche / 2}`} />
          <polyline points={`${bx - fleche},${by - fleche / 2} ${bx},${by} ${bx - fleche},${by + fleche / 2}`} />
        </>
      ) : (
        <>
          <polyline points={`${ax - fleche / 2},${ay + fleche} ${ax},${ay} ${ax + fleche / 2},${ay + fleche}`} />
          <polyline points={`${bx - fleche / 2},${by - fleche} ${bx},${by} ${bx + fleche / 2},${by - fleche}`} />
        </>
      )}

      {/* Texte orienté : horizontal sur un axe X, tourné d'un quart de tour sur
          un axe Y — comme sur un plan, jamais tête en bas. */}
      <text
        x={mx}
        y={my - corps * 0.35}
        fontSize={corps}
        textAnchor="middle"
        stroke="none"
        fill={couleur}
        className="ao-cote-texte"
        data-ao-cote-texte
        transform={horizontal ? undefined : `rotate(-90 ${mx} ${my})`}
      >
        {texte}
      </text>
    </g>
  )
}
