/* eslint-disable react-refresh/only-export-components --
   Les quatre fonctions de TRANSFORMATION exportées ci-dessous sont PURES
   (géométrie, zéro React) : la tâche exige explicitement un « test unitaire de
   la transformation », qui doit donc pouvoir les appeler sans monter l'écran.
   Les sortir dans un `.js` voisin séparerait la formule de son unique lecteur
   pour satisfaire une règle de fast-refresh qui ne concerne pas des fonctions
   sans état ; même dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import RetourAtelier from './atelier/RetourAtelier'

/* ============================================================================
   CAL63 — CALER UN PLAN IMPORTÉ : translation, rotation, ÉCHELLE SAISIE.
   ----------------------------------------------------------------------------
   Constat de la tâche : l'atelier n'a aucune manipulation de plan importé
   (aucun `rotate`/`scale` de calque dans `roofPro11/`). Un plan déposé reste
   donc un dessin muet, dans l'unité DU FICHIER — et `services/import_plan.py`
   (CAL62) le dit noir sur blanc : « un DXF qui ne déclare pas $INSUNITS et un
   PDF (points typographiques) rendent `unite='inconnu'`, et c'est la
   calibration de l'atelier qui donne l'échelle. Une conversion supposée
   produirait un plan faux qui a l'air juste. » Cet écran EST cette calibration.

   L'ÉCHELLE VIENT D'UNE DISTANCE SAISIE, JAMAIS D'UNE ESTIMATION. On ne déduit
   l'échelle ni du cartouche, ni de l'unité déclarée, ni d'une hypothèse de
   format : l'utilisateur DÉSIGNE DEUX POINTS du plan et TAPE la distance
   RÉELLE qui les sépare. Sans cette saisie, `echelleDepuisDeuxPoints` rend
   `null` et l'écran refuse de convertir — il n'invente pas un facteur 1.

   LE CALAGE EST PERSISTÉ DANS LE DOCUMENT DE CONCEPTION (`roof_layout`, clé
   `planImporte`, schéma v2 `additionalProperties: true`), relu au montage par
   la MÊME porte `layout/` (CAL18) — aucun second stockage, aucune seconde
   forme d'URL.

   D'OÙ VIENT LE CONTOUR (CALX39). L'analyseur de CAL62 a désormais sa porte
   HTTP : `POST calepinages/<pk>/importer-plan/` (contrat
   `apps/calepinage/contract_samples/calepinage_import_plan.json`). Le fichier
   déposé ici est ANALYSÉ par le serveur, qui rend ses calques ; le calque
   choisi rend le contour. Cette porte n'écrit RIEN — ni `roof_layout`, ni
   document : l'enregistrement reste les deux boutons du bas, et c'est
   l'utilisateur qui les presse. Le contour peut toujours arriver par la
   propriété `contour` ou depuis un calage déjà enregistré ; sans aucun des
   trois, l'écran le DIT au lieu d'afficher un calque vide qui aurait l'air
   cassé.

   LE SERVEUR NE DEVINE AUCUNE ÉCHELLE, ET CET ÉCRAN NON PLUS : la réponse
   porte l'unité DÉCLARÉE par le fichier (ou « inconnu ») et le motif qui dit
   pourquoi l'échelle vient d'ici. Un refus est rendu SOUS le champ fautif
   (`fichier` ou `calque`), avec le bandeau qui le nomme.
   ========================================================================== */

const RAD = Math.PI / 180

/**
 * CAL63 — l'ÉCHELLE, depuis deux points de référence et la distance RÉELLE
 * saisie entre eux. Rend `{ echelle, distancePlan, source: 'saisie' }`, ou
 * `null` si l'un des deux points manque, si les deux points sont confondus,
 * ou si la distance réelle n'est pas une longueur strictement positive.
 *
 * JAMAIS de repli sur 1 : une échelle inventée produit un plan faux qui a
 * l'air juste — exactement ce que la docstring de CAL62 interdit.
 */
export function echelleDepuisDeuxPoints(a, b, distanceReelleM) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length < 2 || b.length < 2) {
    return null
  }
  const reelle = Number(distanceReelleM)
  if (!Number.isFinite(reelle) || reelle <= 0) return null
  const dx = Number(b[0]) - Number(a[0])
  const dy = Number(b[1]) - Number(a[1])
  const distancePlan = Math.hypot(dx, dy)
  if (!Number.isFinite(distancePlan) || distancePlan === 0) return null
  return {
    echelle: reelle / distancePlan,
    distancePlan,
    source: 'saisie',
  }
}

