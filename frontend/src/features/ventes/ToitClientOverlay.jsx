/* L-MAP (fondateur 26/08/2026 : « when the client draws its roof, there is a
   special section in the lead form that shows it — but I want it VISIBLE ON
   THE MAP IN THE 3D LAYOUTER ») — le contour dessiné par le client, rendu
   comme repère PASSIF sur la carte du calepinage 3D (`ToitureDesign.jsx`).
   ---------------------------------------------------------------------------
   MÊME calcul que la fiche lead (`traceToit.js`, `TraceToitClient.jsx`, PR
   #568) : `dessinerContour`/`formaterSurface` sont APPELÉS, jamais réécrits —
   la surface affichée ici est TOUJOURS celle déjà validée côté fiche lead,
   jamais un second calcul qui pourrait diverger (règle « zéro chiffre
   inventé »).

   POURQUOI UN CALQUE SÉPARÉ, PAS LE TRACÉ DU BUILDER LUI-MÊME. Le builder
   (`@roofbuilder`, apps/web/src/scripts/roofPro11) SÈME déjà sa zone active
   depuis `roof_outline` au boot (`hydrateFromLead`/`hydrateFromDevis`) — mais
   cette zone est ENSUITE éditable (le commercial la retouche, ajoute des
   zones, glisse des panneaux) : après une édition, plus rien à l'écran ne
   montre ce que le client a RÉELLEMENT dessiné. Ce calque garde une trace
   PERMANENTE et NON ÉDITABLE de ce dessin d'origine, à côté du calepinage
   courant — jamais confondue avec lui.

   AUCUNE INTERFÉRENCE AVEC LES INTERACTIONS EXISTANTES (tracé, glissé de
   panneau, sélection de groupe/rangée PV34) : `pointer-events: none` sur tout
   le bloc (roofbuilder.css) — le navigateur route déjà tout événement de
   pointeur SOUS ce calque, quel que soit son z-index. Rien à câbler, rien à
   tester du côté « le clic traverse » : c'est une garantie du CSS, pas un
   comportement JS à maintenir.

   RIEN N'EST INVENTÉ : sans contour exploitable (< 3 sommets, emprise nulle),
   `dessinerContour` rend `null` et ce composant rend `null` — jamais un cadre
   vide, jamais un « 0 m² ». */
import { useMemo } from 'react'
import { dessinerContour, formaterSurface } from '../crm/workspace/traceToit'

export default function ToitClientOverlay({ contour, visible = true }) {
  const dessin = useMemo(() => dessinerContour(contour), [contour])
  if (!dessin || !visible) return null

  const surface = formaterSurface(dessin.aireM2)
  const libelle = surface ? `Toit dessiné par le client · ${surface}` : 'Toit dessiné par le client'

  return (
    <div className="rp9-toit-client" data-testid="rp9-toit-client" aria-hidden="true">
      <svg
        className="rp9-toit-client-forme"
        viewBox={`-2 -2 ${dessin.largeur + 4} ${dessin.hauteur + 4}`}
        preserveAspectRatio="xMidYMid meet"
        focusable="false"
      >
        <polygon points={dessin.points} className="rp9-toit-client-polygone" />
      </svg>
      <p className="rp9-toit-client-label">{libelle}</p>
    </div>
  )
}
