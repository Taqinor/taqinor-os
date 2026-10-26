import { useCallback, useEffect, useRef, useState } from 'react'
import { LocateFixed, ShieldAlert, ShieldCheck, Info } from 'lucide-react'
import { Button } from '../../ui'
import installationsApi from '../../api/installationsApi'

/* ============================================================================
   REVUE CHANTIER 26/10/2026 — le suivi devient AUTOMATIQUE (fondateur : « sans
   qu'ils aient rien à faire »), dans le cadre de la loi 09-08 et de la
   délibération CNDP 17-2014 (pas de suivi caché) :
     * `gps_consentement === 'actif'` (consentement posé par le responsable ET
       notice acceptée par le technicien) + intervention « en route » / « sur
       site » ⇒ `watchPosition` démarre tout seul (même throttle 60 s ; haute
       précision seulement sur site) et un BANDEAU visible le dit ;
     * hors ligne, les positions sont gardées en mémoire (200 max, copie dans
       `localStorage`) puis envoyées par lots de 20 (`pingPositionsBatch`), du
       plus ancien au plus récent et AVANT le relevé live suivant ;
     * `'a_accepter'` ⇒ carte de la notice + bouton « J'ai lu et j'accepte » ;
     * `'absent'` / `'revoque'` ⇒ une ligne discrète, aucun suivi.
   Nom de fichier/composant conservés : « Ma journée » l'importe tel quel.
   Coexiste avec le pointage manuel F6 (jamais remplacé). Remplace
   l'interrupteur NTMOB9 (opt-in par session, OFF par défaut) : le consentement
   DURABLE (`GpsConsentRecord`) reste posé par un responsable — ce composant
   n'en pose jamais ; il ne fait que recueillir l'ACCUSÉ DE RÉCEPTION de la
   notice par le technicien lui-même.
   ========================================================================== */

// Session ouverte = le technicien est en déplacement ou sur place (F3).
const STATUTS_SESSION_OUVERTE = ['en_route', 'sur_site']

// Throttle : au plus une remontée par minute (watchPosition peut déclencher
// bien plus souvent selon l'appareil) — jamais un ping par évènement brut.
const PING_MIN_INTERVAL_MS = 60 * 1000

// Rattrapage hors-ligne : au plus 200 positions gardées en mémoire (les plus
// anciennes tombent), envoyées par lots de 20 (borne serveur de `ping-lot`).
const TAMPON_MAX = 200
const LOT_TAILLE = 20

// Revue 26/10/2026 (F3) — le tampon est recopié dans `localStorage` sous
// `gps-tampon-<id>` : il survit à un rechargement ET au démontage du composant
// quand la session se ferme (« terminée ») hors ligne. Le serveur accepte ce
// rattrapage tant que les points datent d'avant la fin de la session.
const PREFIXE_TAMPON = 'gps-tampon-'
// Ids dont un composant monté gère lui-même le tampon.
const tamponsMontes = new Set()
let attenteEnCours = false

