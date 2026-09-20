/* eslint-disable react-refresh/only-export-components --
   `documentTerrain`, `pasMesure` et `tauxOccupation` sont des fonctions PURES
   (une saisie + un plan du moteur → le document persisté et les deux chiffres
   affichés). Le test jumeau les exerce sans monter l'écran, parce que ce sont
   ELLES qui garantissent qu'aucun pas ni aucun taux n'est inventé côté client.
   Même dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'

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

/** Une saisie numérique, ou `null` — jamais un 0 de remplacement. */
export function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/**
 * CAL89 — le PAS INTER-RANGÉES, MESURÉ sur les rangées que le moteur a posées.
 * Le plus petit écart entre deux `y0` consécutifs distincts. Moins de deux
 * rangées ⇒ `null` : non mesurable, et on ne le remplace pas.
 */
export function pasMesure(rangees) {
  const y = Array.from(
    new Set((rangees ?? [])
      .map((r) => Number(r?.y0))
      .filter((v) => Number.isFinite(v))),
  ).sort((a, b) => a - b)
  if (y.length < 2) return null
  let min = Infinity
  for (let i = 1; i < y.length; i += 1) min = Math.min(min, y[i] - y[i - 1])
  return Number.isFinite(min) && min > 0 ? min : null
}

/** Emprise totale (m²) des tables RENDUES par le moteur. */
export function empriseTablesM2(tables) {
  return (tables ?? []).reduce((acc, t) => {
    const l = Math.abs(Number(t?.x1) - Number(t?.x0))
    const p = Math.abs(Number(t?.y1) - Number(t?.y0))
    return Number.isFinite(l) && Number.isFinite(p) ? acc + l * p : acc
  }, 0)
}

/**
 * CAL89 — le TAUX D'OCCUPATION DU SOL (GCR), une SORTIE : emprises des tables
 * du moteur ÷ surface du terrain. L'un des deux termes manque ⇒ `null`.
 */
export function tauxOccupation(tables, aireTerrainM2) {
  const aire = nombre(aireTerrainM2)
  if (aire === null || aire <= 0) return null
  const emprise = empriseTablesM2(tables)
  if (!emprise) return null
  return emprise / aire
}

/** Le contour métrique du terrain, depuis les dimensions SAISIES. */
export function contourTerrain(largeurM, profondeurM) {
  const l = nombre(largeurM)
  const p = nombre(profondeurM)
  if (l === null || p === null || l <= 0 || p <= 0) return null
  return [[0, 0], [l, 0], [l, p], [0, p]]
}

/**
 * CAL89 — la DEMANDE envoyée au moteur (contrat `pose.json`, clé `demande`).
 * Aucune clé inventée : chaque nom est celui du document d'entrée du moteur.
 */
