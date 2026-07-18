import { createElement, useState, useRef, useEffect, useCallback } from 'react'
import {
  User, TrendingUp, Zap, Droplet, Home, ClipboardList, Globe, FileText,
} from 'lucide-react'
import { ErrorBoundary } from '../../../ui'
import { getField, WEB_ORIGIN_FIELDS } from './draftCore'
import SectionContact from './sections/SectionContact'
import SectionPipeline from './sections/SectionPipeline'
import SectionEnergie, { SectionPompage } from './sections/SectionEnergie'
import SectionSite from './sections/SectionSite'
import SectionVisite from './sections/SectionVisite'
import SectionDivers, { SectionOrigine } from './sections/SectionDivers'

// LW11 — Le centre : registre de sections + nav-chips sticky (scroll-spy rAF,
// aria-current), repli persisté par section, wrapper `<form>` en création.
// Chaque section est PURE (présentation) et reçoit { state, setField, errors,
// mode, refData } ; SectionsPane possède la STRUCTURE (anchors data-nav-id,
// entête repliable, ErrorBoundary par section — motif VX205).

const COLLAPSE_KEY = 'taqinor.lw.collapsed'
const readCollapsed = () => {
  try { return JSON.parse(localStorage.getItem(COLLAPSE_KEY)) || {} } catch { return {} }
}
const writeCollapsed = (map) => {
  try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify(map)) } catch { /* best-effort */ }
}

// Entête repliable + anchor de scroll-spy autour du contenu pur d'une section.
function WorkspaceSection({ id, title, Icon, collapsed, onToggle, children }) {
  return (
    <section className="lw-section" data-nav-id={id}>
      <button
        type="button"
        className="lw-section-head"
        aria-expanded={!collapsed}
        onClick={onToggle}
      >
        {Icon && <Icon className="lw-section-icon" aria-hidden="true" size={16} />}
        <span className="lw-section-title">{title}</span>
        <span className="lw-section-chevron" aria-hidden="true">{collapsed ? '▸' : '▾'}</span>
      </button>
      {!collapsed && (
        <div className="lw-section-body">
          <ErrorBoundary>{children}</ErrorBoundary>
        </div>
      )}
    </section>
  )
}

export default function SectionsPane({
  state, setField, errors, mode, focusSection = null,
  formId, onSubmit, refData = {},
}) {
  const scrollRef = useRef(null)
  const rafRef = useRef(null)
  const [collapsed, setCollapsed] = useState(() => {
    // « Origine web » repliée par défaut (blueprint) ; le reste ouvert.
    const stored = readCollapsed()
    return { origine: true, ...stored }
  })

  const agricole = getField(state, 'type_installation') === 'agricole'
  const hasWebOrigin = WEB_ORIGIN_FIELDS.some((k) => {
    const v = state.server ? state.server[k] : undefined
    return v !== undefined && v !== null && v !== ''
  })

  // Registre ORDONNÉ des sections du centre. Les zones de CONSULTATION
  // (Devis/Activités/Pièces/Doublons/Historique) ont quitté le centre pour le
  // rail contexte (blueprint D3) : ici, uniquement ce qui se SAISIT.
  const registry = [
    { id: 'contact', label: 'Contact', Icon: User, Comp: SectionContact },
    { id: 'pipeline', label: 'Suivi commercial', Icon: TrendingUp, Comp: SectionPipeline },
    { id: 'energie', label: 'Profil énergétique', Icon: Zap, Comp: SectionEnergie },
    ...(agricole ? [{ id: 'pompage', label: 'Pompage', Icon: Droplet, Comp: SectionPompage }] : []),
    { id: 'toiture', label: 'Toiture & site', Icon: Home, Comp: SectionSite },
    { id: 'visite', label: 'Visite technique', Icon: ClipboardList, Comp: SectionVisite },
    ...(hasWebOrigin ? [{ id: 'origine', label: 'Origine web', Icon: Globe, Comp: SectionOrigine }] : []),
    { id: 'divers', label: 'Compléments', Icon: FileText, Comp: SectionDivers },
  ]

  const [active, setActive] = useState(registry[0]?.id ?? 'contact')

  const toggle = useCallback((id) => {
    setCollapsed((prev) => {
      const next = { ...prev, [id]: !prev[id] }
      writeCollapsed(next)
      return next
    })
  }, [])

  const jumpTo = useCallback((id) => {
    const box = scrollRef.current
    const el = box?.querySelector(`[data-nav-id="${id}"]`)
    if (!el) return
    // Déplie la section ciblée avant d'y sauter.
    setCollapsed((prev) => (prev[id] ? { ...prev, [id]: false } : prev))
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // Scroll-spy throttlé rAF (corrige le smell recon 01 §6.11 : itération non
  // throttlée à chaque tick de scroll).
  const onScroll = useCallback(() => {
    if (rafRef.current) return
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null
      const box = scrollRef.current
      if (!box) return
      const top = box.getBoundingClientRect().top
      // 'contact' est toujours la 1re section (fallback stable — pas de dép registry).
      let current = 'contact'
      for (const el of box.querySelectorAll('[data-nav-id]')) {
        if (el.getBoundingClientRect().top - top <= 90) current = el.dataset.navId
      }
      setActive(current)
    })
  }, [])

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }, [])

  // QX25/VX223 — ouverture directe sur une section (prop `focusSection` ou clé
  // sessionStorage ciblant CE lead), une seule fois.
  const focusRan = useRef(false)
  useEffect(() => {
    if (mode !== 'edit' || focusRan.current) return
    let target = focusSection
    if (!target) {
      try {
        const raw = sessionStorage.getItem('taqinor.leadform.pendingFocus')
        if (raw) {
          const pending = JSON.parse(raw)
          sessionStorage.removeItem('taqinor.leadform.pendingFocus')
          if (pending && String(pending.leadId) === String(state.leadId)) target = pending.section
        }
      } catch { /* best-effort */ }
    }
    if (!target) return
    focusRan.current = true
    setTimeout(() => jumpTo(target), 0)
  }, [mode, focusSection, state.leadId, jumpTo])

  const sectionProps = { state, setField, errors, mode, refData }

  const content = (
    <div className="lw-zone lw-center" ref={scrollRef} onScroll={onScroll}>
      <nav className="lw-secnav" aria-label="Sections du lead">
        {registry.map((s) => (
          <button
            key={s.id}
            type="button"
            className="lw-secnav-chip"
            aria-current={active === s.id ? 'true' : undefined}
            onClick={() => jumpTo(s.id)}
          >
            {s.Icon && <s.Icon className="lw-secnav-icon" aria-hidden="true" size={14} />}
            <span>{s.label}</span>
          </button>
        ))}
      </nav>
      <div className="lw-sections">
        {registry.map(({ id, label, Icon, Comp }) => (
          <WorkspaceSection
            key={id}
            id={id}
            title={label}
            Icon={Icon}
            collapsed={!!collapsed[id]}
            onToggle={() => toggle(id)}
          >
            {/* createElement explicite — même faux positif compilateur que
                LeadWorkspace (balise JSX dynamique « jamais utilisée »). */}
            {createElement(Comp, sectionProps)}
          </WorkspaceSection>
        ))}
      </div>
    </div>
  )

  // Le `<form>` n'existe qu'en création (display:contents — jamais entre la
  // grille et le corps scrollable, cause racine P0).
  if (mode === 'create') {
    return (
      <form id={formId} className="lw-form" noValidate onSubmit={onSubmit}>
        {content}
      </form>
    )
  }
  return content
}
