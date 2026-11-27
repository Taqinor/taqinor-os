import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import useDocumentCalepinage from './useDocumentCalepinage'
import RetourAtelier from './atelier/RetourAtelier'
import { RAISON_LECTURE_SEULE, lireConflit } from './conflitEcriture'
import { messageRefus } from './commun/refusServeur'
import { demarrerCapteurs, lireInclinaison, lireVisee, arreter as arreterCapteurs } from './capteursTelephone'
import { enregistrerPentePan } from './atelier/coque/etapes/EtapeToit.helpers'
import { mesuresDeVisite, panParDefaut, penteRetenue, pourcentageDepuisPente, saisieDuPan, sourceDePente, suggestionsEnAttente, zonesDuDocument } from './SaisiePente.helpers'

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

// ACAL535 — la source d'une suggestion lue sur le relief déposé (celle du serveur,
// contrat calepinage_suggestion_pente.json › relief › source).
const SOURCE_RELIEF = "relief fourni par l'installateur"

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
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <input
        type="number"
        /* Règle fondateur : aucune borne, aucun pas — jamais de snap. */
        step="any"
        id={`cal-pente-${cle}`}
        value={valeur ?? ''}
        onChange={(e) => onChange(cle, e.target.value)}
        className="mt-1 w-full rounded border border-border bg-[var(--cal-surface)] px-2 py-1 text-sm text-foreground"
      />
    </label>
  )
}

const MODES = [
  ['degres', 'En degrés'],
  ['pourcentage', 'En pourcentage'],
  ['cotes', 'Aux cotes'],
]

