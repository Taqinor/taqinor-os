/* eslint-disable react-refresh/only-export-components --
   `documentOmbriere` et `totauxParBatiment` sont des fonctions PURES (une
   saisie + un plan du moteur → le document persisté et les totaux affichés).
   Le test jumeau les exerce sans monter l'écran, parce que ce sont ELLES qui
   garantissent qu'aucune charge n'est calculée et qu'aucun total n'est inventé.
   Même dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import { nombre, pasMesure, tauxOccupation, contourTerrain, demandeMoteur } from './ModeTerrain'

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
  )
}
