// ODY2 — Le Menu d'accueil plein écran : la porte d'entrée de l'ERP.
// ----------------------------------------------------------------------------
// Paradigme ODY (fondateur 2026-08-01, « comme Odoo, en mieux ») : à l'ouverture
// on voit SES apps — celles installées par la société (ModuleToggle, ODX6) ET
// autorisées pour le rôle (ARC47). Rien d'autre.
//
// Règles tenues ici :
//   • source UNIQUE de la liste d'apps = `useInstalledApps()` (ODY1) — jamais
//     un 2ᵉ registre, jamais un filtrage recopié ;
//   • favoris = LA clé partagée VX9/VX10 (`lib/apps/appPrefs.js`), jamais une
//     2ᵉ clé localStorage ; récents = 3 max, même clé que le lanceur VX9 ;
//   • AUCUN fetch bloquant : tout vient du bootstrap `/auth/me/` + du registre
//     (les badges vivants ODY10 se posent PAR-DESSUS, sans retarder la grille) ;
//   • type-ahead à la Odoo : taper filtre, Entrée ouvre la première, ↑↓←→
//     naviguent, Échap efface (et rend le focus au champ) ;
//   • fond signature « Lumière sur Nuit » : halo brass ≤8 % sur la surface —
//     seul écran autorisé au dégradé avec ModuleHero (contrainte VXD).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Star } from 'lucide-react'
import useInstalledApps from '../../lib/apps/useInstalledApps'
import { readPinned, writePinned, readRecent, pushRecent } from '../../lib/apps/appPrefs'
import { normalise, grouperApps } from '../../lib/apps/appSearch'
import AppIcon from '../../ui/AppIcon'
import { runAppTransition, marquerIconeSortante } from '../../lib/apps/appTransition'

