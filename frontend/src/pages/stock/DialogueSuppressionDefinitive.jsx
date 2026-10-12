import { useState } from 'react'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Input,
} from '../../ui'

/* Confirmation de suppression définitive (AlertDialog + saisie de confirmation)
   commune à Stock (produit) et Fournisseurs : `resume` = récapitulatif de
   l'élément, `expected` = texte à retaper, `idChamp` = id du champ de saisie. */
export default function DialogueSuppressionDefinitive({
  description, resume, expected, idChamp, loading, onCancel, onConfirm,
}) {
  const [typed, setTyped] = useState('')
  const isValid = typed.trim() === expected.trim()

  return (
    <AlertDialog open onOpenChange={(o) => { if (!o) onCancel() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="text-destructive">Suppression définitive</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>

        <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm leading-relaxed">
          {resume}
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor={idChamp}>
            Tapez <code className="rounded bg-destructive/10 px-1.5 py-0.5 text-destructive">{expected}</code> pour confirmer
          </label>
          <Input id={idChamp} value={typed} onChange={(e) => setTyped(e.target.value)}
                 placeholder={`Saisir : ${expected}`} autoFocus />
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Annuler</AlertDialogCancel>
          <AlertDialogAction
            disabled={!isValid || loading}
            onClick={(e) => { e.preventDefault(); onConfirm() }}
          >
            {loading ? 'Suppression…' : 'Supprimer définitivement'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