/**
 * CAL63 — la TRANSFORMATION d'un point du plan : rotation autour d'un pivot,
 * mise à l'échelle, puis translation. L'ordre est figé (et testé) parce que
 * deux ordres différents donnent deux plans différents.
 *
 * `calage` : `{ pivot: [x, y], rotationDeg, echelle, translation: [tx, ty] }`.
 * Toute composante absente est NEUTRE (pivot à l'origine, rotation nulle,
 * échelle 1, translation nulle) — neutre, pas « devinée » : le neutre ne
 * déplace rien, une estimation, si.
 */
export function appliquerCalage(point, calage = {}) {
  if (!Array.isArray(point) || point.length < 2) return null
  const [px, py] = calage.pivot ?? [0, 0]
  const angle = Number(calage.rotationDeg ?? 0) * RAD
  const k = Number.isFinite(Number(calage.echelle)) && Number(calage.echelle) > 0
    ? Number(calage.echelle) : 1
  const [tx, ty] = calage.translation ?? [0, 0]

  const dx = Number(point[0]) - Number(px)
  const dy = Number(point[1]) - Number(py)
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)
  const rx = dx * cos - dy * sin
  const ry = dx * sin + dy * cos
  return [
    Number(px) + rx * k + Number(tx),
    Number(py) + ry * k + Number(ty),
  ]
}

/** CAL63 — le contour entier calé. Un contour non exploitable rend `[]`. */
export function calerContour(contour, calage) {
  if (!Array.isArray(contour)) return []
  return contour
    .map((point) => appliquerCalage(point, calage))
    .filter(Boolean)
}

/**
 * CAL63 — AIMANTATION : un point se colle au sommet de mur/objet le plus
 * proche, à condition qu'il soit DANS la tolérance. Hors tolérance, le point
 * ne bouge pas (`aimante: false`) — on ne tire jamais un tracé vers un mur
 * éloigné « pour faire propre ».
 */
export function aimanter(point, cibles, tolerance) {
  const seuil = Number(tolerance)
  if (!Array.isArray(point) || !Array.isArray(cibles) || !cibles.length
    || !Number.isFinite(seuil) || seuil <= 0) {
    return { point, aimante: false, distance: null }
  }
  let meilleure = null
  let distanceMin = Infinity
  for (const cible of cibles) {
    if (!Array.isArray(cible) || cible.length < 2) continue
    const d = Math.hypot(Number(cible[0]) - Number(point[0]),
      Number(cible[1]) - Number(point[1]))
    if (d < distanceMin) {
      distanceMin = d
      meilleure = cible
    }
  }
  if (meilleure === null || distanceMin > seuil) {
    return { point, aimante: false, distance: Number.isFinite(distanceMin) ? distanceMin : null }
  }
  return { point: [Number(meilleure[0]), Number(meilleure[1])], aimante: true, distance: distanceMin }
}

/** Une valeur servie, ou le tiret de l'inconnu — jamais un zéro de repli. */
function texte(brut, suffixe = '') {
  if (brut === null || brut === undefined || brut === '') return '—'
  return `${brut}${suffixe}`
}

function ChampNombre({ cle, label, valeur, erreur, onChange }) {
  return (
    <label className="block" data-testid={`cal-calage-champ-${cle}`}>
      <span className="tech-label text-lune-faint">{label}</span>
      <input
        type="number"
        step="any"
        id={`cal-calage-${cle}`}
        value={valeur ?? ''}
        onChange={(e) => onChange(cle, e.target.value)}
        aria-invalid={erreur ? 'true' : undefined}
        className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      />
      {erreur && (
        <span role="alert" data-testid={`cal-calage-erreur-${cle}`}
          className="mt-1 block text-xs text-red-300">{erreur}</span>
      )}
    </label>
  )
}

