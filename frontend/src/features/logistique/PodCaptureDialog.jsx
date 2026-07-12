// XSTK2 — Capture de la preuve de livraison (POD, FG330) depuis mobile :
// nom + signature tracée (SignaturePad local, même donnée que FG69 —
// data-URL PNG), photo de la remise (réutilise `FileUpload` existant +
// `recordsApi.uploadAttachment`, mêmes conventions que F7/F8), position GPS
// (mêmes conventions que le check-in F6) et note libre. Une seule preuve par
// livraison (OneToOne serveur) : si une preuve existe déjà, ce dialogue
// l'ÉDITE (PATCH) au lieu d'en recréer une.
import { useEffect, useState } from 'react'
import { MapPin } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import recordsApi from '../../api/recordsApi'
import { Button, FileUpload, Spinner } from '../../ui'
import { compressImage } from '../../ui/file-utils'
import SignaturePad from './SignaturePad'

export default function PodCaptureDialog({ livraison, onClose, onSaved }) {
  const [existing, setExisting] = useState(null)
  const [loading, setLoading] = useState(true)
  const [signataireNom, setSignataireNom] = useState('')
  const [signatureData, setSignatureData] = useState(null)
  const [photoFile, setPhotoFile] = useState(null)
  const [note, setNote] = useState('')
  const [gps, setGps] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getPreuvesLivraison({ livraison: livraison.id })
      .then((r) => {
        if (!alive) return
        const list = r.data?.results ?? r.data ?? []
        const pod = list[0] ?? null
        setExisting(pod)
        if (pod) {
          setSignataireNom(pod.signataire_nom || '')
          setNote(pod.note || '')
        }
      })
      .catch(() => { if (alive) setExisting(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [livraison.id])

  const captureGps = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      (pos) => setGps({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setGps(null),
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }

  const save = async () => {
    if (!signatureData && !existing?.signature_data) {
      setError('La signature est requise.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = {
        livraison: livraison.id,
        signataire_nom: signataireNom || null,
        note: note || null,
        ...(signatureData ? { signature_data: signatureData } : {}),
        ...(gps ? { gps_lat: gps.lat, gps_lng: gps.lng } : {}),
      }
      const res = existing
        ? await installationsApi.updatePreuveLivraison(existing.id, payload)
        : await installationsApi.createPreuveLivraison(payload)
      const pod = res.data
      if (photoFile) {
        // VX246(a) — la photo POD terrain (souvent 4-8 Mo) est compressée avant
        // upload ; compressImage laisse passer intacts PDF/SVG et tout non-image.
        const toSend = await compressImage(photoFile)
        const up = await recordsApi.uploadAttachment(
          'installations.PreuveLivraison', pod.id, toSend)
        const attachmentId = up.data?.id
        if (attachmentId) {
          await installationsApi.updatePreuveLivraison(pod.id, { photo: attachmentId })
        }
      }
      onSaved?.()
    } catch (err) {
      setError(err?.response?.data?.detail || "Enregistrement de la preuve impossible.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Preuve de livraison — {livraison.reference}</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body flex flex-col gap-3">
          {loading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
          ) : (
            <>
              <label className="form-label" htmlFor="pod-nom">Nom du destinataire</label>
              <input
                id="pod-nom"
                className="form-control"
                value={signataireNom}
                onChange={(e) => setSignataireNom(e.target.value)}
                placeholder="ex. M. Alami"
              />

              <span className="form-label">Signature</span>
              <SignaturePad onChange={setSignatureData} />
              {existing?.signature_data && !signatureData && (
                <p className="text-xs text-muted-foreground">
                  Une signature est déjà enregistrée — retracez pour la remplacer.
                </p>
              )}

              <span className="form-label">Photo de la remise (optionnel)</span>
              <FileUpload
                accept="image/*"
                multiple={false}
                onFiles={(files) => setPhotoFile(files[0] ?? null)}
              />
              {photoFile && <p className="text-xs text-muted-foreground">{photoFile.name}</p>}

              <div className="flex items-center gap-2">
                <Button type="button" size="sm" variant="outline" onClick={captureGps}>
                  <MapPin className="size-4" aria-hidden="true" /> Position GPS
                </Button>
                {gps && (
                  <span className="text-xs text-muted-foreground">
                    {gps.lat.toFixed(5)}, {gps.lng.toFixed(5)}
                  </span>
                )}
              </div>

              <label className="form-label" htmlFor="pod-note">Note (optionnel)</label>
              <textarea
                id="pod-note"
                className="form-control"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
              />

              {error && <p className="form-error" role="alert">{error}</p>}
            </>
          )}
        </div>

        <div className="modal-footer">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="button" loading={busy} disabled={busy || loading} onClick={save}>
            {busy ? 'Enregistrement…' : 'Enregistrer la preuve'}
          </Button>
        </div>
      </div>
    </div>
  )
}
