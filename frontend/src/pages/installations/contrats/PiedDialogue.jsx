// Pied commun des dialogues de l'onglet Contrats : erreur en place, puis
// [avant] Annuler [actions].
import { Button } from '../../../ui'

/** Message d'erreur en place + pied de dialogue : `avant`, Annuler, puis les actions (enfants). */
export default function PiedDialogue({
  erreur, annuler, libelleAnnuler = 'Annuler', avant = null, children,
}) {
  return (
    <>
      {erreur && <p className="contrats-acte__erreur" role="alert">{erreur}</p>}
      <div className="contrats-dialogue__pied">
        {avant}
        <Button variant="ghost" className="contrats-acte__bouton" onClick={annuler}>
          {libelleAnnuler}
        </Button>
        {children}
      </div>
    </>
  )
}