export default function HomeMenu() {
  const navigate = useNavigate()
  const apps = useInstalledApps()
  const [query, setQuery] = useState('')
  const [pinned, setPinned] = useState(readPinned)
  const [recent] = useState(readRecent)
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)
  // Refs des tuiles, indexées par POSITION dans l'ordre de parcours : on y
  // rend le focus impérativement (jamais via un effet sur un nœud conditionnel).
  const tileRefs = useRef([])

  const sections = useMemo(
    () => grouperApps(apps, { query, pinned, recent }),
    [apps, query, pinned, recent],
  )
  // Ordre de parcours clavier = concaténation des sections dans l'ordre affiché.
  const ordre = useMemo(() => sections.flatMap((s) => s.apps), [sections])

  // La requête a changé : la première tuile redevient l'active (« Entrée ouvre
  // la première »). Ajustement en phase de rendu (patron React « ajuster l'état
  // quand une valeur change »), pas d'effet-setState.
  const [lastQuery, setLastQuery] = useState(query)
  if (query !== lastQuery) {
    setLastQuery(query)
    setActiveIndex(0)
  }

  // ODY11 — entrer dans une app : la pastille cliquée est animée à part (View
  // Transitions quand dispo), sinon le fondu de route existant (VX134(c))
  // suffit, et sous `prefers-reduced-motion` c'est INSTANTANÉ. La navigation
  // n'est JAMAIS conditionnée à la réussite de l'effet (cf. appTransition.js).
  const ouvrir = useCallback((app, node) => {
    if (!app) return
    pushRecent(app.key)
    const nettoyer = marquerIconeSortante(node)
    const transition = runAppTransition(() => navigate(app.to))
    if (transition?.finished?.then) transition.finished.then(nettoyer, nettoyer)
    else nettoyer()
  }, [navigate])

  const basculerFavori = useCallback((event, key) => {
    event.stopPropagation()
    event.preventDefault()
    setPinned((courant) => {
      const suivant = courant.includes(key)
        ? courant.filter((k) => k !== key)
        : [...courant, key]
      writePinned(suivant)
      return suivant
    })
  }, [])

  const focusTuile = useCallback((index) => {
    setActiveIndex(index)
    const node = tileRefs.current[index]
    if (node && typeof node.focus === 'function') node.focus()
  }, [])

  // Clavier du CHAMP de recherche : ↓/→ entrent dans la grille, Entrée ouvre la
  // première app, Échap efface la requête.
  const onSearchKeyDown = useCallback((event) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      setQuery('')
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      ouvrir(ordre[0], tileRefs.current[0]?.closest?.('.home-menu-cell'))
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      if (ordre.length === 0) return
      event.preventDefault()
      focusTuile(0)
    }
  }, [ordre, ouvrir, focusTuile])

  // Clavier des TUILES : flèches (grille linéarisée — l'ordre visuel suit
  // l'ordre du DOM), Home/Fin, Entrée/Espace ouvre, Échap efface et rend le
  // focus au champ. Toute autre touche imprimable renvoie la frappe dans le
  // champ de recherche : le type-ahead reste vrai même le focus dans la grille.
  const onTileKeyDown = useCallback((event, index) => {
    const { key } = event
    if (key === 'ArrowRight' || key === 'ArrowDown') {
      event.preventDefault()
      focusTuile(Math.min(index + 1, ordre.length - 1))
      return
    }
    if (key === 'ArrowLeft' || key === 'ArrowUp') {
      event.preventDefault()
      if (index === 0) { inputRef.current?.focus(); return }
      focusTuile(index - 1)
      return
    }
    if (key === 'Home') { event.preventDefault(); focusTuile(0); return }
    if (key === 'End') { event.preventDefault(); focusTuile(ordre.length - 1); return }
    if (key === 'Escape') {
      event.preventDefault()
      setQuery('')
      inputRef.current?.focus()
      return
    }
    // Espace est EXCLU : sur un <button>, il active (sémantique native), il ne
    // se tape pas dans la recherche.
    if (key.length === 1 && key !== ' ' && !event.metaKey && !event.ctrlKey && !event.altKey) {
      // Frappe imprimable : on rebascule dans le champ, la lettre y est ajoutée.
      event.preventDefault()
      setQuery((q) => q + key)
      inputRef.current?.focus()
    }
  }, [ordre.length, focusTuile])

  // Focus initial sur le champ : la page EST le type-ahead. Effet vide → nœud
  // toujours monté (le champ n'est pas conditionnel), pas de callback ref
  // nécessaire.
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  let position = -1

  return (
    <div className="home-menu" data-testid="home-menu">
      {/* Fond signature « Lumière sur Nuit » — purement décoratif. */}
      <div className="home-menu-glow" aria-hidden="true" />

      <div className="home-menu-inner">
        <header className="home-menu-head">
          <h2 className="home-menu-title">Mes applications</h2>
          <p className="home-menu-subtitle">
            Choisissez une application pour y entrer. Tapez pour filtrer.
          </p>
        </header>

        <div className="home-menu-searchbar">
          <Search size={16} strokeWidth={1.75} aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            className="home-menu-search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onSearchKeyDown}
            placeholder="Rechercher une application…"
            aria-label="Rechercher une application"
            autoComplete="off"
          />
        </div>

        {sections.length === 0 ? (
          <p className="home-menu-vide" role="status">
            {normalise(query)
              ? 'Aucune application ne correspond à cette recherche.'
              : 'Aucune application activée.'}
          </p>
        ) : (
          sections.map((section) => (
            <section key={section.id} className="home-menu-section">
              <h3 className="home-menu-section-title">{section.titre}</h3>
              <div className="home-menu-grid" role="list">
                {section.apps.map((app) => {
                  position += 1
                  const index = position
                  const estFavori = pinned.includes(app.key)
                  return (
                    /* Cellule = conteneur de la tuile ET de l'étoile. Les deux
                       sont des <button> FRÈRES, jamais imbriqués : un contrôle
                       dans un contrôle est une violation axe (nested-interactive)
                       et casse la sémantique au lecteur d'écran. */
                    <div
                      key={app.key}
                      role="listitem"
                      className="home-menu-cell"
                      style={app.accent
                        ? { '--module-accent': `var(--module-accent-${app.accent})` }
                        : undefined}
                    >
                      <button
                        type="button"
                        ref={(node) => { tileRefs.current[index] = node }}
                        className="home-menu-tile"
                        tabIndex={index === activeIndex ? 0 : -1}
                        onFocus={() => setActiveIndex(index)}
                        onClick={(e) => ouvrir(app, e.currentTarget.closest('.home-menu-cell'))}
                        onKeyDown={(e) => onTileKeyDown(e, index)}
                      >
                        {/* ODY9 — LE composant d'icône d'app, partagé avec le
                            lanceur VX9, les épinglés VX10 et l'écran
                            Applications ODX5. */}
                        <AppIcon icon={app.icon} accent={app.accent} size="sm" />
                        <span className="home-menu-tile-label">{app.label}</span>
                      </button>
                      <button
                        type="button"
                        className="home-menu-tile-pin"
                        tabIndex={-1}
                        aria-label={estFavori
                          ? `Retirer ${app.label} des favoris`
                          : `Ajouter ${app.label} aux favoris`}
                        onClick={(e) => basculerFavori(e, app.key)}
                      >
                        <Star
                          size={13}
                          strokeWidth={1.75}
                          aria-hidden="true"
                          fill={estFavori ? 'currentColor' : 'none'}
                        />
                      </button>
                    </div>
                  )
                })}
              </div>
            </section>
          ))
        )}
      </div>
    </div>
  )
}
