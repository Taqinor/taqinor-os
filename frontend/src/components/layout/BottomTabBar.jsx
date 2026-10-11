// I36 — Barre d'onglets inférieure (mobile ≤ 768 px uniquement, via CSS).
// Navigation primaire au pouce, inset de zone sûre iOS respecté.
//
// ODY6 — LE MÊME PARADIGME AU POUCE (fondateur 2026-08-01).
// ----------------------------------------------------------------------------
// Avant ODY6, cette barre était une pile GLOBALE de 4 raccourcis codés en dur
// (Accueil `/dashboard`, Leads, Devis, Activités) — trois apps différentes
// mélangées sous le pouce, exactement ce que le paradigme « ERP-Apps » retire
// du bureau. Désormais :
//
//   • en IMMERSION (une app est active, cf. `useActiveApp` — ODY4), la barre
//     n'affiche QUE les onglets de CETTE app, plus un onglet « Apps » qui EST
//     la sortie (il remplace l'ancien onglet « Accueil » figé sur
//     `/dashboard` ; le tableau de bord est devenu une app comme une autre) ;
//   • le tiroir « Plus » (VX12) n'est plus la grille de TOUTES les catégories
//     mais le tiroir DE L'APP ACTIVE : ses sections, et elles seules ;
//   • hors de toute app (Menu d'accueil `/apps`, préférences, écrans
//     transverses) la barre ne rend RIEN : sur mobile le Menu d'accueil EST
//     l'accueil, une barre d'onglets qui pointerait vers lui-même n'ajouterait
//     qu'un repère faux. Le ⊞ de l'en-tête reste la sortie partout.
//
// ODY33 — le chemin LEGACY (pile globale de 4 onglets + grille de toutes les
// catégories) et son kill-switch ODY30 sont retirés : un seul rendu reste.
import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Menu, X, LayoutGrid } from 'lucide-react'
// ODY4/ODY6 — l'app active (dérivée de la ROUTE, jamais d'un état mémorisé) et
// la sortie canonique vers le Menu d'accueil.
import { useActiveApp, HOME_MENU_PATH } from '../../lib/apps/ActiveAppContext'

// M156 — Plafond DUR de 5 onglets atteignables au pouce : au-delà, le 5e
// raccourci serait hors zone de pouce confortable.
const MAX_TABS = 5
// ODY6 — l'onglet « Apps » (la sortie) occupe UN des 5 créneaux : il en reste
// donc 4 pour l'app. Si l'app a plus de 4 sections, on en montre 3 et le 4e
// créneau devient « Plus » (tiroir de l'app) — jamais 6 onglets.
const MAX_APP_TABS = MAX_TABS - 1

/**
 * splitAppTabs — répartition PURE des sections d'une app entre onglets directs
 * et tiroir « Plus ». Testable sans React.
 *   ≤ 4 sections → toutes directes, aucun « Plus » (rien à cacher) ;
 *   > 4 sections → 3 directes + « Plus » qui ouvre la liste COMPLÈTE.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function splitAppTabs(items) {
  const all = items ?? []
  if (all.length <= MAX_APP_TABS) return { directs: all, more: false }
  return { directs: all.slice(0, MAX_APP_TABS - 1), more: true }
}

// La barre EST celle de l'app active.
export default function BottomTabBar() {
  const activeApp = useActiveApp()
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Hors de toute app : aucune barre (le Menu d'accueil est l'accueil mobile).
  if (!activeApp) return null

  const { directs, more } = splitAppTabs(activeApp.items)

  return (
    <>
      <nav
        className="bottom-tabbar bottom-tabbar--app"
        aria-label={`Navigation ${activeApp.label}`}
        data-app={activeApp.key}
      >
        {/* LA SORTIE, au pouce : elle remplace l'ancien onglet « Accueil »
            figé sur /dashboard. Nom accessible « Apps » — délibérément
            DIFFÉRENT de « Toutes les apps » (le ⊞ de l'en-tête et le pied de
            la Sidebar), pour qu'aucune assertion e2e existante ne se retrouve
            avec deux cibles homonymes. */}
        <NavLink
          to={HOME_MENU_PATH}
          end
          className={({ isActive }) => `bottom-tab bottom-tab-apps${isActive ? ' active' : ''}`}
        >
          <LayoutGrid size={20} aria-hidden="true" />
          <span className="bottom-tab-label">Apps</span>
        </NavLink>

        {directs.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end
            // Le libellé est tronqué par ellipsis quand il est long
            // (« Approvisionnement », « Bons de commande ») : le tooltip natif
            // garde le texte entier accessible, comme la Sidebar (VX175(d)).
            title={item.label}
            className={({ isActive }) => `bottom-tab${isActive ? ' active' : ''}`}
          >
            <span className="bottom-tab-icon" aria-hidden="true">{item.icon}</span>
            <span className="bottom-tab-label">{item.label}</span>
          </NavLink>
        ))}

        {more && (
          <button type="button" className="bottom-tab bottom-tab-more"
                  onClick={() => setDrawerOpen(true)}
                  aria-label={`Plus de sections de ${activeApp.label}`}>
            <Menu size={20} aria-hidden="true" />
            <span className="bottom-tab-label">Plus</span>
          </button>
        )}
      </nav>
      {drawerOpen && (
        <AppSectionsDrawer app={activeApp} onClose={() => setDrawerOpen(false)} />
      )}
    </>
  )
}

/* ODY6 — Tiroir « Plus » DE L'APP : une seule liste, ses sections et elles
   seules. Plus de grille de catégories inter-apps (c'était le lanceur d'apps
   déguisé — le Menu d'accueil le fait mieux, et l'onglet « Apps » y mène).
   Un seul niveau : l'app est déjà le niveau, la contrainte ODY « ≤ 2 niveaux
   de menu » est donc tenue par construction. */
function AppSectionsDrawer({ app, onClose }) {
  return (
    <div
      className="app-grid-drawer"
      role="dialog"
      aria-modal="true"
      // Nom accessible porté par un aria-label sur le conteneur (jamais un
      // heading) : ajouter un <h*> nommé d'après une app créerait un doublon
      // de rôle `heading` avec le titre de la page (assertions e2e).
      aria-label={`Sections de ${app.label}`}
    >
      <div className="app-grid-overlay" onClick={onClose} />
      <div className="app-grid-panel">
        <div className="app-grid-header">
          <span className="app-grid-title">{app.label}</span>
          <button type="button" className="app-grid-close" onClick={onClose} aria-label="Fermer">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        {/* Pas de `role="list"` ici : axe exige alors des enfants `listitem`
            (règle `aria-required-children`, impact critique) — une liste de
            liens n'a besoin d'aucun rôle ARIA pour être correcte. */}
        <div className="app-grid-items">
          {app.items.map((item) => (
            <NavLink key={item.to} to={item.to} end className="app-grid-item" onClick={onClose}>
              <span className="app-grid-item-icon">{item.icon}</span>
              <span className="app-grid-item-label">{item.label}</span>
            </NavLink>
          ))}
        </div>
      </div>
    </div>
  )
}
