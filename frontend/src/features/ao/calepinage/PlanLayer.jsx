import { useCallback, useMemo, useRef } from 'react'
import { cn } from '../../../lib/cn'

/* ============================================================================
   AOF92 — `PlanLayer` : rendu du plan de calepinage CALCULÉ PAR LE SERVEUR.
   ----------------------------------------------------------------------------
   RÈGLE CARDINALE DE LA LANE (en-tête du Groupe AOF, reprise par AOF94) :
   **aucune position, aucune cote et aucun chiffre métier n'est calculé ici.**
   Ce composant est un TRADUCTEUR : il pose en SVG, verbatim, les rectangles,
   segments et textes que `core/calepinage/` a produits. Tout ce qui est
   calculé côté front se limite à la FENÊTRE d'affichage (viewBox = zoom +
   centre), qui n'est pas une grandeur métier.

   Conséquence assumée sur le repère : le serveur émet déjà des coordonnées de
   DESSIN (origine en haut-gauche du cadre, x vers la droite, y vers le bas),
   la conversion depuis le repère métier (y nord ↑) est faite une seule fois
   dans `core/calepinage/rendu` — le même code qui produit les planches
   imprimées. Le front ne renverse AUCUN axe : une planche PDF et l'écran
   montrent donc, par construction, exactement la même géométrie (« dessiné =
   compté »).

   ── Contrat de charge utile (publié ici, consommé tel quel) ────────────────
   plan = {
     cadre:   { x_min, y_min, largeur_m, hauteur_m },        // emprise dessinée
     rangees: [{ id, orientation: 'portrait'|'paysage'|'mixte',
                 tables: [{ id, x, y, largeur_m, hauteur_m,
                            faitage: { x1, y1, x2, y2 } }] }],
     allees:      [{ id, x, y, largeur_m, hauteur_m, cote?: { texte, x, y } }],
     rives:       [{ id, x, y, largeur_m, hauteur_m, cote?: { texte, x, y } }],
     degagements: [{ id, x, y, largeur_m, hauteur_m }],       // halos
     obstacles:   [{ id, repere, x, y, largeur_m, hauteur_m, provenance }],
     zones:       [{ id, nom, contour: [[x, y], …] }],
     legende?:    [{ cle, libelle }],   // libellés SERVEUR (facultatif)
   }
   Toute `cote` est un TEXTE déjà formaté par le serveur (formateur français
   `core.formats_fr`) : le front ne formate, n'arrondit et ne recompose aucun
   nombre.

   ── PV31 — bandes d'accroche du mode « rangées imposées » ─────────────────
   `rangeesImposees` (optionnel, `[[y0, kit], …]` — fourni par
   `useCalepinageImpose`) fait apparaître une bande interactive PAR RANGÉE à
   son ordonnée `y0` RÉELLE. L'épaisseur de la bande (`EPAISSEUR_BANDE_M`) est
   une géométrie d'INTERACTION, exactement au même titre que le zoom
   (AOF92) — jamais une cote posée par le moteur, jamais rendue comme une
   table. `yPropose` (ordonnée en cours de glissé) ne dessine qu'un TRAIT
   pointillé, jamais un rectangle : une pose qui n'est pas encore confirmée
   par le serveur ne peut pas se présenter comme une table.
   ========================================================================== */

// Présence d'une couche — question de RENDU (« y a-t-il quelque chose à
// dessiner ? »), volontairement écrite sur un paramètre anonyme : elle ne
// dérive aucune grandeur métier (cf. la garde de code d'AOF94).
const aDes = (liste) => Array.isArray(liste) && liste.length > 0

// Couches dessinables, dans l'ORDRE de superposition (du fond vers le dessus).
// `cle` sert aussi de clé de légende : la légende est GÉNÉRÉE depuis les
// couches réellement présentes dans la charge utile, jamais écrite en dur.
const COUCHES = [
  { cle: 'zones', libelle: 'Zones', champ: 'zones', swatch: 'fill-info/15 stroke-info' },
  { cle: 'allees', libelle: 'Allées cotées', champ: 'allees', swatch: 'fill-muted stroke-muted-foreground' },
  { cle: 'rives', libelle: 'Rives', champ: 'rives', swatch: 'fill-transparent stroke-muted-foreground' },
  { cle: 'degagements', libelle: 'Dégagements', champ: 'degagements', swatch: 'fill-warning/15 stroke-warning' },
  { cle: 'obstacles', libelle: 'Obstacles', champ: 'obstacles', swatch: 'fill-destructive/15 stroke-destructive' },
  { cle: 'tables', libelle: 'Tables PV (trait de faîtage)', champ: 'rangees', swatch: 'fill-primary/20 stroke-primary' },
]

