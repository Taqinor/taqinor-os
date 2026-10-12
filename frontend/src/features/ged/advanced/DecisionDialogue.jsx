import { useState } from 'react'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  toast,
} from '../../../ui'
import { errMessage } from './shared.js'
import { ChampCommentaire } from './ChampsGed.jsx'

/* Dialogue d'approbation / rejet GED, partagé par les demandes d'approbation
   (ApprobationPage) et les dispositions de rétention (RetentionPage) : même
   commentaire optionnel, mêmes boutons, seuls l'objet, le résumé et les deux
   appels API changent. Un seul endroit — jamais recopié page par page. */
export default function DecisionDialogue({ decision, onClose, onDone, objet, appels, children }) {
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)
  const approuver = decision.type === 'approuver'

  const submit = async () => {
    setSaving(true)
    try {
      if (approuver) await appels.approuver(decision.demande.id, { commentaire })
      else await appels.rejeter(decision.demande.id, { commentaire })
      toast.success(approuver ? 'Demande approuvée.' : 'Demande rejetée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{approuver ? `Approuver ${objet}` : `Rejeter ${objet}`}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            {children}
          </p>
          <ChampCommentaire commentaire={commentaire} setCommentaire={setCommentaire} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button variant={approuver ? 'default' : 'destructive'} onClick={submit} disabled={saving}>
            {saving ? '…' : (approuver ? 'Approuver' : 'Rejeter')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
