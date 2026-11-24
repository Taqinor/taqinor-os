import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useDocumentCalepinage from '../useDocumentCalepinage'
import { panParDefaut, zonesDuDocument } from '../SaisiePente.helpers'
import { demarrerCapteurs, lireInclinaison, lireVisee, arreter as arreterCapteurs } from '../capteursTelephone'
import { messageRefus, refusServeur } from '../commun/refusServeur'
import { lireConflit } from '../conflitEcriture'
import { Icone } from '../atelier/coque/primitives'
import { PlanDessus } from '../client/partiesClient'
import { planDessus } from '../client/vueClient.helpers'
import { champsDuReleve, corpsDuReleve, validerAvantEnvoi } from './corpsReleve'
import {
  LARGEUR, LONGUEUR, avecMesure, chainesSaisies, dateDuJour, mesureDesChaines, mesureDuCapteur,
  cotesDuToit, ligneProjet, noteHorsLigne, nomDirection, penteDuPan, versPoint, versVirgule,
} from './releveTelephone'
import usePhotosReleve from './usePhotosReleve'
import useReleveEnFile from './useReleveEnFile'
import useBrouillonReleve, { compterMesures } from './useBrouillonReleve'
import TuilesPhotos from './TuilesPhotos'
import { CarteMesure, ChampDecimal, PictoBoussole } from './CarteMesure'

/* ============================================================================
   « RELEVÉ DE VISITE » AU TÉLÉPHONE (`/calepinage/:id/releve`, maquette Telephone, 390×844).
   Assemblé avec ce qui EXISTE : le relevé terrain (même corps, même porte que
   `PanneauReleve`), la pente du pan (même écriture que `SaisiePente`), les capteurs
   (`capteursTelephone`), les photos de site et leur file hors ligne (`fileEnvoiPhotos`).
   Une valeur tapée n'est jamais dite « mesurée » ; sans capteur, la saisie à la main
   le dit. « Terminer le relevé » enregistre ce que le panneau de l'atelier enregistre
   (création, ou correction du relevé courant) — aucun statut neuf.
   ========================================================================== */

const SANS_LECTURE = 'Aucune lecture du capteur : réessayez, ou saisissez la valeur à la main.'

/* T4-U4-020 / T4-U4-023 — les champs du pan (pente, orientation tapée) écrits par `layout/section/`, en ligne comme au
   retour du réseau ; et leur nom, accordé (« La pente et l’orientation du toit partiront… »). */
function champsDuPan(pente, azimutTape) {
  const champs = {}
  if (pente) {
    champs.pitchDeg = pente.degres
    champs.pitchSource = pente.capteur
      ? { mode: 'degres', degres: pente.degres, provenance: 'telephone' } : { mode: 'degres', degres: pente.degres }
  }
  if (azimutTape !== null) {
    champs.facingAzimuthDeg = azimutTape
    champs.facingManual = true
    champs.facingAzimuthSource = 'saisie'
    champs.facingAzimuthPrecisionDeg = null
  }
  return champs
}
function nomDuPan(champs) {
  const p = champs?.pitchDeg !== undefined
  const o = champs?.facingAzimuthDeg !== undefined
  if (p && o) return { nom: 'Pente et orientation du toit', phrase: 'La pente et l’orientation du toit partiront', pluriel: true }
  if (p) return { nom: 'Pente du toit', phrase: 'La pente du toit partira', pluriel: false }
  return { nom: 'Orientation du toit', phrase: 'L’orientation du toit partira', pluriel: false }
}
const attendre = (ms) => new Promise((r) => { setTimeout(r, ms) })

/* ACAL1812 — le champ fautif d'un refus (clé du serveur ou de la validation locale) → l'identifiant du champ à l'écran. */
function champFautif(champs) {
  const cle = Object.keys(champs ?? {})[0] ?? ''
  if (cle === 'precision_azimut_deg') return 'releve-precision'
  if (cle.startsWith('azimut')) return 'releve-azimut-main'
  const chaine = /^chaines\[(\d+)\]/.exec(cle)
  if (chaine) return Number(chaine[1]) === 1 ? 'releve-largeur' : 'releve-longueur'
  return null
}