// NB : helpers volontairement NON exportés — un fichier `.jsx` du dépôt
// n'exporte que des composants (`react-refresh/only-export-components`) ; ils
// sont couverts au travers du rendu par `PlanLayer.test.jsx`.
function legendeDuPlan(plan) {
  const libellesServeur = new Map(
    (plan?.legende || []).map((entree) => [entree.cle, entree.libelle]),
  )
  return COUCHES.filter((couche) => aDes(plan?.[couche.champ])).map((couche) => ({
    cle: couche.cle,
    libelle: libellesServeur.get(couche.cle) ?? couche.libelle,
    swatch: couche.swatch,
  }))
}

// Fenêtre d'affichage : SEUL calcul autorisé ici (géométrie de viewport, pas
// une grandeur métier). `zoom` > 1 rapproche ; `centre` recadre.
function viewBoxDuCadre(cadre, zoom = 1, centre = null) {
  if (!cadre) return '0 0 1 1'
  const facteur = Number.isFinite(zoom) && zoom > 0 ? zoom : 1
  const l = cadre.largeur_m / facteur
  const h = cadre.hauteur_m / facteur
  const cx = centre?.x ?? cadre.x_min + cadre.largeur_m / 2
  const cy = centre?.y ?? cadre.y_min + cadre.hauteur_m / 2
  return `${cx - l / 2} ${cy - h / 2} ${l} ${h}`
}

function Rectangles({ items, className, role }) {
  if (!aDes(items)) return null
  return (
    <g data-couche={role}>
      {items.map((item) => (
        <rect
          key={item.id}
          data-item={role}
          data-repere={item.repere ?? undefined}
          x={item.x}
          y={item.y}
          width={item.largeur_m}
          height={item.hauteur_m}
          className={className}
          vectorEffect="non-scaling-stroke"
          strokeWidth={1}
        />
      ))}
    </g>
  )
}

// PV31 — épaisseur de la bande d'accroche d'une rangée. Géométrie de VIEWPORT
// (comme `ZOOM_MIN/ZOOM_MAX` de `CalepinageStudio`), pas une cote posée par
// le moteur : elle sert uniquement à offrir une cible de pointeur.
const EPAISSEUR_BANDE_M = 0.30

// Ordonnée SVG (repère du `viewBox`) sous un `clientY` d'évènement pointeur.
// `getScreenCTM()`/`createSVGPoint()` ne sont pas implémentés par jsdom : on
// s'appuie sur `getBoundingClientRect()` (implémenté, et trivialement
// simulable en test), qui suffit puisque le SVG ne subit ni rotation ni
// inclinaison — seuls un décalage et une mise à l'échelle uniforme le long de
// l'axe Y séparent le repère écran du `viewBox`.
function yDepuisClientY(svgEl, viewBox, clientY) {
  if (!svgEl || typeof svgEl.getBoundingClientRect !== 'function') return null
  const rect = svgEl.getBoundingClientRect()
  if (!rect || !rect.height) return null
  const morceaux = String(viewBox).split(' ').map(Number)
  const [, vbY, , vbH] = morceaux
  if (!Number.isFinite(vbY) || !Number.isFinite(vbH)) return null
  return vbY + ((clientY - rect.top) / rect.height) * vbH
}

function Cotes({ items }) {
  if (!aDes(items)) return null
  const cotes = items.filter((item) => item.cote?.texte)
  if (!aDes(cotes)) return null
  return (
    <g data-couche="cotes">
      {cotes.map((item) => (
        <text
          key={`cote-${item.id}`}
          data-item="cote"
          x={item.cote.x}
          y={item.cote.y}
          className="fill-foreground"
          style={{ fontSize: '0.35px' }}
          textAnchor="middle"
        >
          {item.cote.texte}
        </text>
      ))}
    </g>
  )
}

