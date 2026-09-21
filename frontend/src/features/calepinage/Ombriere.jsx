/* eslint-disable react-refresh/only-export-components --
   `documentOmbriere`, `totauxParBatiment` et `coupeOmbriere` sont des fonctions
   PURES (une saisie + un plan du moteur → le document persisté, les totaux
   affichés et la mise en page de la coupe). Le test jumeau les exerce sans
   monter l'écran, parce que ce sont ELLES qui garantissent qu'aucune charge
   n'est calculée, qu'aucun total n'est inventé et qu'aucune hauteur n'est
   supposée. Même dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import RetourAtelier from './atelier/RetourAtelier'
import calepinageApi from '../../api/calepinageApi'
import {
  nombre, pasMesure, tauxOccupation, contourTerrain, demandeMoteur, planVue2D,
} from './ModeTerrain'
import { formatCote, milieu } from './plan2d'
import { formatNumber } from '../../lib/format'

/* ============================================================================
   CAL91 — L'OMBRIÈRE / CARPORT, SURFACE DE POSE À PART ENTIÈRE.
   ----------------------------------------------------------------------------
   Constat : rien dans le dépôt ne traitait l'ombrière (grep `carport|ombrière`
   : zéro) alors que c'est une demande courante des clients tertiaires. Une
   ombrière pave comme un toit incliné et se totalise avec le reste du site.

   ELLE RÉUTILISE CAL89, ELLE NE LE REFAIT PAS. Le contour, la demande moteur,
   le pas MESURÉ sur les rangées renvoyées et le taux d'occupation viennent des
   fonctions pures de `ModeTerrain.jsx` : deux implémentations, ce serait deux
   ombrières qui divergent. Seules trois saisies sont PROPRES à l'ombrière :
   l'emprise, la HAUTEUR LIBRE et le SENS D'ÉCOULEMENT (qui est aussi l'azimut
   d'empilement envoyé au moteur).

   AUCUN CHIFFRAGE DE STRUCTURE — la tâche l'exige : pas de descente de
   charges, pas de section de poteau, pas de masse, pas de prix. Cet écran POSE
   des modules sur une emprise ; il ne dimensionne aucun ouvrage. Un test relit
   cette source pour le tenir.

   LES TOTAUX PAR BÂTIMENT : `buildingId` est la MÊME clé que celle des pans de
   toiture (CAL59). L'ombrière apparaît donc dans le total de son bâtiment à
   côté des pans, sans qu'aucun total ne soit tenu à la main — et un bâtiment
   dont aucun pan n'a encore de plan n'affiche pas 0, il affiche « — ».

   LA HAUTEUR LIBRE N'EST JAMAIS SUPPOSÉE : absente, la couverture n'est pas
   levée et l'écran le dit. Une ombrière « à 2,50 m par défaut » serait un
   chiffre inventé sur lequel un client signerait.
   ========================================================================== */

/**
 * CAL91 — la surface de pose OMBRIÈRE persistée dans le document v2
 * (`poseSurfaces[]`, `kind: "ombriere"`). Aucune clé de structure, de charge
 * ni de prix : le contrat n'en déclare aucune, et cette fonction n'en écrit
 * aucune.
 */
