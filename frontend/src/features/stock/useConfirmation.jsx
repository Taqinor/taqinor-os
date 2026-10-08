import { useCallback, useRef, useState } from 'react'
import { ConfirmDialog } from '../../ui/ConfirmDialog'

/* ASTK231 (C-ASTK-042, FOUR-19) — confirmation des gestes des écrans stock par
   l'AlertDialog COMMUNE (`ui/ConfirmDialog`), jamais `window.confirm` (boîte
   native bloquante, hors thème, refusée par l'oracle n°8 de qa-explorer).

   Usage :
     const [confirmer, dialogueConfirmation] = useConfirmation()
     const supprimer = async (x) => {
       if (!(await confirmer({ title: 'Supprimer ?', confirmLabel: 'Supprimer' }))) return
       …
     }
     return (<div>… {dialogueConfirmation}</div>)

   `confirmer(opts)` résout `true` (bouton d'action) ou `false` (Annuler,
   Échap, clic hors boîte). `opts` : { title, description?, confirmLabel?,
   severity? ('low'|'medium'), } — une chaîne seule vaut `title`. */
export function useConfirmation() {
  const [options, setOptions] = useState(null)
  const resoudre = useRef(null)

  const confirmer = useCallback((opts) => new Promise((resolve) => {
    resoudre.current?.(false)
    resoudre.current = resolve
    setOptions(typeof opts === 'string' ? { title: opts } : (opts ?? {}))
  }), [])

  const fermer = (ok) => {
    const resolve = resoudre.current
    resoudre.current = null
    setOptions(null)
    resolve?.(ok)
  }

  const dialogueConfirmation = (
    <ConfirmDialog
      open={!!options}
      onOpenChange={(o) => { if (!o) fermer(false) }}
      severity={options?.severity ?? 'medium'}
      title={options?.title ?? ''}
      description={options?.description}
      confirmLabel={options?.confirmLabel ?? 'Confirmer'}
      onConfirm={() => fermer(true)}
    />
  )

  return [confirmer, dialogueConfirmation]
}
