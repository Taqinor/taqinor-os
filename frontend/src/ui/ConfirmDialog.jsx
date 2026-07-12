import { useState } from 'react'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogFooter,
  AlertDialogTitle, AlertDialogDescription, AlertDialogCancel, AlertDialogAction,
} from './AlertDialog'
import { Input } from './Input'

// VX244 — primitive de confirmation À SÉVÉRITÉ. Défaut prouvé : 68
// `window.confirm` dans 44 fichiers, UNE seule gravité — supprimer un litige
// client (dossier légal), un article KB avec sous-arbre, un secret webhook et
// un preset UI passaient tous par le MÊME dialog natif alors que le repo sait
// déjà faire mieux (`ForceDeleteModal` de `StockList.jsx`, la confirmation
// « maison » d'`UsersManagement.jsx`) sans jamais l'avoir généralisé.
//
// `severity` :
//   - 'low'    — confirmation simple (Annuler/Confirmer), pas de saisie.
//   - 'medium' — variante visuelle destructive, pas de saisie.
//   - 'high'   — confirmation TAPÉE obligatoire (`confirmText`) : le bouton
//                d'action reste désactivé tant que la saisie ne correspond
//                pas EXACTEMENT.
//
// Sémantique clavier délibérée :
//   - Escape (comportement Radix par défaut sur l'AlertDialog) ANNULE
//     TOUJOURS, quelle que soit la sévérité ;
//   - Entrée ne confirme JAMAIS un `high` — le contenu n'est PAS un `<form>`,
//     donc taper puis Entrée dans le champ ne soumet rien ; seul un clic
//     explicite sur le bouton (activé une fois la saisie valide) confirme.
const SEVERITY_STYLES = {
  low: { titleClass: '', actionVariant: 'default' },
  medium: { titleClass: 'text-destructive', actionVariant: 'destructive' },
  high: { titleClass: 'text-destructive', actionVariant: 'destructive' },
}

/**
 * @param {{
 *   open: boolean, onOpenChange: (open: boolean) => void,
 *   severity?: 'low'|'medium'|'high', title: string, description?: string,
 *   confirmLabel?: string, cancelLabel?: string,
 *   confirmText?: string, // requis pour severity='high' (à retaper à l'identique)
 *   loading?: boolean, onConfirm: () => void, children?: import('react').ReactNode,
 * }} props
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  severity = 'medium',
  title,
  description,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  confirmText,
  loading = false,
  onConfirm,
  children,
}) {
  const [typed, setTyped] = useState('')
  const isHigh = severity === 'high'
  const isValid = !isHigh || (confirmText != null && typed.trim() === String(confirmText).trim())
  const style = SEVERITY_STYLES[severity] || SEVERITY_STYLES.medium

  const handleOpenChange = (next) => {
    if (!next) setTyped('')
    onOpenChange?.(next)
  }

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className={style.titleClass}>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>

        {children}

        {isHigh && (
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="confirm-dialog-typed">
              Tapez <code className="rounded bg-destructive/10 px-1.5 py-0.5 text-destructive">{confirmText}</code> pour confirmer
            </label>
            <Input
              id="confirm-dialog-typed"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={`Saisir : ${confirmText}`}
              autoFocus
            />
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            variant={style.actionVariant}
            disabled={!isValid || loading}
            onClick={(e) => { e.preventDefault(); onConfirm?.() }}
          >
            {loading ? 'En cours…' : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export default ConfirmDialog
