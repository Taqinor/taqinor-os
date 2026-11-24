import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useDocumentCalepinage from '../useDocumentCalepinage'
import { panParDefaut, zonesDuDocument } from '../SaisiePente.helpers'
import { demarrerCapteurs, lireInclinaison, lireVisee, arreter as arreterCapteurs } from '../capteursTelephone'
import { messageRefus, refusServeur } from '../commun/refusServeur'
import { lireConflit } from '../conflitEcriture'
import { Icone } from '../atelier/coque/primitives'
import { champsDuReleve, corpsDuReleve, validerAvantEnvoi } from './corpsReleve'
import {
  LARGEUR, LONGUEUR, avecMesure, chainesSaisies, dateDuJour, mesureDesChaines, mesureDuCapteur,
  ligneProjet, noteHorsLigne, nomDirection, penteDuPan, versPoint, versVirgule,
} from './releveTelephone'
import usePhotosReleve from './usePhotosReleve'
import useReleveEnFile from './useReleveEnFile'
import TuilesPhotos from './TuilesPhotos'
import { CarteMesure, ChampDecimal } from './CarteMesure'

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

  const [titre, setTitre] = useState('')
  const [releve, setReleve] = useState({ id: null, releveLe: '', notes: '', chaines: [], photoIds: [] })
  const [azimutDeg, setAzimutDeg] = useState('')
  const [precisionDeg, setPrecisionDeg] = useState('')
  const [azimutMain, setAzimutMain] = useState('') // ACAL1814 — l'orientation TAPÉE : écrite sur le pan, jamais en azimut boussole
  const [capteurLu, setCapteurLu] = useState(false) // une lecture du capteur dans cette séance : elle prime sur l'orientation déjà tapée du pan
  const [azimutEcrit, setAzimutEcrit] = useState('') // la valeur tapée déjà écrite sur le pan (évite de la réécrire)
  const [pente, setPente] = useState(null) // { degres, capteur } — en attente de « Terminer »
  const [capteursActifs, setCapteursActifs] = useState(false)
  const [manuel, setManuel] = useState({ pente: false, azimut: false })
  const [motifs, setMotifs] = useState({})
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState(false)
  const [message, setMessage] = useState(null) // { texte, ton: 'ok' | 'refus', champ: identifiant du champ fautif à ramener en vue }
  const reponse = useRef(null)
  /* ACAL1810 — le relevé terminé hors ligne attend dans la file des photos ; au retour du réseau il part SEUL. */
  const fileReleve = useReleveEnFile(id, {
    onEnvoye: (envoye) => {
      if (envoye?.id) setReleve((r) => ({ ...r, id: envoye.id }))
      setMessage({ texte: 'Relevé envoyé.', ton: 'ok' })
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

  useEffect(() => {
    if (!id) return undefined
    let vivant = true
    Promise.resolve(calepinageApi.calepinages.releve?.(id)).then((res) => {
      const courant = (res?.data?.releves ?? []).find((r) => r.id === res?.data?.releve_courant_id)
      if (!vivant || !courant) return
      const c = champsDuReleve(courant)
      setReleve({ id: courant.id, releveLe: c.releveLe, notes: c.notes, chaines: chainesSaisies(c.chaines), photoIds: c.photoIds })
      setAzimutDeg(c.azimutDeg)
      setPrecisionDeg(c.precisionDeg)
    }).catch(() => {})
    Promise.resolve(calepinageApi.calepinages.get?.(id)).then((res) => {
      if (vivant) setTitre(ligneProjet(res?.data))
    }).catch(() => {})
    return () => { vivant = false; arreterCapteurs() }
  }, [id])

  const majMesure = (nom, valeur) => setReleve((r) => ({
    ...r, chaines: avecMesure(r.chaines, nom, valeur), [`saisie${nom}`]: valeur,
  }))
  const valeurChamp = (nom) => releve[`saisie${nom}`] ?? versVirgule(mesureDesChaines(releve.chaines, nom))

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
    if (m) setPente({ degres: m.penteDeg, capteur: true })
  }
  const mesurerAzimut = async () => {
    const m = await lireCapteur('azimut')
    if (m && m.azimutDeg !== null) { setAzimutDeg(String(m.azimutDeg)); setAzimutMain(''); setCapteurLu(true) }
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
  const enregistrerPan = async (aEcrirePente, azimutTape) => {
    const champs = {}
    if (aEcrirePente) {
      const v = pente.degres
      champs.pitchDeg = v
      champs.pitchSource = pente.capteur ? { mode: 'degres', degres: v, provenance: 'telephone' } : { mode: 'degres', degres: v }
    }
    if (azimutTape !== null) {
      champs.facingAzimuthDeg = azimutTape
      champs.facingManual = true
      champs.facingAzimuthSource = 'saisie'
      champs.facingAzimuthPrecisionDeg = null
    }
    const res = await calepinageApi.calepinages.enregistrerSectionLayout(id, {
      cle: 'zones', zone_id: zone.id, champs, base_empreinte: doc.empreinte,
    })
    const mises = res?.data?.roof_layout?.zones
      ?? zonesDuDocument(doc.document).map((z) => (String(z.id) === String(zone.id) ? { ...z, ...champs } : z))
    doc.appliquerSection('zones', mises, res?.data?.empreinte_document ?? null)
    // La pente tapée RESTE lue (« 22° · saisie à la main ») : seule la marque « déjà écrite » évite de la réécrire.
    if (aEcrirePente) setPente((p) => ({ ...p, enregistree: true }))
    if (azimutTape !== null) setAzimutEcrit(String(azimutTape))
  }

  const terminer = async () => {
    // ACAL1814 — seule une mesure de capteur (boussole) part en azimut du relevé, et exige sa précision.
    const azimut = versPoint(azimutDeg)
    const precision = versPoint(precisionDeg)
    const tape = versPoint(azimutMain)
    const azimutTape = tape !== '' && Number.isFinite(Number(tape)) && tape !== azimutEcrit ? Number(tape) : null
    const fautes = validerAvantEnvoi(releve.chaines, azimut, precision)
    setErreurs(fautes)
    setMessage(null)
    if (Object.keys(fautes).length) {
      setMessage({ texte: Object.values(fautes)[0], ton: 'refus', champ: champFautif(fautes) })
      return
    }
    setEnCours(true)
    const corps = corpsDuReleve({
      releveLe: releve.releveLe || dateDuJour(), chaines: releve.chaines, azimutDeg: azimut,
      precisionDeg: precision, notes: releve.notes, photoIds: releve.photoIds,
    })
    const pretAEcrire = !!zone && doc.etat === 'ok'
    const penteAEcrire = !!pente && !pente.enregistree && pretAEcrire
    const azimutAEcrire = azimutTape !== null && pretAEcrire
    const panAEcrire = penteAEcrire || azimutAEcrire
    const sansPanPourAzimut = azimutTape !== null && !zone
    /* Sans réseau (ou coupure en route) : le relevé reste sur le téléphone, dans la file, et le DIT en vue. */
    const garderSurLeTelephone = async () => {
      await fileReleve.garder(corps, releve.id)
      setReleve((r) => ({ ...r, releveLe: corps.releve_le }))
      setMessage({
        texte: `Relevé gardé sur ce téléphone : il partira au retour du réseau.${panAEcrire
          ? ` ${[penteAEcrire && 'La pente du toit', azimutAEcrire && 'L’orientation du toit'].filter(Boolean).join(' et ')
          } s’enregistrera au prochain « Terminer le relevé » avec du réseau.` : ''}`,
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
  return (
    <div className="cal-tel" data-testid="cal-releve">
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

      <div className="cal-tel-corps">
        <TuilesPhotos photos={photos.photos} genresEnFile={photos.genresEnFile} enCours={photos.enCours}
          message={photos.message} onDeposer={deposer} />

        <section className="cal-tel-section" data-testid="releve-mesures">
          <h2 className="cal-tel-h">Mesures</h2>
          <div className="cal-tel-deux">
            <ChampDecimal id="releve-longueur" testId="releve-longueur" libelle="Longueur" unite="m"
              valeur={valeurChamp(LONGUEUR)} onChange={(v) => majMesure(LONGUEUR, v)} />
            <ChampDecimal id="releve-largeur" testId="releve-largeur" libelle="Largeur" unite="m"
              valeur={valeurChamp(LARGEUR)} onChange={(v) => majMesure(LARGEUR, v)} />
          </div>

          <CarteMesure testId="releve-pente" libelle="Pente du toit"
            valeur={carteP.valeur ?? 'à mesurer'} bouton={carteP.bouton} onBouton={mesurerPente} desactive={!zone}>
            {carteP.aide && <p className="cal-tel-aide" data-testid="releve-pente-aide">{carteP.aide}</p>}
            {sansPan && <p className="cal-tel-aide" data-testid="releve-pente-sans-pan">Aucun pan dessiné : la pente s’enregistre sur un pan, tracez le toit dans l’atelier.</p>}
            {motifs.pente && <p role="alert" className="cal-tel-aide">{motifs.pente}</p>}
            {manuel.pente && zone && (
              <ChampDecimal id="releve-pente-main" testId="releve-pente-main" libelle="Pente saisie à la main" unite="°" compact
                valeur={pente && !pente.capteur ? versVirgule(pente.saisie) : ''}
                onChange={(v) => { const n = Number(versPoint(v)); setPente(v.trim() === '' || !Number.isFinite(n) ? null : { degres: n, capteur: false, saisie: versPoint(v) }) }} />
            )}
          </CarteMesure>

          <CarteMesure testId="releve-orientation" libelle="Le toit regarde vers"
            valeur={direction ? `${direction}${aMain ? ' · saisie à la main' : ''}` : 'à relever'}
            bouton="Boussole" onBouton={mesurerAzimut}>
            {motifs.azimut && <p role="alert" className="cal-tel-aide">{motifs.azimut}</p>}
            {manuel.azimut && (
              <ChampDecimal id="releve-azimut-main" testId="releve-azimut-main" libelle="Orientation saisie à la main (0 = nord)" unite="°" compact
                valeur={versVirgule(azimutMain !== '' ? azimutMain : azimutDuPan)}
                onChange={(v) => { setAzimutMain(versPoint(v)); setCapteurLu(false) }} />
            )}
            {azimutDeg !== '' && !aMain && (
              <ChampDecimal id="releve-precision" testId="releve-precision" libelle="Précision de la boussole (±)" unite="°" compact
                valeur={versVirgule(precisionDeg)} onChange={(v) => setPrecisionDeg(versPoint(v))} />
            )}
            {erreurs.precision_azimut_deg && <p role="alert" className="cal-tel-erreur" data-testid="releve-erreur-precision">{erreurs.precision_azimut_deg}</p>}
          </CarteMesure>
          {Object.keys(erreurs).filter((c) => c.startsWith('chaines')).map((c) => (
            <p key={c} role="alert" className="cal-tel-erreur">{erreurs[c]}</p>
          ))}
        </section>

        {(photos.enAttente > 0 || fileReleve.enAttente || !enLigne) && (
          <section className="cal-tel-note" data-testid="releve-note-hors-ligne">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 21h14" /></svg>
            <span>{noteHorsLigne(photos.enAttente, enLigne, fileReleve.enAttente)}</span>
          </section>
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
  )
}
