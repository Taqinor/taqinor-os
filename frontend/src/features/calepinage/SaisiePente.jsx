/* eslint-disable react-refresh/only-export-components --
   Les conversions de pente sont des fonctions PURES (trigonométrie, zéro
   React) : la tâche exige que les TROIS modes soient confrontés à 0,1° près
   sur un cas de test, ce qui suppose de les appeler sans monter l'écran. Même
   dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import useDocumentCalepinage from './useDocumentCalepinage'
import RetourAtelier from './atelier/RetourAtelier'
import { RAISON_LECTURE_SEULE, lireConflit } from './conflitEcriture'

/* ============================================================================
   CAL58 — LA PENTE : en degrés, en pourcentage, OU PAR COTES.
   ----------------------------------------------------------------------------
   Constat : la pente ne s'entre aujourd'hui qu'en DEGRÉS (puces ~15/22/30/45°
   + curseur fin 5-45°, `pages/ventes/ToitureDesign.jsx`). Sur un chantier, la
   pente se lit pourtant aussi en POURCENTAGE (la convention des couvreurs et
   des plans) et se MESURE au mètre : portée et hauteur de faîtage. Trois
   chemins, une seule grandeur.

   LA VALEUR RETENUE DIT TOUJOURS D'OÙ ELLE VIENT (`source` : `degres`,
   `pourcentage`, `cotes`) — sans quoi personne ne peut savoir si la pente
   affichée a été mesurée ou estimée à l'œil.

   RÈGLE FONDATEUR — JAMAIS DE SNAP, JAMAIS DE REFUS. Aucun `min`/`max`, aucun
   `step` autre que `any`, aucun arrondi : la valeur STOCKÉE est la pente
   exacte issue de la conversion, et seul l'AFFICHAGE est arrondi au dixième.
   Une saisie hors des puces historiques (2°, 62,4°) est acceptée telle quelle.

   ZÉRO CHIFFRE INVENTÉ : une saisie absente ou inexploitable (portée nulle)
   rend `null` — jamais 0°, qui se lirait « toiture plate » alors que rien n'a
   été mesuré.
   ========================================================================== */

const DEG = 180 / Math.PI

function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/** CAL58 — pente en degrés, telle quelle (aucun arrondi, aucune borne). */
export function penteDepuisDegres(degres) {
  return nombre(degres)
}

/**
 * CAL58 — pente en degrés depuis un POURCENTAGE de pente (hauteur/portée).
 * 100 % = 45°, 57,735 % = 30°. Un pourcentage négatif est accepté tel quel
 * (un plan peut décrire une contre-pente) : on ne refuse pas une saisie.
 */
export function penteDepuisPourcentage(pourcentage) {
  const p = nombre(pourcentage)
  if (p === null) return null
  return Math.atan(p / 100) * DEG
}

/**
 * CAL58 — pente en degrés depuis les COTES mesurées : portée (l'horizontale)
 * et hauteur de faîtage (la verticale). Portée nulle ou absente ⇒ `null` :
 * une division par zéro ne produit pas une pente, elle produit un mensonge.
 */
export function penteDepuisCotes(porteeM, hauteurFaitageM) {
  const portee = nombre(porteeM)
  const hauteur = nombre(hauteurFaitageM)
  if (portee === null || hauteur === null || portee === 0) return null
  return Math.atan(hauteur / portee) * DEG
}

/** CAL58 — la réciproque, pour afficher la pente retenue en pourcentage. */
export function pourcentageDepuisPente(degres) {
  const d = nombre(degres)
  if (d === null) return null
  return Math.tan(d / DEG) * 100
}

/**
 * CAL58 — LA VALEUR RETENUE et SA PROVENANCE, depuis la saisie des trois
 * modes. Le mode ACTIF tranche : deux modes remplis ne se moyennent pas (une
 * moyenne serait un quatrième chiffre que personne n'a mesuré).
 */
