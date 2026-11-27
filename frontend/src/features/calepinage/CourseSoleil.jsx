import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import useDocumentCalepinage, { useLatitudeDuSite } from './useDocumentCalepinage'
import SunDiagram from './SunDiagram'
import { LegendeCourbes } from './LegendeCourbes'
import { sunDirection as sunPosition, WINTER_SOLSTICE_DAY as JOUR_SOLSTICE_HIVER } from '@rooflib/roofPro2'
import { HAUTEUR_TOIT_HYPOTHESE_M, centroideDuContour, obstructionsDuPan } from './obstructionMath'
import { idBatimentDuPan } from '@roofpro/batiment'
import RetourAtelier from './atelier/RetourAtelier'
import { PhraseHeureIndisponible, dateDuJourDeScene, formaterHeureLegale, useAnneeSoleil, useHeureLegale } from './HeureLegale'

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

   ACAL74 — LA HAUTEUR DU BÂTIMENT VIENT DU DOCUMENT, PAS D'UNE SAISIE D'ÉCRAN.
   ----------------------------------------------------------------------------
   Le champ « hauteur de toit » de cet écran était une saisie locale perdue au
   rechargement, alors que l'atelier écrit déjà la hauteur du bâtiment
   (`buildings[].hauteurM` + sa `source`, désigné par `zones[].buildingId`). Le
   panneau lit désormais CETTE hauteur — document lu par `useDocumentCalepinage`
   — et l'affiche avec sa provenance. Sans hauteur de bâtiment pour le pan,
   l'hypothèse de 6 m reste affichée comme telle, avec un lien vers l'atelier
   pour la saisir : il n'y a plus de second endroit où la saisir.

   CALX118 — LE SOLEIL DE SCÈNE, ENFIN VISIBLE DANS LE DIAGRAMME.
   ----------------------------------------------------------------------------
   Constat : le diagramme polaire existait déjà (`SunDiagram.jsx`) mais aucun
   repère n'y suivait le soleil de scène du builder 3D (contrat CALX88,
   `scene{sunDay,sunHour}` — le jour/l'heure RÉELLEMENT affichés à l'atelier).
   Ce panneau lit `layout.scene` (racine du document, à côté de `horizonProfile`
   et `pin`) et le passe à `SunDiagram`, qui trace le repère avec la MÊME
   formule que les trois courbes de référence (`sunPosition`, jamais une
   deuxième). `scene` absent (document antérieur à CALX88/CALX119, ou jamais
   touché) ⇒ comportement d'aujourd'hui NOMMÉ : solstice d'hiver, midi — jamais
   un 21 juin supposé silencieusement.
   ========================================================================== */

/** La mention exacte exigée par la tâche — jamais reformulée. */
const MENTION_HYPOTHESE_TOIT = 'hauteur de toit supposée à 6 m (2 étages × '
  + '3 m), non mesurée'

/** CALX118 — soleil de scène par défaut quand `layout.scene` est absent : le MÊME
 *  défaut que le builder 3D (`roof-tool-pro11.ts`, W87) — solstice d'hiver, midi. */
const SCENE_SUN_HOUR_DEFAUT = 12

function libellePan(zone, index) {
  return zone?.label || `Pan ${index + 1}`
}