export function documentOmbriere(saisie, reponse) {
  const contour = contourTerrain(saisie.largeurM, saisie.profondeurM)
  const aire = contour ? nombre(saisie.largeurM) * nombre(saisie.profondeurM) : null
  const plan = (reponse?.plans ?? [])[0] ?? null
  const tables = plan?.tables ?? []
  return {
    kind: 'ombriere',
    id: saisie.repere || 'OMBRIERE',
    label: saisie.label || 'Ombrière',
    buildingId: saisie.buildingId || '',
    contourM: contour ?? [],
    areaM2: aire,
    tiltDeg: nombre(saisie.tiltDeg),
    clearHeightM: nombre(saisie.clearHeightM),
    flowAzimuthDeg: nombre(saisie.flowAzimuthDeg),
    rowAzimuthDeg: nombre(saisie.flowAzimuthDeg),
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

/**
 * CAL91 — LES TOTAUX PAR BÂTIMENT : les pans de toiture (`zones[]`, compte
 * posé dans `geometry.count`) ET les surfaces de pose (`poseSurfaces[]`,
 * compte rendu par le moteur), regroupés par `buildingId`.
 *
 * Un bâtiment dont RIEN n'est encore posé rend `modules: null` — pas `0`, qui
 * se lirait « rien ne tient » alors que rien n'a été calculé.
 */
export function totauxParBatiment(layout) {
  const total = new Map()
  const ajouter = (batiment, compte, genre) => {
    const cle = batiment || '(bâtiment unique)'
    const courant = total.get(cle) ?? { batiment: cle, modules: null, pans: 0, ombrieres: 0, sols: 0 }
    if (Number.isFinite(compte)) courant.modules = (courant.modules ?? 0) + compte
    if (genre === 'pan') courant.pans += 1
    if (genre === 'ombriere') courant.ombrieres += 1
    if (genre === 'sol') courant.sols += 1
    total.set(cle, courant)
  }
  for (const zone of layout?.zones ?? []) {
    ajouter(zone?.buildingId, Number(zone?.geometry?.count), 'pan')
  }
  for (const surface of layout?.poseSurfaces ?? []) {
    ajouter(surface?.buildingId, Number(surface?.engine?.modules), surface?.kind)
  }
  return Array.from(total.values())
}

/* ============================================================================
   CALX51 — L'OMBRIÈRE EST DESSINÉE, ET LEVÉE À LA HAUTEUR SAISIE.
   ----------------------------------------------------------------------------
   Constat : cet écran était le jumeau du mode terrain — un formulaire et des
   totaux, sans vue. Le placement existait pourtant, PUR et testé, dans le
   builder (`construireOmbriere`, `@roofpro/scene3d`) et n'avait aucun appelant.
   On le branche : c'est LUI qui lève la couverture, et c'est LUI qui refuse de
   deviner. Hauteur libre absente ⇒ l'altitude des tables reste 0 et le manque
   est affiché avec les mots du service ; aucune hauteur de confort n'est
   écrite nulle part, ni dans le code, ni sur l'écran.

   DEUX DESSINS, AUCUN CALCUL : le PLAN réutilise la mise en page du mode
   terrain (`planVue2D`) — une seule mise en page pour les deux surfaces de
   pose, sinon elles divergeraient. La COUPE (ci-dessous) ne fait que lire
   l'altitude que le service a posée sur chaque table.

   AUCUNE CHARGE, AUCUNE STRUCTURE — la règle de CAL91 ne bouge pas : ces
   dessins placent des formes, ils ne dimensionnent aucun ouvrage.
   ========================================================================== */

/** Zone de dessin de la coupe (unités du `viewBox`). */
export const COUPE_LARGEUR = 900
export const COUPE_HAUTEUR = 260

/**
 * CALX51 — la COUPE sur la largeur de l'ombrière : le sol, et la couverture à
 * l'altitude que `construireOmbriere` a posée sur chaque table.
 *
 * Le sol (altitude 0) fait TOUJOURS partie du cadre : c'est par rapport à lui
 * que la hauteur libre se lit. Altitude nulle ⇒ aucune cote de hauteur n'est
 * tracée, parce qu'il n'y a rien à coter. Aucune table ⇒ `null` : rien n'est
 * dessiné plutôt qu'une ombrière supposée.
 */
export function coupeOmbriere({
  tables = [],
  largeurPx = COUPE_LARGEUR,
  hauteurPx = COUPE_HAUTEUR,
  margePx = 28,
} = {}) {
  if (!(largeurPx > 0) || !(hauteurPx > 0)) return null
  const segments = []
  for (const t of tables ?? []) {
    const cx = Number(t?.cx)
    const l = Number(t?.largeurM)
    const z = Number(t?.z)
    if (![cx, l, z].every((v) => Number.isFinite(v))) continue
    segments.push({ x0: cx - l / 2, x1: cx + l / 2, z })
  }
  if (!segments.length) return null

  let minX = Infinity
  let maxX = -Infinity
  let altitudeM = 0
  for (const s of segments) {
    if (s.x0 < minX) minX = s.x0
    if (s.x1 > maxX) maxX = s.x1
    if (s.z > altitudeM) altitudeM = s.z
  }
  const etendueX = Math.max(1e-6, maxX - minX)
  const etendueZ = Math.max(1e-6, altitudeM)
  const marge = Math.max(0, Math.min(Math.min(largeurPx, hauteurPx) / 2 - 1, margePx))
  const pxParM = Math.min((largeurPx - 2 * marge) / etendueX, (hauteurPx - 2 * marge) / etendueZ)
  const decX = (largeurPx - etendueX * pxParM) / 2
  const decZ = (hauteurPx - etendueZ * pxParM) / 2
  // Une altitude qui monte va vers le HAUT du dessin : y décroît à l'écran.
  const versPx = (x, z) => [decX + (x - minX) * pxParM, decZ + (altitudeM - z) * pxParM]

  return {
    largeurPx,
    hauteurPx,
    pxParM,
    altitudeM,
    sol: { from: versPx(minX, 0), to: versPx(maxX, 0) },
    tables: segments.map((s) => ({ z: s.z, from: versPx(s.x0, s.z), to: versPx(s.x1, s.z) })),
    coteHauteur: altitudeM > 0
      ? { lengthM: altitudeM, from: versPx(minX, 0), to: versPx(minX, altitudeM) }
      : null,
  }
}

const SAISIE_VIDE = {
  repere: 'OMBRIERE',
  label: 'Ombrière',
  buildingId: '',
  largeurM: '',
  profondeurM: '',
  clearHeightM: '',
  tiltDeg: '',
  flowAzimuthDeg: '',
  moduleLongM: '',
  moduleCourtM: '',
  puissanceWc: '',
  modulesParTable: '',
  alleeM: '',
}

const CHAMPS = [
  ['largeurM', 'Emprise — largeur (m)'],
  ['profondeurM', 'Emprise — profondeur (m)'],
  ['clearHeightM', 'Hauteur libre sous l’ombrière (m)'],
  ['tiltDeg', 'Inclinaison de la couverture (°)'],
  ['flowAzimuthDeg', 'Sens d’écoulement (°, 180 = sud)'],
  ['moduleLongM', 'Module — grand côté (m)'],
  ['moduleCourtM', 'Module — petit côté (m)'],
  ['puissanceWc', 'Module — puissance (Wc)'],
  ['modulesParTable', 'Modules par travée'],
  ['alleeM', 'Allée imposée entre rangées (m) — vide = politique du moteur'],
]

function auDixieme(v) {
  return v === null || v === undefined ? '—' : Math.round(v * 10) / 10
}

export default function Ombriere({ calepinageId: idPropose = null, persister = true }) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [saisie, setSaisie] = useState(SAISIE_VIDE)
  const [layout, setLayout] = useState(null)
  const [reponse, setReponse] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [message, setMessage] = useState(null)
  // CALX51 — le PLACEUR de l'ombrière (`construireOmbriere`), chargé à
  // l'ouverture de l'écran seulement : `scene3d` porte aussi la couche WebGL,
  // qu'un import statique ferait tomber dans le paquet de cette route. Rangé
  // dans un objet : une fonction nue passée à `setState` serait lue comme une
  // mise à jour, pas comme une valeur.
  const [placeur, setPlaceur] = useState(null)
  const [placeurAbsent, setPlaceurAbsent] = useState(false)

  useEffect(() => {
    let annule = false
    import('@roofpro/scene3d')
      .then((mod) => {
        if (annule) return
        if (typeof mod?.construireOmbriere === 'function') {
          setPlaceur({ construireOmbriere: mod.construireOmbriere })
        } else {
          setPlaceurAbsent(true)
        }
      })
      .catch(() => { if (!annule) setPlaceurAbsent(true) })
    return () => { annule = true }
  }, [])

  // RELECTURE — une ombrière déjà enregistrée revient telle quelle.
  useEffect(() => {
    if (!calepinageId || !persister) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        const doc = res?.data?.roof_layout ?? null
        setLayout(doc)
        const omb = (doc?.poseSurfaces ?? []).find((s) => s?.kind === 'ombriere')
        if (!omb) return
        const contour = omb.contourM ?? []
        const texte = (v) => (v === null || v === undefined ? '' : String(v))
        setSaisie((s) => ({
          ...s,
          repere: omb.id ?? s.repere,
          label: omb.label ?? s.label,
          buildingId: omb.buildingId ?? s.buildingId,
          largeurM: contour.length === 4 ? String(contour[1][0]) : s.largeurM,
          profondeurM: contour.length === 4 ? String(contour[2][1]) : s.profondeurM,
          clearHeightM: texte(omb.clearHeightM) || s.clearHeightM,
          tiltDeg: texte(omb.tiltDeg) || s.tiltDeg,
          flowAzimuthDeg: texte(omb.flowAzimuthDeg) || s.flowAzimuthDeg,
        }))
        setReponse({
          plans: [{ modules: omb.engine?.modules ?? null, tables: omb.engine?.tables ?? [] }],
          version_moteur: omb.engine?.versionMoteur ?? null,
          hash_entree: omb.engine?.hashEntree ?? null,
          _pasRecharge: omb.engine?.rowPitchM ?? null,
        })
      })
      .catch(() => { if (!annule) setLayout(null) })
    return () => { annule = true }
  }, [calepinageId, persister])

  const majChamp = (cle, brut) => setSaisie((s) => ({ ...s, [cle]: brut }))

  const calculer = () => {
    // Le SENS D'ÉCOULEMENT est l'azimut d'empilement : une seule grandeur,
    // saisie une seule fois, passée telle quelle à la demande de CAL89.
    const demande = demandeMoteur({ ...saisie, rowAzimuthDeg: saisie.flowAzimuthDeg })
    if (!demande) {
      setMessage('Emprise et module incomplets : rien n’est envoyé au moteur, '
        + 'et surtout aucune valeur par défaut inventée.')
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
          || 'Le moteur n’a pas pu poser cette ombrière.')
      })
  }

  const enregistrer = () => {
    if (!reponse) {
      setMessage('Aucun plan du moteur : il n’y a rien à enregistrer.')
      return
    }
    const surface = documentOmbriere(saisie, reponse)
    const autres = (layout?.poseSurfaces ?? [])
      .filter((s) => !(s?.kind === 'ombriere' && (s?.id ?? '') === surface.id))
    const doc = { ...(layout ?? {}), poseSurfaces: [...autres, surface] }
    Promise.resolve(calepinageApi.calepinages.enregistrerLayoutCalepinage(calepinageId, doc))
      .then(() => {
        setLayout(doc)
        setMessage('Ombrière enregistrée dans la conception.')
      })
      .catch(() => setMessage('L’ombrière n’a pas pu être enregistrée.'))
  }

  const plan = (reponse?.plans ?? [])[0] ?? null
  const pas = plan ? (pasMesure(plan.rangees) ?? reponse?._pasRecharge ?? null) : null
  const hauteur = nombre(saisie.clearHeightM)
  const ecoulement = nombre(saisie.flowAzimuthDeg)
  const aire = contourTerrain(saisie.largeurM, saisie.profondeurM)
    ? nombre(saisie.largeurM) * nombre(saisie.profondeurM)
    : null

  // CALX51 — l'ombrière PLACÉE par le service : c'est lui qui lève (ou non) la
  // couverture, à partir de la seule hauteur libre SAISIE. La pente du sol
  // n'est pas une donnée de cet écran : le service le dit dans `nonMesure`,
  // on ne lui en souffle aucune.
  const champ = placeur && plan
    ? placeur.construireOmbriere(plan, {
      tiltDeg: nombre(saisie.tiltDeg),
      hauteurLibreM: hauteur,
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
  const coupe = champ ? coupeOmbriere({ tables: champ.tables }) : null
  // L'ALTITUDE AFFICHÉE est celle que le service a posée sur les tables, pas la
  // saisie relue : c'est la seule façon de voir qu'une hauteur absente ne lève
  // rien du tout.
  const altitudeCouverture = champ && champ.tables.length
    ? Math.max(...champ.tables.map((t) => Number(t.z)))
    : null

  // Les totaux affichés incluent l'ombrière EN COURS, pas seulement celles déjà
  // enregistrées — sinon le total mentirait jusqu'au prochain enregistrement.
  const layoutAffiche = plan
    ? {
      ...(layout ?? {}),
      poseSurfaces: [
        ...((layout?.poseSurfaces ?? []).filter(
          (s) => !(s?.kind === 'ombriere' && (s?.id ?? '') === (saisie.repere || 'OMBRIERE')),
        )),
        documentOmbriere(saisie, reponse),
      ],
    }
    : layout
  const totaux = totauxParBatiment(layoutAffiche)

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="cine-card mt-6 p-6" data-testid="cal-ombriere">
        <p className="tech-label rule-brass text-brass-300">Ombrière / carport</p>
        <p className="mt-2 text-xs text-lune-faint">
          Une surface de pose comme une autre : elle pave comme un toit incliné et
          se totalise avec le site. Aucune charge, aucune structure n’est calculée
          ici.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="block text-sm text-lune-soft">
            <span className="tech-label text-lune-faint">Bâtiment (pour les totaux)</span>
            <input
              type="text"
              value={saisie.buildingId}
              data-testid="cal-ombriere-buildingId"
              onChange={(e) => majChamp('buildingId', e.target.value)}
              className="mt-1 w-full rounded border border-white/15 bg-transparent px-2 py-1 text-white"
            />
          </label>
          {CHAMPS.map(([cle, label]) => (
            <label key={cle} className="block text-sm text-lune-soft">
              <span className="tech-label text-lune-faint">{label}</span>
              <input
                type="number"
                step="any"
                value={saisie[cle]}
                data-testid={`cal-ombriere-${cle}`}
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
            data-testid="cal-ombriere-calculer"
            className="rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200"
          >
            {enCours ? 'Calcul en cours…' : 'Calculer l’ombrière'}
          </button>
          {persister && (
            <button
              type="button"
              onClick={enregistrer}
              data-testid="cal-ombriere-enregistrer"
              className="rounded border border-white/15 px-4 py-2 text-sm font-semibold text-white"
            >
              Enregistrer l’ombrière
            </button>
          )}
        </div>

        {message && (
          <p className="mt-3 text-sm text-lune-soft" role="status"
            data-testid="cal-ombriere-message">{message}</p>
        )}

        {/* LA HAUTEUR LIBRE N'EST JAMAIS SUPPOSÉE. */}
        <p className="mt-3 text-xs text-lune-faint" data-testid="cal-ombriere-hauteur">
          {hauteur === null || hauteur <= 0
            ? 'Hauteur libre non renseignée : la couverture n’est pas levée en 3D '
              + '(aucune hauteur par défaut n’est supposée).'
            : `Couverture posée à ${auDixieme(hauteur)} m — la hauteur saisie.`}
        </p>

        {plan && (
          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-white/10 pt-4 sm:grid-cols-3">
            <div data-testid="cal-ombriere-modules">
              <dd className="fig text-lg text-white">{plan.modules ?? '—'}</dd>
              <dt className="tech-label text-lune-faint">Modules posés (moteur)</dt>
            </div>
            <div data-testid="cal-ombriere-travees">
              <dd className="fig text-lg text-white">{(plan.tables ?? []).length}</dd>
              <dt className="tech-label text-lune-faint">Travées posées</dt>
            </div>
            <div data-testid="cal-ombriere-pas">
              <dd className="fig text-lg text-white">
                {pas === null ? '—' : `${auDixieme(pas)} m`}
              </dd>
              <dt className="tech-label text-lune-faint">
                {pas === null
                  ? 'Pas non mesurable (moins de 2 rangées)'
                  : 'Pas inter-rangées (mesuré sur le plan)'}
              </dt>
            </div>
          </dl>
        )}

        {/* CALX51 — L'OMBRIÈRE DESSINÉE : le plan, puis la coupe où la couverture
            est levée à la hauteur libre SAISIE (ou pas levée du tout). */}
        {(plan || placeurAbsent) && (
          <section
            className="mt-5 border-t border-white/10 pt-4"
            data-testid="cal-ombriere-vue"
            aria-label="Ombrière dessinée"
          >
            <p className="tech-label text-lune-faint">
              Ombrière dessinée — travées posées et couverture levée
            </p>

            {placeurAbsent && (
              <p className="mt-2 text-sm text-alert-300" data-testid="cal-ombriere-vue-indisponible">
                Le tracé de l’ombrière n’a pas pu être chargé : les chiffres du
                moteur restent affichés ci-dessus, et rien n’est dessiné à leur
                place.
              </p>
            )}

            {vue && (
              <>
                <svg
                  data-testid="cal-ombriere-svg"
                  viewBox={`0 0 ${vue.largeurPx} ${vue.hauteurPx}`}
                  width="100%"
                  role="img"
                  aria-label={`Ombrière en plan — ${vue.tables.length} travée(s) posée(s) par le moteur`}
                  className="mt-2 text-brass-200"
                >
                  <polygon
                    data-testid="cal-ombriere-emprise-tracee"
                    points={vue.contour.map((p) => p.join(',')).join(' ')}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  />
                  {vue.rangees.map((r) => (
                    <line
                      key={r.y0}
                      data-testid="cal-ombriere-rangee"
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
                      data-testid="cal-ombriere-travee"
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
                        data-testid="cal-ombriere-cote"
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
                </svg>

                <p className="mt-2 text-xs text-lune-faint" data-testid="cal-ombriere-emprise">
                  {vue.tables.length} travée(s) dessinée(s) — emprise{' '}
                  {formatNumber(champ.empriseTablesM2, { decimals: 1 })} m² ;{' '}
                  {champ.modules ?? '—'} module(s) posé(s) par le moteur.
                </p>
              </>
            )}

            {coupe && (
              <svg
                data-testid="cal-ombriere-coupe"
                viewBox={`0 0 ${coupe.largeurPx} ${coupe.hauteurPx}`}
                width="100%"
                role="img"
                aria-label="Coupe sur la largeur — couverture et hauteur libre"
                className="mt-3 text-brass-200"
              >
                <line
                  data-testid="cal-ombriere-sol"
                  x1={coupe.sol.from[0]}
                  y1={coupe.sol.from[1]}
                  x2={coupe.sol.to[0]}
                  y2={coupe.sol.to[1]}
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeOpacity="0.55"
                />
                {coupe.tables.map((t, i) => (
                  <line
                    key={i}
                    data-testid="cal-ombriere-couverture"
                    x1={t.from[0]}
                    y1={t.from[1]}
                    x2={t.to[0]}
                    y2={t.to[1]}
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                ))}
                {coupe.coteHauteur && (
                  <>
                    <line
                      data-testid="cal-ombriere-trait-hauteur"
                      x1={coupe.coteHauteur.from[0]}
                      y1={coupe.coteHauteur.from[1]}
                      x2={coupe.coteHauteur.to[0]}
                      y2={coupe.coteHauteur.to[1]}
                      stroke="currentColor"
                      strokeWidth="1.5"
                    />
                    <text
                      data-testid="cal-ombriere-cote-hauteur"
                      x={milieu(coupe.coteHauteur.from, coupe.coteHauteur.to)[0] + 6}
                      y={milieu(coupe.coteHauteur.from, coupe.coteHauteur.to)[1]}
                      fontSize="12"
                      textAnchor="start"
                      fill="currentColor"
                    >
                      {formatCote(coupe.coteHauteur.lengthM)}
                    </text>
                  </>
                )}
              </svg>
            )}

            {altitudeCouverture !== null && (
              <p
                className="mt-2 text-xs text-lune-faint"
                data-testid="cal-ombriere-altitude"
                data-altitude-m={String(altitudeCouverture)}
              >
                {altitudeCouverture > 0
                  ? `Couverture levée à ${formatCote(altitudeCouverture)} — l’altitude `
                    + 'posée sur les travées, celle de la hauteur libre saisie.'
                  : 'Couverture non levée : les travées restent à l’altitude du sol, '
                    + 'faute de hauteur libre saisie.'}
              </p>
            )}

            {champ && (
              <p className="mt-1 text-xs text-lune-faint" data-testid="cal-ombriere-ecoulement">
                {ecoulement === null
                  ? 'Sens d’écoulement non renseigné : les rangées sont empilées '
                    + 'selon l’axe du plan, sans orientation affirmée.'
                  : `Sens d’écoulement saisi : ${ecoulement}° — c’est l’axe `
                    + 'd’empilement des rangées, du haut vers le bas du plan.'}
              </p>
            )}

            {champ && champ.nonMesure.length > 0 && (
              <ul
                className="mt-2 list-disc pl-5 text-xs text-lune-faint"
                data-testid="cal-ombriere-nonmesure"
              >
                {champ.nonMesure.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* LES TOTAUX PAR BÂTIMENT — l'ombrière y figure à côté des pans. */}
        {totaux.length > 0 && (
          <table className="mt-5 w-full text-sm" data-testid="cal-ombriere-totaux">
            <thead>
              <tr className="tech-label text-lune-faint">
                <th className="py-1 text-left">Bâtiment</th>
                <th className="py-1 text-right">Pans</th>
                <th className="py-1 text-right">Ombrières</th>
                <th className="py-1 text-right">Champs au sol</th>
                <th className="py-1 text-right">Modules</th>
              </tr>
            </thead>
            <tbody>
              {totaux.map((t) => (
                <tr key={t.batiment} data-testid={`cal-ombriere-total-${t.batiment}`}>
                  <td className="py-1 text-white">{t.batiment}</td>
                  <td className="py-1 text-right text-lune-soft">{t.pans}</td>
                  <td className="py-1 text-right text-lune-soft">{t.ombrieres}</td>
                  <td className="py-1 text-right text-lune-soft">{t.sols}</td>
                  <td className="fig py-1 text-right text-white">{t.modules ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
