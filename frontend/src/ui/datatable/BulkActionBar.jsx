import { useEffect, useRef, useState } from 'react'
import { X, MoreHorizontal, Copy } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../Button'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel,
} from '../DropdownMenu'
import { rowsToTSV } from './csv.js'
import { toast } from '../confirm'

/* ============================================================================
   VX110 — « Copier » vers le presse-papiers en TSV. Colle proprement en colonnes
   dans Excel/Sheets, et en texte lisible dans WhatsApp — sans passer par un
   fichier .csv. Réutilise la garde anti-injection via `rowsToTSV`/`escapeCSVCell`.
   ========================================================================== */

/** Écrit du texte au presse-papiers (Clipboard API + repli execCommand pour les
 *  contextes qui la bloquent). Renvoie une promesse résolue à `true`/`false`. */
async function writeClipboard(text) {
  if (navigator?.clipboard?.writeText) {
    try { await navigator.clipboard.writeText(text); return true } catch { /* repli */ }
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  } catch { return false }
}

/** Copie les lignes fournies au presse-papiers en TSV, avec toast de résultat.
 *  `rows` = la sélection si elle existe, sinon les lignes filtrées. */
export async function copyRowsAsTSV(rows, columns) {
  const list = rows || []
  if (!list.length) { toast.error('Aucune ligne à copier.'); return false }
  const ok = await writeClipboard(rowsToTSV(list, columns))
  if (ok) toast.success(`${list.length} ligne(s) copiée(s) — collez dans Excel.`)
  else toast.error('Copie impossible — réessayez.')
  return ok
}

/** Descripteur d'action « Copier » prêt à pousser dans `bulkActions`. Copie la
 *  sélection `rows`, ou `filteredRows` si aucune sélection. */
export function buildCopyTSVAction({ rows, filteredRows, columns }) {
  return {
    id: 'copy-tsv',
    label: 'Copier',
    icon: Copy,
    onClick: () => copyRowsAsTSV(rows?.length ? rows : (filteredRows || []), columns),
  }
}

/* ============================================================================
   H32/H132 — Barre d'actions groupées flottante. CONFIGURABLE : les actions sont
   passées en props (`actions`), jamais codées en dur sur les leads. Dès qu'au
   moins une ligne est sélectionnée, la barre GLISSE en bas-centre (fixe,
   persistante au défilement) ; ancrée en bas sur mobile, flottante centrée sur
   desktop.
   `actions` = [{ id, label, icon?, variant?, onClick(selection), destructive? }]
   H132 — au-delà de 3 actions, les suivantes passent dans un menu de débordement
   « Plus », et un bouton « Tout désélectionner » remet la sélection à zéro.
   ========================================================================== */

const MAX_INLINE = 3

// VX133 — la garde `if (!count) return null` démonte la barre INSTANTANÉMENT
// au premier clic sur la dernière ligne : jamais d'animation de sortie
// malgré le commentaire H132 ci-dessous qui prétendait « glisser depuis le
// bas ». Pattern exit-sans-lib (aucune dépendance de transition dans le
// repo) : on reste monté un `--motion-fast` de plus après que `count`
// retombe à 0, le temps de jouer `slide-out-bottom`, puis on démonte pour de
// vrai sur `onAnimationEnd`.
export function BulkActionBar({ count, actions = [], onClear, className }) {
  const [mounted, setMounted] = useState(count > 0)
  const wasOpen = useRef(count > 0)

  useEffect(() => {
    if (count > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- (ré)ouvre la barre synchronement avec le compteur de sélection
      setMounted(true)
      wasOpen.current = true
    } else if (wasOpen.current) {
      // Reste monté le temps de l'animation de sortie ; onAnimationEnd
      // démontera réellement une fois `slide-out-bottom` terminée.
      wasOpen.current = false
    }
  }, [count])

  if (!mounted) return null
  const open = count > 0
  const inline = actions.slice(0, MAX_INLINE)
  const overflow = actions.slice(MAX_INLINE)
  return (
    <div
      role="region"
      aria-label={`${count} ligne(s) sélectionnée(s)`}
      className={cn(
        'fixed inset-x-0 bottom-0 z-[var(--z-sticky)] flex justify-center px-3 pb-3',
        'sm:bottom-6 pointer-events-none',
        className,
      )}
    >
      <div
        onAnimationEnd={() => { if (!open) setMounted(false) }}
        className={cn(
          'pointer-events-auto flex w-full max-w-2xl items-center gap-2 rounded-xl border border-border',
          'bg-popover/95 p-2 pl-3 text-popover-foreground shadow-ui-lg backdrop-blur',
          // H132/VX133 — entrée ET sortie glissées depuis le bas (respecte
          // prefers-reduced-motion via la définition de l'animation).
          open ? 'animate-slide-in-bottom' : 'animate-slide-out-bottom',
        )}
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          <span className="inline-flex min-w-6 items-center justify-center rounded-md bg-primary px-1.5 py-0.5 text-xs font-semibold text-primary-foreground">
            {count}
          </span>
          <span className="hidden sm:inline text-muted-foreground">sélectionné{count > 1 ? 's' : ''}</span>
        </span>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          {inline.map((a) => {
            const Icon = a.icon
            return (
              <Button
                key={a.id}
                size="sm"
                variant={a.variant ?? (a.destructive ? 'destructive' : 'secondary')}
                onClick={() => a.onClick?.()}
              >
                {Icon && <Icon />}
                <span className={cn(a.iconOnlyMobile && 'hidden sm:inline')}>{a.label}</span>
              </Button>
            )
          })}
          {overflow.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="secondary">
                  <MoreHorizontal />
                  <span>Plus</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="top">
                <DropdownMenuLabel>Autres actions</DropdownMenuLabel>
                {overflow.map((a) => {
                  const Icon = a.icon
                  return (
                    <DropdownMenuItem key={a.id} destructive={a.destructive} onSelect={() => a.onClick?.()}>
                      {Icon && <Icon />} {a.label}
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button variant="ghost" size="sm" onClick={onClear} aria-label="Tout désélectionner">
            <X />
            <span className="hidden sm:inline">Tout désélectionner</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

export default BulkActionBar
