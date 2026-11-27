import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { todayLocalIso } from '../../lib/dateLocale'
import calepinageApi from '../../api/calepinageApi'
import useDocumentCalepinage, {
  ecrireSection, MESSAGE_ILLISIBLE, useLatitudeDuSite,
} from './useDocumentCalepinage'
import {
  sortedHorizonPoints, horizonMaxHeightDeg, hourlyHorizonFactors, maskedHourCount,
} from '@rooflib/horizonEngine'
import SunDiagram from './SunDiagram'
import { LegendeCourbes } from './LegendeCourbes'
import RetourAtelier from './atelier/RetourAtelier'
import { demarrerCapteurs, lireVisee } from './capteursTelephone'
import {
  lireFichierHorizon, nombreDeColonnes, CONVENTION_NORD, CONVENTION_SUD,
} from './horizonFichier'

/* ============================================================================
   CAL93 — L'HORIZON LOINTAIN, tracé en fond de la course du soleil, et appliqué
   à la production en poste de perte SÉPARÉ.
   ----------------------------------------------------------------------------
   Constat de la tâche : l'atelier ne connaît que l'ombrage PROCHE tracé à la
   main — une montagne à l'ouest n'existe pas pour lui. Le service CAL92
   (`apps/calepinage/services/horizon.py`) obtient un profil PVGIS
   (`printhorizon`), désormais exposé par `GET
   .../calepinages/<pk>/horizon/` (contrat
   `apps/calepinage/contract_samples/calepinage_horizon.json`) : le bouton
   « Récupérer depuis PVGIS » l'appelle et remplit le profil ; la saisie
   manuelle reste toujours possible ensuite — un relevé terrain (jumelles +
   boussole, ou une carte IGN) bat de toute façon un modèle numérique de
   terrain sur un site encaissé. Sans épingle posée ou PVGIS injoignable, le
   serveur rend `points: []` et un `detail` explicite (CAL92) : affiché tel
   quel, jamais un horizon plat inventé.

   PERSISTANCE : le profil voyage dans le MÊME document que la pose (CAL18
   `roof_layout`, endpoint déjà réel — `layout`/`enregistrerLayoutCalepinage`),
   sous la clé `horizonProfile` (contrat `roof_layout_v2.schema.json`,
   `$defs/horizonProfile`). Au prochain chargement de l'atelier
   (`roof-tool-pro11.ts applyDevisHydration`), le profil est relu et son dérate
   HORAIRE est appliqué à la production — TOUJOURS un poste séparé de
   l'ombrage proche (`shadingUi.ts recomputeHorizonFactors`), jamais fondu avec
   lui.

   ZÉRO CHIFFRE INVENTÉ : moins de deux points saisis ⇒ aucun horizon n'est
   affiché. ACAL124 — la simulation (`services/horizon.py`) exige un TOUR
   complet (au moins 8 directions, `DIRECTIONS_MINIMALES`) : en dessous,
   « Enregistrer » est désactivé et le dit (le serveur garde son refus).
   Tout geste sur un profil PVGIS (ajout OU retrait d'un point) le requalifie
   en « saisie » : un profil corrigé n'est plus un profil mesuré. La hauteur maximale et le
   compte d'heures masquées affichés ici sont TOUJOURS recalculés depuis les
   points actuels, jamais mémorisés indépendamment.
   ========================================================================== */

/** ACAL124 — miroir de `DIRECTIONS_MINIMALES` (services/horizon.py) : sous ce
 * nombre de directions DISTINCTES, la simulation refuse le profil. */
const DIRECTIONS_MINIMALES = 8
const MESSAGE_TOUR_INCOMPLET = 'Le calcul exige un tour complet : au moins 8 directions'

/** Le nombre de directions DISTINCTES (azimut ramené dans [0, 360[). */
function directionsDistinctes(points) {
  return new Set(sortedHorizonPoints(points).map((p) => p.azimuthDeg)).size
}

/** ACAL518 — l'azimut MANQUANT d'un tour : règle du serveur (`services/horizon.py`), un écart circulaire
 * > 2 × la médiane des écarts ; rend le milieu du plus grand écart, ou null (aucun pas codé). */