export default function SaisiePente({
  calepinageId: idPropose, onChange = null, persister = true, documentVivant = null,
  lectureSeule = false,
  zoneInitiale = '', // maquette Main — le pan ACTIF de l'atelier quand l'étape Toit ouvre ce formulaire (« Modifier »)
  onEnregistre = null, // appelé après une pente enregistrée (la carte de l'étape Toit relit son document)
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
  const [zoneChoisie, setZoneChoisie] = useState(String(zoneInitiale ?? ''))
  // ACAL208 — la visite reprise (lecture seule) et ce que l'utilisateur en a retenu.
  const [visite, setVisite] = useState(null)
  const [deVisite, setDeVisite] = useState(false)
  const [orientationRetenue, setOrientationRetenue] = useState(false)
  // ACAL519 — mesure au téléphone : proposition « à confirmer », précision de boussole DÉCLARÉE.
  const [capteurOuvert, setCapteurOuvert] = useState(false)
  const [mesureTel, setMesureTel] = useState(null)
  const [precisionTel, setPrecisionTel] = useState('')
  const [refusTel, setRefusTel] = useState(null)

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
  // ACAL1341 — un pan « Toit plat » n'a pas de pente à écrire : ni enregistrement ni mesure au téléphone.
  const plat = persister && zone?.roofType === 'flat'
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

  const decider = async (operation, zoneId = undefined, relief = null) => {
    if (doc.etat !== 'ok' || lectureSeule) return null
    const base = documentVivant?.empreinte || doc.empreinte
    if (!base) {
      setMessageSuggestions('Conception illisible : rien n’est enregistré.')
      return null
    }
    try {
      // ACAL535 — un relief déposé (GeoTIFF) passe par sa propre porte serveur : même réponse.
      let corps = { operation, base_empreinte: base, ...(zoneId ? { zone_id: zoneId } : {}) }
      if (relief) {
        corps = new FormData()
        corps.append('relief', relief)
        corps.append('base_empreinte', base)
      }
      const res = await (relief
        ? calepinageApi.calepinages.suggestionPenteRelief(calepinageId, corps)
        : calepinageApi.calepinages.decisionSuggestionPente(calepinageId, corps))
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
        // ACAL280 — le motif serveur (400 : son champ) avant tout repli.
        setMessageSuggestions(messageRefus(e, operation === 'proposer'
          ? 'La suggestion IGN n’a pas pu être obtenue.'
          : 'La décision sur la suggestion n’a pas pu être enregistrée.'))
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

  // ACAL535 — « Lire la pente sur un relief de drone » : le fichier est lu par le serveur
  // (aucun appel IGN) ; chaque pan couvert reçoit une suggestion à décider ci-dessous.
  const deposerRelief = async (evenement) => {
    const fichier = evenement.target.files?.[0]
    evenement.target.value = ''
    if (!fichier) return
    setMessageSuggestions(null)
    const rendu = await decider('proposer', undefined, fichier)
    if (rendu) setMessageSuggestions('Pente lue sur votre relief : décidez ci-dessous, rien n’est appliqué d’office.')
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
    const rendu = await enregistrerPentePan({ calepinageId, doc, documentVivant, zone, zones, champs })
    if (rendu.ok) {
      setOrientationRetenue(false)
      onEnregistre?.()
    }
    setMessage(rendu.message)
  }

  const capteursPresents = typeof window !== 'undefined' && typeof window.DeviceOrientationEvent !== 'undefined'
  const ouvrirTelephone = async () => {
    const depart = await demarrerCapteurs()
    if (depart.indisponible) { setRefusTel({ champ: 'capteur', motif: depart.motif }); return }
    setRefusTel(null)
    setCapteurOuvert(true)
  }
  const prendreMesureTel = () => {
    const inc = lireInclinaison()
    const visee = lireVisee()
    if (inc.indisponible || visee.indisponible) {
      setRefusTel({ champ: 'capteur', motif: inc.motif || visee.motif })
      return
    }
    const c = Math.cos(inc.betaDeg * Math.PI / 180) * Math.cos(inc.gammaDeg * Math.PI / 180)
    setRefusTel(null)
    setMesureTel({
      penteDeg: Math.acos(Math.max(-1, Math.min(1, c))) * 180 / Math.PI,
      azimutDeg: (visee.azimutDeg + 180) % 360, // le haut du téléphone vise le faîte : le pan regarde à l'opposé
    })
  }
  const confirmerMesureTel = async () => {
    if (lectureSeule || !mesureTel || !zone || doc.etat !== 'ok') return
    const precision = Number(String(precisionTel).replace(',', '.'))
    const champs = {
      pitchDeg: mesureTel.penteDeg,
      pitchSource: { mode: 'degres', degres: mesureTel.penteDeg, provenance: 'telephone' },
    }
    const precisionOk = precisionTel.trim() !== '' && Number.isFinite(precision) && precision > 0
    if (precisionOk) {
      champs.facingAzimuthDeg = mesureTel.azimutDeg
      champs.facingAzimuthSource = 'releve'
      champs.facingAzimuthPrecisionDeg = precision
    }
    try {
      const res = await calepinageApi.calepinages.enregistrerSectionLayout(calepinageId, {
        cle: 'zones', zone_id: zone.id, champs, base_empreinte: documentVivant?.empreinte || doc.empreinte,
      })
      const mises = res?.data?.roof_layout?.zones
        ?? zones.map((z) => (String(z.id) === String(zone.id) ? { ...z, ...champs } : z))
      doc.appliquerSection('zones', mises, res?.data?.empreinte_document ?? null)
      documentVivant?.appliquerSection?.('zones', mises, res?.data?.empreinte_document ?? null)
      setRefusTel(precisionOk ? null : { champ: 'precision',
        motif: 'Déclarez la précision de la boussole pour confirmer aussi l’orientation : seule la pente est enregistrée.' })
      setMesureTel(null)
      arreterCapteurs()
      setCapteurOuvert(false)
      setMessage(`Pente mesurée au téléphone enregistrée sur le pan « ${zone.label || zone.id} ».`)
    } catch (e) {
      setRefusTel({ champ: 'capteur', motif: messageRefus(e, 'La mesure n’a pas pu être enregistrée.') })
    }
  }

  return (
    <>
      <RetourAtelier calepinageId={calepinageId} />
      <div className="rounded-xl border border-border bg-card mt-6 p-6" data-testid="cal-pente">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Pente de la toiture</p>

      {persister && zones.length > 0 && (
        <label className="mt-3 block text-sm text-foreground">
          Pan
          <select value={zoneId} data-testid="cal-pente-pan"
            onChange={(e) => setZoneChoisie(e.target.value)}
            className="mt-1 w-full rounded border border-border bg-[var(--cal-surface)] px-2 py-1 text-sm text-foreground">
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
          <span className="text-sm text-foreground" data-testid="cal-pente-visite-mesure">
            {`Mesure de la visite : ${visite.penteDeg}°`}
          </span>
          <button type="button" onClick={utiliserPenteVisite}
            data-testid="cal-pente-visite-utiliser"
            className="rounded border border-brass-400/60 px-3 py-1 text-xs text-primary-text">
            Utiliser
          </button>
        </div>
      )}
      {persister && visite?.orientation && (
        <div className="mt-2 flex flex-wrap items-center gap-3" data-testid="cal-pente-visite-orientation">
          <span className="text-sm text-foreground" data-testid="cal-pente-visite-orientation-mesure">
            {`Orientation de la visite : ${visite.orientation.libelle}, ${visite.orientation.azimutDeg}° boussole, précision ${String(visite.orientation.precisionDeg).replace('.', ',')}°`}
          </span>
          <button type="button" onClick={() => setOrientationRetenue(true)}
            disabled={orientationRetenue}
            data-testid="cal-pente-visite-orientation-utiliser"
            className="rounded border border-brass-400/60 px-3 py-1 text-xs text-primary-text disabled:opacity-50">
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
              ? 'bg-primary/15 text-primary-text' : 'text-foreground'}`}
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
          <dd className="fig text-lg text-foreground">
            {retenue ? `${auDixieme(retenue.degres)} °` : '—'}
          </dd>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pente retenue</dt>
        </div>
        <div data-testid="cal-pente-source">
          <dd className="text-sm text-foreground">
            {retenue ? LIBELLE_SOURCE[retenue.source] : 'aucune pente mesurée'}
          </dd>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">D’où elle vient</dt>
        </div>
        <div data-testid="cal-pente-equivalent">
          <dd className="fig text-lg text-foreground">
            {retenue ? `${auDixieme(pourcentageDepuisPente(retenue.degres))} %` : '—'}
          </dd>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Soit, en pourcentage</dt>
        </div>
      </dl>

      {persister && lectureSeule && (
        <p className="mt-4 text-xs text-muted-foreground" data-testid="cal-pente-lecture-seule">
          {RAISON_LECTURE_SEULE}
        </p>
      )}
      {plat && (
        <p className="mt-4 text-sm text-foreground" data-testid="cal-pente-plat">
          Toit plat : ce pan n’a pas de pente à saisir. Pour un toit incliné, changez sa forme par les tuiles.
        </p>
      )}
      {persister && !plat && (
        <button type="button" onClick={enregistrer} disabled={lectureSeule}
          data-testid="cal-pente-enregistrer"
          className="mt-4 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-primary-text disabled:opacity-50">
          Enregistrer la pente
        </button>
      )}
      {message && (
        <p className="mt-3 text-sm text-foreground" role="status"
          data-testid="cal-pente-message">{message}</p>
      )}

      {/* ACAL519 — mesure au téléphone : absente sans capteur (donc invisible au bureau). */}
      {persister && !lectureSeule && !plat && capteursPresents && (
        <details className="mt-4" data-testid="pente-tel">
          <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-primary-text">Mesurer avec le téléphone</summary>
          <p className="text-xs text-muted-foreground">
            Posez le téléphone à plat sur le toit, le haut vers le faîte. La boussole peut dévier près du métal.
          </p>
          {!capteurOuvert ? (
            <button type="button" onClick={ouvrirTelephone} data-testid="pente-tel-demarrer"
              className="mt-2 min-h-11 rounded border border-border px-3 text-sm text-foreground">Activer les capteurs</button>
          ) : (
            <button type="button" onClick={prendreMesureTel} data-testid="pente-tel-mesurer"
              className="mt-2 min-h-11 rounded border border-border px-3 text-sm text-foreground">Prendre la mesure</button>
          )}
          {mesureTel && (
            <div className="mt-2 space-y-2" data-testid="pente-tel-proposition">
              <p className="text-sm text-foreground">
                {`Pente proposée : ${auDixieme(mesureTel.penteDeg)}° · orientation proposée : ${auDixieme(mesureTel.azimutDeg)}° (à confirmer)`}
              </p>
              <label className="block text-sm text-foreground">
                Précision de la boussole (°)
                <input type="text" inputMode="decimal" step="any" value={precisionTel}
                  data-testid="pente-tel-precision"
                  onChange={(e) => setPrecisionTel(e.target.value)}
                  className="fig mt-1 h-11 w-full border border-border bg-background px-2 text-base text-foreground" />
              </label>
              <button type="button" onClick={confirmerMesureTel} data-testid="pente-tel-confirmer"
                className="min-h-11 rounded bg-brass-500/20 px-4 text-sm font-semibold text-primary-text">Confirmer</button>
            </div>
          )}
          {refusTel && (
            <span role="alert" className="mt-1 block text-xs text-red-300" data-testid={`pente-tel-erreur-${refusTel.champ}`}>
              {refusTel.motif}
            </span>
          )}
        </details>
      )}

      {/* CALX29 — suggestion LiDAR IGN, visible SEULEMENT si la lecture
          locale dit `disponible: true` (France). */}
      {/* ACAL535 — « Lire la pente sur un relief de drone » : replié, expert, tous pays ;
          le fichier est lu par le serveur, aucun appel IGN. */}
      {persister && !lectureSeule && (
        <details className="mt-4" data-testid="cal-pente-relief">
          <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-primary-text">
            Lire la pente sur un relief de drone
          </summary>
          <label className="block text-sm text-foreground">
            Relief GeoTIFF (WGS84, en degrés)
            <input type="file" accept=".tif,.tiff,image/tiff" onChange={deposerRelief}
              data-testid="cal-pente-relief-fichier"
              className="mt-1 block min-h-11 w-full border border-border bg-background px-2 py-2 text-base text-foreground" />
          </label>
        </details>
      )}

      {(ignDisponible || suggestions.length > 0 || messageSuggestions) && (
        <div className="mt-6 border-t border-border pt-4" data-testid="cal-pente-lidar">
          {ignDisponible && (
            <>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pente par pan, depuis l’IGN</p>
              <button type="button" onClick={suggererDepuisIGN}
                disabled={chargementSuggestions || lectureSeule}
                data-testid="cal-pente-lidar-suggerer"
                className="mt-2 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-primary-text">
                {chargementSuggestions ? 'Interrogation de l’IGN…' : 'Suggérer depuis l’IGN'}
              </button>
            </>
          )}

          {suggestions.length > 0 && (
            <>
              <p className="mt-3 text-xs text-foreground" data-testid="cal-pente-lidar-mention">
                Les obstacles posés sur la toiture ne sont pas dans cette donnée
                d’élévation : ils restent à saisir à la main.
              </p>
              <ul className="mt-2 space-y-2">
                {suggestions.map((suggestion) => (
                  <li key={suggestion.zoneId}
                    data-testid={`cal-pente-lidar-suggestion-${suggestion.zoneId}`}
                    className="rounded border border-border p-3 text-sm text-foreground">
                    <p>
                      Pan {suggestion.zoneId} — {auDixieme(suggestion.valeurDeg)} °
                    </p>
                    <p className="text-xs text-foreground">
                      Pente du terrain ({suggestion.source === SOURCE_RELIEF ? SOURCE_RELIEF : 'LiDAR IGN'}) — n’est jamais recopiée dans la pente du pan.
                    </p>
                    <p className="text-xs text-muted-foreground" data-testid={`cal-pente-lidar-source-${suggestion.zoneId}`}>
                      {suggestion.source} · {suggestion.suggestedAt}
                    </p>
                    <div className="mt-2 flex gap-2">
                      <button type="button" onClick={() => accepterSuggestion(suggestion)}
                        disabled={lectureSeule}
                        data-testid={`cal-pente-lidar-accepter-${suggestion.zoneId}`}
                        className="rounded bg-brass-500/20 px-3 py-1 text-xs font-semibold text-primary-text">
                        Accepter
                      </button>
                      <button type="button" onClick={() => jeterSuggestion(suggestion)}
                        disabled={lectureSeule}
                        data-testid={`cal-pente-lidar-jeter-${suggestion.zoneId}`}
                        className="rounded px-3 py-1 text-xs text-foreground">
                        Jeter
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          {messageSuggestions && (
            <p className="mt-3 text-sm text-foreground" role="status"
              data-testid="cal-pente-lidar-message">{messageSuggestions}</p>
          )}
        </div>
      )}
    </div>
    </>
  )
}
