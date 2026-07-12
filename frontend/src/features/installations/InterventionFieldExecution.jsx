// F5–F8 — panneaux d'exécution terrain d'une intervention, montés dans le
// volet détail de la page Interventions :
//   * F5 — liste de préparation (matériel du chantier + outils du kit), cases
//     « chargé », pourcentage, confirmation « Tout est chargé » (requise pour
//     quitter « À préparer »), drapeau « manquant » → bon de commande brouillon.
//   * F6 — départ-dépôt / check-in GPS (géolocalisation navigateur, aucun
//     service externe) / retour, et distance-au-site.
//   * F7/F8 — capture guidée par shot list (avant/pendant/après), galerie, et
//     checklist des photos obligatoires manquantes (garde « Terminée »).
// Tout le texte est en français ; les identifiants techniques restent en anglais.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle2, MapPin, Navigation, Truck, Camera, Trash2, AlertTriangle,
  PackageCheck, ShoppingCart, Images, RotateCw, Upload, X, Phone, UserPlus,
  ShieldCheck, Wrench, Clock,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import savApi from '../../api/savApi'
import {
  Button, Badge, Spinner, Checkbox, Progress, toast,
} from '../../ui'
import { formatDateTime, formatDate } from '../../lib/format'
import { telHref } from '../../lib/contactLinks'
import { downloadVCard } from '../../lib/vcard'
import { withOfflineFallback, FIELD_OPS } from './offline/fieldOutbox'
import CameraCapture from '../pwa/CameraCapture'
import { compressImage } from '../../ui/file-utils'
import {
  makeCapturedPage, rotatePageInList, removePageFromList, rotateImageBlob,
} from '../ged/capture'
import { garantieLabel, garantieColor } from '../sav/equipement'
import { TICKET_OPEN_STATUSES, TICKET_STATUS_LABELS } from '../sav/ticketStatuses'

// N91/F21 — message commun quand une action a été MISE EN FILE (hors-ligne) :
// elle se synchronisera toute seule au retour du réseau.
const QUEUED_MSG = 'Hors ligne — enregistré, synchro au retour du réseau.'

// VX105 — un upload photo/mémo n'est PAS filé (pas d'outbox binaire — territoire
// FG386) : un échec réseau signifie que la photo est PERDUE si le technicien ne
// la reprend pas. Le message d'échec doit donc être DISTINCT du « mis en file »
// de succès du panneau voisin, et persistant (jamais l'illusion d'un envoi).
function isNetworkFailure(err) {
  return (typeof navigator !== 'undefined' && navigator.onLine === false) || !err?.response
}
function photoUploadError(err) {
  if (isNetworkFailure(err)) {
    toast.error(
      'Photo NON envoyée — réseau indisponible. Reprenez-la au retour du réseau.',
      { duration: Infinity })
    return
  }
  toast.error(err?.response?.data?.detail ?? 'Téléversement impossible.')
}

const PHASES = [
  ['avant', 'Avant'],
  ['pendant', 'Pendant'],
  ['apres', 'Après'],
]

