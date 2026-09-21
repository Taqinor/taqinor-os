import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import { construireCoupe, MONTANT_AVANT_M } from '../coupeRangees'
import { formatNumber } from '../../../lib/format'

/* ============================================================================
   CALX121 — LE PANNEAU « COUPE » : LA COUPE TRANSVERSALE D'UNE RANGÉE SUR
   L'AUTRE.
   ----------------------------------------------------------------------------
   CONSTAT. Le pas inter-rangées est déjà calculé par la géométrie solaire
   (`apps/web/src/lib/roofPro2.ts:320-346`) puis vérifié par lancer de rayons
   (`apps/web/src/scripts/roofPro11/scene3d.ts:1959-2008`, `publishRowPitch`),
   mais le résultat n'est qu'un TEXTE : rien ne DESSINE la coupe, et le
   commercial ne peut pas montrer pourquoi le pas vaut ce qu'il vaut.
   Parité HelioScope — le pas de rangée se règle par une règle d'ombrage nulle
   de 10 h à 14 h au solstice d'hiver :
   https://help-center.helioscope.com/hc/en-us/articles/4465778056595-Step-by-Step-Commercial-Design

   CE PANNEAU NE POSE RIEN ET NE CALCULE AUCUNE PHYSIQUE : toute l'arithmétique
   (inclinaison, pas MESURÉ, hauteur hors-tout, rayon solaire de conception,
   longueur d'ombre) vit dans `../coupeRangees.js`, une fonction PURE. Ce
   fichier lit le document `roof_layout` déjà persisté (MÊME source que
   `CourseSoleil.jsx` — `GET .../layout/`, jamais `builderApi` : le document
   est ce que le serveur et le 3D s'accordent à dire), choisit le pan ACTIF
   (`activeAreaId`), et met la coupe renvoyée EN PAGE.

   ÉTAT VIDE, JAMAIS UN DESSIN INVENTÉ : un pan sans géométrie posée, une
   inclinaison absente, un pas non mesurable (moins de deux rangées) ou une
   latitude inconnue affichent tous « non calculée » et le motif exact que
   `construireCoupe` a renvoyé — jamais une coupe à moitié dessinée.
   ========================================================================== */

// Conventions de DESSIN uniquement (mise à l'échelle du SVG) — aucune ne
// modifie ni n'approxime une valeur physique lue de la coupe.
const PX_PAR_M = 90
const MARGE_G = 30
const MARGE_D = 40
const MARGE_H = 20
const HAUTEUR_SOL = 40
const EPAISSEUR_PANNEAU_PX = 4

function xPx(metres) {
  return MARGE_G + metres * PX_PAR_M
}
function yPx(hauteurM) {
  return HAUTEUR_SOL - hauteurM * PX_PAR_M
}

function CoupeSvg({ coupe }) {
  const baseM = coupe.flush ? 0 : MONTANT_AVANT_M
  const sommetM = coupe.flush ? coupe.riseM : coupe.hauteurHorsToutM
  const rangee1 = { xAvant: 0, xArriere: coupe.depthFootprintM }
  const rangee2 = { xAvant: coupe.rowPitchM, xArriere: coupe.rowPitchM + coupe.depthFootprintM }
  const largeurTotaleM = rangee2.xArriere + Math.max(0.4, coupe.longueurOmbreM * 0.15)
  const largeurPx = xPx(largeurTotaleM) + MARGE_D
  const hauteurPx = HAUTEUR_SOL + MARGE_H + Math.max(sommetM, 0.5) * PX_PAR_M

  const xOmbre = coupe.longueurOmbreM > 0 ? rangee1.xArriere + coupe.longueurOmbreM : null
  const ombreAtteintRangee2 = xOmbre !== null && xOmbre > rangee2.xAvant

  return (
    <svg
      viewBox={`0 0 ${largeurPx} ${hauteurPx}`}
      role="img"
      aria-label={`Coupe transversale de deux rangées consécutives, inclinaison ${coupe.tiltDeg}°, pas ${coupe.rowPitchM.toFixed(2)} m`}
      className="w-full max-w-2xl"
      data-testid="cal-coupe-svg"
    >
      {/* Toit / sol de référence. */}
      <line
        x1={0} y1={yPx(0)} x2={largeurPx} y2={yPx(0)}
        stroke="#3a4258" strokeWidth="1"
        data-testid="cal-coupe-sol"
      />

      {[rangee1, rangee2].map((r, i) => (
        <line
          key={i}
          x1={xPx(r.xAvant)} y1={yPx(baseM)}
          x2={xPx(r.xArriere)} y2={yPx(sommetM)}
          stroke="#e0b25c" strokeWidth={EPAISSEUR_PANNEAU_PX}
          strokeLinecap="round"
          data-testid={`cal-coupe-rangee-${i}`}
        />
      ))}

      {/* Cote du pas, entre les deux bords avant. */}
      <line
        x1={xPx(rangee1.xAvant)} y1={yPx(0) + 14} x2={xPx(rangee2.xAvant)} y2={yPx(0) + 14}
        stroke="#8f9bb8" strokeWidth="1" markerStart="url(#cal-coupe-fleche)" markerEnd="url(#cal-coupe-fleche)"
      />
      <text
        x={(xPx(rangee1.xAvant) + xPx(rangee2.xAvant)) / 2} y={yPx(0) + 28}
        fontSize="11" fill="#8f9bb8" textAnchor="middle"
        data-testid="cal-coupe-cote-pas"
      >
        {`pas ${coupe.rowPitchM.toFixed(2)} m`}
      </text>

      {/* Rayon solaire de conception, arrivant sur le bord arrière (haut) de
          la première rangée, et l'ombre qu'il projette au sol. */}
      {coupe.longueurOmbreM > 0 && (
        <>
          <line
            x1={xPx(rangee1.xArriere) - 30} y1={yPx(sommetM) - 30}
            x2={xPx(rangee1.xArriere)} y2={yPx(sommetM)}
            stroke="#f4d35e" strokeWidth="1.5" strokeDasharray="3 2"
            data-testid="cal-coupe-rayon-solaire"
          />
          <line
            x1={xPx(rangee1.xArriere)} y1={yPx(0)}
            x2={xPx(xOmbre)} y2={yPx(0)}
            stroke="#f4d35e" strokeWidth="3"
            data-testid="cal-coupe-ombre"
          />
          <text
            x={(xPx(rangee1.xArriere) + xPx(xOmbre)) / 2} y={yPx(0) - 6}
            fontSize="10" fill="#f4d35e" textAnchor="middle"
          >
            {`ombre ${coupe.longueurOmbreM.toFixed(2)} m`}
          </text>
        </>
      )}

      <defs>
        <marker id="cal-coupe-fleche" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <circle cx="3" cy="3" r="1.5" fill="#8f9bb8" />
        </marker>
      </defs>

      {ombreAtteintRangee2 && (
        <text
          x={xPx(rangee2.xAvant)} y={yPx(0) - 20}
          fontSize="10" fill="#d0654f" textAnchor="middle"
          data-testid="cal-coupe-alerte-ombrage"
        >
          L’ombre atteint la rangée suivante à ce pas
        </text>
      )}
    </svg>
  )
}