function estHorsLigne() {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

function lireTampon(id) {
  try {
    const brut = JSON.parse(window.localStorage.getItem(PREFIXE_TAMPON + id) || '[]')
    return Array.isArray(brut) ? brut : []
  } catch { return [] }
}

function ecrireTampon(id, points) {
  try {
    if (points.length) window.localStorage.setItem(PREFIXE_TAMPON + id, JSON.stringify(points))
    else window.localStorage.removeItem(PREFIXE_TAMPON + id)
  } catch { /* stockage indisponible (navigation privée) : tampon mémoire seul */ }
}

// Envoie `tampon` (muté sur place) par lots de 20, du plus ancien au plus
// récent (F2 : le serveur juge chaque franchissement d'après le relevé
// précédent). Un refus serveur (4xx) jette le lot (le renvoyer en boucle ne
// servirait à rien), une coupure garde le reste. `persister` après chaque lot.
async function envoyerTampon(id, tampon, persister) {
  tampon.sort((a, b) => String(a.captured_at).localeCompare(String(b.captured_at)))
  while (tampon.length && !estHorsLigne()) {
    const lot = tampon.slice(0, LOT_TAILLE)
    try {
      await installationsApi.pingPositionsBatch(id, lot)
    } catch (err) {
      if (!err?.response) break // réseau : on garde, on réessaiera
    }
    tampon.splice(0, lot.length)
    persister()
  }
}

/** Positions restées en attente pour une intervention dont la session s'est
 *  fermée hors ligne (composant démonté) : envoyées par « Ma journée » à
 *  l'ouverture et au retour du réseau. Ignore les tampons d'un suivi monté. */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé avec le tampon qu'il vide (D-ENF22)
export async function viderTamponsGpsEnAttente() {
  if (attenteEnCours || typeof window === 'undefined' || estHorsLigne()) return
  attenteEnCours = true
  try {
    const ids = []
    try {
      for (let i = 0; i < window.localStorage.length; i += 1) {
        const cle = window.localStorage.key(i)
        if (cle?.startsWith(PREFIXE_TAMPON)) ids.push(cle.slice(PREFIXE_TAMPON.length))
      }
    } catch { return }
    for (const id of ids) {
      if (!/^\d+$/.test(id) || tamponsMontes.has(Number(id))) continue
      const tampon = lireTampon(id)
      await envoyerTampon(Number(id), tampon, () => ecrireTampon(id, tampon))
      if (!tampon.length) ecrireTampon(id, tampon)
    }
  } finally { attenteEnCours = false }
}

/** Notice d'information (loi 09-08 art. 5), telle que servie par le serveur. */
export function NoticeGeoloc({ notice }) {
  if (!notice) return null
  const liste = (titre, items) => (items?.length ? (
    <div>
      <p className="font-medium">{titre}</p>
      <ul className="list-disc pl-5">
        {items.map((t) => <li key={t}>{t}</li>)}
      </ul>
    </div>
  ) : null)
  return (
    <div className="flex flex-col gap-2 text-[12px]" data-testid="gps-notice">
      <p>{notice.texte}</p>
      {notice.responsable && <p><span className="font-medium">Responsable : </span>{notice.responsable}</p>}
      {liste('Pourquoi', notice.finalites)}
      {liste('Données relevées', notice.donnees)}
      {liste('Qui les voit', notice.destinataires)}
      <p>
        <span className="font-medium">Conservation : </span>
        {notice.retention_jours} jours, puis suppression automatique.
      </p>
      {liste('Vos droits', notice.droits)}
      <p className="text-muted-foreground">
        Récépissé CNDP : {notice.recepisse_cndp} · notice {notice.version}
      </p>
    </div>
  )
}

/** Charge la notice à la demande (jamais au montage du suivi actif). */
function useNotice(charger) {
  const [notice, setNotice] = useState(null)
  useEffect(() => {
    if (!charger || notice) return undefined
    const appel = installationsApi.getMonConsentementGps?.()
    if (!appel) return undefined
    let vivant = true
    appel
      .then((r) => { if (vivant) setNotice(r?.data?.notice ?? null) })
      .catch(() => {})
    return () => { vivant = false }
  }, [charger, notice])
  return notice
}

/** Carte « J'ai lu et j'accepte » — accusé de réception UNIQUE. */
function CarteAccord({ onAccepte }) {
  const notice = useNotice(true)
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  const accepter = async () => {
    setBusy(true); setErreur(null)
    try {
      await installationsApi.accepterConsentementGps()
      onAccepte()
    } catch {
      setErreur("Accord non enregistré — réessayez ou prévenez votre responsable.")
    } finally { setBusy(false) }
  }
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3"
      data-testid="gps-carte-accord">
      <p className="flex items-center gap-1.5 text-[13px] font-medium">
        <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
        {notice?.titre || 'Information sur la géolocalisation pendant vos interventions'}
      </p>
      <NoticeGeoloc notice={notice} />
      {erreur && <p className="text-[12px] text-warning" role="alert">{erreur}</p>}
      <Button size="sm" onClick={accepter} loading={busy} disabled={busy}>
        J&apos;ai lu et j&apos;accepte
      </Button>
    </div>
  )
}

