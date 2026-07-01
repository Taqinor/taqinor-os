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
import {
  CheckCircle2, MapPin, Navigation, Truck, Camera, Trash2, AlertTriangle,
  PackageCheck,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Button, Badge, Spinner, Checkbox, Progress, toast,
} from '../../ui'
import { formatDateTime } from '../../lib/format'
import { withOfflineFallback, FIELD_OPS } from './offline/fieldOutbox'
import CameraCapture from '../pwa/CameraCapture'

// N91/F21 — message commun quand une action a été MISE EN FILE (hors-ligne) :
// elle se synchronisera toute seule au retour du réseau.
const QUEUED_MSG = 'Hors ligne — enregistré, synchro au retour du réseau.'

const PHASES = [
  ['avant', 'Avant'],
  ['pendant', 'Pendant'],
  ['apres', 'Après'],
]

// ── F5 — Liste de préparation ────────────────────────────────────────────────
export function PreparationPanel({ intervention, onChanged }) {
  const id = intervention.id
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

  return (
    <div className="flex flex-col gap-3 py-2 text-sm">
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
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef(null)
  const pendingSlot = useRef(null)
  // FG385 — créneau dont la caméra en direct est ouverte (null = aucune).
  const [camSlot, setCamSlot] = useState(null)

  const load = useCallback(() => installationsApi.getPhotos(id)
    .then((r) => setData(r.data))
    .catch(() => setData(null))
    .finally(() => setLoading(false)), [id])
  useEffect(() => { load() }, [load])

  const pick = (slot) => { pendingSlot.current = slot; fileRef.current?.click() }
  // Flux d'upload commun (choix de fichier ET capture caméra en direct).
  const uploadPhoto = async (file, slot) => {
    if (!file) return
    setBusy(true)
    try {
      await installationsApi.ajouterPhoto(id, file, slot)
      toast.success('Photo ajoutée.')
      await load(); onChanged?.()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Téléversement impossible.')
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
        <img src={photo.url} alt={photo.filename}
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
