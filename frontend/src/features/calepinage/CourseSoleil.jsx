import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import SunDiagram, { COURBES_REPERE } from './SunDiagram'
import { HAUTEUR_TOIT_HYPOTHESE_M, centroideDuContour, obstructionsDuPan } from './obstructionMath'

/* ============================================================================
   CAL96 — LA COURSE DU SOLEIL, PAR PAN.
   ----------------------------------------------------------------------------
   Constat de la tâche : l'astronomie est disponible (`sunDirection`, consommée
   par `shadingUi.ts`/`scene3d.ts`) mais aucun diagramme de course du soleil
   n'était affiché nulle part. Ce diagramme se lit PAR PAN (les toitures
   multi-plans, CAL59, n'ont pas toutes le même azimut ni la même hauteur
   d'obstruction) : un sélecteur choisit le pan (zone du document) sur lequel
   le diagramme se recentre.

   MÊME REPÈRE que `HorizonPanel.jsx` (CAL93, `SunDiagram.jsx` partagé) :
   solstices/équinoxe en fond, l'horizon lointain (CAL92/CAL93) en aire pleine
   par-dessus, et ICI en plus les obstructions PROCHES (CAL94 — obstacles de
   toiture à hauteur saisie CAL66 + objets d'environnement CAL67, les deux
   seules sources qui voyagent dans le document) marquées à leur azimut/hauteur
   angulaire RÉELS, vus depuis le centroïde du pan sélectionné.

   ZÉRO CHIFFRE INVENTÉ : sans repère GPS (pin), aucune course n'est tracée ;
   un obstacle sans hauteur saisie n'apparaît pas (il ne projette rien) ; aucune
   donnée météo n'entre dans ce diagramme — c'est de la géométrie/astronomie
   pure, pas une prévision.

   CALX52 — LA HAUTEUR DE TOIT SUPPOSÉE DU DIAGRAMME, ENFIN LISIBLE.
   ----------------------------------------------------------------------------
   Constat : `obstructionMath.js` exporte `HAUTEUR_TOIT_HYPOTHESE_M = 6` « en
   se déclarant affichée comme telle », mais cet écran appelait
   `obstructionsDuPan(origine, obstacles, environment)` SANS le 4ᵉ argument —
   la valeur retombait donc silencieusement à 6 m, sans qu'aucun mot ne le
   dise à l'écran. Cette hauteur ne sert qu'aux objets d'ENVIRONNEMENT
   référencés au sol (CAL67) : leur hauteur EFFECTIVE au-dessus du plan du
   champ est `heightM − roofHeightM`. Ce panneau AFFICHE la hauteur employée
   et sa provenance sous le diagramme, et offre un champ qui la REMPLACE (la
   provenance passe alors à « saisie ») ; sans saisie, la mention exacte
   accompagne chaque marqueur d'obstruction proche.
   ========================================================================== */

/** La mention exacte exigée par la tâche — jamais reformulée. */
const MENTION_HYPOTHESE_TOIT = 'hauteur de toit supposée à 6 m (2 étages × '
  + '3 m), non mesurée'

function libellePan(zone, index) {
  return zone?.label || `Pan ${index + 1}`
}

