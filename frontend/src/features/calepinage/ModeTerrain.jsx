/* eslint-disable react-refresh/only-export-components --
   `documentTerrain`, `pasMesure`, `tauxOccupation` et `planVue2D` sont des
   fonctions PURES (une saisie + un plan du moteur → le document persisté, les
   deux chiffres affichés et la mise en page du dessin). Le test jumeau les
   exerce sans monter l'écran, parce que ce sont ELLES qui garantissent
   qu'aucun pas, aucun taux ni aucune cote n'est inventé côté client.
   Même dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import RetourAtelier from './atelier/RetourAtelier'
import calepinageApi from '../../api/calepinageApi'
import useDocumentCalepinage, { ecrireSection, MESSAGE_ILLISIBLE } from './useDocumentCalepinage'
import {
  nombre, pasMesure, tauxOccupation, contourTerrain, documentSurfacePose, saisieDepuisSurface, reponseDepuisSurface,
  entreeMoteurChangee, surfacesDuGenre, remplacerSurface, retirerSurface, repereLibre,
  KIND_SOL,
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

export default function ModeTerrain({ calepinageId: idPropose = null, persister = true, documentVivant = null }) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [saisie, setSaisie] = useState(SAISIE_VIDE)
  // ACAL24 — l'UNIQUE lecture du document (hook) : un échec donne `erreur`, jamais
  // un document vide ; l'écriture ne porte que la clé `poseSurfaces`.
  const doc = useDocumentCalepinage(calepinageId, { actif: persister })
  const [reponse, setReponse] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [message, setMessage] = useState(null)
  // CALX50 — le PLACEUR de tables du builder (`construireChampPose`), chargé à
  // l'ouverture de l'écran seulement. Rangé dans un objet : passer une fonction
  // nue à un `setState` serait lu comme une mise à jour, pas comme une valeur.
  const [placeur, setPlaceur] = useState(null)
  const [placeurAbsent, setPlaceurAbsent] = useState(false)

  useEffect(() => {
    let annule = false
    import('@roofpro/scene3d')
      .then((mod) => {
        if (annule) return
        if (typeof mod?.construireChampPose === 'function') {
          setPlaceur({ construireChampPose: mod.construireChampPose })
        } else {
          setPlaceurAbsent(true)
        }
      })
      .catch(() => { if (!annule) setPlaceurAbsent(true) })
    return () => { annule = true }
  }, [])

  // RELECTURE — un champ au sol déjà enregistré revient tel quel (une fois par
  // lecture serveur, jamais à une application locale d'une section écrite).
  const [lectureHydratee, setLectureHydratee] = useState(null)
  if (persister && doc.etat === 'ok' && lectureHydratee !== doc.generation) {
    setLectureHydratee(doc.generation)
    const sol = surfacesDuGenre(doc.document?.poseSurfaces, KIND_SOL)[0]
    if (sol) {
      setSaisie((s) => ({ ...s, ...saisieDepuisSurface(sol) }))
      // Le plan RECHARGÉ est celui du moteur : on le réaffiche sans le refaire.
      setReponse(reponseDepuisSurface(sol))
    }
  }

  const surfaces = surfacesDuGenre(doc.document?.poseSurfaces, KIND_SOL)
  const repereCourant = saisie.repere || 'TERRAIN'
  const dejaEnregistree = surfaces.some((s) => s.id === repereCourant)

  const majChamp = (cle, brut) => {
    setSaisie((s) => ({ ...s, [cle]: brut }))
    // ACAL25 — le plan calculé ne vaut que pour la saisie qui l'a produit : dès
    // qu'une entrée du moteur change, il est invalidé (jamais un document mixte
    // contour 80 m / plan moteur 40 m).
    if (reponse && entreeMoteurChangee(cle)) {
      setReponse(null)
      setMessage('Une entrée du moteur a changé : recalculez le plan avant d’enregistrer.')
    }
  }

  // Une surface déjà enregistrée est rééditée (liste) ; « Nouvelle surface » en
  // ouvre une autre, sous un repère libre.
  const choisirSurface = (surface) => {
    setSaisie((s) => ({ ...s, ...saisieDepuisSurface(surface) }))
    setReponse(reponseDepuisSurface(surface))
    setMessage(null)
  }
  const nouvelleSurface = () => {
    setSaisie((s) => ({
      ...s, repere: repereLibre(doc.document?.poseSurfaces, KIND_SOL), label: '',
    }))
    setReponse(null)
    setMessage(null)
  }

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
        setMessage(motifChampVide(res?.data))
      })
      .catch((e) => {
        setEnCours(false)
        setReponse(null)
        setMessage(motifRefus(e?.response?.data)
          || 'Le moteur n’a pas pu poser ce champ au sol.')
      })
  }

  const enregistrer = async () => {
    if (doc.etat !== 'ok') return
    if (!reponse) {
      setMessage('Aucun plan du moteur : il n’y a rien à enregistrer.')
      return
    }
    const surface = documentTerrain(saisie, reponse)
    // ACAL25 — la surface est remplacée PAR id : les autres surfaces sol restent.
    const valeur = remplacerSurface(doc.document?.poseSurfaces, surface)
    const res = await ecrireSection({
      calepinageId, cle: 'poseSurfaces', valeur, empreinte: doc.empreinte, documentVivant,
    })
    if (res.ok) {
      doc.appliquerSection('poseSurfaces', valeur, res.empreinte)
      setMessage('Champ au sol enregistré dans la conception.')
    } else if (res.conflit) {
      setMessage('La conception a changé ailleurs : elle est relue, enregistrez de nouveau.')
      doc.recharger()
    } else {
      setMessage(res.motif || 'Le champ au sol n’a pas pu être enregistré.')
    }
  }

  const supprimer = async () => {
    if (doc.etat !== 'ok' || !dejaEnregistree) return
    const valeur = retirerSurface(doc.document?.poseSurfaces, KIND_SOL, repereCourant)
    const res = await ecrireSection({
      calepinageId, cle: 'poseSurfaces', valeur, empreinte: doc.empreinte, documentVivant,
    })
    if (res.ok) {
      doc.appliquerSection('poseSurfaces', valeur, res.empreinte)
      setMessage('Surface supprimée de la conception.')
    } else if (res.conflit) {
      setMessage('La conception a changé ailleurs : elle est relue, recommencez.')
      doc.recharger()
    } else {
      setMessage(res.motif || 'La surface n’a pas pu être supprimée.')
    }
  }

  const plan = (reponse?.plans ?? [])[0] ?? null
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
              disabled={doc.etat !== 'ok' || !reponse}
              title={reponse ? undefined : 'Calculez le plan avant d’enregistrer'}
              data-testid="cal-terrain-enregistrer"
              className="rounded border border-white/15 px-4 py-2 text-sm font-semibold text-white"
            >
              Enregistrer le champ
            </button>
          )}
        </div>

        {persister && surfaces.length > 0 && (
          <div className="mt-4" role="group" aria-label="Surfaces au sol enregistrées">
            <p className="tech-label text-lune-faint">Surfaces enregistrées</p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {surfaces.map((surface) => (
                <li key={surface.id}>
                  <button
                    type="button"
                    onClick={() => choisirSurface(surface)}
                    aria-pressed={surface.id === repereCourant}
                    className="rounded border border-white/15 px-3 py-1 text-sm text-white aria-pressed:bg-white/10"
                  >
                    {`${surface.label || 'Champ au sol'} (${surface.id})`}
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={nouvelleSurface}
              className="mt-2 rounded border border-white/15 px-3 py-1 text-sm text-white"
            >
              Nouvelle surface
            </button>
          </div>
        )}

        {persister && dejaEnregistree && (
          <button
            type="button"
            onClick={supprimer}
            disabled={doc.etat !== 'ok'}
            className="mt-3 rounded border border-red-300/40 px-3 py-1 text-sm text-red-300"
          >
            Supprimer cette surface
          </button>
        )}

        {persister && doc.etat === 'erreur' && (
          <p className="mt-3 text-sm text-red-300" role="alert"
           >{MESSAGE_ILLISIBLE}</p>
        )}

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