// ── F5 — Liste de préparation ────────────────────────────────────────────────
export function PreparationPanel({ intervention, onChanged }) {
  const id = intervention.id
  const navigate = useNavigate()
  const [prep, setPrep] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => installationsApi.getPreparation(id)
    .then((r) => setPrep(r.data))
    .catch(() => setPrep(null))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  const toggleMateriel = async (ligne, charge) => {
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.cocherMateriel(id, ligne.id, charge),
        FIELD_OPS.COCHER_MATERIEL, { intervention: id, ligne: ligne.id, charge })
      if (r.queued) {
        // Hors ligne : reflète l'état localement (l'op est filée) et resync au
        // retour réseau.
        setPrep((p) => p && ({
          ...p,
          materiel: (p.materiel ?? []).map((l) => l.id === ligne.id ? { ...l, charge } : l),
        }))
        toast.success(QUEUED_MSG)
      } else { setPrep(r.data) }
      onChanged?.()
    } catch { toast.error('Mise à jour impossible.') } finally { setBusy(false) }
  }
  const toggleOutil = async (ligne, coche) => {
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.cocherOutil(id, ligne.id, coche),
        FIELD_OPS.COCHER_OUTIL, { intervention: id, ligne: ligne.id, coche })
      if (r.queued) {
        setPrep((p) => p && ({
          ...p,
          outils: (p.outils ?? []).map((l) => l.id === ligne.id ? { ...l, coche } : l),
        }))
        toast.success(QUEUED_MSG)
      } else { setPrep(r.data) }
      onChanged?.()
    } catch { toast.error('Mise à jour impossible.') } finally { setBusy(false) }
  }
  const confirmer = async () => {
    setBusy(true)
    try {
      const r = await installationsApi.confirmerCharge(id)
      setPrep(r.data); onChanged?.()
      toast.success('Préparation confirmée — « Tout est chargé ».')
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Toutes les lignes doivent être cochées.')
    } finally { setBusy(false) }
  }
  const commander = async () => {
    setBusy(true)
    try {
      const r = await installationsApi.commanderManques(id)
      toast.success(`Bon de commande brouillon créé (${r.data.nb_lignes} ligne(s)).`)
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Commande impossible.')
    } finally { setBusy(false) }
  }

  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4" /> Chargement de la préparation…
    </p>
  )
  if (!prep) return (
    <p className="py-4 text-sm text-muted-foreground">Préparation indisponible.</p>
  )

  const completion = prep.completion ?? 0
  const allChecked = (prep.materiel ?? []).every((m) => m.charge)
    && (prep.outils ?? []).every((o) => o.coche)

  return (
    <div className="flex flex-col gap-4 py-2 text-sm">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Préparation</span>
          <span className="font-medium">{completion}%</span>
        </div>
        <Progress value={completion} />
      </div>

      {/* ── Matériel (nomenclature gelée du chantier) ── */}
      <div className="flex flex-col gap-1.5">
        <span className="text-muted-foreground">Matériel</span>
        {(prep.materiel ?? []).length === 0
          ? <span className="text-muted-foreground">Aucun matériel à préparer.</span>
          : (prep.materiel ?? []).map((m) => (
            <label key={m.id} className="flex items-center gap-2 rounded border border-border p-2">
              <Checkbox checked={m.charge} disabled={busy}
                onCheckedChange={(v) => toggleMateriel(m, !!v)} />
              <span className="flex-1">{m.designation}</span>
              <Badge tone="neutral">× {m.quantite_requise}</Badge>
              {m.manquant && (
                <Badge tone="danger" title={`Manque ${m.quantite_manquante}`}>
                  <AlertTriangle className="size-3" aria-hidden="true" /> Manquant
                </Badge>
              )}
            </label>
          ))}
      </div>

      {/* ── Outils (kit d'outillage) ── */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Outillage</span>
          {prep.kit_nom && <Badge tone="info">{prep.kit_nom}</Badge>}
        </div>
        {(prep.outils ?? []).length === 0
          ? <span className="text-muted-foreground">Aucun kit d'outillage sélectionné.</span>
          : (prep.outils ?? []).map((o) => (
            <label key={o.id} className="flex items-center gap-2 rounded border border-border p-2">
              <Checkbox checked={o.coche} disabled={busy}
                onCheckedChange={(v) => toggleOutil(o, !!v)} />
              <span className="flex-1">{o.libelle}</span>
            </label>
          ))}
      </div>

      {/* ── Manques → bon de commande brouillon ── */}
      {(prep.nb_manques ?? 0) > 0 && (
        <Button size="sm" variant="outline" onClick={commander} disabled={busy}>
          <PackageCheck className="size-4" aria-hidden="true" />
          Commander les manques ({prep.nb_manques})
        </Button>
      )}

      {/* VX227 — un besoin NON prévu par la nomenclature part vers une nouvelle
          demande d'achat, chantier pré-sélectionné (le tap ouvre la DA avec le
          contexte terrain déjà renseigné, sans ressaisie). */}
      {intervention.installation && (
        <Button size="sm" variant="ghost" disabled={busy}
          onClick={() => navigate(
            `/chantiers/demandes-achat?chantier=${intervention.installation}&intervention=${id}`)}>
          <ShoppingCart className="size-4" aria-hidden="true" />
          Autre besoin non prévu → Nouvelle demande d'achat
        </Button>
      )}

      {/* ── Confirmation « Tout est chargé » ── */}
      <Button size="sm" onClick={confirmer}
        disabled={busy || prep.tout_charge || !allChecked}
        variant={prep.tout_charge ? 'success' : 'default'}>
        {prep.tout_charge ? (
          <><CheckCircle2 className="size-4" aria-hidden="true" /> Tout est chargé</>
        ) : 'Confirmer « Tout est chargé »'}
      </Button>
      {!prep.tout_charge && (
        <p className="text-[11.5px] text-muted-foreground">
          La confirmation « Tout est chargé » est requise avant de quitter
          « À préparer ».
        </p>
      )}
    </div>
  )
}