export function penteRetenue(mode, saisie = {}) {
  if (mode === 'pourcentage') {
    const degres = penteDepuisPourcentage(saisie.pourcentage)
    return degres === null ? null : { degres, source: 'pourcentage' }
  }
  if (mode === 'cotes') {
    const degres = penteDepuisCotes(saisie.porteeM, saisie.hauteurFaitageM)
    return degres === null ? null : { degres, source: 'cotes' }
  }
  const degres = penteDepuisDegres(saisie.degres)
  return degres === null ? null : { degres, source: 'degres' }
}

const LIBELLE_SOURCE = {
  degres: 'saisie en degrés',
  pourcentage: 'convertie depuis un pourcentage de pente',
  cotes: 'mesurée aux cotes (portée et hauteur de faîtage)',
}

/** Affichage au dixième — l'AFFICHAGE seulement : la valeur reste exacte. */
function auDixieme(valeur) {
  return valeur === null || valeur === undefined ? '—' : valeur.toFixed(1)
}

function Champ({ cle, label, valeur, onChange }) {
  return (
    <label className="block" data-testid={`cal-pente-champ-${cle}`}>
      <span className="tech-label text-lune-faint">{label}</span>
      <input
        type="number"
        /* Règle fondateur : aucune borne, aucun pas — jamais de snap. */
        step="any"
        id={`cal-pente-${cle}`}
        value={valeur ?? ''}
        onChange={(e) => onChange(cle, e.target.value)}
        className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      />
    </label>
  )
}

/* ACAL252 — la pente est celle d'UN PAN (`zones[i].pitchDeg` + `pitchSource`), jamais une
   clé racine du document. `pitchSource` dit d'où elle vient (schéma `pitchSource`) : le mode
   et SES champs ; `provenance: 'visite'` s'y ajoute quand la valeur vient de la visite. */
export function zonesDuDocument(document) {
  return (Array.isArray(document?.zones) ? document.zones : [])
    .filter((z) => z && z.id !== undefined && z.id !== null)
}

/** Le pan proposé par défaut : le pan ACTIF de l'atelier, sinon le premier. */
export function panParDefaut(document) {
  const zones = zonesDuDocument(document)
  const actif = zones.find((z) => String(z.id) === String(document?.activeAreaId))
  return String((actif ?? zones[0])?.id ?? '')
}

const texte = (v) => (v === null || v === undefined ? '' : String(v))

/** La saisie (mode + champs) qui reproduit ce que le pan a enregistré. */
export function saisieDuPan(zone) {
  const vide = { degres: '', pourcentage: '', porteeM: '', hauteurFaitageM: '' }
  const source = zone?.pitchSource
  const deg = zone?.pitchDeg
  if (source && typeof source === 'object') {
    const mode = source.mode === 'pourcentage' || source.mode === 'cotes' ? source.mode : 'degres'
    return {
      mode,
      saisie: {
        degres: texte(source.degres ?? (mode === 'degres' ? deg : null)),
        pourcentage: texte(source.pourcentage),
        porteeM: texte(source.porteeM),
        hauteurFaitageM: texte(source.hauteurFaitageM),
      },
    }
  }
  if (typeof deg === 'number' && Number.isFinite(deg)) {
    return { mode: 'degres', saisie: { ...vide, degres: String(deg) } }
  }
  return { mode: 'degres', saisie: vide }
}

/** `pitchSource` à écrire : le mode retenu et ses SEULS champs (valeurs exactes). */
export function sourceDePente(retenue, saisie, deVisite = false) {
  const n = (v) => nombre(v)
  let source
  if (retenue.source === 'pourcentage') {
    source = { mode: 'pourcentage', pourcentage: n(saisie.pourcentage) }
  } else if (retenue.source === 'cotes') {
    source = {
      mode: 'cotes', porteeM: n(saisie.porteeM), hauteurFaitageM: n(saisie.hauteurFaitageM),
    }
  } else {
    source = { mode: 'degres', degres: retenue.degres }
  }
  return deVisite && source.mode === 'degres' ? { ...source, provenance: 'visite' } : source
}