export default function CourseSoleil({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [layout, setLayout] = useState(null)
  const [panId, setPanId] = useState(null)
  const [chargement, setChargement] = useState(!!calepinageId)
  const [erreur, setErreur] = useState(null)
  // CALX52 — vide = l'hypothèse par défaut (6 m) ; une saisie valide la
  // REMPLACE et fait passer la provenance à « saisie ».
  const [hauteurToitSaisie, setHauteurToitSaisie] = useState('')

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        const document = res?.data?.roof_layout ?? null
        setLayout(document)
        const zones = Array.isArray(document?.zones) ? document.zones : []
        const active = zones.find((z) => z.id === document?.activeAreaId) ?? zones[0]
        setPanId(active?.id ?? null)
      })
      .catch(() => { if (!annule) setErreur('Impossible de charger la conception.') })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [calepinageId])

  const zones = Array.isArray(layout?.zones) ? layout.zones : []
  const zone = zones.find((z) => z.id === panId) ?? zones[0] ?? null
  const latitudeDeg = typeof layout?.pin?.lat === 'number' ? layout.pin.lat : null
  const horizonPoints = Array.isArray(layout?.horizonProfile?.points) ? layout.horizonProfile.points : []

  // CALX52 — la hauteur RETENUE et sa provenance : une saisie numérique
  // valide REMPLACE l'hypothèse (jamais un NaN qui glisserait dans la
  // géométrie) ; sans saisie exploitable, l'hypothèse documentée s'applique.
  const nombreSaisi = hauteurToitSaisie === '' ? null : Number(hauteurToitSaisie)
  const hauteurToitSaisieValide = nombreSaisi !== null && Number.isFinite(nombreSaisi)
  const provenanceHauteurToit = hauteurToitSaisieValide ? 'saisie' : 'hypothese'
  const hauteurToitM = hauteurToitSaisieValide ? nombreSaisi : HAUTEUR_TOIT_HYPOTHESE_M

  const obstructions = useMemo(() => {
    if (!zone) return []
    const origine = centroideDuContour(zone.vertices)
    if (!origine) return []
    return obstructionsDuPan(origine, zone.obstacles, layout?.environment, hauteurToitM)
  }, [zone, layout?.environment, hauteurToitM])

  if (chargement) {
    return <div className="cine-card mt-6 p-6" data-testid="cal-course-soleil-loading">Chargement…</div>
  }

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-course-soleil">
      <p className="tech-label rule-brass text-brass-300">Course du soleil</p>
      <p className="mt-1 text-sm text-lune-faint">
        Azimut (0°=Nord) en abscisse, hauteur du soleil en ordonnée, pour les trois jours
        de repère (solstices et équinoxe). L’horizon lointain saisi (Horizon lointain) et
        les obstructions proches à hauteur saisie sont surimprimés à leur position réelle.
      </p>

      {erreur && <p className="mt-2 text-sm text-red-300" role="alert">{erreur}</p>}

      {zones.length > 1 && (
        <div className="mt-3">
          <label htmlFor="cal-course-soleil-pan" className="tech-label text-lune-faint">
            Pan
          </label>
          <select
            id="cal-course-soleil-pan"
            value={panId ?? ''}
            onChange={(e) => setPanId(e.target.value)}
            className="mt-1 block rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
          >
            {zones.map((z, i) => (
              <option key={z.id} value={z.id}>{libellePan(z, i)}</option>
            ))}
          </select>
        </div>
      )}

      {!zone && !erreur && (
        <p className="mt-3 text-sm text-lune-faint">Aucun pan tracé dans cette conception.</p>
      )}

      {zone && (
        <div className="mt-4">
          <SunDiagram
            latitudeDeg={latitudeDeg}
            horizonPoints={horizonPoints}
            obstructions={obstructions}
            ariaLabel={`Course du soleil du pan ${libellePan(zone, zones.indexOf(zone))}`}
          />
          <div className="mt-1 flex flex-wrap gap-3 text-xs text-lune-faint">
            {COURBES_REPERE.map((c) => (
              <span key={c.jour} className="inline-flex items-center gap-1">
                <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 2, background: c.couleur }} />
                {c.label}
              </span>
            ))}
            <span className="inline-flex items-center gap-1">
              <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 10, background: 'rgba(90,60,30,0.55)' }} />
              Horizon lointain
            </span>
            <span className="inline-flex items-center gap-1">
              <span aria-hidden="true" style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#d0654f' }} />
              Obstruction proche
            </span>
          </div>

          {/* CALX52 — la hauteur de toit EMPLOYÉE et sa provenance, TOUJOURS
              lisibles sous le diagramme (jamais une valeur muette). */}
          <div className="mt-3 border-t border-white/10 pt-3" data-testid="cal-course-soleil-hauteur-toit">
            <label htmlFor="cal-course-soleil-hauteur-toit-champ" className="tech-label text-lune-faint">
              Hauteur de toit employée pour les obstructions proches
            </label>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <input
                id="cal-course-soleil-hauteur-toit-champ"
                data-testid="cal-course-soleil-hauteur-toit-champ"
                type="number"
                step="any"
                value={hauteurToitSaisie}
                onChange={(e) => setHauteurToitSaisie(e.target.value)}
                placeholder={String(HAUTEUR_TOIT_HYPOTHESE_M)}
                className="w-24 rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
              />
              <span className="fig text-sm text-white" data-testid="cal-course-soleil-hauteur-toit-valeur">
                {`${hauteurToitM} m`}
              </span>
            </div>
            <p
              className="mt-1 text-xs text-lune-faint"
              data-testid="cal-course-soleil-hauteur-toit-provenance"
            >
              {provenanceHauteurToit === 'saisie'
                ? `Hauteur de toit saisie : ${hauteurToitM} m.`
                : MENTION_HYPOTHESE_TOIT}
            </p>
          </div>

          {/* La mention accompagne CHAQUE marqueur d'obstruction proche
              (règle de la tâche) : aucune obstruction n'est tracée sans que
              la hauteur employée soit lisible juste à côté d'elle. */}
          {obstructions.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-lune-faint" data-testid="cal-course-soleil-obstructions-hauteur">
              {obstructions.map((o, i) => (
                <li
                  key={`${o.label ?? 'obs'}-${i}`}
                  data-testid={`cal-course-soleil-obstruction-hauteur-${i}`}
                >
                  {`${o.label ?? 'Obstruction'} — ${provenanceHauteurToit === 'saisie'
                    ? `hauteur de toit saisie : ${hauteurToitM} m`
                    : MENTION_HYPOTHESE_TOIT}`}
                </li>
              ))}
            </ul>
          )}

          {latitudeDeg === null && (
            <p className="mt-1 text-xs text-amber-300">
              Latitude du site inconnue (aucun repère posé) — la course du soleil n’est pas tracée.
            </p>
          )}
          {!horizonPoints.length && (
            <p className="mt-1 text-xs text-lune-faint">
              Aucun horizon lointain saisi (voir « Horizon lointain ») — non tracé.
            </p>
          )}
          {!obstructions.length && (
            <p className="mt-1 text-xs text-lune-faint">
              Aucune obstruction proche à hauteur saisie sur ce pan — aucune n’est surimprimée.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
