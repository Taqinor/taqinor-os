import { Button } from './Button'

/* Pied d'une modale de formulaire (ResponsiveDialog) : Annuler (outline) puis
   « Enregistrer » (modification) / « Créer » (création), désactivable. Un seul
   endroit pour Garanties et Alertes KPI. */
export default function PiedModaleFormulaire({ onAnnuler, saving, desactive, enEdition }) {
  return (
    <div className="flex justify-end gap-2">
      <Button type="button" variant="outline" onClick={onAnnuler}>Annuler</Button>
      <Button type="submit" loading={saving} disabled={desactive}>
        {enEdition ? 'Enregistrer' : 'Créer'}
      </Button>
    </div>
  )
}