/* ACAL208 — l'orientation d'une visite est un CHOIX de la rose des vents ; son azimut
   boussole est le centre du secteur, sa précision la demi-largeur du secteur (22,5°).
   Proposition affichée, jamais appliquée d'office (D7). */
const ROSE = {
  nord: ['nord', 0], nord_est: ['nord-est', 45], est: ['est', 90], sud_est: ['sud-est', 135],
  sud: ['sud', 180], sud_ouest: ['sud-ouest', 225], ouest: ['ouest', 270],
  nord_ouest: ['nord-ouest', 315],
}
const PRECISION_SECTEUR_DEG = 22.5

/** Les mesures de la visite reprise utiles à l'onglet : pente et orientation (ou `null`). */
export function mesuresDeVisite(etat) {
  const mesures = Array.isArray(etat?.mesures) ? etat.mesures : []
  const trouver = (code) => mesures.find((m) => m?.code === code)?.valeur
  const pente = nombre(trouver('pente_deg'))
  const choix = ROSE[trouver('orientation')]
  return {
    penteDeg: pente,
    orientation: choix
      ? { libelle: choix[0], azimutDeg: choix[1], precisionDeg: PRECISION_SECTEUR_DEG }
      : null,
  }
}

const MODES = [
  ['degres', 'En degrés'],
  ['pourcentage', 'En pourcentage'],
  ['cotes', 'Aux cotes'],
]

/**
 * ACAL66 — les suggestions de pente IGN EN ATTENTE du document : un pan dont
 * `pitchSuggestion.status` vaut `suggeree`. Lecture PURE du document (la
 * suggestion y est persistée par `POST suggestions-pente/`, ACAL65) : rouvrir
 * l'onglet retrouve la même liste.
 */
export function suggestionsEnAttente(document) {
  const zones = Array.isArray(document?.zones) ? document.zones : []
  return zones
    .filter((z) => z?.pitchSuggestion?.status === 'suggeree')
    .map((z) => ({
      zoneId: String(z.id ?? ''),
      valeurDeg: z.pitchSuggestion.valeurDeg ?? null,
      source: z.pitchSuggestion.source ?? '',
      suggestedAt: z.pitchSuggestion.suggestedAt ?? '',
    }))
}