export default function GpsTrackingToggle({ intervention }) {
  // L'accord donné ICI bascule le suivi sans attendre le rechargement de la
  // tournée (le serveur, lui, le sait déjà).
  const [accepteIci, setAccepteIci] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [arrete, setArrete] = useState(false)
  const [pourquoi, setPourquoi] = useState(false)
  const notice = useNotice(pourquoi)
  const dernierEnvoiRef = useRef(0)
  const tamponRef = useRef([])
  const envoiLotRef = useRef(false)

  const statut = intervention?.statut
  const sessionOuverte = STATUTS_SESSION_OUVERTE.includes(statut) && !intervention?.annulee
  const interventionId = intervention?.id
  const consentement = (accepteIci && intervention?.gps_consentement === 'a_accepter')
    ? 'actif' : intervention?.gps_consentement
  const geoDisponible = typeof navigator !== 'undefined' && !!navigator.geolocation
  const suivi = sessionOuverte && consentement === 'actif' && geoDisponible && !arrete

  const garder = useCallback((point) => {
    const t = tamponRef.current
    t.push(point)
    if (t.length > TAMPON_MAX) t.splice(0, t.length - TAMPON_MAX)
    if (interventionId) ecrireTampon(interventionId, t)
  }, [interventionId])

  // Vide le tampon (mémoire + copie locale) par lots de 20, chronologique.
  const viderTampon = useCallback(async () => {
    if (envoiLotRef.current || !interventionId) return
    envoiLotRef.current = true
    try {
      await envoyerTampon(interventionId, tamponRef.current,
        () => ecrireTampon(interventionId, tamponRef.current))
    } finally { envoiLotRef.current = false }
  }, [interventionId])

  // F3 — au montage : reprend le tampon laissé par une page rechargée et
  // l'envoie ; au démontage (session fermée) : dernier envoi best-effort —
  // ce qui ne part pas reste dans `localStorage` pour « Ma journée ».
  useEffect(() => {
    if (!interventionId) return undefined
    tamponsMontes.add(interventionId)
    const restaure = lireTampon(interventionId)
    if (restaure.length) {
      tamponRef.current = [...restaure, ...tamponRef.current]
      viderTampon()
    }
    return () => {
      tamponsMontes.delete(interventionId)
      viderTampon()
    }
  }, [interventionId, viderTampon])

  // Appelé par le callback `watchPosition` (asynchrone, jamais synchrone
  // dans le corps de l'effet) — seul endroit où `Date.now()` est lu.
  const surPosition = useCallback((position) => {
    const maintenant = Date.now()
    if (maintenant - dernierEnvoiRef.current < PING_MIN_INTERVAL_MS) return
    dernierEnvoiRef.current = maintenant
    const point = {
      lat: position.coords.latitude,
      lng: position.coords.longitude,
      accuracy_m: position.coords.accuracy ?? null,
      captured_at: new Date(position.timestamp || maintenant).toISOString(),
    }
    if (estHorsLigne()) { garder(point); return }
    const envoyerLive = () => installationsApi.pingPosition({ ...point, intervention: interventionId })
      .then(() => { if (tamponRef.current.length) viderTampon() })
      .catch((err) => {
        const code = err?.response?.status
        if (!code) { garder(point); return } // coupure : rattrapage plus tard
        if (code === 403 || code === 409) {
          setArrete(true)
          setErreur(code === 403
            ? "Suivi de position refusé par le serveur — prévenez votre responsable."
            : "Suivi de position arrêté : l'intervention n'est plus en cours.")
        }
      })
    if (!tamponRef.current.length) { envoyerLive(); return }
    // F2 — les relevés plus anciens du tampon partent AVANT le relevé live.
    // S'il reste du tampon (coupure, ou envoi déjà en cours), le relevé live
    // le rejoint en queue : l'ordre chronologique est gardé.
    viderTampon().then(() => {
      if (tamponRef.current.length) garder(point)
      else envoyerLive()
    })
  }, [interventionId, garder, viderTampon])

  useEffect(() => {
    if (!suivi) return undefined
    const watchId = navigator.geolocation.watchPosition(
      surPosition,
      () => setErreur(
        'Position indisponible — vérifiez que la géolocalisation est autorisée.'),
      // Haute précision (GPS, plus gourmande) seulement sur le chantier.
      { enableHighAccuracy: statut === 'sur_site', maximumAge: 30000 },
    )
    // Jamais en tâche de fond permanente : coupé dès que la session se ferme
    // (statut hors liste), que le consentement tombe, ou au démontage.
    return () => navigator.geolocation.clearWatch(watchId)
  }, [suivi, statut, surPosition])

  // Retour du réseau : on vide le tampon hors-ligne.
  useEffect(() => {
    if (!suivi || typeof window === 'undefined') return undefined
    const enLigne = () => { viderTampon() }
    window.addEventListener('online', enLigne)
    return () => window.removeEventListener('online', enLigne)
  }, [suivi, viderTampon])

  if (!sessionOuverte || !consentement) return null

  const ref = intervention?.installation_reference || `#${interventionId}`

  if (consentement === 'a_accepter') {
    return <CarteAccord onAccepte={() => setAccepteIci(true)} />
  }

  if (consentement !== 'actif') {
    return (
      <p className="flex items-center gap-1 text-[12px] text-muted-foreground"
        data-testid="gps-non-active">
        <LocateFixed className="size-3.5" aria-hidden="true" />
        Suivi de position non activé pour vous
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-primary/30 bg-primary/5 p-2.5"
      data-testid="gps-tracking-toggle" role="status">
      <p className="flex flex-wrap items-center gap-1.5 text-[12px] font-medium">
        <LocateFixed className="size-4 text-primary" aria-hidden="true" />
        Position partagée avec votre responsable — intervention {ref}
        <button type="button" className="inline-flex items-center gap-0.5 text-primary underline"
          onClick={() => setPourquoi((v) => !v)} aria-expanded={pourquoi}>
          <Info className="size-3.5" aria-hidden="true" /> Pourquoi ?
        </button>
      </p>
      {pourquoi && <NoticeGeoloc notice={notice} />}
      {!geoDisponible && (
        <p className="flex items-center gap-1 text-[12px] text-warning">
          <ShieldAlert className="size-3.5" aria-hidden="true" />
          Géolocalisation indisponible sur cet appareil — utilisez le pointage manuel.
        </p>
      )}
      {geoDisponible && erreur && (
        <p className="flex items-center gap-1 text-[12px] text-warning">
          <ShieldAlert className="size-3.5" aria-hidden="true" /> {erreur}
        </p>
      )}
    </div>
  )
}

/** « Mes positions du jour » (droit d'accès, loi 09-08 art. 7) — chargé
 *  seulement quand le technicien ouvre le volet. */
export function MesPositionsDuJour() {
  const [ouvert, setOuvert] = useState(false)
  const [positions, setPositions] = useState(null)
  const [erreur, setErreur] = useState(false)
  useEffect(() => {
    if (!ouvert || positions) return undefined
    let vivant = true
    const appel = installationsApi.getMesPositions?.()
    if (!appel) return undefined
    appel
      .then((r) => { if (vivant) setPositions(Array.isArray(r?.data) ? r.data : []) })
      .catch(() => { if (vivant) setErreur(true) })
    return () => { vivant = false }
  }, [ouvert, positions])
  return (
    <details className="rounded-lg border border-border bg-card p-3 text-[12px]"
      data-testid="mes-positions-du-jour"
      onToggle={(e) => setOuvert(e.currentTarget.open)}>
      <summary className="cursor-pointer font-medium">Mes positions du jour</summary>
      <div className="pt-2">
        {erreur && <p className="text-warning">Chargement impossible.</p>}
        {!erreur && positions === null && ouvert && <p className="text-muted-foreground">Chargement…</p>}
        {positions?.length === 0 && (
          <p className="text-muted-foreground">Aucune position relevée aujourd&apos;hui.</p>
        )}
        {positions?.length > 0 && (
          <ul className="flex flex-col gap-0.5">
            {positions.map((p) => (
              <li key={p.id}>
                {new Date(p.captured_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                {' — '}
                {p.distance_site_km != null
                  ? `${p.distance_site_km} km du chantier${p.hors_perimetre ? ' (hors périmètre)' : ''}`
                  : `${Number(p.lat).toFixed(4)}, ${Number(p.lng).toFixed(4)}`}
              </li>
            ))}
          </ul>
        )}
        <p className="pt-1 text-muted-foreground">
          Conservées 30 jours puis supprimées automatiquement.
        </p>
      </div>
    </details>
  )
}
