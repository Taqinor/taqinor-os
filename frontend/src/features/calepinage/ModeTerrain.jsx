/* eslint-disable react-refresh/only-export-components --
   `documentTerrain`, `pasMesure`, `tauxOccupation` et `planVue2D` sont des
   fonctions PURES (une saisie + un plan du moteur → le document persisté, les
   deux chiffres affichés et la mise en page du dessin). Le test jumeau les
   exerce sans monter l'écran, parce que ce sont ELLES qui garantissent
   qu'aucun pas, aucun taux ni aucune cote n'est inventé côté client.
   Même dérogation que `module.config.jsx` du même module. */
import RetourAtelier from './atelier/RetourAtelier'
import useSurfacePose from './useSurfacePose'
import ActionsSurfacePose from './ActionsSurfacePose'
import {
  nombre, pasMesure, tauxOccupation, contourTerrain, documentSurfacePose, KIND_SOL,
} from './surfacePose'
import { formatCote, milieu } from './plan2d'
import { formatNumber } from '../../lib/format'

/* ============================================================================
   CAL89 — LE MODE TERRAIN : UNE CENTRALE AU SOL DANS L'ATELIER.
   ----------------------------------------------------------------------------
   Constat : tout le tracé de l'atelier suppose un TOIT (type de toit
   obligatoire, `ToitureDesign.jsx`) ; aucun mode terrain n'existe. Cet écran
   ouvre le mode terrain SANS toucher une ligne du chemin toiture : il écrit
   dans le MÊME document (`roof_layout`, clé additive `poseSurfaces`, contrat
   `roof_layout_v2.schema.json`) et parle à la MÊME porte moteur
   (`POST /calepinage/moteur/pose/`, contrat `pose.json`).

   CE QUI EST SAISI, ET CE QUI VIENT DU MOTEUR — la frontière ne bouge jamais :
     * SAISI : les dimensions du terrain, sa pente, l'orientation des rangées,
       l'inclinaison des tables, le module, et l'allée entre rangées quand elle
       est imposée (`parametres.allee_m`, le paramètre du moteur lui-même).
     * RENDU PAR LE MOTEUR : les tables posées, le compte de modules, et le PAS
       INTER-RANGÉES réellement appliqué — MESURÉ sur les rangées renvoyées
       (`plans[].rangees[].y0` consécutifs). Il n'existe AUCUNE seconde formule
       de pas dans cet écran : c'est la règle de CAL88, qui fait vivre la
       physique anti-ombrage dans le moteur (`core/calepinage/surfaces/sol.py`)
       et nulle part ailleurs. Moins de deux rangées ⇒ pas non mesurable ⇒ on
       affiche « — » et on le DIT.

   LE TAUX D'OCCUPATION DU SOL (GCR) EST UNE SORTIE, jamais une saisie ni un
   objectif : somme des emprises des TABLES RENDUES PAR LE MOTEUR ÷ surface du
   terrain SAISIE. Les deux termes viennent donc du serveur et de la saisie —
   aucun des deux n'est estimé.

   LIMITE CONNUE, DITE PLUTÔT QUE MASQUÉE : le contrat d'échange v1 du moteur ne
   connaît PAS encore le genre de surface « sol » (`core/calepinage/
   serialisation.py` le refuse explicitement, et le test
   `test_le_contrat_v1_refuse_le_sol_explicitement` le fige). Le terrain est
   donc soumis comme une surface de pose HORIZONTALE (`type: "polygone"`,
   `pente_deg: 0`), et le pas affiché est celui que le moteur a APPLIQUÉ. Le
   jour où la porte accepte `sol`, seul le `type` envoyé change ici.
   ========================================================================== */

/** Axe des rangées DÉRIVÉ par le serveur (ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD). */
export const AXE_AUTO = 'AUTO'

/** ACAL75 — la mention exacte du champ « Pente du terrain » (jamais reformulée). */
export const MENTION_PENTE_NON_PRISE_EN_COMPTE
  = 'non prise en compte par le calcul — terrain supposé plat'

/**
 * ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD — un plan du moteur à 0 module n'est pas
 * un « optimum » à afficher en silence : on DIT qu'aucune table ne tient.
 * `null` quand il y a au moins un module (ou pas de plan).
 */
