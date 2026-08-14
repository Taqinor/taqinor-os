import { useEffect, useState } from 'react'

import api from '../../api/axios'
import {
  Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
  Input, Label, Spinner, Textarea,
} from '../../ui'
import { toast } from '../../ui/confirm'
import AttachmentsPanel from '../../components/AttachmentsPanel'

/* ============================================================================
   NTLOG34 — Wizard « Clôturer une réserve / ouvrir un litige »
   ----------------------------------------------------------------------------
   À la saisie d'une `ReserveReception` (NTLOG18), ce mini-wizard enchaîne
   nature du dommage → photos → transporteur pré-rempli EN UNE SEULE
   soumission de réserve (le `LitigeTransport` naît automatiquement côté
   serveur dans le MÊME appel — `services.creer_litige_depuis_reserve`,
   appelé par `ReserveReceptionViewSet.perform_create` — jamais un second
   POST vers un endpoint litige). Les photos sont déposées UNE SEULE FOIS,
   sur la réserve (`records.Attachment`, cible `transport.reservereception`
   déclarée dans `apps/transport/platform.py`) : le litige n'a PAS sa propre
   cible chatter/pièces jointes (absente de `record_targets`) — il retrouve
   ces mêmes photos via la référence croisée `reserve.litige`, exactement
   comme `reclamation_pdf.py` (NTLOG19) le fait déjà côté PDF. Il n'y a donc
   structurellement JAMAIS de double-upload.
   ========================================================================== */

const STEPS = ['nature', 'photos', 'confirmation']

export default function ReserveEtLitigeWizard({ etape, ordre, onClose, onCreated }) {
  const [stepIndex, setStepIndex] = useState(0)
  const [nature, setNature] = useState('')
  const [montant, setMontant] = useState('')
  const [saving, setSaving] = useState(false)
  const [reserve, setReserve] = useState(null)
  const [transporteurNom, setTransporteurNom] = useState(null)

  useEffect(() => {
    const transporteurId = ordre?.installations_transporteur_id
    if (!transporteurId) { setTransporteurNom('—'); return }
    let active = true
    api.get(`/installations/transporteurs/${transporteurId}/`)
      .then((r) => { if (active) setTransporteurNom(r.data?.nom || '—') })
      .catch(() => { if (active) setTransporteurNom('—') })
    return () => { active = false }
  }, [ordre?.installations_transporteur_id])

  const step = STEPS[stepIndex]

  const creerReserve = async () => {
    setSaving(true)
    try {
      const { data } = await api.post('/transport/reserves-reception/', {
        etape: etape.id,
        nature_reserve: nature,
        montant_estime_dommage: montant || null,
      })
      setReserve(data)
      setStepIndex(1)
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  const terminer = () => {
    toast.success(
      reserve?.litige
        ? 'Réserve enregistrée — litige ouvert automatiquement.'
        : 'Réserve enregistrée.',
    )
    onCreated?.(reserve)
    onClose?.()
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Réserve à réception</DialogTitle>
        </DialogHeader>

        {step === 'nature' && (
          <div className="flex flex-col gap-3">
            <div>
              <Label htmlFor="rl-nature">Nature du dommage</Label>
              <Textarea id="rl-nature" rows={3} value={nature} onChange={(e) => setNature(e.target.value)} />
            </div>
            <div className="max-w-xs">
              <Label htmlFor="rl-montant">Montant estimé du dommage (MAD)</Label>
              <Input
                id="rl-montant" type="number" step="any"
                value={montant} onChange={(e) => setMontant(e.target.value)}
              />
            </div>
          </div>
        )}

        {step === 'photos' && reserve && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted-foreground">
              Photos de la réserve (ces mêmes photos accompagneront la réclamation transporteur).
            </p>
            <AttachmentsPanel model="transport.reservereception" id={reserve.id} />
          </div>
        )}

        {step === 'confirmation' && (
          <div className="flex flex-col gap-2 text-sm">
            <p>
              <strong>Transporteur :</strong>{' '}
              {transporteurNom == null ? <Spinner className="inline size-3" /> : transporteurNom}
            </p>
            <p><strong>Nature :</strong> {nature || '—'}</p>
            <p><strong>Montant estimé :</strong> {montant || '—'} MAD</p>
            {reserve?.litige && (
              <p className="text-muted-foreground">
                Litige #{reserve.litige} ouvert automatiquement — aucune ressaisie nécessaire.
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          {step === 'nature' && (
            <Button type="button" disabled={saving || !nature} onClick={creerReserve}>
              {saving ? 'Enregistrement…' : 'Suivant'}
            </Button>
          )}
          {step === 'photos' && (
            <Button type="button" onClick={() => setStepIndex(2)}>Suivant</Button>
          )}
          {step === 'confirmation' && (
            <Button type="button" onClick={terminer}>Terminer</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
