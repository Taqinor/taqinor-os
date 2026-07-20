import { ChevronDown, Link2 } from 'lucide-react'
import {
  Button,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator,
} from '../../../ui'
import { toastSuccess, toastError } from '../../../lib/toast'

// LB50 — LE TITRE EST LE SÉLECTEUR DE VUES (patron Twenty/Attio/Folk,
// docs/design/leads-cockpit-blueprint.md) : `[Pipeline · 143 ▾]`. Le trigger
// porte le nom de la vue ACTIVE (« Pipeline » par défaut, sinon le nom de la
// SavedView appliquée) + le compteur filtré ; le menu porte les vues du
// compte (★ rang 1 = défaut de connexion, ▲▼ réordonner, 🔗 copier le lien,
// ✕ supprimer) + « ⭐ Enregistrer la vue actuelle… ». Il remplace le <h2>,
// les chips SavedViewsBar inline ET l'item ⋯ « Enregistrer » — desktop ET
// mobile. Pure re-présentation : tout l'état vit dans LeadsPage
// (useAccountViews + applySavedView/saveCurrentView/moveSavedView/
// deleteSavedView/buildShareUrl).
export default function LeadViewPicker({
  activeName, count, savedViews,
  onApply, onSave, onMove, onDelete, buildShareUrl,
}) {
  const copyLink = async (v) => {
    if (!buildShareUrl) return
    try {
      await navigator.clipboard.writeText(buildShareUrl(v))
      toastSuccess('Lien copié.')
    } catch {
      toastError('Copie du lien impossible.')
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          className="lvp-trigger"
          aria-label={`Vues — vue active : ${activeName}`}
        >
          <span className="lvp-name">{activeName}</span>
          <span className="count-badge">{count}</span>
          <ChevronDown aria-hidden="true" className="lvp-chevron" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="lvp-menu">
        {savedViews.map((v, i) => (
          <div key={v.name} className="lvp-row">
            <DropdownMenuItem className="lvp-apply" onSelect={() => onApply(v)}>
              {i === 0 && (
                <span className="lp-saved-view-star" title="Vue par défaut à chaque connexion">★</span>
              )}
              {v.name}
            </DropdownMenuItem>
            <div className="lvp-row-actions">
              <button
                type="button" className="lp-saved-view-move"
                disabled={i === 0}
                aria-label={`Monter la vue ${v.name} (le rang 1 est le défaut de connexion)`}
                title="Monter"
                onClick={() => onMove(v, -1)}
              >▲</button>
              <button
                type="button" className="lp-saved-view-move"
                disabled={i === savedViews.length - 1}
                aria-label={`Descendre la vue ${v.name}`}
                title="Descendre"
                onClick={() => onMove(v, 1)}
              >▼</button>
              {buildShareUrl && (
                <button
                  type="button" className="lp-saved-view-share"
                  aria-label={`Copier le lien de la vue ${v.name}`}
                  title="Copier le lien"
                  onClick={() => copyLink(v)}
                ><Link2 aria-hidden="true" size={12} /></button>
              )}
              <button
                type="button" className="lp-saved-view-del"
                aria-label={`Supprimer la vue ${v.name}`}
                onClick={() => onDelete(v.name)}
              >✕</button>
            </div>
          </div>
        ))}
        {savedViews.length > 0 && <DropdownMenuSeparator />}
        <DropdownMenuItem onSelect={onSave}>
          ⭐ Enregistrer la vue actuelle…
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
