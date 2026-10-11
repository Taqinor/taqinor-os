import {
  Label, Textarea, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'

/* Champs de formulaire GED partagés par les dialogues des écrans avancés
   (approbation, rétention, tags, checklist, planifications) : choix d'un
   document et commentaire optionnel. Un seul endroit — jamais recopiés. */

export function ChampDocument({
  documents, documentId, setDocumentId, disabled, ariaLabel,
}) {
  return (
    <div>
      <Label>Document</Label>
      <Select value={documentId} onValueChange={setDocumentId} disabled={disabled}>
        <SelectTrigger aria-label={ariaLabel}><SelectValue placeholder="Choisir un document…" /></SelectTrigger>
        <SelectContent>
          {documents.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  )
}

export function ChampCommentaire({ commentaire, setCommentaire }) {
  return (
    <div>
      <Label>Commentaire (optionnel)</Label>
      <Textarea value={commentaire} onChange={(e) => setCommentaire(e.target.value)} rows={3} />
    </div>
  )
}
