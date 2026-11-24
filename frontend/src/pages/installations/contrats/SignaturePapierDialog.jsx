// « Signé sur papier » : le client a signé la version imprimée. On note son nom
// et la date. Corps envoyé = `corps_marquer_signe` du contrat :
// { signataire_nom, signe_le }.
import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Button, Input, Label, toast,
} from '../../../ui'
import documentsApi from '../../../api/documentsApi'
import useActeContenu from './useActeContenu'
import PiedDialogue from './PiedDialogue'
import { useSoumission } from './useSoumission'

function aujourdhui() {
  const d = new Date()
  const deux = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`
}

export default function SignaturePapierDialog({ open, onOpenChange, acte, onDone }) {
  const { acte: detail } = useActeContenu(acte?.id, open)
  const [nomSaisi, setNomSaisi] = useState(null)
  const [date, setDate] = useState(aujourdhui)
  const { occupe, erreur, soumettre } = useSoumission()

  const nom = nomSaisi ?? detail?.contenu?.client?.nom_complet ?? ''

  const enregistrer = async () => {
    const ok = await soumettre(() => documentsApi.marquerActeSigne(acte.id, {
      signataire_nom: nom.trim(),
      signe_le: date,
    }))
    if (ok) {
      toast.success('Acte marqué signé sur papier.')
      onDone?.()
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="Signature sur papier" className="contrats-dialogue">
        <DialogHeader>
          <DialogTitle>« {acte?.titre} » signé sur papier</DialogTitle>
          <DialogDescription>
            Indiquez qui a signé et quel jour. Une fois marqué signé, l’acte ne se rouvre plus :
            gardez l’exemplaire papier signé.
          </DialogDescription>
        </DialogHeader>

        <div className="contrats-champ">
          <Label htmlFor="contrats-pap-nom">Nom du signataire</Label>
          <Input id="contrats-pap-nom" value={nom} onChange={(e) => setNomSaisi(e.target.value)} />
        </div>
        <div className="contrats-champ">
          <Label htmlFor="contrats-pap-date">Date de signature</Label>
          <Input id="contrats-pap-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <PiedDialogue erreur={erreur} annuler={() => onOpenChange(false)}>
          <Button
            className="contrats-acte__bouton"
            disabled={occupe || !nom.trim() || !date}
            onClick={enregistrer}
          >
            Marquer signé
          </Button>
        </PiedDialogue>
      </DialogContent>
    </Dialog>
  )
}