// ── VX107 — Résumé client LECTURE SEULE (garantie + dernier ticket SAV +
//    mise en service). « C'est encore sous garantie ? Vous êtes déjà venus ? »
//    répondu sur site sans appeler le bureau ni ouvrir la fiche de 1 600 lignes.
//    Mêmes appels savApi déjà en prod (InstallationDetail) — aucune route
//    nouvelle, ZÉRO écriture. (Migre vers RecordShell quand ARC46 atterrira.)
function ClientInfoPanel({ intervention }) {
  const installationId = intervention.installation
  const [equipements, setEquipements] = useState([])
  const [tickets, setTickets] = useState([])
  const [dateMes, setDateMes] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    if (!installationId) { setLoading(false); return undefined }
    let alive = true
    setLoading(true)
    Promise.allSettled([
      savApi.getEquipements({ installation: installationId }),
      savApi.getTickets({ installation: installationId, ouvert: 'tous' }),
      installationsApi.getInstallation(installationId),
    ]).then(([eq, tk, inst]) => {
      if (!alive) return
      if (eq.status === 'fulfilled') setEquipements(eq.value.data?.results ?? eq.value.data ?? [])
      if (tk.status === 'fulfilled') setTickets(tk.value.data?.results ?? tk.value.data ?? [])
      if (inst.status === 'fulfilled') setDateMes(inst.value.data?.date_mise_en_service ?? null)
    }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [installationId])

  if (!installationId) return null
  if (loading) return (
    <div className="flex items-center gap-2 rounded border border-border bg-muted/40 p-2 text-[12px] text-muted-foreground">
      <Spinner className="size-3.5" /> Chargement des infos client…
    </div>
  )

  const mainEq = equipements[0]
  // Dernier ticket OUVERT (le plus récent) — jamais un ticket clos.
  const lastOpen = [...tickets]
    .filter((t) => TICKET_OPEN_STATUSES.includes(t.statut))
    .sort((a, b) => String(b.date_creation ?? '').localeCompare(String(a.date_creation ?? '')))[0]

  return (
    <div className="flex flex-col gap-1.5 rounded border border-border bg-muted/40 p-2 text-[12.5px]">
      <span className="font-medium">Infos client</span>
      {/* Garantie du matériel principal. */}
      <div className="flex items-center gap-1.5">
        <ShieldCheck className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        {mainEq ? (
          <span className="flex flex-wrap items-center gap-1">
            <span className="text-muted-foreground">{mainEq.designation || mainEq.produit_nom || 'Matériel'} :</span>
            <span style={{ color: garantieColor(mainEq) }} className="font-medium">
              {garantieLabel(mainEq)}
            </span>
            {equipements.length > 1 && (
              <span className="text-muted-foreground">+ {equipements.length - 1} autre(s)</span>
            )}
          </span>
        ) : (
          <span className="text-muted-foreground">Aucun équipement enregistré.</span>
        )}
      </div>
      {/* Dernier ticket SAV ouvert. */}
      <div className="flex items-center gap-1.5">
        <Wrench className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        {lastOpen ? (
          <span className="flex flex-wrap items-center gap-1">
            <span className="font-medium">{lastOpen.reference}</span>
            <Badge tone="warning">{TICKET_STATUS_LABELS[lastOpen.statut] ?? lastOpen.statut}</Badge>
            {lastOpen.description && (
              <span className="truncate text-muted-foreground">— {lastOpen.description}</span>
            )}
          </span>
        ) : (
          <span className="text-muted-foreground">Aucun ticket SAV ouvert.</span>
        )}
      </div>
      {/* Date de mise en service. */}
      {dateMes && (
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Clock className="size-3.5 shrink-0" aria-hidden="true" />
          <span>Mise en service le {formatDate(dateMes)}</span>
        </div>
      )}
    </div>
  )
}