export function motifChampVide(reponse) {
  const plan = (reponse?.plans ?? [])[0] ?? null
  if (!plan) return null
  const modules = Number(plan.modules)
  if (!Number.isFinite(modules) || modules > 0) return null
  return 'Aucune table ne tient dans ce terrain avec cette saisie : le moteur '
    + 'n’a posé aucun module. Réduisez le nombre de modules par table ou '
    + 'agrandissez le terrain.'
}

/** Motif FRANÇAIS d'un refus du serveur (400 DRF `{champ: [motif]}`), ou `null`. */
export function motifRefus(data) {
  if (!data || typeof data !== 'object') return null
  if (typeof data.detail === 'string') return data.detail
  for (const cle of ['demande', 'calepinage']) {
    const v = data[cle]
    if (Array.isArray(v) && v.length) return String(v[0])
    if (typeof v === 'string' && v) return v
  }
  return null
}

/* ACAL25 — les fonctions pures de mesure vivent dans `surfacePose.js` (une seule
   copie, partagée avec l'ombrière) ; ré-exportées ici pour les appelants et les
   tests existants. */
export {
  nombre, pasMesure, empriseTablesM2, tauxOccupation, contourTerrain,
} from './surfacePose'

/**
 * CAL89 — la DEMANDE envoyée au moteur (contrat `pose.json`, clé `demande`).
 * Aucune clé inventée : chaque nom est celui du document d'entrée du moteur.
 */
export function demandeMoteur(saisie, { alleeParDefautM = null } = {}) {
  const contour = contourTerrain(saisie.largeurM, saisie.profondeurM)
  if (!contour) return null
  const azimut = nombre(saisie.rowAzimuthDeg)
  const inclinaison = nombre(saisie.tiltDeg)
  const moduleLong = nombre(saisie.moduleLongM)
  const moduleCourt = nombre(saisie.moduleCourtM)
  const puissance = nombre(saisie.puissanceWc)
  const modulesParTable = nombre(saisie.modulesParTable)
  const allee = nombre(saisie.alleeM)
  if (moduleLong === null || moduleCourt === null || puissance === null) return null

  // ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD — l'axe des rangées n'est PAS choisi
  // ici : il est IMPOSÉ par le kit et l'azimut (un module par table plein sud
  // ⇒ rangées est-ouest). `AUTO` demande au serveur de le dériver avec la
  // règle du moteur (`orientation.axe_rangee_impose`) — l'ancien `NORD_SUD`
  // codé en dur rendait un 400 « inconstructible » au cas le plus courant.
  const parametres = {
    kits: ['terrain'],
    axe_rangee: AXE_AUTO,
    mode_pose: 'rangees_explicites_dp',
    pas_recherche_m: 0.01,
  }
  // L'allée n'est envoyée QUE si elle est imposée : sinon le moteur applique
  // sa propre politique — on ne lui souffle jamais une valeur inventée ici.
  // ACAL75 — SEULE exception, déclarée par l'appelant : l'ombrière est une
  // couverture CONTINUE (`alleeParDefautM: 0`, pose jointive) ; l'écran le DIT.
  if (allee !== null) parametres.allee_m = allee
  else if (alleeParDefautM !== null) parametres.allee_m = alleeParDefautM

  return {
    schema_version: 1,
    repere: saisie.repere || 'TERRAIN',
    contour,
    surfaces: [{
      // Le genre « sol » n'est pas encore accepté par le contrat d'échange :
      // le terrain voyage comme surface de pose horizontale (cf. en-tête).
      type: 'polygone',
      repere: saisie.repere || 'TERRAIN',
      contour,
      trous: [],
      axe_rangee: AXE_AUTO,
      niveau: 0,
      pente_deg: 0,
      azimut_deg: azimut === null ? 180 : azimut,
      origine: [0, 0],
      coupures: [],
    }],
    kits: [{
      code: 'terrain',
      libelle: 'Table terrain',
      module_long_m: moduleLong,
      module_court_m: moduleCourt,
      puissance_module_wc: puissance,
      inclinaison_deg: inclinaison === null ? 0 : inclinaison,
      orientation: 'PORTRAIT',
      modules_par_table: modulesParTable === null ? 1 : modulesParTable,
      faitage_m: 0,
    }],
    parametres,
    obstacles: [],
    zones: [],
  }
}

