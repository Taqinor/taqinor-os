// VX35 — Sidebar verticale des Paramètres (remplace le TabsList plat scrollable).
// Architecture d'information ≤ 2 niveaux (façon Stripe/Linear) : familles
// (SETTINGS_GROUPS) → onglets. La recherche existante est rendue EN TÊTE de la
// sidebar via le slot `searchSlot` (aucune logique de recherche ici : elle reste
// dans ParametresEntreprise / searchSettings, inchangée).
//
// Contrat : les clés d'onglets ne changent pas ; `onSelect(key)` reçoit la même
// clé que celle passée jusqu'ici à setTab, donc le rendu du formulaire est
// identique. `groupTabs()` garantit qu'aucun onglet ne disparaît (fallback
// « Avancé »).
import { cn } from '../../lib/cn'

export default function SettingsSidebar({ groups, activeTab, onSelect, searchSlot }) {
  return (
    <nav aria-label="Sections des paramètres" className="pe-settings-sidebar w-full shrink-0 md:w-64">
      {searchSlot ? <div className="mb-3">{searchSlot}</div> : null}
      <div className="flex flex-col gap-4">
        {groups.map(group => (
          <div key={group.key}>
            <h3 className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {group.label}
            </h3>
            <ul className="flex flex-col gap-0.5">
              {group.tabs.map(t => {
                const active = t.key === activeTab
                return (
                  <li key={t.key}>
                    <button
                      type="button"
                      onClick={() => onSelect(t.key)}
                      aria-current={active ? 'page' : undefined}
                      className={cn(
                        'flex w-full items-center rounded-md px-3 py-1.5 text-left text-sm transition-colors',
                        active
                          ? 'bg-accent font-medium text-foreground'
                          : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                      )}
                    >
                      {t.label}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  )
}