/**
 * Rend le plan de calepinage renvoyé par le serveur.
 *
 * @param {object}  plan       Charge utile serveur (contrat ci-dessus).
 * @param {number}  [zoom=1]   Facteur de zoom (fenêtre d'affichage seulement).
 * @param {{x:number,y:number}} [centre]  Centre de la fenêtre (m).
 * @param {string}  [titre]    Nom accessible du canvas.
 * @param {Array}   [rangeesImposees]  PV31 — `[[y0, kit], …]` à éditer ; `null`/absent = pas de bandes.
 * @param {number|null} [rangeeSelectionnee]  Index sélectionné dans `rangeesImposees`.
 * @param {number|null} [yPropose]  Ordonnée en cours de glissé (ligne pointillée).
 * @param {Function} [onRangeePointerDown]  `(index, event) => void` — pointerdown sur une bande.
 * @param {Function} [onFondPointerDown]    `(y, event) => void` — pointerdown hors bande (ajout).
 * @param {Function} [onPointerMoveSvg]     `(y, event) => void` — déplacement sur le canvas.
 * @param {Function} [onPointerUpSvg]       `(event) => void` — relâchement sur le canvas.
 */
export default function PlanLayer({
  plan, zoom = 1, centre = null, titre = 'Plan de calepinage', className,
  rangeesImposees = null, rangeeSelectionnee = null, yPropose = null,
  onRangeePointerDown, onFondPointerDown, onPointerMoveSvg, onPointerUpSvg,
}) {
  const viewBox = useMemo(() => viewBoxDuCadre(plan?.cadre, zoom, centre), [plan?.cadre, zoom, centre])
  const legende = useMemo(() => legendeDuPlan(plan), [plan])
  const svgRef = useRef(null)

  // PV31 — pointerdown sur le FOND (pas sur une bande, qui appelle
  // `stopPropagation`) : ajoute une rangée à l'ordonnée cliquée.
  const gererPointerDownFond = useCallback((event) => {
    if (!onFondPointerDown) return
    const y = yDepuisClientY(svgRef.current, viewBox, event.clientY)
    if (y === null) return
    onFondPointerDown(y, event)
  }, [onFondPointerDown, viewBox])

  const gererPointerMove = useCallback((event) => {
    if (!onPointerMoveSvg) return
    const y = yDepuisClientY(svgRef.current, viewBox, event.clientY)
    if (y === null) return
    onPointerMoveSvg(y, event)
  }, [onPointerMoveSvg, viewBox])

  if (!plan?.cadre) return null

  return (
    <div className={cn('flex min-h-0 flex-1 flex-col gap-2', className)}>
      <svg
        ref={svgRef}
        data-ao-canvas="calepinage"
        role="img"
        aria-label={titre}
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        className="min-h-0 w-full flex-1 rounded-md border border-border bg-card"
        onPointerDown={gererPointerDownFond}
        onPointerMove={gererPointerMove}
        onPointerUp={onPointerUpSvg}
      >
        <title>{titre}</title>

        {/* Zones : contours polygonaux fournis par le serveur. */}
        {aDes(plan.zones) && (
          <g data-couche="zones">
            {plan.zones.map((zone) => (
              <polygon
                key={zone.id}
                data-item="zone"
                points={(zone.contour || []).map((point) => point.join(',')).join(' ')}
                className="fill-info/10 stroke-info"
                vectorEffect="non-scaling-stroke"
                strokeWidth={1}
              />
            ))}
          </g>
        )}

        <Rectangles items={plan.allees} role="allee" className="fill-muted/60 stroke-muted-foreground" />
        <Rectangles items={plan.rives} role="rive" className="fill-none stroke-muted-foreground [stroke-dasharray:4_3]" />
        <Rectangles items={plan.degagements} role="degagement" className="fill-warning/15 stroke-warning" />
        <Rectangles items={plan.obstacles} role="obstacle" className="fill-destructive/15 stroke-destructive" />

        {/* Tables PV : rectangle + trait de faîtage, tous deux aux coordonnées
            SERVEUR. Les rangées sont des groupes — jamais un regroupement
            recalculé côté front. */}
        {aDes(plan.rangees) && (
          <g data-couche="tables">
            {plan.rangees.map((rangee) => (
              <g key={rangee.id} data-item="rangee" data-orientation={rangee.orientation}>
                {(rangee.tables || []).map((table) => (
                  <g key={table.id}>
                    <rect
                      data-item="table"
                      x={table.x}
                      y={table.y}
                      width={table.largeur_m}
                      height={table.hauteur_m}
                      className="fill-primary/20 stroke-primary"
                      vectorEffect="non-scaling-stroke"
                      strokeWidth={1}
                    />
                    {table.faitage && (
                      <line
                        data-item="faitage"
                        x1={table.faitage.x1}
                        y1={table.faitage.y1}
                        x2={table.faitage.x2}
                        y2={table.faitage.y2}
                        className="stroke-primary"
                        vectorEffect="non-scaling-stroke"
                        strokeWidth={1.5}
                      />
                    )}
                  </g>
                ))}
              </g>
            ))}
          </g>
        )}

        <Cotes items={[...(plan.allees || []), ...(plan.rives || [])]} />

        {/* Repères lettrés des obstacles (A, B, C…) — texte SERVEUR. */}
        {aDes(plan.obstacles) && (
          <g data-couche="reperes">
            {plan.obstacles.filter((obstacle) => obstacle.repere).map((obstacle) => (
              <text
                key={`repere-${obstacle.id}`}
                data-ao-repere={obstacle.repere}
                x={obstacle.x}
                y={obstacle.y}
                className="fill-destructive font-semibold"
                style={{ fontSize: '0.4px' }}
              >
                {obstacle.repere}
              </text>
            ))}
          </g>
        )}

        {/* PV31 — bandes d'accroche des rangées (interaction seule, jamais
            une table) : couche VOLONTAIREMENT la plus HAUTE, pour capter le
            pointeur avant tout ce qui est dessous. */}
        {Array.isArray(rangeesImposees) && (
          <g data-couche="rangees-imposees">
            {rangeesImposees.map((ligne, index) => (
              <rect
                key={`bande-${index}`}
                data-item="rangee-bande"
                data-rangee-index={index}
                data-rangee-selectionnee={rangeeSelectionnee === index ? 'true' : undefined}
                aria-label={`Rangée ${index + 1}`}
                x={plan.cadre.x_min}
                y={ligne[0]}
                width={plan.cadre.largeur_m}
                height={EPAISSEUR_BANDE_M}
                className={cn(
                  'cursor-grab fill-transparent stroke-transparent',
                  '[@media(hover:hover)]:hover:fill-info/10',
                  rangeeSelectionnee === index && 'fill-info/20 stroke-info [stroke-dasharray:2_2]',
                )}
                vectorEffect="non-scaling-stroke"
                strokeWidth={1}
                onPointerDown={(event) => {
                  event.stopPropagation()
                  onRangeePointerDown?.(index, event)
                }}
              />
            ))}
          </g>
        )}

        {/* Ligne PROPOSÉE pendant un glissé — un TRAIT, jamais un rectangle :
            une pose non confirmée par le serveur ne se présente pas comme une
            table posée (AOF92/AOF94). */}
        {Number.isFinite(yPropose) && (
          <line
            data-item="rangee-proposee"
            x1={plan.cadre.x_min}
            y1={yPropose}
            x2={plan.cadre.x_min + plan.cadre.largeur_m}
            y2={yPropose}
            className="stroke-info [stroke-dasharray:6_3]"
            vectorEffect="non-scaling-stroke"
            strokeWidth={2}
          />
        )}
      </svg>

      {aDes(legende) && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Légende du plan">
          {legende.map((entree) => (
            <li key={entree.cle} data-legende={entree.cle} className="flex items-center gap-1.5">
              <svg viewBox="0 0 10 10" className="size-3" aria-hidden="true">
                <rect x="0.5" y="0.5" width="9" height="9" className={entree.swatch} strokeWidth={1} />
              </svg>
              {entree.libelle}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
