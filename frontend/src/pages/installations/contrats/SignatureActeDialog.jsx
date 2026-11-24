// Signature sur place d'un acte : le client trace sa signature (SignaturePad,
// le même composant que la livraison). Corps envoyé = `corps_signer` du contrat
// (apps/documents/contract_samples/acte_contractuel.json) :
// { signature_client, signataire_nom, lieu }.
import { useState } from 'react'
import { PenLine } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Button, Input, Label, toast,
} from '../../../ui'
import documentsApi from '../../../api/documentsApi'
import SignaturePad from '../../../features/installations/SignaturePad'
import useActeContenu from './useActeContenu'
import { detailErreur } from './outils'

export default function SignatureActeDialog({ open, onOpenChange, acte, onSigned }) {
  const { acte: detail } = useActeContenu(acte?.id, open)
  const [signature, setSignature] = useState(null)
  const [nomSaisi, setNomSaisi] = useState(null)
  const [lieuSaisi, setLieuSaisi] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState('')

  // Préremplis depuis l'acte, tant que l'utilisateur n'a rien tapé.
  const nom = nomSaisi ?? detail?.contenu?.client?.nom_complet ?? ''
  const lieu = lieuSaisi ?? detail?.contenu?.lieu ?? ''

  const enregistrer = async () => {
    setOccupe(true)
    setErreur('')
    try {
      await documentsApi.signerActe(acte.id, {
        signature_client: signature,
        signataire_nom: nom.trim(),
        lieu: lieu.trim(),
      })
      toast.success('Signature enregistrée : l’acte est signé.')
      onSigned?.()
    } catch (err) {
      setErreur(await detailErreur(err))
    } finally {
      setOccupe(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="Signature sur place" className="contrats-dialogue">
        <DialogHeader>
          <DialogTitle>Faire signer « {acte?.titre} »</DialogTitle>
          <DialogDescription>
            Le client signe du doigt ou à la souris. Une fois signé, l’acte ne se rouvre plus :
            la signature, le nom, la date et l’empreinte du texte sont conservés comme preuve.
          </DialogDescription>
        </DialogHeader>

        <div className="contrats-champ">
          <Label htmlFor="contrats-sig-nom">Nom du signataire</Label>
          <Input id="contrats-sig-nom" value={nom} onChange={(e) => setNomSaisi(e.target.value)} />
        </div>
        <div className="contrats-champ">
          <Label htmlFor="contrats-sig-lieu">Lieu de signature</Label>
          <Input id="contrats-sig-lieu" value={lieu} onChange={(e) => setLieuSaisi(e.target.value)} />
        </div>
        <SignaturePad onChange={setSignature} />

        {erreur && <p className="contrats-acte__erreur" role="alert">{erreur}</p>}

        <div className="contrats-dialogue__pied">
          <Button variant="ghost" className="contrats-acte__bouton" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button
            className="contrats-acte__bouton"
            disabled={occupe || !signature || !nom.trim()}
            onClick={enregistrer}
          >
            <PenLine className="size-4" aria-hidden="true" /> Enregistrer la signature
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
