// NTUX12 — Favoris épinglés : widget autonome (Dashboard/sidebar) listant les
// enregistrements épinglés par l'utilisateur courant avec accès direct.
// STRICTEMENT PERSONNEL côté serveur (get_queryset filtre déjà owner=user) :
// ce widget n'affiche jamais les favoris d'un collègue. Même patron que
// `RecentEntitiesWidget.jsx` (NTUX11) — rend RIEN si la liste est vide.
import { Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../ui'
import { ROUTE, TYPE_LABEL, TYPE_ACCENT } from '../../lib/search/entityRoutes'
import { useFavoris } from './useFavoris'

// Clé de modèle serveur ('<app_label>.<model>', cf. FavoriUtilisateurSerializer)
// → clé de type ROUTE/TYPE_LABEL/TYPE_ACCENT (lib/search/entityRoutes.js) —
// même table que la palette ⌘K et les Récents, aucune route dupliquée. Un
// `modele` absent d'ici (favori sur un type encore non câblé à la recherche
// globale) reste affiché — juste sans navigation directe, jamais masqué.
const MODELE_TO_TYPE = {
  'crm.lead': 'lead',
  'crm.client': 'client',
  'ventes.devis': 'devis',
  'facturation.facture': 'facture',
  'installations.installation': 'chantier',
  'sav.ticket': 'ticket',
  'stock.produit': 'produit',
}

export default function FavorisWidget() {
  const navigate = useNavigate()
  const { favoris, loading } = useFavoris()

  if (loading || !favoris.length) return null

  return (
    <Card className="cv-auto" data-testid="favoris-widget">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Star className="size-4 text-muted-foreground" aria-hidden="true" />
          Favoris
        </CardTitle>
        <CardDescription>Vos enregistrements épinglés</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-1">
          {favoris.map((f) => {
            const type = MODELE_TO_TYPE[f.modele]
            const make = type && ROUTE[type]
            return (
              <li key={f.id}>
                <button
                  type="button"
                  disabled={!make}
                  onClick={() => make && navigate(make(f.object_id))}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-accent/60 focus-ring disabled:cursor-default disabled:opacity-60 disabled:hover:bg-transparent"
                >
                  {type && TYPE_ACCENT[type] && (
                    <span
                      className="size-1.5 shrink-0 rounded-full"
                      style={{ background: `var(--module-accent-${TYPE_ACCENT[type]})` }}
                      aria-hidden="true"
                    />
                  )}
                  <span className="min-w-0 flex-1 truncate font-medium text-foreground">
                    {f.libelle || (type && TYPE_LABEL[type]) || 'Élément épinglé'}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