function azimutManquant(points) {
  const az = [...new Set(points.map((p) => p.azimuthDeg))].sort((a, b) => a - b)
  if (az.length < 3) return null
  const ecarts = az.map((a, i) => (az[(i + 1) % az.length] - a + 360) % 360 || 360)
  const mediane = [...ecarts].sort((a, b) => a - b)[Math.floor(ecarts.length / 2)]
  const pire = ecarts.indexOf(Math.max(...ecarts))
  return ecarts[pire] > 2 * mediane ? Math.round((az[pire] + ecarts[pire] / 2) % 360) : null
}

function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

export default function HorizonPanel({ calepinageId: idPropose, documentVivant = null } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  // ACAL24 — l'UNIQUE lecture du document (hook) : un échec donne `erreur`, jamais
  // un document vide sur lequel « Enregistrer » écraserait la conception.
  const doc = useDocumentCalepinage(calepinageId)
  const [points, setPoints] = useState([])
  const [source, setSource] = useState('saisie')
  const [releve, setReleve] = useState(null) // ACAL517 : provenance « relevé téléphone », effacée à toute modification
  const [saisie, setSaisie] = useState({ azimut: '', hauteur: '' })
  const [message, setMessage] = useState(null)
  const [recuperation, setRecuperation] = useState(false)
  const [fichier, setFichier] = useState(null) // { nom, texte }
  const [convention, setConvention] = useState(null) // ACAL458 : jamais présélectionnée
  const [telephone, setTelephone] = useState(false) // ACAL518 : capteurs démarrés
  const [precision, setPrecision] = useState('') // ACAL518 : précision de la boussole, DÉCLARÉE
  const chargement = doc.etat === 'chargement'
  const illisible = doc.etat === 'erreur'

  // Hydratation de la saisie : UNE fois par lecture serveur (jamais à une
  // application locale d'une section écrite).
  const [lectureHydratee, setLectureHydratee] = useState(null)
  if (doc.etat === 'ok' && lectureHydratee !== doc.generation) {
    setLectureHydratee(doc.generation)
    const profil = doc.document?.horizonProfile
    if (profil && Array.isArray(profil.points)) {
      setPoints(sortedHorizonPoints(profil.points))
      setSource(profil.source === 'pvgis' ? 'pvgis' : 'saisie')
      setReleve(profil.releve ?? null)
    }
  }

  // ACAL251 — latitude de l'épingle du document, sinon du repère servi (détail).
  const latitudeDeg = useLatitudeDuSite(calepinageId, doc.etat === 'ok' ? doc.document : null)
  const hauteurMaxDeg = horizonMaxHeightDeg(points)
  // ACAL254 — le MÊME compte que l'atelier : heures (mois × heure) de la matrice de
  // dérate réellement appliquée à la production, en heures — plus de pas de 0,5 h.
  const heuresMasquees = typeof latitudeDeg === 'number' ? maskedHourCount(hourlyHorizonFactors(latitudeDeg, points)) : 0
  const exploitable = sortedHorizonPoints(points).length >= 2
  // ACAL124 — un profil NON vide qui ne fait pas le tour ne s'enregistre pas
  // (vide = retirer le profil, toujours permis).
  const tourIncomplet = points.length > 0 && directionsDistinctes(points) < DIRECTIONS_MINIMALES

  function ajouterPoint() {
    const az = nombre(saisie.azimut)
    const h = nombre(saisie.hauteur)
    if (az === null || h === null) {
      setMessage('Azimut et hauteur doivent être des nombres — rien n’a été ajouté.')
      return
    }
    setPoints((prev) => sortedHorizonPoints([...prev, { azimuthDeg: az, heightDeg: h }]))
    setSaisie({ azimut: '', hauteur: '' })
    setSource('saisie') // toute saisie manuelle bascule la source (jamais mélangée à `pvgis`)
    setReleve(null)
    setMessage(null)
  }

  // ACAL518 — « Relever au téléphone » : une visée par toucher, précision de la boussole DÉCLARÉE.
  const capteursPresents = typeof window !== 'undefined' && typeof window.DeviceOrientationEvent !== 'undefined'
  async function ouvrirTelephone() {
    const depart = await demarrerCapteurs()
    if (depart.indisponible) { setMessage(depart.motif); return }
    setTelephone(true)
    setMessage(null)
  }
  function enregistrerVisee() {
    const precisionDeg = nombre(precision)
    const v = lireVisee()
    if (v.indisponible) { setMessage(v.motif); return }
    setPoints((prev) => sortedHorizonPoints([...prev, { azimuthDeg: v.azimutDeg, heightDeg: v.hauteurDeg }]))
    setSource('saisie')
    setReleve({ mode: 'telephone', date: todayLocalIso(), precisionDeg })
    setMessage(null)
  }

  function retirerPoint(index) {
    setPoints((prev) => sortedHorizonPoints(prev).filter((_, i) => i !== index))
    // ACAL124 — un profil PVGIS dont on retire un point est un profil CORRIGÉ.
    setSource('saisie')
    setReleve(null)
  }

  function recupererDepuisPvgis() {
    if (!calepinageId) return
    setRecuperation(true)
    setMessage(null)
    Promise.resolve(calepinageApi.calepinages.horizon(calepinageId))
      .then((res) => {
        const donnees = res?.data ?? {}
        const profil = Array.isArray(donnees.points) ? donnees.points : []
        if (!profil.length) {
          setMessage(donnees.detail || 'PVGIS n’a rendu aucun point d’horizon exploitable.')
          return
        }
        setPoints(sortedHorizonPoints(profil))
        setSource('pvgis')
        setReleve(null)
        setMessage(`Profil PVGIS récupéré (${profil.length} points) — à enregistrer pour l’appliquer.`)
      })
      .catch(() => setMessage('Le profil d’horizon n’a pas pu être récupéré depuis PVGIS.'))
      .finally(() => setRecuperation(false))
  }

  function choisirFichier(e) {
    const f = e.target.files?.[0]
    if (!f) { setFichier(null); return }
    const lecteur = new FileReader()
    lecteur.onload = () => setFichier({ nom: f.name, texte: String(lecteur.result ?? '') })
    lecteur.readAsText(f)
  }

  function importerFichier() {
    const r = lireFichierHorizon(fichier.texte, convention)
    if (r.erreur) { setMessage(`Import refusé — ${r.erreur}`); return }
    if (directionsDistinctes(r.points) < DIRECTIONS_MINIMALES) { setMessage(`Import refusé — ${MESSAGE_TOUR_INCOMPLET}.`); return }
    setPoints(sortedHorizonPoints(r.points))
    setSource('saisie')
    setReleve(null)
    const conv = r.format.startsWith('deux') ? `, ${convention === CONVENTION_NORD ? '0° = Nord, sens horaire' : '0° = Sud, + vers l’Ouest'}` : ''
    setMessage(`Fichier ${fichier.nom} importé (${r.format}${conv}) — à enregistrer pour l’appliquer.`)
  }

  async function enregistrer() {
    if (doc.etat !== 'ok' || tourIncomplet) return
    const propres = sortedHorizonPoints(points)
    // ACAL24 — UNE clé, par `layout/section/` ; `null` retire le profil.
    const valeur = propres.length >= 2
      ? { source, points: propres, hauteurMaxDeg: horizonMaxHeightDeg(propres), ...(releve ? { releve } : {}) }
      : null
    const res = await ecrireSection({
      calepinageId, cle: 'horizonProfile', valeur, empreinte: doc.empreinte, documentVivant,
    })
    if (res.ok) {
      doc.appliquerSection('horizonProfile', valeur, res.empreinte)
      setMessage(
        propres.length >= 2
          ? 'Profil d’horizon enregistré — la simulation affichée est périmée : relancez-la (Production › Lancer) pour l’appliquer.'
          : 'Profil retiré — aucun horizon n’est appliqué.',
      )
    } else if (res.conflit) {
      setMessage('La conception a changé ailleurs : elle est relue, enregistrez de nouveau.')
      doc.recharger()
    } else {
      setMessage(res.motif || 'Le profil d’horizon n’a pas pu être enregistré.')
    }
  }

  if (chargement) {
    return (
      <>
        <RetourAtelier calepinageId={calepinageId} />
        <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-horizon-loading">Chargement…</div>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-horizon">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Horizon lointain</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Le relief à distance (montagne, crête, immeuble éloigné) qui masque le soleil aux
        heures rasantes — un poste de perte SÉPARÉ de l’ombrage proche tracé sur le toit.
        Saisissez au moins 8 directions réparties sur tout le tour (azimut, hauteur
        angulaire) : le calcul exige un tour complet ; sans profil, rien ne change.
      </p>

      <div className="mt-3">
        <button
          type="button"
          onClick={recupererDepuisPvgis}
          disabled={recuperation || !calepinageId}
          className="min-h-11 rounded border border-border px-3 py-1.5 text-sm font-semibold text-foreground hover:bg-muted disabled:opacity-50"
        >
          {recuperation ? 'Récupération…' : 'Récupérer depuis PVGIS'}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-3" data-testid="cal-horizon-import">
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Fichier d’horizon (.txt, .csv)</span>
          <input type="file" accept=".txt,.csv,text/plain" onChange={choisirFichier} className="mt-1 block min-h-11 text-sm text-foreground" data-testid="cal-horizon-fichier" />
        </label>
        <label className="flex items-center gap-1 text-sm text-foreground">
          <input type="radio" name="cal-horizon-convention" checked={convention === CONVENTION_NORD} onChange={() => setConvention(CONVENTION_NORD)} />
          0° = Nord, sens horaire
        </label>
        <label className="flex items-center gap-1 text-sm text-foreground">
          <input type="radio" name="cal-horizon-convention" checked={convention === CONVENTION_SUD} onChange={() => setConvention(CONVENTION_SUD)} />
          0° = Sud, + vers l’Ouest
        </label>
        <button
          type="button"
          onClick={importerFichier}
          disabled={!fichier || (convention === null && nombreDeColonnes(fichier.texte) !== 1)}
          className="min-h-11 rounded border border-border px-3 py-1.5 text-sm font-semibold text-foreground hover:bg-muted disabled:opacity-50"
        >
          Importer
        </button>
      </div>

      <div className="mt-4">
        <SunDiagram
          latitudeDeg={latitudeDeg}
          horizonPoints={points}
          ariaLabel="Course du soleil et horizon lointain, par azimut"
          testId="cal-horizon-diagramme"
        />
        <LegendeCourbes libelleHorizon="Horizon saisi" />
        {latitudeDeg === null && (
          <p className="mt-1 text-xs text-amber-300">
            Latitude du site inconnue (aucun repère posé) — la course du soleil n’est pas tracée.
          </p>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hauteur maximale</span>
          <div className="fig text-foreground" data-testid="cal-horizon-hauteur-max">
            {hauteurMaxDeg === null ? '—' : `${hauteurMaxDeg.toFixed(1)}°`}
          </div>
        </div>
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Heures masquées (jour moyen de chaque mois, en heures)</span>
          <div className="fig text-foreground" data-testid="cal-horizon-heures-masquees">
            {exploitable ? heuresMasquees : '—'}
          </div>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Points du profil (azimut °, hauteur °)</p>
        <ul className="mt-2 flex flex-col gap-1" data-testid="cal-horizon-points">
          {sortedHorizonPoints(points).map((p, i) => (
            <li key={`${p.azimuthDeg}-${i}`} className="flex items-center gap-2 text-sm">
              <span className="fig">{p.azimuthDeg.toFixed(0)}°</span>
              <span className="fig">{p.heightDeg.toFixed(1)}°</span>
              <button
                type="button"
                onClick={() => retirerPoint(i)}
                className="text-xs text-red-300 underline"
                aria-label={`Retirer le point à ${p.azimuthDeg.toFixed(0)}°`}
              >
                Retirer
              </button>
            </li>
          ))}
          {!points.length && <li className="text-sm text-muted-foreground">Aucun point saisi.</li>}
        </ul>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="block" data-testid="cal-horizon-champ-azimut">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Azimut (°, 0=Nord)</span>
            <input
              type="number"
              step="any"
              value={saisie.azimut}
              onChange={(e) => setSaisie((s) => ({ ...s, azimut: e.target.value }))}
              className="mt-1 min-h-11 w-28 rounded border border-border bg-[var(--cal-surface)] px-2 py-1 text-sm text-foreground"
            />
          </label>
          <label className="block" data-testid="cal-horizon-champ-hauteur">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hauteur angulaire (°)</span>
            <input
              type="number"
              step="any"
              value={saisie.hauteur}
              onChange={(e) => setSaisie((s) => ({ ...s, hauteur: e.target.value }))}
              className="mt-1 min-h-11 w-28 rounded border border-border bg-[var(--cal-surface)] px-2 py-1 text-sm text-foreground"
            />
          </label>
          <button
            type="button"
            onClick={ajouterPoint}
            className="min-h-11 rounded border border-border px-3 py-1.5 text-sm font-semibold text-foreground hover:bg-muted"
          >
            Ajouter le point
          </button>
        </div>
      </div>

      {capteursPresents && (
        <details className="mt-4" data-testid="horizon-tel">
          <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-foreground">Relever au téléphone</summary>
          {!telephone && (
            <button type="button" onClick={ouvrirTelephone} data-testid="horizon-tel-demarrer"
              className="min-h-11 rounded border border-border px-3 text-sm font-semibold text-foreground">
              Démarrer les capteurs
            </button>
          )}
          {telephone && (
            <div className="mt-2" data-testid="horizon-tel-visees">
              <label className="block text-sm text-foreground">
                Précision de la boussole (°)
                <input type="number" step="any" min="0" value={precision} onChange={(e) => setPrecision(e.target.value)}
                  data-testid="horizon-tel-precision"
                  className="mt-1 block min-h-11 w-28 rounded border border-border bg-transparent px-2 text-sm text-foreground" />
              </label>
              <p className="mt-2 text-sm text-muted-foreground" data-testid="horizon-tel-compte">
                Visée {directionsDistinctes(points)} sur {DIRECTIONS_MINIMALES} minimum
                {azimutManquant(points) !== null ? ` · il manque une visée vers ${azimutManquant(points)}°` : ''}
              </p>
              <button type="button" onClick={enregistrerVisee} disabled={!(nombre(precision) > 0)} data-testid="horizon-tel-viser"
                className="mt-2 min-h-11 rounded border border-border px-3 text-sm font-semibold text-foreground disabled:opacity-50">
                Enregistrer cette visée
              </button>
              {!(nombre(precision) > 0) && (
                <p className="mt-1 text-sm text-muted-foreground" data-testid="horizon-tel-sans-precision">
                  Déclarez la précision de la boussole pour viser.
                </p>
              )}
            </div>
          )}
        </details>
      )}

      {/* ACAL1815 — le message passe SOUS le bouton (pleine largeur) : sur la même rangée, il l'écrasait au téléphone. */}
      <div className="mt-4 flex flex-col items-start gap-2" data-testid="cal-horizon-enregistrer-rangee">
        <button
          type="button"
          onClick={enregistrer}
          disabled={doc.etat !== 'ok' || tourIncomplet}
          className="min-h-11 rounded border border-brass-400/60 px-4 py-2 text-sm font-semibold text-primary-text hover:bg-brass-400/10 disabled:opacity-50"
        >
          Enregistrer le profil
        </button>
        {tourIncomplet && !illisible && (
          <p className="text-sm text-amber-300">
            {MESSAGE_TOUR_INCOMPLET} ({directionsDistinctes(points)} relevée(s)).
          </p>
        )}
        {illisible && (
          <p className="text-sm text-red-300" role="alert">
            {MESSAGE_ILLISIBLE}
          </p>
        )}
        {message && <p className="w-full text-sm text-muted-foreground" role="status">{message}</p>}
      </div>
    </div>
    </>
  )
}