/**
 * CAL89 — la surface de pose PERSISTÉE dans le document v2
 * (`poseSurfaces[]`, contrat `roof_layout_v2.schema.json`). ACAL25 : un simple
 * appel du survivant `surfacePose.js::documentSurfacePose` (le même que pour
 * l'ombrière) — module et allée compris.
 */
export function documentTerrain(saisie, reponse) {
  return documentSurfacePose(saisie, reponse, KIND_SOL)
}

/* ============================================================================
   CALX50 — LE CHAMP EST DESSINÉ, PLUS SEULEMENT COMPTÉ.
   ----------------------------------------------------------------------------
   Constat : cet écran postait au moteur et n'affichait que quatre nombres. Le
   placement des tables existait pourtant déjà, PUR et testé, dans le builder
   (`construireChampPose`, `@roofpro/scene3d`) — sans aucun appelant applicatif.
   On le branche : les tables, le compte, le pas, l'emprise et le taux viennent
   de LUI ; cet écran ne fait que les METTRE EN PAGE.

   CHARGEMENT PARESSEUX, comme le builder dans `ToitureDesign.jsx` : le module
   `scene3d` porte aussi la couche WebGL (Three + le lecteur de cartes). Un
   import statique les ferait tomber dans le paquet de CETTE route alors qu'on
   n'a besoin que d'une fonction de placement. Le module ne se charge donc
   qu'une fois l'écran ouvert ; s'il ne se charge pas, on le DIT et on ne
   dessine rien à sa place.

   CE QUI N'EST PAS RÉUTILISÉ, ET POURQUOI — `Vue2DPlan.jsx` projette un toit
   GÉORÉFÉRENCÉ : son résumé nomme des axes E-O / N-S et son compte s'intitule
   « module(s) ». Ici il n'y a AUCUN ancrage géographique (le terrain est saisi
   en mètres, les rangées tournées d'un azimut saisi) et les rectangles posés
   sont des TABLES, pas des modules : afficher ces deux libellés serait
   affirmer deux choses fausses. On garde donc les primitives de plan
   (`formatCote`, `milieu` de `plan2d.js`) et on pose le dessin dessus.

   `nonMesure` EST AFFICHÉ TEL QUEL : pente non renseignée, pas non mesurable,
   taux non calculable — chaque manque est dit avec les mots du service, jamais
   comblé par une valeur de remplacement.
   ========================================================================== */

/** Zone de dessin du champ (unités du `viewBox`, pas des pixels d'écran). */
export const VUE_LARGEUR = 900
export const VUE_HAUTEUR = 520

/**
 * CALX50 — la MISE EN PAGE du champ : mètres du moteur → coordonnées de la
 * zone de dessin. La MÊME échelle sur les deux axes (une longueur lue sur le
 * dessin est la longueur réelle), et l'axe des rangées vers le HAUT.
 *
 * Aucune géométrie n'est décidée ici : le contour vient de la saisie, les
 * tables de `construireChampPose`, les rangées et le pas du moteur. Contour de
 * moins de trois sommets ⇒ `null` : il n'y a rien à dessiner, et on ne dessine
 * pas un champ supposé.
 */