export function demandeMoteur(saisie) {
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

  const parametres = {
    kits: ['terrain'],
    axe_rangee: 'NORD_SUD',
    mode_pose: 'rangees_explicites_dp',
    pas_recherche_m: 0.01,
  }
  // L'allée n'est envoyée QUE si elle est imposée : sinon le moteur applique
  // sa propre politique — on ne lui souffle jamais une valeur inventée ici.
  if (allee !== null) parametres.allee_m = allee

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
      axe_rangee: 'NORD_SUD',
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
 * (`poseSurfaces[]`, contrat `roof_layout_v2.schema.json`). Tout ce qui vient
 * du moteur est recopié tel quel sous `engine` ; rien n'y est recalculé.
 */
export function documentTerrain(saisie, reponse) {
  const contour = contourTerrain(saisie.largeurM, saisie.profondeurM)
  const aire = contour
    ? nombre(saisie.largeurM) * nombre(saisie.profondeurM)
    : null
  const plan = (reponse?.plans ?? [])[0] ?? null
  const tables = plan?.tables ?? []
  return {
    kind: 'sol',
    id: saisie.repere || 'TERRAIN',
    label: saisie.label || 'Champ au sol',
    contourM: contour ?? [],
    areaM2: aire,
    terrainSlopeDeg: nombre(saisie.penteTerrainDeg),
    rowAzimuthDeg: nombre(saisie.rowAzimuthDeg),
    tiltDeg: nombre(saisie.tiltDeg),
    engine: {
      modules: Number.isFinite(Number(plan?.modules)) ? Number(plan.modules) : null,
      rowPitchM: pasMesure(plan?.rangees),
      tables,
      groundCoverageRatio: tauxOccupation(tables, aire),
      versionMoteur: reponse?.version_moteur ?? null,
      hashEntree: reponse?.hash_entree ?? null,
    },
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

export default function ModeTerrain({ calepinageId: idPropose = null, persister = true }) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [saisie, setSaisie] = useState(SAISIE_VIDE)
  const [layout, setLayout] = useState(null)
  const [reponse, setReponse] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [message, setMessage] = useState(null)

  // RELECTURE — un champ au sol déjà enregistré revient tel quel.
  useEffect(() => {
    if (!calepinageId || !persister) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        const doc = res?.data?.roof_layout ?? null
        setLayout(doc)
        const sol = (doc?.poseSurfaces ?? []).find((s) => s?.kind === 'sol')
        if (!sol) return
        const contour = sol.contourM ?? []
        setSaisie((s) => ({
          ...s,
          repere: sol.id ?? s.repere,
          label: sol.label ?? s.label,
          largeurM: contour.length === 4 ? String(contour[1][0]) : s.largeurM,
          profondeurM: contour.length === 4 ? String(contour[2][1]) : s.profondeurM,
          penteTerrainDeg: sol.terrainSlopeDeg === null || sol.terrainSlopeDeg === undefined
            ? s.penteTerrainDeg : String(sol.terrainSlopeDeg),
          rowAzimuthDeg: sol.rowAzimuthDeg === null || sol.rowAzimuthDeg === undefined
            ? s.rowAzimuthDeg : String(sol.rowAzimuthDeg),
          tiltDeg: sol.tiltDeg === null || sol.tiltDeg === undefined
            ? s.tiltDeg : String(sol.tiltDeg),
        }))
        // Le plan RECHARGÉ est celui du moteur : on le réaffiche sans le refaire.
        setReponse({
          plans: [{ modules: sol.engine?.modules ?? null, tables: sol.engine?.tables ?? [] }],
          version_moteur: sol.engine?.versionMoteur ?? null,
          hash_entree: sol.engine?.hashEntree ?? null,
          _pasRecharge: sol.engine?.rowPitchM ?? null,
        })
      })
      .catch(() => { if (!annule) setLayout(null) })
    return () => { annule = true }
  }, [calepinageId, persister])

  const majChamp = (cle, brut) => setSaisie((s) => ({ ...s, [cle]: brut }))

  const calculer = () => {
    const demande = demandeMoteur(saisie)
    if (!demande) {
      setMessage('Dimensions du terrain et du module incomplètes : rien n’est '
        + 'envoyé au moteur, et surtout aucune valeur par défaut inventée.')
      return
    }
    setMessage(null)
    setEnCours(true)
    Promise.resolve(calepinageApi.moteur.pose({ demande }))
      .then((res) => {
        setEnCours(false)
        setReponse(res?.data ?? null)
      })
      .catch((e) => {
        setEnCours(false)
        setReponse(null)
        setMessage(e?.response?.data?.detail
          || 'Le moteur n’a pas pu poser ce champ au sol.')
      })
  }

  const enregistrer = () => {
    if (!reponse) {
      setMessage('Aucun plan du moteur : il n’y a rien à enregistrer.')
      return
    }
    const surface = documentTerrain(saisie, reponse)
    const autres = (layout?.poseSurfaces ?? []).filter((s) => s?.kind !== 'sol')
    const doc = { ...(layout ?? {}), poseSurfaces: [...autres, surface] }
    Promise.resolve(calepinageApi.calepinages.enregistrerLayoutCalepinage(calepinageId, doc))
      .then(() => {
        setLayout(doc)
        setMessage('Champ au sol enregistré dans la conception.')
      })
      .catch(() => setMessage('Le champ au sol n’a pas pu être enregistré.'))
  }

  const plan = (reponse?.plans ?? [])[0] ?? null
  const pas = plan ? (pasMesure(plan.rangees) ?? reponse?._pasRecharge ?? null) : null
  const aire = contourTerrain(saisie.largeurM, saisie.profondeurM)
    ? nombre(saisie.largeurM) * nombre(saisie.profondeurM)
    : null
  const taux = plan ? tauxOccupation(plan.tables, aire) : null

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-terrain">
      <p className="tech-label rule-brass text-brass-300">Mode terrain — centrale au sol</p>
      <p className="mt-2 text-xs text-lune-faint">
        Les dimensions sont saisies ; les tables, le compte et le pas
        inter-rangées viennent du moteur. Le mode toiture n’est pas touché.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {CHAMPS.map(([cle, label]) => (
          <label key={cle} className="block text-sm text-lune-soft">
            <span className="tech-label text-lune-faint">{label}</span>
            <input
              type="number"
              step="any"
              value={saisie[cle]}
              data-testid={`cal-terrain-${cle}`}
              onChange={(e) => majChamp(cle, e.target.value)}
              className="mt-1 w-full rounded border border-white/15 bg-transparent px-2 py-1 text-white"
            />
          </label>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={calculer}
          disabled={enCours}
          data-testid="cal-terrain-calculer"
          className="rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200"
        >
          {enCours ? 'Calcul en cours…' : 'Calculer le champ au sol'}
        </button>
        {persister && (
          <button
            type="button"
            onClick={enregistrer}
            data-testid="cal-terrain-enregistrer"
            className="rounded border border-white/15 px-4 py-2 text-sm font-semibold text-white"
          >
            Enregistrer le champ
          </button>
        )}
      </div>

      {message && (
        <p className="mt-3 text-sm text-lune-soft" role="status"
          data-testid="cal-terrain-message">{message}</p>
      )}

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
    </div>
  )
}