export default function SaisiePente({
  calepinageId: idPropose, onChange = null, persister = true, documentVivant = null,
  lectureSeule = false,
}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [mode, setMode] = useState('degres')
  const [saisie, setSaisie] = useState({
    degres: '', pourcentage: '', porteeM: '', hauteurFaitageM: '',
  })
  // ACAL24 — l'UNIQUE lecture du document (hook) : un échec donne `erreur`, jamais
  // un document vide. ACAL252 — la pente est celle du PAN choisi : elle s'écrit par la
  // primitive d'écriture par section (`layout/section/`, C-ACAL-044), jamais par le
  // remplacement du document. La DÉCISION sur une suggestion IGN passe, elle, par le
  // serveur (`suggestions-pente/`, ACAL65/ACAL66).
  const doc = useDocumentCalepinage(calepinageId, { actif: persister })
  const layout = doc.document
  const [message, setMessage] = useState(null)
  const [zoneChoisie, setZoneChoisie] = useState('')
  // ACAL208 — la visite reprise (lecture seule) et ce que l'utilisateur en a retenu.
  const [visite, setVisite] = useState(null)
  const [deVisite, setDeVisite] = useState(false)
  const [orientationRetenue, setOrientationRetenue] = useState(false)

  /* CALX29 — Suggestion de pente LiDAR IGN, FRANCE SEULEMENT.
     `disponible` vient d'une LECTURE LOCALE (`GET .../suggestion-pente/`,
     aucune requête sortante même quand le service est offert) : c'est elle,
     et elle seule, qui commande l'affichage du bouton. */
  const [ignDisponible, setIgnDisponible] = useState(false)
  const [chargementSuggestions, setChargementSuggestions] = useState(false)
  const [messageSuggestions, setMessageSuggestions] = useState(null)

  // RELECTURE : la pente DU PAN choisi, relue dans le document (une fois par lecture
  // serveur et par pan).
  const zones = zonesDuDocument(layout)
  const zoneId = zones.some((z) => String(z.id) === zoneChoisie)
    ? zoneChoisie : panParDefaut(layout)
  const zone = zones.find((z) => String(z.id) === zoneId) ?? null
  const [lectureHydratee, setLectureHydratee] = useState(null)
  const cleHydratation = `${doc.generation}|${zoneId}`
  if (persister && doc.etat === 'ok' && lectureHydratee !== cleHydratation) {
    setLectureHydratee(cleHydratation)
    const relu = saisieDuPan(zone)
    setMode(relu.mode)
    setSaisie(relu.saisie)
    setDeVisite(false)
    setOrientationRetenue(false)
  }

  // ACAL208 — les mesures de la visite validée, proposées (jamais appliquées d'office).
  useEffect(() => {
    if (!persister || !calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.releveVisite?.(calepinageId))
      .then((res) => { if (!annule) setVisite(mesuresDeVisite(res?.data)) })
      .catch(() => { if (!annule) setVisite(null) })
    return () => { annule = true }
  }, [calepinageId, persister])

  // CALX29 — la lecture locale qui décide si le bouton existe. Société hors
  // France ⇒ `disponible: false` ⇒ pas de bouton, pas d'appel de suggestion.
  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres?.suggestionPenteDisponible?.())
      .then((res) => { if (!annule) setIgnDisponible(res?.data?.disponible === true) })
      .catch(() => { if (!annule) setIgnDisponible(false) })
    return () => { annule = true }
  }, [])

  // ACAL66 — la suggestion et sa décision (proposer / accepter / refuser) sont des
  // actes SERVEUR : `POST suggestions-pente/` avec le jeton d'écriture, le
  // document rendu est poussé dans l'atelier vivant. Jamais d'écriture locale
  // `{...layout, zones}` : la suggestion est la pente du TERRAIN, elle n'est
  // JAMAIS recopiée dans la pente du pan (D-ACAL-19).
  const suggestions = suggestionsEnAttente(layout)

  const decider = async (operation, zoneId = undefined) => {
    if (doc.etat !== 'ok' || lectureSeule) return null
    const base = documentVivant?.empreinte || doc.empreinte
    if (!base) {
      setMessageSuggestions('Conception illisible : rien n’est enregistré.')
      return null
    }
    try {
      const res = await calepinageApi.calepinages.decisionSuggestionPente(calepinageId, {
        operation, base_empreinte: base, ...(zoneId ? { zone_id: zoneId } : {}),
      })
      const zones = res?.data?.roof_layout?.zones
      const empreinte = res?.data?.empreinte_document ?? null
      if (Array.isArray(zones)) {
        doc.appliquerSection('zones', zones, empreinte)
        // L'atelier vivant reprend le jeton rendu (sa scène n'est pas touchée :
        // la suggestion ne change ni la pente ni la production).
        documentVivant?.appliquerSection?.('zones', zones, empreinte)
      }
      return res?.data ?? {}
    } catch (e) {
      const statut = e?.response?.status
      const donnees = e?.response?.data
      // Lot 2 critique #32 — jeton périmé (relu) ≠ verrou (motif serveur).
      const conflit = lireConflit(e)
      if (conflit?.documentModifie) {
        setMessageSuggestions('La conception a changé ailleurs : elle est relue, recommencez.')
        doc.recharger()
      } else if (conflit) {
        setMessageSuggestions(conflit.motif)
      } else if (statut === 403) {
        setMessageSuggestions(donnees?.pays || donnees?.detail
          || 'La suggestion IGN n’est pas offerte pour cette société.')
      } else {
        setMessageSuggestions(operation === 'proposer'
          ? 'La suggestion IGN n’a pas pu être obtenue.'
          : 'La décision sur la suggestion n’a pas pu être enregistrée.')
      }
      return null
    }
  }

  const suggererDepuisIGN = async () => {
    if (doc.etat !== 'ok') return
    setChargementSuggestions(true)
    setMessageSuggestions(null)
    const rendu = await decider('proposer')
    setChargementSuggestions(false)
    if (rendu && !suggestionsEnAttente(rendu.roof_layout).length) {
      setMessageSuggestions('Aucun pan ne porte assez de points d’altitude exploitables : '
        + 'aucune pente n’est suggérée (ou chaque pan a déjà une décision).')
    }
  }

  const jeterSuggestion = async (suggestion) => {
    // Le relevé paraît faux, ou le dessinateur préfère sa saisie : le refus est
    // PERSISTÉ (`refusee`), la pente saisie reste la SEULE vérité.
    const rendu = await decider('refuser', suggestion.zoneId)
    if (rendu) setMessageSuggestions('Suggestion jetée : la pente du pan est inchangée.')
  }

  const accepterSuggestion = async (suggestion) => {
    const rendu = await decider('accepter', suggestion.zoneId)
    if (rendu) {
      setMessageSuggestions(
        `Suggestion validée (${suggestion.source}) : pente du terrain, la pente du pan n’est pas modifiée.`,
      )
    }
  }

  const majChamp = (cle, brut) => {
    const suivante = { ...saisie, [cle]: brut }
    setSaisie(suivante)
    setDeVisite(false)
    if (onChange) onChange(penteRetenue(mode, suivante))
  }

  const changerMode = (suivant) => {
    setMode(suivant)
    setDeVisite(false)
    if (onChange) onChange(penteRetenue(suivant, saisie))
  }

  const retenue = penteRetenue(mode, saisie)

  // ACAL208 — « Utiliser » : la mesure de la visite REMPLIT la saisie du pan choisi ; rien
  // n'est enregistré avant « Enregistrer la pente ».
  const utiliserPenteVisite = () => {
    if (visite?.penteDeg === null || visite?.penteDeg === undefined) return
    setMode('degres')
    const suivante = { ...saisie, degres: String(visite.penteDeg) }
    setSaisie(suivante)
    setDeVisite(true)
    if (onChange) onChange(penteRetenue('degres', suivante))
  }

  const enregistrer = async () => {
    if (lectureSeule) return // Lot 2 critique #32
    if (doc.etat !== 'ok') {
      setMessage('Conception illisible : rien n’est enregistré.')
      return
    }
    if (!zone) {
      setMessage('Aucun pan dans la conception : dessinez un pan avant d’enregistrer sa pente.')
      return
    }
    if (!retenue) {
      setMessage('Aucune pente n’est encore mesurée : rien n’est enregistré, '
        + 'et surtout pas un 0° qui se lirait « toiture plate ».')
      return
    }
    const champs = {
      // La valeur EXACTE, jamais l'arrondi d'affichage.
      pitchDeg: retenue.degres,
      pitchSource: sourceDePente(retenue, saisie, deVisite),
    }
    if (orientationRetenue && visite?.orientation) {
      champs.facingAzimuthDeg = visite.orientation.azimutDeg
      champs.facingAzimuthSource = 'visite'
      champs.facingAzimuthPrecisionDeg = visite.orientation.precisionDeg
    }
    // ACAL316 — le jeton de l'atelier vivant s'il existe, sinon celui de la lecture : un
    // document changé ailleurs répond 409 plutôt que d'être écrasé.
    const base = documentVivant?.empreinte || doc.empreinte
    try {
      const res = await calepinageApi.calepinages.enregistrerSectionLayout(calepinageId, {
        cle: 'zones', zone_id: zone.id, champs, base_empreinte: base,
      })
      const apres = res?.data?.empreinte_document ?? null
      const rendues = res?.data?.roof_layout?.zones
      const mises = Array.isArray(rendues) ? rendues : zones.map((z) => (
        String(z.id) === String(zone.id) ? { ...z, ...champs } : z))
      doc.appliquerSection('zones', mises, apres)
      documentVivant?.appliquerSection?.('zones', mises, apres)
      setOrientationRetenue(false)
      setMessage(`Pente enregistrée sur le pan « ${zone.label || zone.id} ».`)
    } catch (e) {
      // Lot 2 critique #32 — jeton périmé (relu) ≠ verrou (motif serveur).
      const conflit = lireConflit(e)
      if (conflit?.documentModifie) {
        setMessage('La conception a changé ailleurs : elle est relue, recommencez.')
        doc.recharger()
      } else if (conflit) {
        setMessage(conflit.motif)
      } else {
        setMessage('La pente n’a pas pu être enregistrée.')
      }
    }
  }

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="cine-card mt-6 p-6" data-testid="cal-pente">
      <p className="tech-label rule-brass text-brass-300">Pente de la toiture</p>

      {persister && zones.length > 0 && (
        <label className="mt-3 block text-sm text-lune-soft">
          Pan
          <select value={zoneId} data-testid="cal-pente-pan"
            onChange={(e) => setZoneChoisie(e.target.value)}
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white">
            {zones.map((z) => (
              <option key={z.id} value={String(z.id)}>{z.label || z.id}</option>
            ))}
          </select>
        </label>
      )}

      {/* ACAL208 — les mesures de la VISITE, proposées : « Utiliser » remplit la saisie du
          pan choisi, jamais d'application d'office (D7). */}
      {persister && visite?.penteDeg !== null && visite?.penteDeg !== undefined && (
        <div className="mt-3 flex flex-wrap items-center gap-3" data-testid="cal-pente-visite">
          <span className="text-sm text-lune-soft" data-testid="cal-pente-visite-mesure">
            {`Mesure de la visite : ${visite.penteDeg}°`}
          </span>
          <button type="button" onClick={utiliserPenteVisite}
            data-testid="cal-pente-visite-utiliser"
            className="rounded border border-brass-400/60 px-3 py-1 text-xs text-brass-200">
            Utiliser
          </button>
        </div>
      )}
      {persister && visite?.orientation && (
        <div className="mt-2 flex flex-wrap items-center gap-3" data-testid="cal-pente-visite-orientation">
          <span className="text-sm text-lune-soft" data-testid="cal-pente-visite-orientation-mesure">
            {`Orientation de la visite : ${visite.orientation.libelle}, ${visite.orientation.azimutDeg}° boussole, précision ${String(visite.orientation.precisionDeg).replace('.', ',')}°`}
          </span>
          <button type="button" onClick={() => setOrientationRetenue(true)}
            disabled={orientationRetenue}
            data-testid="cal-pente-visite-orientation-utiliser"
            className="rounded border border-brass-400/60 px-3 py-1 text-xs text-brass-200 disabled:opacity-50">
            {orientationRetenue ? 'Orientation retenue (à enregistrer)' : 'Utiliser l’orientation'}
          </button>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2" role="radiogroup"
        aria-label="Mode de saisie de la pente">
        {MODES.map(([cle, label]) => (
          <button
            key={cle}
            type="button"
            role="radio"
            aria-checked={mode === cle}
            data-testid={`cal-pente-mode-${cle}`}
            onClick={() => changerMode(cle)}
            className={`rounded px-3 py-1 text-sm ${mode === cle
              ? 'bg-brass-500/20 text-brass-200' : 'text-lune-soft'}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {mode === 'degres' && (
          <Champ cle="degres" label="Pente (°)" valeur={saisie.degres}
            onChange={majChamp} />
        )}
        {mode === 'pourcentage' && (
          <Champ cle="pourcentage" label="Pente (%)" valeur={saisie.pourcentage}
            onChange={majChamp} />
        )}
        {mode === 'cotes' && (
          <>
            <Champ cle="porteeM" label="Portée (m)" valeur={saisie.porteeM}
              onChange={majChamp} />
            <Champ cle="hauteurFaitageM" label="Hauteur de faîtage (m)"
              valeur={saisie.hauteurFaitageM} onChange={majChamp} />
          </>
        )}
      </div>

      {/* LA VALEUR RETENUE ET SA PROVENANCE, toujours affichées ensemble. */}
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        <div data-testid="cal-pente-valeur">
          <dd className="fig text-lg text-white">
            {retenue ? `${auDixieme(retenue.degres)} °` : '—'}
          </dd>
          <dt className="tech-label text-lune-faint">Pente retenue</dt>
        </div>
        <div data-testid="cal-pente-source">
          <dd className="text-sm text-white">
            {retenue ? LIBELLE_SOURCE[retenue.source] : 'aucune pente mesurée'}
          </dd>
          <dt className="tech-label text-lune-faint">D’où elle vient</dt>
        </div>
        <div data-testid="cal-pente-equivalent">
          <dd className="fig text-lg text-white">
            {retenue ? `${auDixieme(pourcentageDepuisPente(retenue.degres))} %` : '—'}
          </dd>
          <dt className="tech-label text-lune-faint">Soit, en pourcentage</dt>
        </div>
      </dl>

      {persister && lectureSeule && (
        <p className="mt-4 text-xs text-lune-faint" data-testid="cal-pente-lecture-seule">
          {RAISON_LECTURE_SEULE}
        </p>
      )}
      {persister && (
        <button type="button" onClick={enregistrer} disabled={lectureSeule}
          data-testid="cal-pente-enregistrer"
          className="mt-4 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200 disabled:opacity-50">
          Enregistrer la pente
        </button>
      )}
      {message && (
        <p className="mt-3 text-sm text-lune-soft" role="status"
          data-testid="cal-pente-message">{message}</p>
      )}

      {/* CALX29 — suggestion LiDAR IGN, visible SEULEMENT si la lecture
          locale dit `disponible: true` (France). */}
      {ignDisponible && (
        <div className="mt-6 border-t border-white/10 pt-4" data-testid="cal-pente-lidar">
          <p className="tech-label text-lune-faint">Pente par pan, depuis l’IGN</p>
          <button type="button" onClick={suggererDepuisIGN}
            disabled={chargementSuggestions || lectureSeule}
            data-testid="cal-pente-lidar-suggerer"
            className="mt-2 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200">
            {chargementSuggestions ? 'Interrogation de l’IGN…' : 'Suggérer depuis l’IGN'}
          </button>

          {suggestions.length > 0 && (
            <>
              <p className="mt-3 text-xs text-lune-soft" data-testid="cal-pente-lidar-mention">
                Les obstacles posés sur la toiture ne sont pas dans cette donnée
                d’élévation : ils restent à saisir à la main.
              </p>
              <ul className="mt-2 space-y-2">
                {suggestions.map((suggestion) => (
                  <li key={suggestion.zoneId}
                    data-testid={`cal-pente-lidar-suggestion-${suggestion.zoneId}`}
                    className="rounded border border-white/10 p-3 text-sm text-white">
                    <p>
                      Pan {suggestion.zoneId} — {auDixieme(suggestion.valeurDeg)} °
                    </p>
                    <p className="text-xs text-lune-soft">
                      Pente du terrain (LiDAR IGN) — n’est jamais recopiée dans la pente du pan.
                    </p>
                    <p className="text-xs text-lune-faint" data-testid={`cal-pente-lidar-source-${suggestion.zoneId}`}>
                      {suggestion.source} · {suggestion.suggestedAt}
                    </p>
                    <div className="mt-2 flex gap-2">
                      <button type="button" onClick={() => accepterSuggestion(suggestion)}
                        disabled={lectureSeule}
                        data-testid={`cal-pente-lidar-accepter-${suggestion.zoneId}`}
                        className="rounded bg-brass-500/20 px-3 py-1 text-xs font-semibold text-brass-200">
                        Accepter
                      </button>
                      <button type="button" onClick={() => jeterSuggestion(suggestion)}
                        disabled={lectureSeule}
                        data-testid={`cal-pente-lidar-jeter-${suggestion.zoneId}`}
                        className="rounded px-3 py-1 text-xs text-lune-soft">
                        Jeter
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          {messageSuggestions && (
            <p className="mt-3 text-sm text-lune-soft" role="status"
              data-testid="cal-pente-lidar-message">{messageSuggestions}</p>
          )}
        </div>
      )}
    </div>
    </>
  )
}
