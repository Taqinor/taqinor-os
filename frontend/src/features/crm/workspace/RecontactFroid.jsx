import { useState } from 'react'
import { Button, FormField, Textarea } from '../../../ui'
import crmApi from '../../../api/crmApi'
import { toast } from '../../../ui/confirm'
import { getApiError } from '../../../lib/apiError'
import useDroitMetier from '../../sav/useDroitMetier'
import { COLD_STAGE } from '../stages'

/* Un lead parqué au « Froid » dont le client répond : UN bouton, une question,
   et le serveur (POST /crm/leads/<id>/recontact/, contrat `lead_recontact.json`)
   rouvre le dossier. Aucune règle ici : le serveur juge (409 `detail` en français,
   400 `canal`). Le geste exige responsable/admin côté serveur ; on masque donc le
   bouton sans le droit d'écriture CRM. */
const CANAUX = [
  { cle: 'appel', libelle: 'Au téléphone' },
  { cle: 'whatsapp', libelle: 'Sur WhatsApp' },
]

export default function RecontactFroid({ lead, onDone }) {
  const peutModifier = useDroitMetier('crm_modifier')
  const [ouvert, setOuvert] = useState(false)
  const [canal, setCanal] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [erreurs, setErreurs] = useState({})

  const visible = lead?.id != null && lead.stage === COLD_STAGE && peutModifier
    && !lead.perdu && !lead.ne_plus_contacter && !lead.is_archived
  if (!visible) return null

  const fermer = () => { setOuvert(false); setCanal(''); setNote(''); setErreurs({}) }

  const envoyer = async () => {
    if (!canal) { setErreurs({ canal: 'Choisissez comment le client s’est manifesté.' }); return }
    setBusy(true); setErreurs({})
    try {
      const corps = { canal }
      if (note.trim()) corps.note = note.trim()
      await crmApi.recontacterLead(lead.id, corps, { suppressErrorToast: true })
      toast.success('Dossier rouvert.')
      fermer()
      onDone?.()
    } catch (err) {
      const { message, fieldErrors } = getApiError(err, 'Réouverture du dossier impossible.')
      setErreurs(fieldErrors?.canal ? { canal: fieldErrors.canal } : { detail: message })
    } finally {
      setBusy(false)
    }
  }

  if (!ouvert) {
    return (
      <Button type="button" size="sm" variant="outline" data-testid="recontact-ouvrir"
        onClick={() => setOuvert(true)}>
        Le client a répondu
      </Button>
    )
  }
  return (
    <div className="mt-1.5 space-y-2 rounded-md border p-2 text-sm" data-testid="recontact-panneau">
      <FormField label="Comment le client s’est-il manifesté ?" error={erreurs.canal}>
        <div className="flex flex-col gap-1" role="radiogroup" aria-label="Comment le client s’est-il manifesté ?">
          {CANAUX.map((c) => (
            <label key={c.cle} className="flex items-center gap-2">
              <input type="radio" name="recontact-canal" value={c.cle}
                checked={canal === c.cle} onChange={() => setCanal(c.cle)} />
              {c.libelle}
            </label>
          ))}
        </div>
      </FormField>
      <FormField label="Note (facultative)" htmlFor="recontact-note">
        <Textarea id="recontact-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </FormField>
      {erreurs.detail && (
        <p role="alert" className="text-xs text-danger" data-testid="recontact-erreur">{erreurs.detail}</p>
      )}
      <p className="text-xs text-muted-foreground">
        Le dossier sort du Froid, passe « Contacté », et l’étape « Appeler le client — il a répondu au message » est posée.
      </p>
      <div className="flex gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={fermer} disabled={busy}>Annuler</Button>
        <Button type="button" size="sm" onClick={envoyer} disabled={busy} data-testid="recontact-envoyer">
          Rouvrir le dossier
        </Button>
      </div>
    </div>
  )
}