function useEnLigne() {
  const [enLigne, setEnLigne] = useState(() => typeof navigator === 'undefined' || navigator.onLine !== false)
  useEffect(() => {
    const maj = () => setEnLigne(navigator.onLine !== false)
    window.addEventListener('online', maj)
    window.addEventListener('offline', maj)
    return () => { window.removeEventListener('online', maj); window.removeEventListener('offline', maj) }
  }, [])
  return enLigne
}

function PastilleHorsLigne() {
  return (
    <span className="cal-tel-pastille" data-testid="releve-hors-ligne">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M2 8.5a15 15 0 0120 0M5.5 12a10 10 0 0113 0M9 15.5a5 5 0 016 0M3 3l18 18" />
      </svg>
      Hors ligne
    </span>
  )
}

export default function ReleveVisite() {
  const { id } = useParams()
  const enLigne = useEnLigne()
  const doc = useDocumentCalepinage(id)
  const zone = zonesDuDocument(doc.document).find((z) => String(z.id) === panParDefaut(doc.document)) ?? null
  const photos = usePhotosReleve(id)
  /* T4-U4-020 / T4-U4-022 — le brouillon des mesures tapées et le pan en attente, gardés sur le téléphone. */
  const brouillons = useBrouillonReleve(id)
  const depart = brouillons.brouillon
  const brouillonRef = useRef(brouillons)
  useEffect(() => { brouillonRef.current = brouillons })

  const [titre, setTitre] = useState('')
  const [releve, setReleve] = useState(() => ({
    id: null, releveLe: '', notes: '', chaines: [], photoIds: [],
    ...(depart.Longueur !== undefined ? { [`saisie${LONGUEUR}`]: depart.Longueur } : {}),
    ...(depart.Largeur !== undefined ? { [`saisie${LARGEUR}`]: depart.Largeur } : {}),
  }))
  const [azimutDeg, setAzimutDeg] = useState(() => depart.boussole?.azimutDeg ?? '')
  const [precisionDeg, setPrecisionDeg] = useState(() => depart.boussole?.precisionDeg ?? '')
  const [azimutMain, setAzimutMain] = useState(() => depart.azimutMain ?? '') // ACAL1814 — l'orientation TAPÉE : écrite sur le pan, jamais en azimut boussole
  const [capteurLu, setCapteurLu] = useState(() => !!depart.boussole) // une lecture du capteur dans cette séance : elle prime sur l'orientation déjà tapée du pan
  const [azimutEcrit, setAzimutEcrit] = useState('') // la valeur tapée déjà écrite sur le pan (évite de la réécrire)
  const [pente, setPente] = useState(() => depart.pente ?? null) // { degres, capteur } — en attente de « Terminer »
  const [capteursActifs, setCapteursActifs] = useState(false)
  const [manuel, setManuel] = useState(() => ({ pente: !!depart.pente && !depart.pente.capteur, azimut: !!depart.azimutMain }))
  const [lecture, setLecture] = useState('ok') // T4-U4-021 — le relevé enregistré a-t-il pu être relu ?
  const [envois, setEnvois] = useState({}) // T4-U4-020 — ce qui est PARTI depuis l'ouverture : { releve: true, pan: nom }
  const [panRefuse, setPanRefuse] = useState(false)
  const panEnVol = useRef(false)
  const conflitsPan = useRef(0)
  const [motifs, setMotifs] = useState({})
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState(false)
  const [feuilleReduite, setFeuilleReduite] = useState(false) // la poignée : la feuille descend, la carte du toit grandit
  const [message, setMessage] = useState(null) // { texte, ton: 'ok' | 'refus', champ: identifiant du champ fautif à ramener en vue }
  const reponse = useRef(null)
  /* ACAL1810 — le relevé terminé hors ligne attend dans la file des photos ; au retour du réseau il part SEUL. */
  const fileReleve = useReleveEnFile(id, {
    onEnvoye: (envoye) => {
      if (envoye?.id) setReleve((r) => ({ ...r, id: envoye.id }))
      setMessage((m) => ({ texte: `Relevé envoyé.${m?.envoiPan ? ` ${m.envoiPan}` : ''}`, ton: 'ok' }))
      setEnvois((e) => ({ ...e, releve: true }))
      // T4-U4-021 — le serveur a pris les mesures : le brouillon les rend, l'écran relit CE QUE LE SERVEUR TIENT.
      brouillonRef.current.oublier([LONGUEUR, LARGEUR, 'boussole'])
      relireRef.current(false)
      photos.recharger()
    },
    onRefus: ({ message: motif, champs }) => {
      setErreurs(champs ?? {})
      setMessage({ texte: motif || 'Le relevé gardé a été refusé par le serveur.', ton: 'refus', champ: champFautif(champs) })
    },
  })

  /* ACAL1812 — la réponse de « Terminer » est EN VUE : le champ fautif défile au centre et prend le focus ; sinon la
     bannière (posée au-dessus du pied) prend le focus, sans défilement de la page. */
  useEffect(() => {
    if (!message) return
    const champ = message.champ ? document.getElementById(message.champ) : null
    if (champ) { champ.scrollIntoView?.({ block: 'center' }); champ.focus({ preventScroll: true }) } else reponse.current?.focus({ preventScroll: true })
  }, [message])

  /* La lecture du relevé ENREGISTRÉ. `garderSaisies` : les mesures du brouillon priment (ouverture) ; après un envoi,
     non — l'écran montre ce que le serveur tient. Un échec se DIT (T4-U4-021), jamais des champs vides muets. */
  const vivantRef = useRef(true)
  const relire = (garderSaisies) => {
    setLecture('ok')
    return Promise.resolve(calepinageApi.calepinages.releve?.(id)).then((res) => {
      const courant = (res?.data?.releves ?? []).find((r) => r.id === res?.data?.releve_courant_id)
      if (!vivantRef.current || !courant) return
      const c = champsDuReleve(courant)
      const garde = garderSaisies ? brouillonRef.current.brouillon : {}
      setReleve((r) => ({
        id: courant.id, releveLe: c.releveLe, notes: c.notes, chaines: chainesSaisies(c.chaines), photoIds: c.photoIds,
        ...(garderSaisies ? Object.fromEntries([LONGUEUR, LARGEUR].filter((n) => r[`saisie${n}`] !== undefined)
          .map((n) => [`saisie${n}`, r[`saisie${n}`]])) : {}),
      }))
      if (!garde.boussole) {
        setAzimutDeg(c.azimutDeg)
        setPrecisionDeg(c.precisionDeg)
      }
    }).catch(() => { if (vivantRef.current) setLecture('erreur') })
  }
  const relireRef = useRef(relire)
  useEffect(() => { relireRef.current = relire })

  useEffect(() => {
    if (!id) return undefined
    let vivant = true
    vivantRef.current = true
    relireRef.current(true)
    Promise.resolve(calepinageApi.calepinages.get?.(id)).then((res) => {
      if (vivant) setTitre(ligneProjet(res?.data))
    }).catch(() => {})
    return () => { vivant = false; vivantRef.current = false; arreterCapteurs() }
  }, [id])

  const majMesure = (nom, valeur) => {
    setReleve((r) => ({ ...r, chaines: avecMesure(r.chaines, nom, valeur), [`saisie${nom}`]: valeur }))
    brouillons.garder({ [nom]: valeur })
  }
  const majPente = (p) => { setPente(p); brouillons.garder({ pente: p }) }
  /* ACAL1836 — sans mesure du relevé ni saisie, les cotes du toit DÉJÀ CRÉÉ (pan rectangulaire servi) sont reprises et DITES
     telles : elles partent avec « Terminer » comme n'importe quelle mesure ; une saisie (même vide) les remplace. */
  const cotesToit = useMemo(() => (zone ? cotesDuToit(zone) : null), [zone])
  const repriseDuToit = (nom) => (releve[`saisie${nom}`] === undefined && mesureDesChaines(releve.chaines, nom) === ''
    ? cotesToit?.[nom] ?? null : null)
  const valeurChamp = (nom) => releve[`saisie${nom}`] ?? versVirgule(mesureDesChaines(releve.chaines, nom) || repriseDuToit(nom) || '')
  const reprises = [LONGUEUR, LARGEUR].some((nom) => repriseDuToit(nom) !== null)
  const chainesEnvoyees = () => [LONGUEUR, LARGEUR].reduce((chaines, nom) => {
    const reprise = repriseDuToit(nom)
    return reprise === null ? chaines : avecMesure(chaines, nom, String(reprise))
  }, releve.chaines)
  const plan = useMemo(() => (doc.etat === 'ok' ? planDessus(doc.document) : null), [doc.etat, doc.document])

  /* Le capteur, démarré par le geste ; refusé ou absent ⇒ la saisie à la main, dite telle. */
  const lireCapteur = async (champ) => {
    if (!capteursActifs) {
      const depart = await demarrerCapteurs()
      if (depart.indisponible) {
        setMotifs((m) => ({ ...m, [champ]: depart.motif }))
        setManuel((m) => ({ ...m, [champ]: true }))
        return null
      }
      setCapteursActifs(true)
      await attendre(400)
    }
    const inc = lireInclinaison()
    const visee = lireVisee()
    if (inc.indisponible || (champ === 'azimut' && visee.indisponible)) {
      setMotifs((m) => ({ ...m, [champ]: SANS_LECTURE }))
      setManuel((m) => ({ ...m, [champ]: true }))
      return null
    }
    setMotifs((m) => ({ ...m, [champ]: null }))
    return mesureDuCapteur(inc, visee)
  }
  const mesurerPente = async () => {
    const m = await lireCapteur('pente')
    if (m) majPente({ degres: m.penteDeg, capteur: true })
  }
  const mesurerAzimut = async () => {
    const m = await lireCapteur('azimut')
    if (m && m.azimutDeg !== null) {
      setAzimutDeg(String(m.azimutDeg)); setAzimutMain(''); setCapteurLu(true)
      brouillons.garder({ azimutMain: '', boussole: { azimutDeg: String(m.azimutDeg), precisionDeg } })
    }
  }

  const carteP = penteDuPan(zone, pente)
  /* ACAL1814 — ce que dit la carte : la valeur tapée, sinon l'orientation saisie déjà écrite sur le pan (relue), sinon la boussole du relevé. */
  const azimutDuPan = zone?.facingAzimuthSource === 'saisie' && Number.isFinite(Number(zone.facingAzimuthDeg))
    && zone.facingAzimuthDeg !== null ? String(zone.facingAzimuthDeg) : ''
  const aMain = azimutMain !== '' || (azimutDuPan !== '' && !capteurLu)
  const azimutLu = azimutMain !== '' ? versPoint(azimutMain) : (aMain ? azimutDuPan : azimutDeg)
  const direction = nomDirection(azimutLu)

  /* Le PAN, écrit exactement comme `SaisiePente` (primitive par section) : la pente, et/ou l'orientation TAPÉE
     (source « saisie », ACAL1814) — UNE seule écriture, un seul jeton. */
  const ecrirePan = async (cible, champs) => {
    const res = await calepinageApi.calepinages.enregistrerSectionLayout(id, {
      cle: 'zones', zone_id: cible.id, champs, base_empreinte: doc.empreinte,
    })
    const mises = res?.data?.roof_layout?.zones
      ?? zonesDuDocument(doc.document).map((z) => (String(z.id) === String(cible.id) ? { ...z, ...champs } : z))
    doc.appliquerSection('zones', mises, res?.data?.empreinte_document ?? null)
    // La pente tapée RESTE lue (« 22° · saisie à la main ») : seule la marque « déjà écrite » évite de la réécrire.
    if (champs.pitchDeg !== undefined) setPente((p) => (p ? { ...p, enregistree: true } : p))
    if (champs.facingAzimuthDeg !== undefined) setAzimutEcrit(String(champs.facingAzimuthDeg))
    brouillonRef.current.oublier(['pente', 'azimutMain'])
  }
  const enregistrerPan = (aEcrirePente, azimutTape) => ecrirePan(zone, champsDuPan(aEcrirePente ? pente : null, azimutTape))

  /* T4-U4-020 — le pan gardé hors ligne repart DÈS que le réseau et le document sont là (même écriture qu'en ligne) ;
     un document changé ailleurs est relu puis réessayé (deux fois au plus) ; un vrai refus se dit et ne boucle pas. */
  const panAttente = brouillons.pan
  useEffect(() => {
    if (!enLigne || !panAttente || doc.etat !== 'ok' || panEnVol.current || panRefuse) return
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return
    const cible = zonesDuDocument(doc.document).find((z) => String(z.id) === String(panAttente.zoneId)) ?? zone
    if (!cible) return
    panEnVol.current = true
    const { nom, pluriel } = nomDuPan(panAttente.champs)
    Promise.resolve().then(() => ecrirePan(cible, panAttente.champs)).then(() => {
      brouillonRef.current.oublierPan()
      setEnvois((e) => ({ ...e, pan: nom }))
      const dit = `${nom} ${pluriel ? 'enregistrées' : 'enregistrée'}.`
      setMessage((m) => (m?.ton === 'ok' && m.texte?.startsWith('Relevé envoyé')
        ? { ...m, texte: `${m.texte} ${dit}` } : { texte: dit, ton: 'ok', envoiPan: dit }))
    }).catch((err) => {
      if (!err?.response) return // réseau encore absent : il reste en attente
      if (lireConflit(err)?.documentModifie && conflitsPan.current < 2) { conflitsPan.current += 1; doc.recharger(); return }
      setPanRefuse(true)
      setMessage({ texte: messageRefus(err, `${nom} gardée${pluriel ? 's' : ''} : refusée${pluriel ? 's' : ''} par le serveur.`), ton: 'refus' })
    }).finally(() => { panEnVol.current = false })
  // eslint-disable-next-line react-hooks/exhaustive-deps -- rejoué sur réseau / document / attente, pas sur chaque rendu
  }, [enLigne, panAttente, doc.etat, doc.empreinte, panRefuse])

  /* Au retour du réseau, un document illisible (écran ouvert hors ligne) est relu : le pan en attente pourra partir. */
  const etaitEnLigne = useRef(enLigne)
  useEffect(() => {
    if (enLigne && !etaitEnLigne.current && doc.etat === 'erreur') doc.recharger()
    etaitEnLigne.current = enLigne
  }, [enLigne, doc])

  const terminer = async () => {
    // ACAL1814 — seule une mesure de capteur (boussole) part en azimut du relevé, et exige sa précision.
    const azimut = versPoint(azimutDeg)
    const precision = versPoint(precisionDeg)
    const tape = versPoint(azimutMain)
    const azimutTape = tape !== '' && Number.isFinite(Number(tape)) && tape !== azimutEcrit ? Number(tape) : null
    const chaines = chainesEnvoyees()
    const fautes = validerAvantEnvoi(chaines, azimut, precision)
    setErreurs(fautes)
    setMessage(null)
    if (Object.keys(fautes).length) {
      setMessage({ texte: Object.values(fautes)[0], ton: 'refus', champ: champFautif(fautes) })
      return
    }
    setEnCours(true)
    const corps = corpsDuReleve({
      releveLe: releve.releveLe || dateDuJour(), chaines, azimutDeg: azimut,
      precisionDeg: precision, notes: releve.notes, photoIds: releve.photoIds,
    })
    const pretAEcrire = !!zone && doc.etat === 'ok'
    const penteAEcrire = !!pente && !pente.enregistree && pretAEcrire
    const azimutAEcrire = azimutTape !== null && pretAEcrire
    const panAEcrire = penteAEcrire || azimutAEcrire
    const sansPanPourAzimut = azimutTape !== null && !zone
    /* Sans réseau (ou coupure en route) : le relevé reste sur le téléphone, dans la file, et le DIT en vue ; la pente et
       l'orientation tapées sont gardées AVEC lui et repartent au retour du réseau (T4-U4-020). */
    const garderSurLeTelephone = async () => {
      await fileReleve.garder(corps, releve.id)
      const champsPan = champsDuPan(pente && !pente.enregistree ? pente : null, azimutTape)
      const aGarder = Object.keys(champsPan).length > 0
      if (aGarder) { brouillons.garderPan({ zoneId: zone?.id ?? null, champs: champsPan }); setPanRefuse(false); conflitsPan.current = 0 }
      setReleve((r) => ({ ...r, releveLe: corps.releve_le }))
      setMessage({
        texte: `Relevé gardé sur ce téléphone : il partira au retour du réseau.${aGarder ? ` ${nomDuPan(champsPan).phrase} avec lui.` : ''}`,
        ton: 'ok',
      })
    }
    try {
      if (typeof navigator !== 'undefined' && navigator.onLine === false) { await garderSurLeTelephone(); return }
      if (panAEcrire) await enregistrerPan(penteAEcrire, azimutAEcrire ? azimutTape : null)
      const res = await (releve.id
        ? calepinageApi.calepinages.corrigerReleve(id, releve.id, corps)
        : calepinageApi.calepinages.enregistrerReleve(id, corps))
      if (fileReleve.enAttente) await fileReleve.oublier() // l'envoi en ligne a réussi : la copie gardée ne repart pas
      if (!sansPanPourAzimut) brouillons.oublier() // le serveur a tout pris : le brouillon est rendu
      else brouillons.oublier([LONGUEUR, LARGEUR, 'pente', 'boussole'])
      if (brouillons.pan) brouillons.oublierPan()
      const nouvelId = res?.data?.releve?.id
      setReleve((r) => ({ ...r, id: nouvelId ?? r.id, releveLe: corps.releve_le }))
      setMessage({
        texte: `${releve.id ? 'Relevé corrigé.' : 'Relevé enregistré.'}${sansPanPourAzimut
          ? ' L’orientation tapée n’est pas enregistrée : aucun pan dessiné, tracez le toit dans l’atelier.' : ''}`,
        ton: 'ok',
      })
    } catch (err) {
      const refus = (texte, champ = null) => setMessage({ texte, ton: 'refus', champ })
      if (!err?.response) {
        try { await garderSurLeTelephone() } catch (e) { refus(e?.message || 'Le relevé n’a pas pu être gardé sur ce téléphone.') }
      } else if (lireConflit(err)?.documentModifie) { refus('Le calepinage a changé ailleurs : il est relu, recommencez.'); doc.recharger() } else {
        const { champs } = refusServeur(err)
        setErreurs(champs)
        refus(messageRefus(err, 'Le relevé a été refusé par le serveur.'), champFautif(champs))
      }
    } finally {
      setEnCours(false)
    }
  }

  const deposer = async (genre, fichier) => {
    const nouvelle = await photos.deposer(genre, fichier)
    if (nouvelle !== null) setReleve((r) => ({ ...r, photoIds: [...r.photoIds, nouvelle] }))
  }

  const sansPan = doc.etat === 'ok' && !zone
  const mesuresGardees = compterMesures(brouillons.brouillon)
  /* T4-U4-020 — chaque pièce dit où elle en est : « en attente » (sur le téléphone) ou « envoyé » (le serveur l'a). */
  const lignesEnvois = [
    fileReleve.enAttente ? { cle: 'releve', texte: 'Relevé : en attente' }
      : envois.releve ? { cle: 'releve', texte: 'Relevé : envoyé', envoye: true } : null,
    panAttente ? { cle: 'pan', texte: `${nomDuPan(panAttente.champs).nom} : en attente` }
      : envois.pan ? { cle: 'pan', texte: `${envois.pan} : ${envois.pan.startsWith('Pente et') ? 'envoyées' : 'envoyée'}`, envoye: true } : null,
    photos.enAttente > 0 ? { cle: 'photos', texte: `Photos : ${photos.enAttente} en attente` }
      : photos.genresEnvoyes.length ? { cle: 'photos', texte: 'Photos : envoyées', envoye: true } : null,
  ].filter(Boolean)
  const longueur = valeurChamp(LONGUEUR)
  const largeur = valeurChamp(LARGEUR)
  return (
    <div className="cal-tel cal-tel-releve" data-testid="cal-releve" data-feuille-reduite={feuilleReduite ? '1' : undefined}>
      {/* ACAL1836 — le toit relevé, derrière la feuille : son plan servi (le même que « Montrer au client »), ses cotes. */}
      <div className="cal-tel-carte-toit" data-testid="releve-carte-toit">
        {plan && <PlanDessus plan={plan} />}
        {longueur && <span className="cal-tel-cote cal-tel-cote-longueur" data-testid="releve-cote-longueur">{longueur}<small>m</small></span>}
        {largeur && <span className="cal-tel-cote cal-tel-cote-largeur" data-testid="releve-cote-largeur">{largeur}<small>m</small></span>}
      </div>

      <header className="cal-tel-entete">
        <Link to={`/calepinage/${id}`} aria-label="Retour" className="cal-tel-retour">
          <Icone nom="retour" taille={22} epaisseur={2} />
        </Link>
        <div className="cal-tel-projet">
          <span className="cal-tel-projet-titre">Relevé de visite</span>
          {titre && <span className="cal-tel-projet-ligne" data-testid="releve-projet">{titre}</span>}
        </div>
        {(!enLigne || photos.enAttente > 0 || fileReleve.enAttente) && <PastilleHorsLigne />}
      </header>

      <div className="cal-tel-feuille">
        <button type="button" className="cal-tel-poignee" data-testid="releve-poignee" aria-expanded={!feuilleReduite}
          aria-label="Agrandir ou réduire la feuille" onClick={() => setFeuilleReduite((r) => !r)}>
          <span />
        </button>

        <div className="cal-tel-corps">
          <TuilesPhotos photos={photos.photos} genresEnFile={photos.genresEnFile} genresEnvoyes={photos.genresEnvoyes} enCours={photos.enCours}
            message={photos.message} onDeposer={deposer} />

          <section className="cal-tel-section cal-tel-mesures" data-testid="releve-mesures">
            <h2 className="cal-tel-h">Mesures</h2>
            {lecture === 'erreur' && (
              <div role="alert" className="cal-tel-erreur" data-testid="releve-lecture-erreur">
                <p className="cal-tel-aide">Le relevé enregistré n’a pas pu être relu : des champs vides ne veulent pas dire qu’il est perdu.</p>
                <button type="button" className="cal-tel-bouton" onClick={() => relire(true)}>Réessayer</button>
              </div>
            )}
            <div className="cal-tel-deux">
              <ChampDecimal id="releve-longueur" testId="releve-longueur" libelle="Longueur" unite="m"
                valeur={longueur} onChange={(v) => majMesure(LONGUEUR, v)} />
              <ChampDecimal id="releve-largeur" testId="releve-largeur" libelle="Largeur" unite="m"
                valeur={largeur} onChange={(v) => majMesure(LARGEUR, v)} />
            </div>
            {reprises && (
              <p className="cal-tel-aide" data-testid="releve-cotes-reprises">
                Reprises du toit dessiné : corrigez-les si votre mesure sur place diffère.
              </p>
            )}

            <div className="cal-tel-cartes">
              <CarteMesure testId="releve-pente" libelle="Pente du toit"
                valeur={carteP.nombre ?? 'à mesurer'} provenance={carteP.provenance} provenanceOk={carteP.provenance === 'mesurée'}
                bouton={carteP.bouton} onBouton={mesurerPente} desactive={!zone}>
                {carteP.aide && <p className="cal-tel-aide" data-testid="releve-pente-aide">{carteP.aide}</p>}
                {sansPan && <p className="cal-tel-aide" data-testid="releve-pente-sans-pan">Aucun pan dessiné : la pente s’enregistre sur un pan, tracez le toit dans l’atelier.</p>}
                {motifs.pente && <p role="alert" className="cal-tel-aide">{motifs.pente}</p>}
                {manuel.pente && zone && (
                  <ChampDecimal id="releve-pente-main" testId="releve-pente-main" libelle="Pente saisie à la main" unite="°" compact
                    valeur={pente && !pente.capteur ? versVirgule(pente.saisie) : ''}
                    onChange={(v) => { const n = Number(versPoint(v)); majPente(v.trim() === '' || !Number.isFinite(n) ? null : { degres: n, capteur: false, saisie: versPoint(v) }) }} />
                )}
              </CarteMesure>

              <CarteMesure testId="releve-orientation" libelle="Le toit regarde vers"
                valeur={direction || 'à relever'} provenance={direction && aMain ? 'saisie à la main' : null}
                bouton="Boussole" icone={<PictoBoussole />} onBouton={mesurerAzimut}>
                {motifs.azimut && <p role="alert" className="cal-tel-aide">{motifs.azimut}</p>}
                {manuel.azimut && (
                  <ChampDecimal id="releve-azimut-main" testId="releve-azimut-main" libelle="Orientation saisie à la main (0 = nord)" unite="°" compact
                    valeur={versVirgule(azimutMain !== '' ? azimutMain : azimutDuPan)}
                    onChange={(v) => { setAzimutMain(versPoint(v)); setCapteurLu(false); brouillons.garder({ azimutMain: versPoint(v), boussole: null }) }} />
                )}
                {azimutDeg !== '' && !aMain && (
                  <ChampDecimal id="releve-precision" testId="releve-precision" libelle="Précision de la boussole (±)" unite="°" compact
                    valeur={versVirgule(precisionDeg)} onChange={(v) => {
                      setPrecisionDeg(versPoint(v)); brouillons.garder({ boussole: { azimutDeg, precisionDeg: versPoint(v) } })
                    }} />
                )}
                {erreurs.precision_azimut_deg && <p role="alert" className="cal-tel-erreur" data-testid="releve-erreur-precision">{erreurs.precision_azimut_deg}</p>}
              </CarteMesure>
            </div>
            {Object.keys(erreurs).filter((c) => c.startsWith('chaines')).map((c) => (
              <p key={c} role="alert" className="cal-tel-erreur">{erreurs[c]}</p>
            ))}
          </section>

          {(photos.enAttente > 0 || fileReleve.enAttente || !enLigne || mesuresGardees > 0) && (
            <section className="cal-tel-note" data-testid="releve-note-hors-ligne">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 21h14" /></svg>
              <span>{noteHorsLigne(photos.enAttente, enLigne, fileReleve.enAttente, mesuresGardees)}</span>
            </section>
          )}
          {lignesEnvois.length > 0 && (
            <ul className="cal-tel-envois" data-testid="releve-envois" aria-label="État des envois">
              {lignesEnvois.map((l) => <li key={l.cle} data-etat={l.envoye ? 'envoye' : 'attente'}>{l.texte}</li>)}
            </ul>
          )}
        </div>

        {/* ACAL1812 — la réponse vit ENTRE le corps défilant et le pied fixe : jamais sous la barre du bas. */}
        {message && (
          <p ref={reponse} tabIndex={-1} role={message.ton === 'refus' ? 'alert' : 'status'} className="cal-tel-message"
            data-ton={message.ton} data-testid="releve-message">{message.texte}</p>
        )}

        <footer className="cal-tel-pied">
          <Link to={`/calepinage/${id}/client`} className="cal-tel-pied-secondaire" data-testid="releve-voir-3d">Voir en 3D</Link>
          <button type="button" className="cal-tel-pied-or" onClick={terminer} disabled={enCours} data-testid="releve-terminer">
            {enCours ? 'Enregistrement…' : 'Terminer le relevé'}
          </button>
        </footer>
      </div>
    </div>
  )
}