export default function OngletCoupeRangees({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [layout, setLayout] = useState(null)
  const [chargement, setChargement] = useState(() => Boolean(calepinageId))
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        setLayout(res?.data?.roof_layout ?? null)
      })
      .catch(() => { if (!annule) setErreur('Impossible de charger la conception.') })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [calepinageId])

  const zones = Array.isArray(layout?.zones) ? layout.zones : []
  const zone = zones.find((z) => z.id === layout?.activeAreaId) ?? zones[0] ?? null
  const latitudeDeg = typeof layout?.pin?.lat === 'number' ? layout.pin.lat : null

  const coupe = zone ? construireCoupe({ zone, latitudeDeg }) : null

  if (chargement) {
    return (
      <p className="mt-3 text-sm text-lune-faint" data-testid="cal-coupe-chargement">
        Chargement de la coupe…
      </p>
    )
  }

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-coupe-panel">
      <p className="tech-label rule-brass text-brass-300">Coupe</p>
      <p className="mt-1 text-sm text-lune-faint">
        Coupe transversale de deux rangées consécutives du pan actif : inclinaison, pas,
        hauteur hors-tout, rayon solaire de conception (midi, solstice d’hiver) et longueur
        d’ombre — toutes valeurs lues de la géométrie déjà posée, aucune recalculée.
      </p>

      {erreur && <p className="mt-2 text-sm text-red-300" role="alert">{erreur}</p>}

      {!erreur && !zone && (
        <p className="mt-3 text-sm text-lune-faint" data-testid="cal-coupe-vide">
          Aucun pan tracé dans cette conception.
        </p>
      )}

      {!erreur && zone && coupe && !coupe.disponible && (
        <p className="mt-3 text-sm text-lune-faint" data-testid="cal-coupe-non-calculee">
          {`Coupe non calculée — ${coupe.motif}`}
        </p>
      )}

      {!erreur && zone && coupe?.disponible && (
        <div className="mt-4">
          <CoupeSvg coupe={coupe} />
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-lune-faint sm:grid-cols-3">
            <div data-testid="cal-coupe-inclinaison">
              <dt className="tech-label">Inclinaison</dt>
              <dd className="fig text-white">{`${formatNumber(coupe.tiltDeg, { decimals: 1 })}°`}</dd>
            </div>
            <div data-testid="cal-coupe-pas">
              <dt className="tech-label">Pas mesuré</dt>
              <dd className="fig text-white">{`${formatNumber(coupe.rowPitchM, { decimals: 2 })} m`}</dd>
            </div>
            <div data-testid="cal-coupe-hauteur">
              <dt className="tech-label">Hauteur hors-tout</dt>
              <dd className="fig text-white">
                {coupe.hauteurHorsToutM === null
                  ? 'non applicable (pose affleurante)'
                  : `${formatNumber(coupe.hauteurHorsToutM, { decimals: 2 })} m`}
              </dd>
            </div>
            <div data-testid="cal-coupe-rayon-solaire-valeur">
              <dt className="tech-label">Rayon solaire (midi, solstice d’hiver)</dt>
              <dd className="fig text-white">{`${formatNumber(coupe.rayonSolaireDeg, { decimals: 1 })}°`}</dd>
            </div>
            <div data-testid="cal-coupe-longueur-ombre">
              <dt className="tech-label">Longueur d’ombre</dt>
              <dd className="fig text-white">{`${formatNumber(coupe.longueurOmbreM, { decimals: 2 })} m`}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  )
}
