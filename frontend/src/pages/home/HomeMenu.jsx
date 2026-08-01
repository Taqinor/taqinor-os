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
//   • AUCUN fetch bloquant : tout vient du bootstrap `/auth/me/` + du registre ;
//   • type-ahead à la Odoo : taper filtre, Entrée ouvre la première, ↑↓←→
//     naviguent, Échap efface (ODY2) ;
//   • préchargement au survol/focus via la table EXISTANTE `prefetchMap.js`
//     (ODY12) et transition de vue à l'entrée (ODY11) ;
//   • réordonnancement au glisser avec `@dnd-kit/core` SEUL, poignée dédiée
//     donc accessible au clavier (ODY13) ;
//   • fond signature « Lumière sur Nuit » : halo brass ≤8 % sur la surface —
//     seul écran autorisé au dégradé avec ModuleHero (contrainte VXD).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  DndContext, KeyboardSensor, PointerSensor, TouchSensor,
  closestCenter, useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { GripVertical, Search, Star } from 'lucide-react'
import useInstalledApps from '../../lib/apps/useInstalledApps'
import {
  readPinned, writePinned, readRecent, pushRecent, readOrder, writeOrder, applyOrder,
} from '../../lib/apps/appPrefs'
import { normalise, grouperApps } from '../../lib/apps/appSearch'
import AppIcon from '../../ui/AppIcon'
import { runAppTransition, marquerIconeSortante } from '../../lib/apps/appTransition'
import { prefetchRoute } from '../../router/prefetchMap'
// ODY14 — premier matin : état vide illustré (variante EmptyState VX40) et
// bannière de prise en main (VX36) remontée sur le Menu d'accueil.
import { EmptyState } from '../../ui/EmptyState'
import { Button } from '../../ui/Button'
import { useIsAdmin } from '../../hooks/useHasPermission'
import OnboardingBanner from '../../components/OnboardingBanner'
import useAppBadges from '../../lib/apps/useAppBadges'
// ODY6 — LE MÊME écran sert d'accueil mobile : sous 768 px la grille passe en
// 3-4 colonnes (CSS) et le type-ahead bureau cède la place à une barre de
// RECHERCHE tactile. Hook média PARTAGÉ (M158) — jamais une 2e détection.
import { useIsMobile } from '../../ui/ResponsiveDialog'

/* ODY13 — annonces FR du glisser-déposer (le défaut de dnd-kit est anglais).
   Un lecteur d'écran doit pouvoir suivre tout le trajet au clavier. */
function construireAnnonces(nomPour) {
  return {
    onDragStart: ({ active }) => `Déplacement de ${nomPour(active.id)} commencé.`,
    onDragOver: ({ active, over }) => (over
      ? `${nomPour(active.id)} sera placée à la position de ${nomPour(over.id)}.`
      : `${nomPour(active.id)} n’est au-dessus d’aucune position valide.`),
    onDragEnd: ({ active, over }) => (over
      ? `${nomPour(active.id)} déposée à la position de ${nomPour(over.id)}.`
      : `${nomPour(active.id)} reposée à sa place.`),
    onDragCancel: ({ active }) => `Déplacement de ${nomPour(active.id)} annulé.`,
  }
}

const INSTRUCTIONS_LECTEUR = {
  draggable:
    'Appuyez sur Entrée ou Espace sur la poignée pour commencer à déplacer une '
    + 'application. Utilisez les flèches pour choisir sa nouvelle position, '
    + 'Entrée ou Espace pour déposer, Échap pour annuler.',
}

/* CelluleApp — une app de la grille. Trois contrôles FRÈRES, jamais imbriqués
   (un contrôle dans un contrôle est une violation axe `nested-interactive`) :
     1. la tuile (ouvre l'app) — c'est elle qui porte la navigation clavier ;
     2. l'étoile (favori) ;
     3. la poignée de déplacement (ODY13) — SÉPARÉE de la tuile exprès : le
        capteur clavier de dnd-kit s'active sur Entrée/Espace, qui sont déjà
        l'activation native du bouton d'ouverture. Les deux sur le même
        élément se voleraient la touche. */