// ── F6 — Trajet & check-in GPS ───────────────────────────────────────────────
export function TrajetPanel({ intervention, onChanged }) {
  const id = intervention.id
  const [busy, setBusy] = useState(false)

  const stampDepart = async () => {
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.departDepot(id),
        FIELD_OPS.DEPART_DEPOT, { intervention: id })
      toast.success(r.queued ? QUEUED_MSG : 'Départ dépôt enregistré.')
      onChanged?.()
    } catch { toast.error('Enregistrement impossible.') } finally { setBusy(false) }
  }
  const stampRetour = async () => {
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.retourDepot(id),
        FIELD_OPS.RETOUR, { intervention: id })
      toast.success(r.queued ? QUEUED_MSG : 'Retour dépôt enregistré.')
      onChanged?.()
    } catch { toast.error('Enregistrement impossible.') } finally { setBusy(false) }
  }
  const checkin = () => {
    if (!navigator.geolocation) {
      // Repli sans coordonnées : on horodate quand même l'arrivée.
      sendCheckin(null, null)
      return
    }
    setBusy(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => sendCheckin(pos.coords.latitude, pos.coords.longitude),
      () => sendCheckin(null, null),
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }
  const sendCheckin = async (lat, lng) => {
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.checkin(id, lat, lng),
        FIELD_OPS.CHECKIN, { intervention: id, lat, lng })
      toast.success(r.queued ? QUEUED_MSG : 'Arrivée sur site enregistrée.')
      onChanged?.()
    } catch { toast.error('Check-in impossible.') } finally { setBusy(false) }
  }

  const dist = intervention.distance_site_km
  // XFSM8 — notes d'accès du chantier, reprises telles quelles (jamais
  // ressaisies) : contact sur site, horaires, consignes particulières.
  const hasAcces = intervention.contact_site_nom || intervention.contact_site_telephone
    || intervention.horaires_acces || intervention.acces_instructions

  return (
    <div className="flex flex-col gap-3 py-2 text-sm">
      {/* VX107 — résumé client lecture seule (garantie / dernier ticket SAV /
          mise en service), consultable sans quitter le Sheet d'intervention. */}
      <ClientInfoPanel intervention={intervention} />
      {hasAcces && (
        <div className="flex flex-col gap-1 rounded border border-border bg-muted/40 p-2">
          <span className="font-medium">Accès au site</span>
          {(intervention.contact_site_nom || intervention.contact_site_telephone) && (
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>Contact : {intervention.contact_site_nom || '—'}</span>
              {/* VX246(e) — le numéro du contact site devient un lien tap-to-call
                  (au lieu d'un texte à recomposer à la main sur le terrain). */}
              {telHref(intervention.contact_site_telephone) && (
                <a className="link-blue inline-flex items-center gap-1"
                   href={telHref(intervention.contact_site_telephone)}>
                  <Phone size={13} aria-hidden="true" />
                  {intervention.contact_site_telephone}
                </a>
              )}
              {/* VX246(d) — bouton discret : enregistre le contact (.vcf) dans le
                  carnet d'adresses du téléphone d'un appui. */}
              <button type="button"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                title="Enregistrer le contact (.vcf)"
                onClick={() => downloadVCard({
                  fullName: intervention.contact_site_nom,
                  mobile: intervention.contact_site_telephone,
                })}>
                <UserPlus size={13} aria-hidden="true" />
                vCard
              </button>
            </span>
          )}
          {intervention.horaires_acces && <span>Horaires : {intervention.horaires_acces}</span>}
          {intervention.acces_instructions && <span>{intervention.acces_instructions}</span>}
        </div>
      )}
      <Row label="Départ dépôt" value={intervention.depart_depot_le
        ? formatDateTime(intervention.depart_depot_le) : '—'} />
      <Row label="Arrivée sur site" value={intervention.arrivee_site_le
        ? formatDateTime(intervention.arrivee_site_le) : '—'} />
      <Row label="Retour dépôt" value={intervention.retour_depot_le
        ? formatDateTime(intervention.retour_depot_le) : '—'} />
      {dist != null && (
        <div className="flex items-center gap-1.5 rounded border border-border p-2">
          <MapPin className="size-4 text-primary" aria-hidden="true" />
          <span>Distance au chantier : <b>{dist} km</b></span>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={stampDepart} disabled={busy}>
          <Truck className="size-4" aria-hidden="true" /> Départ dépôt
        </Button>
        <Button size="sm" onClick={checkin} disabled={busy}>
          <Navigation className="size-4" aria-hidden="true" /> Check-in (arrivée)
        </Button>
        <Button size="sm" variant="outline" onClick={stampRetour} disabled={busy}>
          <Truck className="size-4" aria-hidden="true" /> Retour dépôt
        </Button>
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  )
}

// ── F7/F8 — Capture guidée + galerie + photos obligatoires manquantes ────────
export function PhotosPanel({ intervention, onChanged }) {
  const id = intervention.id
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef(null)
  const burstRef = useRef(null)
  const pendingSlot = useRef(null)
  const burstSlotRef = useRef(null)
  const nextPageId = useRef(1)
  // FG385 — créneau dont la caméra en direct est ouverte (null = aucune).
  const [camSlot, setCamSlot] = useState(null)
  // VX44 — rafale : file d'attente de photos {id, file, rotation} prises « de
  // suite » (le pattern multi-pages de NumeriserPage), revues (retirer/tourner)
  // avant l'envoi groupé vers le MÊME créneau. `pendingSlot` = le créneau ciblé.
  const [rafale, setRafale] = useState([]) // [{id, file, rotation}]
  const [rafaleSlot, setRafaleSlot] = useState(null) // {cle, libelle} ciblé

  const load = useCallback(() => installationsApi.getPhotos(id)
    .then((r) => setData(r.data))
    .catch(() => setData(null))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  const pick = (slot) => { pendingSlot.current = slot; fileRef.current?.click() }
  // VX44 — ouvre le sélecteur multi-fichiers pour une prise en rafale sur un
  // créneau : plusieurs photos s'accumulent avant l'envoi groupé.
  const pickRafale = (slot) => {
    burstSlotRef.current = slot
    setRafaleSlot(slot)
    burstRef.current?.click()
  }
  const onBurstFiles = (e) => {
    const files = Array.from(e.target.files ?? [])
    e.target.value = ''
    if (!files.length) return
    setRafale((prev) => [
      ...prev,
      ...files.map((f) => makeCapturedPage(nextPageId.current++, f)),
    ])
  }
  const rotateRafale = (pid) => setRafale((prev) => rotatePageInList(prev, pid))
  const removeRafale = (pid) => setRafale((prev) => removePageFromList(prev, pid))
  const clearRafale = () => { setRafale([]); setRafaleSlot(null) }
  // Envoi groupé : applique la rotation choisie (canvas), compresse, puis
  // téléverse chaque photo vers le créneau — une seule recharge à la fin.
  const sendRafale = async () => {
    const slot = burstSlotRef.current
    if (!slot || rafale.length === 0) return
    setBusy(true)
    try {
      for (const p of rafale) {
        const oriented = p.rotation === 0 ? p.file : await rotateImageBlob(p.file, p.rotation)
        const toSend = await compressImage(oriented)
        await installationsApi.ajouterPhoto(id, toSend, slot.cle)
      }
      toast.success(`${rafale.length} photo${rafale.length > 1 ? 's' : ''} ajoutée${rafale.length > 1 ? 's' : ''}.`)
      clearRafale()
      await load(); onChanged?.()
    } catch (err) {
      photoUploadError(err)
    } finally { setBusy(false) }
  }
  // Flux d'upload commun (choix de fichier ET capture caméra en direct).
  const uploadPhoto = async (file, slot) => {
    if (!file) return
    setBusy(true)
    try {
      // VX77 — compresse AVANT envoi (bord long ≤1600px, JPEG q0.75) : la
      // photo brute d'un appareil moderne (4-8 Mo) fait caler/timeout la 3G
      // rurale. Les PDF/SVG passent intouchés (compressImage() no-op).
      const toSend = await compressImage(file)
      await installationsApi.ajouterPhoto(id, toSend, slot)
      toast.success('Photo ajoutée.')
      await load(); onChanged?.()
    } catch (err) {
      photoUploadError(err)
    } finally { setBusy(false) }
  }
  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    await uploadPhoto(file, pendingSlot.current)
  }
  const remove = async (photoId) => {
    setBusy(true)
    try { await installationsApi.supprimerPhoto(id, photoId); await load(); onChanged?.() }
    catch { toast.error('Suppression impossible.') } finally { setBusy(false) }
  }

  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4" /> Chargement des photos…
    </p>
  )
  if (!data) return (
    <p className="py-4 text-sm text-muted-foreground">Photos indisponibles.</p>
  )

  const manquants = data.obligatoires_manquants ?? []

  return (
    <div className="flex flex-col gap-4 py-2 text-sm">
      <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp"
        className="hidden" onChange={onFile} />
      <input ref={burstRef} type="file" accept="image/png,image/jpeg,image/webp"
        multiple capture="environment" className="hidden" onChange={onBurstFiles} />

      {/* VX44 — file de rafale : plusieurs photos prises « de suite » sont
          revues (tourner/retirer) puis envoyées d'un coup vers le créneau. */}
      {rafale.length > 0 && (
        <div className="flex flex-col gap-2 rounded border border-primary/40 bg-primary/5 p-2">
          <span className="text-[12px] font-medium">
            {rafale.length} photo{rafale.length > 1 ? 's' : ''} en attente
            {rafaleSlot ? ` — ${rafaleSlot.libelle}` : ''}
          </span>
          <div className="flex flex-wrap gap-2">
            {rafale.map((p) => (
              <div key={p.id} className="relative">
                <img src={URL.createObjectURL(p.file)} alt=""
                  style={{ transform: `rotate(${p.rotation}deg)` }}
                  className="size-20 rounded border border-border object-cover" />
                <button type="button" disabled={busy} onClick={() => rotateRafale(p.id)}
                  title="Pivoter"
                  className="absolute -left-1.5 -top-1.5 rounded-full bg-black/60 p-0.5 text-white shadow disabled:opacity-50">
                  <RotateCw className="size-3" aria-hidden="true" />
                </button>
                <button type="button" disabled={busy} onClick={() => removeRafale(p.id)}
                  title="Retirer"
                  className="absolute -right-1.5 -top-1.5 rounded-full bg-destructive p-0.5 text-white shadow disabled:opacity-50">
                  <X className="size-3" aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={sendRafale} disabled={busy}>
              <Upload className="size-4" aria-hidden="true" />
              Envoyer {rafale.length} photo{rafale.length > 1 ? 's' : ''}
            </Button>
            <Button size="sm" variant="ghost" onClick={clearRafale} disabled={busy}>
              Tout effacer
            </Button>
          </div>
        </div>
      )}

      {/* VX227 — lien croisé discret vers les photos avant/pendant/après du
          chantier : les deux magasins de photos (intervention vs chantier) ne
          sont jamais fusionnés, mais restent navigables l'un vers l'autre. */}
      {intervention.installation && (
        <button type="button"
          onClick={() => navigate(`/chantiers?id=${intervention.installation}`)}
          className="flex items-center gap-1.5 self-start text-[12px] text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground">
          <Images className="size-3.5" aria-hidden="true" />
          Voir aussi les photos du chantier
        </button>
      )}

      {manquants.length > 0 && (
        <div className="rounded border border-destructive/40 bg-destructive/5 p-2">
          <div className="flex items-center gap-1.5 font-medium text-destructive">
            <AlertTriangle className="size-4" aria-hidden="true" />
            Photos obligatoires manquantes
          </div>
          <ul className="mt-1 list-disc pl-5 text-[12px] text-muted-foreground">
            {manquants.map((m) => <li key={m.cle}>{m.libelle}</li>)}
          </ul>
          <p className="mt-1 text-[11.5px] text-muted-foreground">
            Requises avant de passer l'intervention à « Terminée ».
          </p>
        </div>
      )}

      {PHASES.map(([phase, label]) => {
        const slots = data.groupes?.[phase] ?? []
        if (!slots.length) return null
        return (
          <div key={phase} className="flex flex-col gap-2">
            <span className="font-medium text-muted-foreground">{label}</span>
            {slots.map((slot) => (
              <div key={slot.cle} className="rounded border border-border p-2">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5">
                    {slot.libelle}
                    {slot.obligatoire && <Badge tone="danger">Obligatoire</Badge>}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Button size="sm" variant="outline" disabled={busy}
                      onClick={() => pick(slot.cle)}>
                      <Camera className="size-4" aria-hidden="true" /> Photo
                    </Button>
                    {/* VX44 — rafale : plusieurs photos d'affilée sans rouvrir
                        le sélecteur, revues avant l'envoi groupé. */}
                    <Button size="sm" variant="outline" disabled={busy}
                      onClick={() => pickRafale(slot)}
                      title="Prendre plusieurs photos de suite">
                      <Images className="size-4" aria-hidden="true" /> Rafale
                    </Button>
                    <Button size="sm" variant="outline" disabled={busy}
                      onClick={() => setCamSlot((s) => (s === slot.cle ? null : slot.cle))}
                      title="Prendre une photo avec la caméra en direct">
                      <Camera className="size-4" aria-hidden="true" />
                      {camSlot === slot.cle ? 'Fermer' : 'Caméra'}
                    </Button>
                  </div>
                </div>
                {camSlot === slot.cle && (
                  <div className="mb-2 max-w-sm">
                    <CameraCapture
                      onCapture={(file) => uploadPhoto(file, slot.cle)}
                      onClose={() => setCamSlot(null)}
                    />
                  </div>
                )}
                {slot.photos.length === 0
                  ? <span className="text-[12px] text-muted-foreground">Aucune photo.</span>
                  : (
                    <div className="flex flex-wrap gap-2">
                      {slot.photos.map((p) => (
                        <PhotoThumb key={p.id} photo={p} onRemove={remove} busy={busy} />
                      ))}
                    </div>
                  )}
              </div>
            ))}
          </div>
        )
      })}

      {/* Photos rattachées à un créneau désormais retiré/désactivé. */}
      {(data.autres ?? []).length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="font-medium text-muted-foreground">Hors créneau</span>
          {(data.autres ?? []).map((slot) => (
            <div key={slot.cle} className="flex flex-wrap gap-2 rounded border border-border p-2">
              {slot.photos.map((p) => (
                <PhotoThumb key={p.id} photo={p} onRemove={remove} busy={busy} />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PhotoThumb({ photo, onRemove, busy }) {
  return (
    <div className="relative">
      <a href={photo.url} target="_blank" rel="noreferrer">
        <img src={photo.url} alt={photo.filename} loading="lazy"
          className="size-20 rounded border border-border object-cover" />
      </a>
      <button type="button" disabled={busy}
        onClick={() => onRemove(photo.id)}
        title="Supprimer la photo"
        className="absolute -right-1.5 -top-1.5 rounded-full bg-destructive p-0.5 text-white shadow disabled:opacity-50">
        <Trash2 className="size-3" aria-hidden="true" />
      </button>
      <div className="mt-0.5 max-w-20 truncate text-[10px] text-muted-foreground">
        {formatDateTime(photo.created_at)}
      </div>
    </div>
  )
}