export default function PlanImporteCalage({
  calepinageId: idPropose, contour: contourPropose = null,
}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [layout, setLayout] = useState(null)
  const [saisie, setSaisie] = useState({
    translationX: '', translationY: '', rotationDeg: '',
    indexA: '0', indexB: '1', distanceReelleM: '', tolerance: '',
  })
  const [aimantationActive, setAimantationActive] = useState(false)
  const [message, setMessage] = useState(null)
  const [refus, setRefus] = useState(null)
  // CALX39 — le plan déposé, l'analyse rendue par le serveur, le calque choisi
  // et le contour qu'il propose. Rien de tout cela n'est persisté par la porte.
  const [fichierDepose, setFichierDepose] = useState(null)
  const [analyse, setAnalyse] = useState(null)
  const [calqueChoisi, setCalqueChoisi] = useState('')
  const [contourImporte, setContourImporte] = useState(null)
  const [refusImport, setRefusImport] = useState(null)

  // RELECTURE du calage persisté : la MÊME porte `layout/` que la conception.
  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        const document = res?.data?.roof_layout ?? null
        setLayout(document)
        const calage = document?.planImporte?.calage
        if (!calage) return
        setSaisie((s) => ({
          ...s,
          translationX: String(calage.translation?.[0] ?? ''),
          translationY: String(calage.translation?.[1] ?? ''),
          rotationDeg: String(calage.rotationDeg ?? ''),
          indexA: String(calage.indexA ?? '0'),
          indexB: String(calage.indexB ?? '1'),
          distanceReelleM: String(calage.distanceReelleM ?? ''),
        }))
      })
      .catch(() => { if (!annule) setLayout(null) })
    return () => { annule = true }
  }, [calepinageId])

  const contour = contourPropose ?? contourImporte
    ?? layout?.planImporte?.contour ?? null
  const sommets = Array.isArray(contour) ? contour : []

  const pointA = sommets[Number(saisie.indexA)] ?? null
  const pointB = sommets[Number(saisie.indexB)] ?? null
  const mesure = echelleDepuisDeuxPoints(pointA, pointB, saisie.distanceReelleM)

  const calage = {
    pivot: pointA ?? [0, 0],
    rotationDeg: Number(saisie.rotationDeg) || 0,
    echelle: mesure?.echelle,
    translation: [Number(saisie.translationX) || 0, Number(saisie.translationY) || 0],
  }

  // Les sommets des murs/objets DÉJÀ tracés : les cibles d'aimantation. Ils
  // viennent du document de conception, jamais d'une grille inventée.
  const cibles = Array.isArray(layout?.outline) ? layout.outline : []
  const brut = calerContour(sommets, calage)
  const cale = aimantationActive
    ? brut.map((p) => aimanter(p, cibles, Number(saisie.tolerance)).point)
    : brut

  const enregistrer = () => {
    if (!mesure) {
      setRefus('distanceReelleM')
      setMessage(null)
      return
    }
    setRefus(null)
    const document = {
      ...(layout ?? {}),
      planImporte: {
        contour: sommets,
        calage: {
          translation: calage.translation,
          rotationDeg: calage.rotationDeg,
          echelle: mesure.echelle,
          echelle_source: mesure.source,
          indexA: Number(saisie.indexA),
          indexB: Number(saisie.indexB),
          distanceReelleM: Number(saisie.distanceReelleM),
        },
        contour_cale: cale,
      },
    }
    Promise.resolve(calepinageApi.calepinages.enregistrerLayoutCalepinage(calepinageId, document))
      .then(() => {
        setLayout(document)
        setMessage('Calage enregistré : il sera rechargé tel quel.')
      })
      .catch((e) => setMessage(
        e?.response?.data?.roof_layout
        || 'Le calage n’a pas pu être enregistré.'))
  }

  const convertir = () => {
    if (!mesure) {
      setRefus('distanceReelleM')
      return
    }
    setRefus(null)
    const document = { ...(layout ?? {}), outline: cale }
    Promise.resolve(calepinageApi.calepinages.enregistrerLayoutCalepinage(calepinageId, document))
      .then(() => {
        setLayout(document)
        setMessage('Plan converti en tracé de toit.')
      })
      .catch(() => setMessage('La conversion n’a pas pu être enregistrée.'))
  }

  const majChamp = (cle, brutSaisi) => setSaisie((s) => ({ ...s, [cle]: brutSaisi }))

  /* CALX39 — dépose le plan et lit ce que le SERVEUR en dit. `calque` vide =
     première analyse (la liste des calques) ; `calque` renseigné = le contour
     de ce calque. Le fichier n'est pas conservé côté serveur : il repart avec
     le choix du calque. Un refus atterrit SOUS son champ. */
  const envoyerPlan = (calque) => {
    if (!fichierDepose) {
      setRefusImport({
        champ: 'fichier',
        message: 'Déposez un plan (DXF ou PDF vectoriel) avant de lancer l’analyse.',
      })
      return
    }
    const corps = new FormData()
    corps.append('fichier', fichierDepose)
    if (calque) corps.append('calque', calque)
    setRefusImport(null)
    Promise.resolve(calepinageApi.calepinages.importerPlan(calepinageId, corps))
      .then((res) => {
        const donnees = res?.data ?? null
        setAnalyse(donnees)
        if (donnees?.contour) setContourImporte(donnees.contour)
        setMessage(donnees?.message ?? null)
      })
      .catch((e) => {
        // Le motif vient du SERVEUR, et il NOMME son champ (`fichier` ou
        // `calque`) : on ne réécrit ni l'un ni l'autre.
        const corpsErreur = e?.response?.data ?? {}
        const champ = Object.keys(corpsErreur)[0] ?? 'fichier'
        setRefusImport({
          champ,
          message: String(corpsErreur[champ]
            ?? 'Le plan n’a pas pu être analysé.'),
        })
      })
  }

  const blocDepot = (
    <div className="mt-4" data-testid="cal-calage-import">
      <p className="tech-label text-lune-faint">
        Déposer un plan (DXF ou PDF vectoriel)
      </p>
      <input
        type="file"
        id="cal-calage-fichier"
        data-testid="cal-calage-fichier"
        accept=".dxf,.pdf"
        aria-invalid={refusImport?.champ === 'fichier' ? 'true' : undefined}
        onChange={(e) => {
          setFichierDepose(e.target.files?.[0] ?? null)
          setRefusImport(null)
        }}
        className="mt-1 block w-full text-sm text-lune-soft"
      />
      <button type="button" onClick={() => envoyerPlan('')}
        data-testid="cal-calage-analyser"
        className="mt-2 rounded border border-white/15 px-3 py-1 text-sm text-white">
        Analyser le plan
      </button>
      {refusImport?.champ === 'fichier' && (
        <span role="alert" data-testid="cal-calage-erreur-fichier"
          className="mt-1 block text-xs text-red-300">{refusImport.message}</span>
      )}

      {analyse && (
        <div className="mt-3" data-testid="cal-calage-analyse">
          <p className="text-xs text-lune-soft" data-testid="cal-calage-unite">
            Format : {texte(analyse.format)} — unité déclarée par le fichier :{' '}
            {texte(analyse.unite)}
          </p>
          <p className="text-xs text-lune-faint" data-testid="cal-calage-motif-echelle">
            {analyse.motif_echelle}
          </p>
          <label className="mt-2 block" data-testid="cal-calage-champ-calque">
            <span className="tech-label text-lune-faint">Calque d’enveloppe</span>
            <select
              data-testid="cal-calage-calque"
              value={calqueChoisi}
              aria-invalid={refusImport?.champ === 'calque' ? 'true' : undefined}
              onChange={(e) => setCalqueChoisi(e.target.value)}
              className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
            >
              <option value="">— choisir un calque —</option>
              {(analyse.calques ?? []).map((calque) => (
                <option key={calque.nom} value={calque.nom}>
                  {calque.nom} — {calque.entites} tracé(s), {calque.sommets} sommet(s)
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => envoyerPlan(calqueChoisi)}
            data-testid="cal-calage-proposer"
            className="mt-2 rounded bg-brass-500/20 px-3 py-1 text-sm font-semibold text-brass-200">
            Proposer ce contour
          </button>
          {refusImport?.champ === 'calque' && (
            <span role="alert" data-testid="cal-calage-erreur-calque"
              className="mt-1 block text-xs text-red-300">{refusImport.message}</span>
          )}
        </div>
      )}

      {refusImport && (
        <p role="alert" data-testid="cal-calage-bandeau-import"
          className="mt-2 text-xs text-red-300">
          Le champ « {refusImport.champ} » doit être corrigé : {refusImport.message}
        </p>
      )}
    </div>
  )

  if (!sommets.length) {
    return (
      <>
        <RetourAtelier calepinageId={calepinageId} />
        <div className="cine-card mt-6 p-6" data-testid="cal-calage-plan">
          <p className="tech-label rule-brass text-brass-300">Plan importé</p>
          <p className="mt-2 text-sm text-lune-soft" data-testid="cal-calage-sans-plan">
            Aucun plan importé n’est rattaché à ce calepinage : il n’y a donc rien
            à caler. Déposez un plan (DXF ou PDF vectoriel) ci-dessous : le serveur
            l’analyse et propose le contour du calque choisi, sans rien enregistrer.
          </p>
          {blocDepot}
        </div>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="cine-card mt-6 p-6" data-testid="cal-calage-plan">
        <p className="tech-label rule-brass text-brass-300">
          Caler le plan importé
        </p>

      {blocDepot}

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <ChampNombre cle="translationX" label="Translation X"
          valeur={saisie.translationX} onChange={majChamp} />
        <ChampNombre cle="translationY" label="Translation Y"
          valeur={saisie.translationY} onChange={majChamp} />
        <ChampNombre cle="rotationDeg" label="Rotation (°)"
          valeur={saisie.rotationDeg} onChange={majChamp} />
        <ChampNombre cle="tolerance" label="Tolérance d’aimantation"
          valeur={saisie.tolerance} onChange={majChamp} />
      </div>

      <fieldset className="mt-4" data-testid="cal-calage-echelle">
        <legend className="tech-label text-lune-faint">
          L’échelle — deux points de référence et la distance RÉELLE entre eux
        </legend>
        <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <ChampNombre cle="indexA" label="Sommet de référence A"
            valeur={saisie.indexA} onChange={majChamp} />
          <ChampNombre cle="indexB" label="Sommet de référence B"
            valeur={saisie.indexB} onChange={majChamp} />
          <ChampNombre
            cle="distanceReelleM"
            label="Distance réelle A→B (m)"
            valeur={saisie.distanceReelleM}
            erreur={refus === 'distanceReelleM'
              ? 'Mesurez la distance réelle entre les deux points de référence : '
                + 'sans elle, l’échelle serait une estimation, et le plan calé serait faux.'
              : null}
            onChange={majChamp}
          />
        </div>
        <p className="mt-2 text-sm text-lune-soft" data-testid="cal-calage-facteur">
          Échelle :{' '}
          {mesure
            ? `${mesure.echelle} m par unité de plan (source : ${mesure.source})`
            : 'non calculée — aucune échelle n’est estimée à votre place'}
        </p>
      </fieldset>

      <label className="mt-4 flex items-center gap-2 text-sm text-lune-soft">
        <input
          type="checkbox"
          data-testid="cal-calage-aimantation"
          checked={aimantationActive}
          onChange={(e) => setAimantationActive(e.target.checked)}
        />
        Aimanter aux murs et objets déjà tracés ({cibles.length} sommet(s) cible)
      </label>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        <div data-testid="cal-calage-sommets">
          <dd className="fig text-lg text-white">{sommets.length}</dd>
          <dt className="tech-label text-lune-faint">Sommets du plan</dt>
        </div>
        <div data-testid="cal-calage-source">
          <dd className="text-sm text-white">{texte(mesure?.source)}</dd>
          <dt className="tech-label text-lune-faint">Source de l’échelle</dt>
        </div>
        <div data-testid="cal-calage-distance-plan">
          <dd className="fig text-lg text-white">{texte(mesure?.distancePlan)}</dd>
          <dt className="tech-label text-lune-faint">Distance A→B sur le plan</dt>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={enregistrer}
          data-testid="cal-calage-enregistrer"
          className="rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200">
          Enregistrer le calage
        </button>
        <button type="button" onClick={convertir}
          data-testid="cal-calage-convertir"
          className="rounded border border-white/15 px-4 py-2 text-sm font-semibold text-white">
          Convertir en tracé de toit
        </button>
      </div>

      {message && (
        <p className="mt-3 text-sm text-lune-soft" role="status"
          data-testid="cal-calage-message">{message}</p>
      )}
    </div>
    </>
  )
}