export function planVue2D({
  contourM,
  tables = [],
  rangees = [],
  pasM = null,
  compteModules = null,
  largeurPx = VUE_LARGEUR,
  hauteurPx = VUE_HAUTEUR,
  margePx = 28,
} = {}) {
  const contour = (contourM ?? [])
    .map((p) => [Number(p?.[0]), Number(p?.[1])])
    .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]))
  if (contour.length < 3) return null
  if (!(largeurPx > 0) || !(hauteurPx > 0)) return null

  // Les tables telles que le service les a PLACÉES (centre + emprise, mètres).
  const rectangles = []
  for (const t of tables ?? []) {
    const cx = Number(t?.cx)
    const cy = Number(t?.cy)
    const l = Number(t?.largeurM)
    const p = Number(t?.profondeurM)
    if (![cx, cy, l, p].every((v) => Number.isFinite(v))) continue
    rectangles.push([
      [cx - l / 2, cy - p / 2],
      [cx + l / 2, cy - p / 2],
      [cx + l / 2, cy + p / 2],
      [cx - l / 2, cy + p / 2],
    ])
  }

  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const [x, y] of [...contour, ...rectangles.flat()]) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  const etendueX = Math.max(1e-6, maxX - minX)
  const etendueY = Math.max(1e-6, maxY - minY)
  const marge = Math.max(0, Math.min(Math.min(largeurPx, hauteurPx) / 2 - 1, margePx))
  const pxParM = Math.min((largeurPx - 2 * marge) / etendueX, (hauteurPx - 2 * marge) / etendueY)
  const decX = (largeurPx - etendueX * pxParM) / 2
  const decY = (hauteurPx - etendueY * pxParM) / 2
  // L'axe des rangées monte vers le HAUT du dessin : y décroît à l'écran.
  const versPx = ([x, y]) => [decX + (x - minX) * pxParM, decY + (maxY - y) * pxParM]

  const yRangees = Array.from(new Set((rangees ?? [])
    .map((r) => Number(r?.y0))
    .filter((v) => Number.isFinite(v)))).sort((a, b) => a - b)

  const pas = Number.isFinite(pasM) ? pasM : null
  const xCote = minX + etendueX / 2
  const cotePas = pas !== null && yRangees.length >= 2
    ? {
      // Le trait de cote mesure EXACTEMENT le pas rendu par le service : on
      // part de la première rangée et on avance de ce pas, plutôt que de
      // joindre deux rangées qui pourraient être plus éloignées que lui.
      lengthM: pas,
      from: versPx([xCote, yRangees[0]]),
      to: versPx([xCote, yRangees[0] + pas]),
    }
    : null

  return {
    largeurPx,
    hauteurPx,
    pxParM,
    contour: contour.map(versPx),
    tables: rectangles.map((q) => q.map(versPx)),
    rangees: yRangees.map((y) => ({
      y0: y,
      from: versPx([minX, y]),
      to: versPx([maxX, y]),
    })),
    cotes: contour.map((a, i) => {
      const b = contour[(i + 1) % contour.length]
      return {
        lengthM: Math.hypot(b[0] - a[0], b[1] - a[1]),
        from: versPx(a),
        to: versPx(b),
      }
    }),
    cotePas,
    // Le compte du MOTEUR, recopié — jamais le nombre de rectangles dessinés.
    compteModules,
  }
}

const SAISIE_VIDE = {
  repere: 'TERRAIN',
  label: 'Champ au sol',
  largeurM: '',
  profondeurM: '',
  penteTerrainDeg: '',
  rowAzimuthDeg: '',
  tiltDeg: '',
  moduleLongM: '',
  moduleCourtM: '',
  puissanceWc: '',
  modulesParTable: '',
  alleeM: '',
}

const CHAMPS = [
  ['largeurM', 'Largeur du terrain (m)'],
  ['profondeurM', 'Profondeur du terrain (m)'],
  ['penteTerrainDeg', 'Pente du terrain (°)'],
  ['rowAzimuthDeg', 'Orientation des rangées (°, 180 = sud)'],
  ['tiltDeg', 'Inclinaison des tables (°)'],
  ['moduleLongM', 'Module — grand côté (m)'],
  ['moduleCourtM', 'Module — petit côté (m)'],
  ['puissanceWc', 'Module — puissance (Wc)'],
  ['modulesParTable', 'Modules par table'],
  ['alleeM', 'Allée imposée entre rangées (m) — vide = politique du moteur'],
]

function auDixieme(v) {
  return v === null || v === undefined ? '—' : Math.round(v * 10) / 10
}

/** ACAL345 — ce qui distingue cet écran dans `useSurfacePose` (genre, repère, placeur, libellés). */
const POSE_TERRAIN = {
  kind: KIND_SOL,
  repereDefaut: 'TERRAIN',
  saisieVide: SAISIE_VIDE,
  nomPlaceur: 'construireChampPose',
  libelles: {
    enregistre: 'Champ au sol enregistré dans la conception.',
    nonEnregistre: 'Le champ au sol n’a pas pu être enregistré.',
    supprime: 'Surface supprimée de la conception.',
    nonSupprime: 'La surface n’a pas pu être supprimée.',
    echecPose: 'Le moteur n’a pas pu poser ce champ au sol.',
  },
}

