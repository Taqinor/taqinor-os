import { Button } from '../ui'

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
export default function SavedViewsBar({ savedViews, onApply, onDelete }) {
  if (!savedViews || savedViews.length === 0) return null

  return (
    <div className="lp-saved-views">
      {savedViews.map((v) => (
        <span key={v.name} className="lp-saved-view-chip">
          <button type="button" className="lp-saved-view-apply"
                  onClick={() => onApply(v)} title="Appliquer cette vue">
            {v.name}
          </button>
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
