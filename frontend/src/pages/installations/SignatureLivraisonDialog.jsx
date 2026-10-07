// NTMOB16 — signature client tracée sur le bon de livraison chantier.
// Réutilise SignaturePad.jsx (même composant, même forme de donnée data-URL
// PNG, que Logistique/POD et SignatureClientPanel.jsx côté intervention
// FG69/VX106) dans un Dialog déclenché depuis « Bon de livraison » — la
// signature est stockée sur Installation.signature_client (NTMOB16, distinct
// d'Intervention.signature_client) et rejoint le PDF généré juste après
// (apps.documents.builders.generate_bon_livraison). Complémentaire, jamais
// un remplacement de l'e-signature légale loi 53-05 des contrats.
import { useState } from 'react'
import { PenLine } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Button, Input, toast,
} from '../../ui'
import installationsApi from '../../api/installationsApi'
import SignaturePad from '../../features/installations/SignaturePad'

export default function SignatureLivraisonDialog({
  open, onOpenChange, installation, onSigned,
}) {
  const [sig, setSig] = useState(null) // data-URL PNG de la signature tracée
  const [nom, setNom] = useState(installation?.signataire_nom || '')
  // CIQ631/CIQ637 — signataire nommé (fonction, société) et co-signataire
  // optionnel, préremplis depuis le chantier.
  const [sign, setSign] = useState({
    signataire_fonction: installation?.signataire_fonction || '',
    signataire_societe: installation?.signataire_societe || '',
    cosignataire_nom: installation?.cosignataire_nom || '',
    cosignataire_fonction: installation?.cosignataire_fonction || '',
    cosignataire_organisme: installation?.cosignataire_organisme || '',
  })
  const setSigne = (k) => (e) => setSign((p) => ({ ...p, [k]: e.target.value }))
  const [busy, setBusy] = useState(false)

  const enregistrer = async () => {
    if (!sig) { toast.error('Faites signer le client avant d’enregistrer.'); return }
    setBusy(true)
    try {
      // Seuls les champs renseignés partent : le serveur laisse inchangés
      // ceux qui manquent.
      const extra = Object.fromEntries(
        Object.entries(sign).map(([k, v]) => [k, v.trim()]).filter(([, v]) => v))
      await installationsApi.signerClientChantier(installation.id, {
        signature_client: sig, signataire_nom: nom.trim(), ...extra,
      })
      toast.success('Signature enregistrée — jointe au bon de livraison.')
      setSig(null)
      onSigned?.()
      onOpenChange(false)
    } catch (err) {
      toast.error(err?.response?.data?.signature_client
        ?? err?.response?.data?.detail
        ?? 'Enregistrement de la signature impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="Signature — bon de livraison">
        <DialogHeader>
          <DialogTitle>Signature de réception</DialogTitle>
          <DialogDescription>
            Faites tracer une signature au client à la livraison du matériel —
            elle rejoindra le PDF du bon de livraison.
          </DialogDescription>
        </DialogHeader>

        {installation?.signe_le && (
          <p className="text-xs text-muted-foreground">
            Déjà signé par {installation.signataire_nom || 'le client'} —
            tracer une nouvelle signature la remplace.
          </p>
        )}

        <Input placeholder="Nom du signataire (optionnel)"
               value={nom} onChange={(e) => setNom(e.target.value)} />
        <div className="grid gap-2 sm:grid-cols-2">
          <Input aria-label="Fonction du signataire" placeholder="Fonction du signataire"
                 value={sign.signataire_fonction} onChange={setSigne('signataire_fonction')} />
          <Input aria-label="Société du signataire" placeholder="Société du signataire"
                 value={sign.signataire_societe} onChange={setSigne('signataire_societe')} />
          <Input aria-label="Nom du co-signataire" placeholder="Co-signataire (facultatif)"
                 value={sign.cosignataire_nom} onChange={setSigne('cosignataire_nom')} />
          <Input aria-label="Fonction du co-signataire" placeholder="Fonction du co-signataire"
                 value={sign.cosignataire_fonction} onChange={setSigne('cosignataire_fonction')} />
          <Input aria-label="Organisme du co-signataire" placeholder="Organisme du co-signataire"
                 value={sign.cosignataire_organisme} onChange={setSigne('cosignataire_organisme')} />
        </div>
        <SignaturePad onChange={setSig} />

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button disabled={busy || !sig} onClick={enregistrer}>
            <PenLine className="size-4" aria-hidden="true" /> Enregistrer la signature
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