export default function ModeTerrain({ calepinageId: idPropose = null, persister = true, documentVivant = null }) {
  // ACAL345 — l'état d'écran (document, placeur CALX50, relecture, liste,
  // enregistrement/suppression PAR id) vient de `useSurfacePose`, l'UNIQUE
  // copie partagée entre le terrain et l'ombrière.
  const pose = useSurfacePose({ idPropose, persister, documentVivant, ...POSE_TERRAIN })
  const { calepinageId, saisie, reponse, placeur, placeurAbsent, plan, majChamp } = pose

  const calculer = () => pose.poser(
    demandeMoteur(saisie),
    'Dimensions du terrain et du module incomplètes : rien n’est '
      + 'envoyé au moteur, et surtout aucune valeur par défaut inventée.',
  )

  const pas = plan ? (pasMesure(plan.rangees) ?? reponse?._pasRecharge ?? null) : null
  const aire = contourTerrain(saisie.largeurM, saisie.profondeurM)
    ? nombre(saisie.largeurM) * nombre(saisie.profondeurM)
    : null
  const taux = plan ? tauxOccupation(plan.tables, aire) : null

  // CALX50 — le champ PLACÉ par le service, à partir du plan du moteur et des
  // seules grandeurs saisies. Pente absente ⇒ le service le dit dans
  // `nonMesure` ; on n'en suppose aucune à sa place.
  const champ = placeur && plan
    ? placeur.construireChampPose(plan, {
      tiltDeg: nombre(saisie.tiltDeg),
      penteTerrainDeg: nombre(saisie.penteTerrainDeg),
      aireTerrainM2: aire,
    })
    : null
  const vue = champ
    ? planVue2D({
      contourM: contourTerrain(saisie.largeurM, saisie.profondeurM),
      tables: champ.tables,
      rangees: plan?.rangees ?? [],
      pasM: champ.pasInterRangeeM,
      compteModules: champ.modules,
    })
    : null

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="cine-card mt-6 p-6" data-testid="cal-terrain">
        <p className="tech-label rule-brass text-brass-300">Mode terrain — centrale au sol</p>
        <p className="mt-2 text-xs text-lune-faint">
          Les dimensions sont saisies ; les tables, le compte et le pas
          inter-rangées viennent du moteur. Le mode toiture n’est pas touché.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {CHAMPS.map(([cle, label]) => (
            // ACAL75 — la pente du terrain n'entre PAS dans le calcul (la demande
            // part avec `pente_deg: 0`) : le champ est grisé et le dit ; la valeur
            // reste persistée pour le rendu 3D.
            <label
              key={cle}
              className={`block text-sm text-lune-soft${cle === 'penteTerrainDeg' ? ' opacity-60' : ''}`}
            >
              <span className="tech-label text-lune-faint">{label}</span>
              <input
                type="number"
                step="any"
                value={saisie[cle]}
                data-testid={`cal-terrain-${cle}`}
                aria-describedby={cle === 'penteTerrainDeg' ? 'cal-terrain-pente-mention' : undefined}
                onChange={(e) => majChamp(cle, e.target.value)}
                className="mt-1 w-full rounded border border-white/15 bg-transparent px-2 py-1 text-white"
              />
              {cle === 'penteTerrainDeg' && (
                <span id="cal-terrain-pente-mention" className="mt-1 block text-xs text-lune-faint">
                  {MENTION_PENTE_NON_PRISE_EN_COMPTE}
                </span>
              )}
            </label>
          ))}
        </div>

        <ActionsSurfacePose
          pose={pose}
          persister={persister}
          prefixe="cal-terrain"
          onCalculer={calculer}
          libelles={{
            calculer: 'Calculer le champ au sol',
            enregistrer: 'Enregistrer le champ',
            groupe: 'Surfaces au sol enregistrées',
            liste: 'Surfaces enregistrées',
            defaut: 'Champ au sol',
            nouvelle: 'Nouvelle surface',
          }}
        />

        {plan && (
          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-white/10 pt-4 sm:grid-cols-4">
            <div data-testid="cal-terrain-modules">
              <dd className="fig text-lg text-white">{plan.modules ?? '—'}</dd>
              <dt className="tech-label text-lune-faint">Modules posés (moteur)</dt>
            </div>
            <div data-testid="cal-terrain-tables">
              <dd className="fig text-lg text-white">{(plan.tables ?? []).length}</dd>
              <dt className="tech-label text-lune-faint">Tables posées</dt>
            </div>
            <div data-testid="cal-terrain-pas">
              <dd className="fig text-lg text-white">
                {pas === null ? '—' : `${auDixieme(pas)} m`}
              </dd>
              <dt className="tech-label text-lune-faint">
                {pas === null ? 'Pas non mesurable (moins de 2 rangées)' : 'Pas inter-rangées (mesuré sur le plan)'}
              </dt>
            </div>
            <div data-testid="cal-terrain-taux">
              <dd className="fig text-lg text-white">
                {taux === null ? '—' : `${Math.round(taux * 1000) / 10} %`}
              </dd>
              <dt className="tech-label text-lune-faint">
                {taux === null
                  ? 'Taux d’occupation non calculable'
                  : 'Taux d’occupation du sol (sortie)'}
              </dt>
            </div>
          </dl>
        )}

        {/* CALX50 — LE CHAMP DESSINÉ : le plan du moteur, mis en page. */}
        {(plan || placeurAbsent) && (
          <section
            className="mt-5 border-t border-white/10 pt-4"
            data-testid="cal-terrain-vue"
            aria-label="Champ au sol dessiné"
          >
            <p className="tech-label text-lune-faint">
              Champ au sol dessiné — rangées, tables et pas rendus par le moteur
            </p>

            {placeurAbsent && (
              <p className="mt-2 text-sm text-alert-300" data-testid="cal-terrain-vue-indisponible">
                Le tracé du champ n’a pas pu être chargé : les chiffres du moteur
                restent affichés ci-dessus, et rien n’est dessiné à leur place.
              </p>
            )}

            {vue && (
              <>
                <svg
                  data-testid="cal-terrain-svg"
                  viewBox={`0 0 ${vue.largeurPx} ${vue.hauteurPx}`}
                  width="100%"
                  role="img"
                  aria-label={`Champ au sol — ${vue.tables.length} table(s) posée(s) par le moteur`}
                  className="mt-2 text-brass-200"
                >
                  <polygon
                    data-testid="cal-terrain-contour"
                    points={vue.contour.map((p) => p.join(',')).join(' ')}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  />
                  {vue.rangees.map((r) => (
                    <line
                      key={r.y0}
                      data-testid="cal-terrain-rangee"
                      x1={r.from[0]}
                      y1={r.from[1]}
                      x2={r.to[0]}
                      y2={r.to[1]}
                      stroke="currentColor"
                      strokeWidth="0.75"
                      strokeDasharray="6 5"
                      strokeOpacity="0.55"
                    />
                  ))}
                  {vue.tables.map((q, i) => (
                    <polygon
                      key={i}
                      data-testid="cal-terrain-table"
                      points={q.map((p) => p.join(',')).join(' ')}
                      fill="currentColor"
                      fillOpacity="0.25"
                      stroke="currentColor"
                      strokeWidth="0.75"
                    />
                  ))}
                  {vue.cotes.map((c, i) => {
                    const [mx, my] = milieu(c.from, c.to)
                    return (
                      <text
                        key={i}
                        data-testid="cal-terrain-cote"
                        x={mx}
                        y={my}
                        fontSize="12"
                        textAnchor="middle"
                        fill="currentColor"
                      >
                        {formatCote(c.lengthM)}
                      </text>
                    )
                  })}
                  {vue.cotePas && (
                    <>
                      <line
                        data-testid="cal-terrain-trait-pas"
                        x1={vue.cotePas.from[0]}
                        y1={vue.cotePas.from[1]}
                        x2={vue.cotePas.to[0]}
                        y2={vue.cotePas.to[1]}
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                      <text
                        data-testid="cal-terrain-cote-pas"
                        x={milieu(vue.cotePas.from, vue.cotePas.to)[0]}
                        y={milieu(vue.cotePas.from, vue.cotePas.to)[1]}
                        fontSize="12"
                        textAnchor="middle"
                        fill="currentColor"
                      >
                        {formatCote(vue.cotePas.lengthM)}
                      </text>
                    </>
                  )}
                </svg>

                <p className="mt-2 text-xs text-lune-faint" data-testid="cal-terrain-emprise">
                  {vue.tables.length} table(s) dessinée(s) — emprise{' '}
                  {formatNumber(champ.empriseTablesM2, { decimals: 1 })} m² ;{' '}
                  {champ.modules ?? '—'} module(s) posé(s) par le moteur.
                </p>
              </>
            )}

            {champ && champ.nonMesure.length > 0 && (
              <ul
                className="mt-2 list-disc pl-5 text-xs text-lune-faint"
                data-testid="cal-terrain-nonmesure"
              >
                {champ.nonMesure.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </>
  )
}
