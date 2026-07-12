import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, FileUpload, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   XFLT23 — Formulaire de plein de carburant avec OCR reçu de station (gated).
   ----------------------------------------------------------------------------
   La photo du reçu est envoyée à l'OCR qui renvoie des champs pré-remplis
   (date/quantité/prix/station) — l'utilisateur valide TOUJOURS avant création,
   jamais de création automatique. Sans clé OCR configurée côté serveur (503),
   la saisie manuelle reste utilisable normalement (message FR clair).
   ========================================================================== */

export default function PleinDialog({ vehicules = [], onClose, onSaved }) {
  const [vehiculeId, setVehiculeId] = useState('')
  const [datePlein, setDatePlein] = useState('')
  const [kilometrage, setKilometrage] = useState('')
  const [quantite, setQuantite] = useState('')
  const [prixTotal, setPrixTotal] = useState('')
  const [station, setStation] = useState('')
  const [ocrBusy, setOcrBusy] = useState(false)
  const [ocrMessage, setOcrMessage] = useState(null)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(vehiculeId && datePlein)
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(vehiculeId || datePlein || kilometrage || quantite || prixTotal || station)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const surOcr = async (files) => {
    const photo = files[0]
    if (!photo) return
    setOcrBusy(true)
    setOcrMessage(null)
    try {
      const formData = new FormData()
      formData.append('photo', photo)
      const res = await flotteApi.pleins.ocr(formData)
      const champs = res?.data?.champs || {}
      if (champs.date_plein) setDatePlein(champs.date_plein)
      if (champs.quantite != null) setQuantite(String(champs.quantite))
      if (champs.prix_total != null) setPrixTotal(String(champs.prix_total))
      if (champs.station) setStation(champs.station)
      setOcrMessage('Champs pré-remplis depuis le reçu — vérifiez avant d’enregistrer.')
    } catch (err) {
      const status = err?.response?.status
      setOcrMessage(
        status === 503
          ? (err?.response?.data?.detail || 'OCR indisponible — complétez la saisie manuellement.')
          : 'Lecture du reçu impossible — complétez la saisie manuellement.',
      )
    } finally {
      setOcrBusy(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.pleins.create({
        vehicule: Number(vehiculeId),
        date_plein: datePlein,
        kilometrage: kilometrage === '' ? undefined : Number(kilometrage),
        quantite: quantite === '' ? undefined : Number(quantite),
        prix_total: prixTotal === '' ? undefined : Number(prixTotal),
        station,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.kilometrage
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau plein</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <FileUpload
            accept="image/*"
            onFiles={surOcr}
            busy={ocrBusy}
            hint="Photo du reçu de station (OCR — pré-remplissage optionnel)"
          />
          {ocrMessage && <p className="text-xs text-muted-foreground">{ocrMessage}</p>}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="plein-vehicule">Véhicule</Label>
            <select
              id="plein-vehicule"
              autoFocus
              value={vehiculeId}
              onChange={(e) => setVehiculeId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {vehicules.map((v) => (
                <option key={v.id} value={v.id}>{v.immatriculation}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plein-date">Date du plein</Label>
              <Input id="plein-date" type="date" value={datePlein} onChange={(e) => setDatePlein(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plein-km">Kilométrage</Label>
              <Input id="plein-km" type="number" step="any" value={kilometrage} onChange={(e) => setKilometrage(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plein-quantite">Quantité</Label>
              <Input id="plein-quantite" type="number" step="any" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plein-prix">Coût total (MAD)</Label>
              <Input id="plein-prix" type="number" step="any" value={prixTotal} onChange={(e) => setPrixTotal(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="plein-station">Station</Label>
            <Input id="plein-station" value={station} onChange={(e) => setStation(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
