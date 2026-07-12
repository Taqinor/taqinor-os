// VX106 — Signature client sur le compte-rendu d'intervention (FG69).
//
// Le modèle (`signature_client`/`signataire_nom`/`signe_le`), l'endpoint
// `signer-client`, et l'opération offline `SIGNER_CLIENT` (fieldOutbox +
// field_sync) existaient déjà — sans AUCUN écran de trace côté technicien.
// Ce panneau réutilise `SignaturePad` (canvas Pointer Events, zéro dépendance,
// même forme de donnée data-URL PNG que la preuve de livraison) et envoie via
// `withOfflineFallback` : signature capturée en ligne OU mise en file hors
// ligne. Aucune écriture PDF ici (le compte-rendu d'intervention affiche la
// signature côté serveur — hors du moteur /proposal, règle #4).
import { useState } from 'react'
import { PenLine, CheckCircle2 } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import { Button, Input, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'
import { withOfflineFallback, FIELD_OPS } from './offline/fieldOutbox'
import SignaturePad from '../logistique/SignaturePad'

const QUEUED_MSG = 'Hors ligne — signature enregistrée, synchro au retour du réseau.'

export function SignatureClientPanel({ intervention, onChanged }) {
  const id = intervention.id
  const [sig, setSig] = useState(null) // data-URL PNG de la signature tracée
  const [nom, setNom] = useState(intervention.signataire_nom || '')
  const [busy, setBusy] = useState(false)
  // Une signature déjà enregistrée bascule le panneau en mode « re-signer ».
  const [resign, setResign] = useState(false)

  const dejaSignee = !!intervention.signe_le
  const showPad = !dejaSignee || resign

  const enregistrer = async () => {
    if (!sig) { toast.error('Faites signer le client avant d’enregistrer.'); return }
    setBusy(true)
    try {
      const r = await withOfflineFallback(
        () => installationsApi.signerClient(id, {
          signature_client: sig, signataire_nom: nom.trim() }),
        FIELD_OPS.SIGNER_CLIENT,
        { intervention: id, signature_client: sig, signataire_nom: nom.trim() })
      if (r.queued) {
        toast.success(QUEUED_MSG)
      } else {
        toast.success('Signature client enregistrée.')
      }
      setSig(null); setResign(false)
      onChanged?.()
    } catch (err) {
      toast.error(err?.response?.data?.signature_client
        ?? err?.response?.data?.detail
        ?? 'Enregistrement de la signature impossible.')
    } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-3 py-2 text-sm">
      {dejaSignee && (
        <div className="flex items-center gap-2 rounded border border-success/30 bg-success/5 p-2 text-success">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
          <span>
            Signé par <strong>{intervention.signataire_nom || 'le client'}</strong>{' '}
            le {formatDateTime(intervention.signe_le)}
          </span>
        </div>
      )}

      {/* Aperçu de la signature déjà enregistrée (data-URL PNG). */}
      {dejaSignee && !resign && typeof intervention.signature_client === 'string'
        && intervention.signature_client.startsWith('data:image') && (
        <img src={intervention.signature_client} alt="Signature du client"
          className="max-h-32 w-full rounded border border-border bg-white object-contain" />
      )}

      {dejaSignee && !resign && (
        <Button size="sm" variant="outline" onClick={() => setResign(true)}>
          <PenLine className="size-4" aria-hidden="true" /> Re-signer
        </Button>
      )}

      {showPad && (
        <>
          <p className="text-[12px] text-muted-foreground">
            Faites signer le client dans le cadre ci-dessous, puis enregistrez.
          </p>
          <Input placeholder="Nom du signataire (optionnel)"
            value={nom} onChange={(e) => setNom(e.target.value)} />
          <SignaturePad onChange={setSig} />
          <div className="flex items-center gap-2">
            <Button size="sm" disabled={busy || !sig} onClick={enregistrer}>
              <PenLine className="size-4" aria-hidden="true" /> Enregistrer la signature
            </Button>
            {resign && (
              <Button size="sm" variant="ghost" disabled={busy}
                onClick={() => { setSig(null); setResign(false) }}>
                Annuler
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default SignatureClientPanel