function CelluleApp({
  app, index, actif, estFavori, reordonnable, badge,
  onOuvrir, onBasculerFavori, onFocusTuile, onKeyDownTuile, registerRef,
}) {
  const { attributes, listeners, setNodeRef: setDrag, isDragging } = useDraggable({
    id: app.key, disabled: !reordonnable,
  })
  const { setNodeRef: setDrop, isOver } = useDroppable({
    id: app.key, disabled: !reordonnable,
  })
  const setRefs = useCallback((node) => { setDrag(node); setDrop(node) }, [setDrag, setDrop])

  return (
    <div
      ref={setRefs}
      role="listitem"
      // ODY6/ODY31 — ancre DOM stable de la tuile, même convention que
      // `aside.sidebar[data-app]` (ODY4) : les specs Playwright désignent une
      // app par sa CLÉ, jamais par un libellé (que le badge ODY10 rallonge).
      data-app={app.key}
      className={[
        'home-menu-cell',
        isDragging ? 'home-menu-cell--drag' : '',
        isOver ? 'home-menu-cell--over' : '',
      ].filter(Boolean).join(' ')}
      style={app.accent ? { '--module-accent': `var(--module-accent-${app.accent})` } : undefined}
    >
      <button
        type="button"
        ref={(node) => { registerRef(index, node) }}
        className="home-menu-tile"
        tabIndex={actif ? 0 : -1}
        onMouseEnter={() => prefetchRoute(app.to)}
        onFocus={() => { onFocusTuile(index); prefetchRoute(app.to) }}
        onClick={(e) => onOuvrir(app, e.currentTarget.closest('.home-menu-cell'))}
        onKeyDown={(e) => onKeyDownTuile(e, index)}
      >
        <span className="home-menu-tile-iconwrap">
          <AppIcon icon={app.icon} accent={app.accent} size="sm" />
          {/* ODY10 — badge vivant : rendu APRÈS la grille (la réponse fédérée
              arrive plus tard), jamais un « 0 », et absent pour une app dont
              le module est désactivé (le serveur ne l'émet même pas). */}
          {badge && (
            <span className="home-menu-tile-badge" title={badge.label}>
              <span aria-hidden="true">{badge.valeur}</span>
              <span className="sr-only">{`${badge.valeur} — ${badge.label}`}</span>
            </span>
          )}
        </span>
        <span className="home-menu-tile-label">{app.label}</span>
      </button>
      <button
        type="button"
        className="home-menu-tile-pin"
        tabIndex={-1}
        aria-label={estFavori
          ? `Retirer ${app.label} des favoris`
          : `Ajouter ${app.label} aux favoris`}
        onClick={(e) => onBasculerFavori(e, app.key)}
      >
        <Star size={13} strokeWidth={1.75} aria-hidden="true" fill={estFavori ? 'currentColor' : 'none'} />
      </button>
      {reordonnable && (
        <button
          type="button"
          className="home-menu-tile-grip"
          aria-label={`Déplacer ${app.label}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical size={13} strokeWidth={1.75} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

export default function HomeMenu() {
  const navigate = useNavigate()
  const apps = useInstalledApps()
  // ODY6 — au pouce, la page n'est plus « un champ qu'on tape » mais « une
  // grille qu'on touche » : le champ ne prend PAS le focus au chargement
  // (le clavier logiciel masquerait la moitié des apps avant tout geste).
  const tactile = useIsMobile()
  // ODY10 — badges vivants : UN appel agrégé (endpoint fédéré ARC40), cache
  // court, JAMAIS bloquant — `{}` au premier rendu, la grille est peinte
  // d'abord et les compteurs arrivent ensuite.
  const badges = useAppBadges()
  const [query, setQuery] = useState('')
  const [pinned, setPinned] = useState(readPinned)
  const [recent] = useState(readRecent)
  const [ordrePerso, setOrdrePerso] = useState(readOrder)
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)
  // Refs des tuiles, indexées par POSITION dans l'ordre de parcours : on y rend
  // le focus impérativement (jamais via un effet sur un nœud conditionnel).
  const tileRefs = useRef([])
  const registerRef = useCallback((index, node) => { tileRefs.current[index] = node }, [])

  // ODY13 — l'ordre PERSONNEL s'applique à la liste issue de la source unique ;
  // une app absente de l'ordre enregistré (nouvellement installée) reste
  // visible, à la fin — jamais perdue.
  const appsOrdonnees = useMemo(() => applyOrder(apps, ordrePerso), [apps, ordrePerso])

  const sections = useMemo(
    () => grouperApps(appsOrdonnees, { query, pinned, recent }),
    [appsOrdonnees, query, pinned, recent],
  )
  // Ordre de parcours clavier = concaténation des sections dans l'ordre affiché.
  const ordre = useMemo(() => sections.flatMap((s) => s.apps), [sections])

  // Réordonner une grille FILTRÉE n'a pas de sens (l'utilisateur ne voit pas où
  // l'app atterrit) : le glisser n'est actif qu'au repos.
  const recherche = !!normalise(query)
  const reordonnable = !recherche
  // ODY14 — le CTA « Ouvrir Applications » n'a de sens que pour un admin : un
  // non-admin n'y accéderait qu'à un refus (ODX5 est gaté Directeur).
  const estAdmin = useIsAdmin()

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
  // l'ordre du DOM), Home/Fin, Entrée/Espace ouvre (sémantique native du
  // bouton), Échap efface et rend le focus au champ. Toute autre touche
  // imprimable renvoie la frappe dans le champ : le type-ahead reste vrai même
  // le focus dans la grille.
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
      event.preventDefault()
      setQuery((q) => q + key)
      inputRef.current?.focus()
    }
  }, [ordre.length, focusTuile])

  // ODY13 — capteurs : souris/tactile avec seuil d'activation (un clic ne doit
  // jamais démarrer un glisser) + capteur CLAVIER natif de @dnd-kit/core.
  // `@dnd-kit/sortable` n'est PAS installé et reste interdit (NE PAS FAIRE VX).
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )

  const nomPour = useCallback(
    (key) => appsOrdonnees.find((a) => a.key === key)?.label ?? String(key),
    [appsOrdonnees],
  )
  const announcements = useMemo(() => construireAnnonces(nomPour), [nomPour])

  const onDragEnd = useCallback(({ active, over }) => {
    if (!over || over.id === active.id) return
    const cles = appsOrdonnees.map((a) => a.key)
    const depuis = cles.indexOf(active.id)
    const vers = cles.indexOf(over.id)
    if (depuis < 0 || vers < 0) return
    const [deplacee] = cles.splice(depuis, 1)
    cles.splice(vers, 0, deplacee)
    setOrdrePerso(cles)
    // Persistance par utilisateur (localStorage) + notification : le lanceur
    // VX9 lit la MÊME clé, donc grille et lanceur restent dans le même ordre.
    writeOrder(cles)
  }, [appsOrdonnees])

  // Focus initial sur le champ : sur BUREAU la page EST le type-ahead. ODY6 —
  // au pouce on s'en abstient (le clavier logiciel recouvrirait la grille dès
  // l'ouverture). Le champ n'est jamais conditionnel → effet simple, pas de
  // callback ref nécessaire.
  useEffect(() => {
    if (tactile) return
    inputRef.current?.focus()
  }, [tactile])

  let position = -1

  return (
    <div
      className={`home-menu${tactile ? ' home-menu--tactile' : ''}`}
      data-testid="home-menu"
    >
      {/* Fond signature « Lumière sur Nuit » — purement décoratif. */}
      <div className="home-menu-glow" aria-hidden="true" />

      <div className="home-menu-inner">
        <header className="home-menu-head">
          <h2 className="home-menu-title">Mes applications</h2>
          <p className="home-menu-subtitle">
            {tactile
              ? 'Touchez une application pour y entrer.'
              : 'Choisissez une application pour y entrer. Tapez pour filtrer.'}
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
            // ODY6 — clavier logiciel de RECHERCHE (touche « Rechercher »
            // plutôt que « Entrée ») ; la taille ≥16px imposée en CSS empêche
            // iOS de zoomer sur le champ au focus.
            inputMode="search"
            enterKeyHint="search"
          />
        </div>

        {/* ODY14 — la bannière de prise en main (VX36) remonte ici tant que la
            checklist n'est pas finie. Elle se rend elle-même invisible pendant
            son chargement, quand tout est fait ou quand elle a été rejetée :
            aucune société « normale » ne voit donc de flash. */}
        <OnboardingBanner />

        {sections.length === 0 ? (
          <EmptyState
            illustrated={!recherche}
            className="home-menu-vide"
            title={recherche ? 'Aucun résultat' : 'Aucune app activée'}
            description={recherche
              ? 'Aucune application ne correspond à cette recherche.'
              : (estAdmin
                ? 'Aucune application n’est activée pour votre société. Activez-en dans Paramètres → Applications.'
                : 'Aucune application n’est activée pour votre société, ou votre rôle n’en autorise aucune. Demandez à votre administrateur.')}
            action={!recherche && estAdmin ? (
              <Button asChild>
                <Link to="/parametres">Ouvrir Applications</Link>
              </Button>
            ) : null}
          />
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            accessibility={{ announcements, screenReaderInstructions: INSTRUCTIONS_LECTEUR }}
            onDragEnd={onDragEnd}
          >
            {sections.map((section) => (
              <section key={section.id} className="home-menu-section">
                <h3 className="home-menu-section-title">{section.titre}</h3>
                <div className="home-menu-grid" role="list">
                  {section.apps.map((app) => {
                    position += 1
                    const index = position
                    return (
                      <CelluleApp
                        key={app.key}
                        app={app}
                        index={index}
                        actif={index === activeIndex}
                        estFavori={pinned.includes(app.key)}
                        reordonnable={reordonnable}
                        badge={badges[app.key]}
                        onOuvrir={ouvrir}
                        onBasculerFavori={basculerFavori}
                        onFocusTuile={setActiveIndex}
                        onKeyDownTuile={onTileKeyDown}
                        registerRef={registerRef}
                      />
                    )
                  })}
                </div>
              </section>
            ))}
          </DndContext>
        )}
      </div>
    </div>
  )
}
