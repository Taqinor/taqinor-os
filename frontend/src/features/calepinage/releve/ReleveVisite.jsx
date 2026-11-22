import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useDocumentCalepinage from '../useDocumentCalepinage'
import { panParDefaut, zonesDuDocument } from '../SaisiePente.helpers'
import { demarrerCapteurs, lireInclinaison, lireVisee, arreter as arreterCapteurs } from '../capteursTelephone'
import { messageRefus, refusServeur } from '../commun/refusServeur'
import { lireConflit } from '../conflitEcriture'
import { titreProjet } from '../atelier/coque/projet'
import { Icone } from '../atelier/coque/primitives'
import { champsDuReleve, corpsDuReleve, validerAvantEnvoi } from './corpsReleve'
import {
  LARGEUR, LONGUEUR, avecMesure, chainesSaisies, dateDuJour, degres, mesureDesChaines, mesureDuCapteur,
  noteHorsLigne, nomDirection, provenancePente, versPoint, versVirgule,
} from './releveTelephone'
import usePhotosReleve from './usePhotosReleve'
import TuilesPhotos from './TuilesPhotos'
import { CarteMesure, ChampDecimal } from './CarteMesure'
import '../../../styles/calepinage/58-telephone.css'

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
  const [azimutAMain, setAzimutAMain] = useState(false)
  const [pente, setPente] = useState(null) // { degres, capteur } — en attente de « Terminer »
  const [capteursActifs, setCapteursActifs] = useState(false)
  const [manuel, setManuel] = useState({ pente: false, azimut: false })
  const [motifs, setMotifs] = useState({})
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState(false)
  const [message, setMessage] = useState(null)

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
    Promise.resolve(calepinageApi.calepinages.designContext?.(id)).then((res) => {
      if (vivant) setTitre(titreProjet({ calepinageTitre: (res?.data?.calepinage?.titre ?? '').trim(), calepinageId: id, contexte: res?.data }))
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
    if (m && m.azimutDeg !== null) { setAzimutDeg(String(m.azimutDeg)); setAzimutAMain(false) }
  }

  const penteAffichee = pente ? pente.degres : zone?.pitchDeg
  const libellePente = pente ? (pente.capteur ? 'mesurée' : 'saisie à la main') : provenancePente(zone)
  const direction = nomDirection(azimutDeg)

  /* La pente du PAN, écrite exactement comme `SaisiePente` (primitive par section). */
  const enregistrerPente = async () => {
    const v = pente.degres
    const champs = { pitchDeg: v, pitchSource: pente.capteur ? { mode: 'degres', degres: v, provenance: 'telephone' } : { mode: 'degres', degres: v } }
    const res = await calepinageApi.calepinages.enregistrerSectionLayout(id, {
      cle: 'zones', zone_id: zone.id, champs, base_empreinte: doc.empreinte,
    })
    const mises = res?.data?.roof_layout?.zones
      ?? zonesDuDocument(doc.document).map((z) => (String(z.id) === String(zone.id) ? { ...z, ...champs } : z))
    doc.appliquerSection('zones', mises, res?.data?.empreinte_document ?? null)
    setPente(null)
  }

  const terminer = async () => {
    const azimut = versPoint(azimutDeg)
    const precision = versPoint(precisionDeg)
    const fautes = validerAvantEnvoi(releve.chaines, azimut, precision)
    setErreurs(fautes)
    setMessage(null)
    if (Object.keys(fautes).length) return
    setEnCours(true)
    try {
      if (pente && zone && doc.etat === 'ok') await enregistrerPente()
      const corps = corpsDuReleve({
        releveLe: releve.releveLe || dateDuJour(), chaines: releve.chaines, azimutDeg: azimut,
        precisionDeg: precision, notes: releve.notes, photoIds: releve.photoIds,
      })
      const res = await (releve.id
        ? calepinageApi.calepinages.corrigerReleve(id, releve.id, corps)
        : calepinageApi.calepinages.enregistrerReleve(id, corps))
      const nouvelId = res?.data?.releve?.id
      setReleve((r) => ({ ...r, id: nouvelId ?? r.id, releveLe: corps.releve_le }))
      setMessage(releve.id ? 'Relevé corrigé.' : 'Relevé enregistré.')
    } catch (err) {
      if (!err?.response) setMessage('Pas de réseau : les mesures ne sont pas enregistrées. Terminez le relevé au retour du réseau.')
      else if (lireConflit(err)?.documentModifie) { setMessage('Le calepinage a changé ailleurs : il est relu, recommencez.'); doc.recharger() } else {
        const { champs } = refusServeur(err)
        setErreurs(champs)
        setMessage(messageRefus(err, 'Le relevé a été refusé par le serveur.'))
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
        {(!enLigne || photos.enAttente > 0) && <PastilleHorsLigne />}
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
            valeur={penteAffichee === undefined || penteAffichee === null ? 'à mesurer' : `${degres(penteAffichee)} · ${libellePente}`}
            bouton={penteAffichee === undefined || penteAffichee === null ? 'Mesurer' : 'Mesurer encore'}
            onBouton={mesurerPente} desactive={!zone}>
            {sansPan && <p className="cal-tel-aide" data-testid="releve-pente-sans-pan">Aucun pan dessiné : la pente s’enregistre sur un pan, tracez le toit dans l’atelier.</p>}
            {motifs.pente && <p role="alert" className="cal-tel-aide">{motifs.pente}</p>}
            {manuel.pente && zone && (
              <ChampDecimal id="releve-pente-main" testId="releve-pente-main" libelle="Pente saisie à la main" unite="°" compact
                valeur={pente && !pente.capteur ? versVirgule(pente.saisie) : ''}
                onChange={(v) => { const n = Number(versPoint(v)); setPente(v.trim() === '' || !Number.isFinite(n) ? null : { degres: n, capteur: false, saisie: versPoint(v) }) }} />
            )}
          </CarteMesure>

          <CarteMesure testId="releve-orientation" libelle="Le toit regarde vers"
            valeur={direction ? `${direction}${azimutAMain ? ' · saisie à la main' : ''}` : 'à relever'}
            bouton="Boussole" onBouton={mesurerAzimut}>
            {motifs.azimut && <p role="alert" className="cal-tel-aide">{motifs.azimut}</p>}
            {manuel.azimut && (
              <ChampDecimal id="releve-azimut-main" testId="releve-azimut-main" libelle="Orientation saisie à la main (0 = nord)" unite="°" compact
                valeur={azimutAMain ? versVirgule(azimutDeg) : ''}
                onChange={(v) => { setAzimutDeg(versPoint(v)); setAzimutAMain(true) }} />
            )}
            {(azimutDeg !== '' || manuel.azimut) && (
              <ChampDecimal id="releve-precision" testId="releve-precision" libelle="Précision de la boussole (±)" unite="°" compact
                valeur={versVirgule(precisionDeg)} onChange={(v) => setPrecisionDeg(versPoint(v))} />
            )}
            {erreurs.precision_azimut_deg && <p role="alert" className="cal-tel-erreur" data-testid="releve-erreur-precision">{erreurs.precision_azimut_deg}</p>}
          </CarteMesure>
          {Object.keys(erreurs).filter((c) => c.startsWith('chaines')).map((c) => (
            <p key={c} role="alert" className="cal-tel-erreur">{erreurs[c]}</p>
          ))}
        </section>

        {(photos.enAttente > 0 || !enLigne) && (
          <section className="cal-tel-note" data-testid="releve-note-hors-ligne">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 21h14" /></svg>
            <span>{noteHorsLigne(photos.enAttente, enLigne)}</span>
          </section>
        )}
        {message && <p role="status" className="cal-tel-message" data-testid="releve-message">{message}</p>}
      </div>

      <footer className="cal-tel-pied">
        <Link to={`/calepinage/${id}`} className="cal-tel-pied-secondaire" data-testid="releve-voir-3d">Voir en 3D</Link>
        <button type="button" className="cal-tel-pied-or" onClick={terminer} disabled={enCours} data-testid="releve-terminer">
          {enCours ? 'Enregistrement…' : 'Terminer le relevé'}
        </button>
      </footer>
    </div>
  )
}
