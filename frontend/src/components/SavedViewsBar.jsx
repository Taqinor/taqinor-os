import { Link2 } from 'lucide-react'
import { Button } from '../ui'
import { toastSuccess, toastError } from '../lib/toast'

// VX145(c) — Barre « vues enregistrées » partagée. Le balisage était
// copié-collé entre `pages/crm/leads/LeadsPage.jsx` et `pages/crm/ClientList.jsx`
// (même classes `.lp-saved-views/.lp-saved-view-chip/-apply/-del`, déjà
// génériques dans index.css — cf. commentaire FG11) et occupait une rangée
// pleine largeur même sans aucune vue. Ce composant factorise le rendu ;
// l'état (useSavedViews) et la logique save/apply restent dans chaque écran
// (les formes sauvegardées diffèrent : filters+view pour les leads,
// typeFilter pour les clients).
//
// 0 rangée dédiée quand `savedViews` est vide : la liste de puces ne rend
// rien dans ce cas (rien à afficher) ; l'appelant est responsable de placer
// le déclencheur « Enregistrer cette vue » (`onSave`) dans une rangée déjà
// existante (ex. l'en-tête de page ou la rangée de filtres) plutôt que de
// réserver une rangée pleine largeur pour ce seul bouton.
// LB26 — prop ADDITIVE optionnelle `buildShareUrl(view)` (blueprint D5) :
// quand fournie (page leads uniquement, sérialisée via urlFilters.js), chaque
// puce gagne une action « Copier le lien ». Absente (ClientList, DevisList…)
// → comportement STRICTEMENT inchangé, ce composant reste partagé sans forker.
// LB46/LB49 — props ADDITIVES optionnelles : `inline` (chips DANS la ligne de
// contrôle, plus jamais une rangée dédiée — cockpit une ligne) et
// `onMove(v, dir)` (▲▼ de rang, vues de compte : la n°1 est marquée ★ =
// défaut de connexion). Absentes (ClientList…) → rendu STRICTEMENT inchangé.
export default function SavedViewsBar({ savedViews, onApply, onDelete, buildShareUrl, inline, onMove }) {
  if (!savedViews || savedViews.length === 0) return null

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
    <div className={inline ? 'lp-saved-views lp-saved-views-inline' : 'lp-saved-views'}>
      {savedViews.map((v, i) => (
        <span key={v.name} className="lp-saved-view-chip">
          {onMove && i === 0 && (
            <span className="lp-saved-view-star" title="Vue par défaut à chaque connexion" aria-label="Vue par défaut">★</span>
          )}
          <button type="button" className="lp-saved-view-apply"
                  onClick={() => onApply(v)} title="Appliquer cette vue">
            {v.name}
          </button>
          {buildShareUrl && (
            <button type="button" className="lp-saved-view-share"
                    onClick={() => copyLink(v)}
                    aria-label={`Copier le lien de la vue ${v.name}`}
                    title="Copier le lien">
              <Link2 aria-hidden="true" size={12} />
            </button>
          )}
          {onMove && (
            <>
              <button type="button" className="lp-saved-view-move"
                      onClick={() => onMove(v, -1)} disabled={i === 0}
                      aria-label={`Monter la vue ${v.name} (le rang 1 est le défaut de connexion)`}
                      title="Monter">▲</button>
              <button type="button" className="lp-saved-view-move"
                      onClick={() => onMove(v, 1)} disabled={i === savedViews.length - 1}
                      aria-label={`Descendre la vue ${v.name}`}
                      title="Descendre">▼</button>
            </>
          )}
          <button type="button" className="lp-saved-view-del"
                  onClick={() => onDelete(v.name)}
                  aria-label={`Supprimer la vue ${v.name}`}>
            ✕
          </button>
        </span>
      ))}
    </div>
  )
}

// Bouton « ⭐ Enregistrer cette vue » — même style partout (link, sm), séparé
// du corps ci-dessus pour que chaque écran le place dans SA rangée déjà
// existante (en-tête ou filtres) au lieu d'une rangée dédiée.
export function SaveViewButton({ onSave }) {
  return (
    <Button type="button" variant="link" size="sm" onClick={onSave}>
      ⭐ Enregistrer cette vue
    </Button>
  )
}