export default function CourseSoleil({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  // ACAL74 — l'UNIQUE lecture du document (hook) : un échec est une erreur, jamais
  // un document vide.
  const doc = useDocumentCalepinage(calepinageId)
  const layout = doc.document
  const chargement = doc.etat === 'chargement'
  const erreur = doc.etat === 'erreur' ? 'Impossible de charger la conception.' : null
  // Le pan CHOISI par l'utilisateur ; sinon le pan actif du document, sinon le premier.
  const [panChoisi, setPanChoisi] = useState(null)

  const zones = Array.isArray(layout?.zones) ? layout.zones : []
  const zone = zones.find((z) => z.id === panChoisi)
    ?? zones.find((z) => z.id === layout?.activeAreaId) ?? zones[0] ?? null
  // ACAL251 — latitude de l'épingle du document, sinon du repère servi (détail).
  const latitudeDeg = useLatitudeDuSite(calepinageId, layout)
  // ACAL449 — la table d'ombrage servie du pan (écrite par le constructeur, ACAL459) :
  // les bornes de la légende sont celles de la table, au format français.
  const tableOmbrage = zone?.geometry?.shadeTable ?? null
  const facteursOmbrage = Array.isArray(tableOmbrage?.facteurs)
    ? tableOmbrage.facteurs.flat().filter((f) => typeof f === 'number' && f >= 0 && f <= 1) : []
  const fr = (n) => String(n).replace('.', ',')
  const horizonPoints = Array.isArray(layout?.horizonProfile?.points) ? layout.horizonProfile.points : []

  // CALX118 — le soleil de SCÈNE (contrat CALX88) : `scene` absent ⇒ le défaut
  // NOMMÉ du builder (solstice d'hiver, midi), jamais un instant deviné en silence.
  const sceneEnregistree = typeof layout?.scene?.sunDay === 'number' && Number.isFinite(layout.scene.sunDay)
    && typeof layout?.scene?.sunHour === 'number' && Number.isFinite(layout.scene.sunHour)
  const sceneSunDay = sceneEnregistree ? layout.scene.sunDay : JOUR_SOLSTICE_HIVER
  const sceneSunHour = sceneEnregistree ? layout.scene.sunHour : SCENE_SUN_HOUR_DEFAUT
  // ACAL719 — l'heure légale du repère (écart servi par le serveur) ; absente ⇒ la phrase dit pourquoi.
  // T5 (suite d'ACAL1640) — l'année est CELLE de la barre du soleil, comme la phrase d'heure légale de la barre
  // (`anneeDuChampSoleil`) : jamais deux années (ni deux jours, l'année de dessin étant bissextile) pour un même soleil.
  const anneeScene = useAnneeSoleil()
  const dateScene = dateDuJourDeScene(sceneSunDay, anneeScene)
  const legale = useHeureLegale(calepinageId, dateScene)
  const legaleScene = legale.etat === 'ok' && legale.ecart != null ? formaterHeureLegale(sceneSunHour, legale.ecart) : null
  const soleilCourant = latitudeDeg === null ? null : sunPosition(latitudeDeg, sceneSunDay, sceneSunHour)
  const soleilSousHorizon = soleilCourant !== null && soleilCourant.elevationDeg <= 0

  // ACAL74 — la hauteur RETENUE et sa provenance : celle du BÂTIMENT du pan
  // (`buildings[].hauteurM`, avec sa `source`) quand le document la porte ; sinon
  // l'hypothèse documentée, affichée comme telle. Jamais un NaN ni un 0 muet.
  const batiments = Array.isArray(layout?.buildings) ? layout.buildings : []
  // ACAL1447 — un pan sans `buildingId` lit le bâtiment de la convention de l'atelier
  // (`ID_BATIMENT_SANS_ID`, via `idBatimentDuPan`), comme l'atelier : jamais « supposée » à tort.
  const batiment = zone
    ? batiments.find((b) => b?.id === idBatimentDuPan(zone.buildingId)) ?? null
    : null
  const hauteurBatiment = typeof batiment?.hauteurM === 'number'
    && Number.isFinite(batiment.hauteurM) && batiment.hauteurM > 0
    ? batiment.hauteurM : null
  const provenanceHauteurToit = hauteurBatiment === null ? 'hypothese' : 'batiment'
  const hauteurToitM = hauteurBatiment ?? HAUTEUR_TOIT_HYPOTHESE_M
  const sourceBatiment = batiment?.source === 'saisie' ? 'saisie atelier' : (batiment?.source ?? '')
  const mentionHauteur = provenanceHauteurToit === 'batiment'
    ? `hauteur du bâtiment : ${hauteurToitM} m${sourceBatiment ? ` (${sourceBatiment})` : ''}`
    : MENTION_HYPOTHESE_TOIT

  const obstructions = useMemo(() => {
    if (!zone) return []
    const origine = centroideDuContour(zone.vertices)
    if (!origine) return []
    return obstructionsDuPan(origine, zone.obstacles, layout?.environment, hauteurToitM)
  }, [zone, layout?.environment, hauteurToitM])

  if (chargement) {
    return (
      <>
        <RetourAtelier calepinageId={calepinageId} />
        <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-course-soleil-loading">Chargement…</div>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-course-soleil">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Course du soleil</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Azimut (0°=Nord) en abscisse, hauteur du soleil en ordonnée, pour les trois jours
        de repère (solstices et équinoxe). L’horizon lointain saisi (Horizon lointain) et
        les obstructions proches à hauteur saisie sont surimprimés à leur position réelle.
      </p>

      {erreur && <p className="mt-2 text-sm text-red-300" role="alert">{erreur}</p>}

      {zones.length > 1 && (
        <div className="mt-3">
          <label htmlFor="cal-course-soleil-pan" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Pan
          </label>
          <select
            id="cal-course-soleil-pan"
            value={zone?.id ?? ''}
            onChange={(e) => setPanChoisi(e.target.value)}
            className="mt-1 block rounded border border-border bg-[var(--cal-surface)] px-2 py-1 text-sm text-foreground"
          >
            {zones.map((z, i) => (
              <option key={z.id} value={z.id}>{libellePan(z, i)}</option>
            ))}
          </select>
        </div>
      )}

      {!zone && !erreur && (
        <p className="mt-3 text-sm text-muted-foreground">Aucun pan tracé dans cette conception.</p>
      )}

      {zone && (
        <div className="mt-4">
          <SunDiagram
            latitudeDeg={latitudeDeg}
            horizonPoints={horizonPoints}
            obstructions={obstructions}
            sunDay={sceneSunDay}
            sunHour={sceneSunHour}
            tableOmbrage={tableOmbrage}
            ariaLabel={`Course du soleil du pan ${libellePan(zone, zones.indexOf(zone))}`}
          />
          <LegendeCourbes libelleHorizon="Horizon lointain">
            <span className="inline-flex items-center gap-1">
              <span aria-hidden="true" style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#d0654f' }} />
              Obstruction proche
            </span>
            <span className="inline-flex items-center gap-1">
              <span aria-hidden="true" style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#ffd166' }} />
              Soleil de scène
              {legaleScene ? ` (${sceneSunHour} h solaire = ${legaleScene} légale)` : ''}
            </span>
          </LegendeCourbes>

          {/* CALX118 — l'instant du soleil de scène AFFICHÉ, et le défaut NOMMÉ quand le
              document n'en porte aucun (jamais un 21 juin supposé silencieusement). */}
          <p className="mt-1 text-xs text-muted-foreground" data-testid="cal-course-soleil-scene">
            {sceneEnregistree
              ? `Soleil affiché : jour ${sceneSunDay} de l’année (${dateScene}${anneeScene === new Date().getFullYear() ? ', année en cours' : ''}), ${sceneSunHour} h solaire — instant enregistré dans l’atelier 3D.`
              : `Soleil affiché : solstice d’hiver, midi (jour ${JOUR_SOLSTICE_HIVER}, ${SCENE_SUN_HOUR_DEFAUT} h) — aucun instant enregistré, comportement d’aujourd’hui.`}
            {latitudeDeg !== null && soleilSousHorizon
              ? ' Le soleil est sous l’horizon à cet instant : aucun repère tracé.'
              : ''}
            {['fuseau', 'pin', 'erreur'].includes(legale.etat) ? <> <PhraseHeureIndisponible etat={legale.etat} />.</> : null}
          </p>

          {/* ACAL74 — la hauteur EMPLOYÉE et sa provenance, TOUJOURS lisibles sous le
              diagramme : celle du bâtiment du pan (document), ou l'hypothèse. */}
          <div className="mt-3 border-t border-border pt-3" data-testid="cal-course-soleil-hauteur-toit">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Hauteur de toit employée pour les obstructions proches
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="fig text-sm text-foreground" data-testid="cal-course-soleil-hauteur-toit-valeur">
                {`${hauteurToitM} m`}
              </span>
            </div>
            <p
              className="mt-1 text-xs text-muted-foreground"
              data-testid="cal-course-soleil-hauteur-toit-provenance"
            >
              {mentionHauteur}
            </p>
            {provenanceHauteurToit === 'hypothese' && (
              <p className="mt-1 text-xs">
                <Link to={`/calepinage/${calepinageId}`} className="font-semibold text-primary-text underline">
                  Saisir la hauteur dans l’atelier (Bâtiment)
                </Link>
              </p>
            )}
          </div>

          {/* La mention accompagne CHAQUE marqueur d'obstruction proche
              (règle de la tâche) : aucune obstruction n'est tracée sans que
              la hauteur employée soit lisible juste à côté d'elle. */}
          {obstructions.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground" data-testid="cal-course-soleil-obstructions-hauteur">
              {obstructions.map((o, i) => (
                <li
                  key={`${o.label ?? 'obs'}-${i}`}
                  data-testid={`cal-course-soleil-obstruction-hauteur-${i}`}
                >
                  {`${o.label ?? 'Obstruction'} — ${mentionHauteur}`}
                </li>
              ))}
            </ul>
          )}

          {facteursOmbrage.length > 0 ? (
            <p className="mt-1 text-xs text-muted-foreground" data-testid="acal449-legende">
              {`Zones d’ombrage (table servie) : de ${fr(Math.min(...facteursOmbrage))} (plus ombré) à ${fr(Math.max(...facteursOmbrage))} (libre) — teinte d’autant plus forte que le facteur est bas.`}
            </p>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground" data-testid="acal449-absente">
              table d’ombrage absente : rouvrez et enregistrez l’atelier
            </p>
          )}
          {latitudeDeg === null && (
            <p className="mt-1 text-xs text-amber-300">
              Latitude du site inconnue (aucun repère posé) — la course du soleil n’est pas tracée.
            </p>
          )}
          {!horizonPoints.length && (
            <p className="mt-1 text-xs text-muted-foreground">
              Aucun horizon lointain saisi (voir « Horizon lointain ») — non tracé.
            </p>
          )}
          {!obstructions.length && (
            <p className="mt-1 text-xs text-muted-foreground">
              Aucune obstruction proche à hauteur saisie sur ce pan — aucune n’est surimprimée.
            </p>
          )}
        </div>
      )}
    </div>
    </>
  )
}
