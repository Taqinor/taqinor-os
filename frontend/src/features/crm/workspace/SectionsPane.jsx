import { createElement, useState, useRef, useEffect, useCallback, useMemo } from 'react'
import {
  User, TrendingUp, Zap, Droplet, Home, ClipboardList, Globe, FileText, ClipboardCheck, Phone,
} from 'lucide-react'
import { ErrorBoundary } from '../../../ui'
import { useKeyboardAwareScroll } from '../../../hooks/useKeyboardAwareScroll'
import {
  getField, WEB_ORIGIN_FIELDS, hasWebQuestionnaireData, sectionAutoRepliee,
} from './draftCore'
// ROUND 5 — « ce qui manque » : une source unique, partagée avec l'onglet Devis.
import { chipsAComplete, sectionsPointees } from './missingFields'
import { jumpToField } from './jumpToField'
import SectionContact from './sections/SectionContact'
import SectionPipeline from './sections/SectionPipeline'
import SectionEnergie, { SectionPompage, SectionEquipements } from './sections/SectionEnergie'
import SectionSite from './sections/SectionSite'
import SectionVisite from './sections/SectionVisite'
import SectionDivers, { SectionOrigine, SectionWebQuestionnaire } from './sections/SectionDivers'

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
function WorkspaceSection({ id, title, Icon, collapsed, complete, onToggle, children }) {
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
        {/* ROUND 5 — un ✓ DISCRET sur une section repliée parce qu'elle est
            faite : sans lui, « repliée » et « complète » sont visuellement le
            même état, et on rouvre pour vérifier — ce qui annule tout le
            bénéfice. Jamais une boîte, jamais un badge : une coche, ton
            success, et rien du tout dès que la section est ouverte (elle se
            lit alors d'elle-même). */}
        {collapsed && complete && (
          <span className="lw-section-done" title="Section complète" aria-label="Section complète">✓</span>
        )}
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
  // LW34 — clavier virtuel iOS : sur mobile <768 le centre est le SEUL
  // conteneur scrollable (la fenêtre est en Sheet bas plein écran) ; sans ce
  // recentrage, un champ bas de formulaire reste caché sous le clavier.
  // No-op silencieux ailleurs (visualViewport absent hors WebKit mobile).
  useKeyboardAwareScroll({ containerRef: scrollRef })

  const agricole = getField(state, 'type_installation') === 'agricole'
  const hasWebOrigin = WEB_ORIGIN_FIELDS.some((k) => {
    const v = state.server ? state.server[k] : undefined
    return v !== undefined && v !== null && v !== ''
  })
  // DÉCISION FONDATEUR 2026-08-18 — « toutes les questions et les détails
  // doivent atteindre l'ERP » : questionnaire web complet + estimation
  // montrée au visiteur + colonnes structurées QK1/QW2/QW3, invisibles avant
  // (grep frontend = 0). hasWebQuestionnaireData vit dans draftCore.js (pure,
  // testable) — même patron que hasWebOrigin ci-dessus.
  const hasWebQuestionnaire = hasWebQuestionnaireData(state.server)

  // Registre ORDONNÉ des sections du centre. Les zones de CONSULTATION
  // (Devis/Activités/Pièces/Doublons/Historique) ont quitté le centre pour le
  // rail contexte (blueprint D3) : ici, uniquement ce qui se SAISIT.
  const registry = [
    { id: 'contact', label: 'Contact', Icon: User, Comp: SectionContact },
    { id: 'pipeline', label: 'Suivi commercial', Icon: TrendingUp, Comp: SectionPipeline },
    { id: 'energie', label: 'Profil énergétique', Icon: Zap, Comp: SectionEnergie },
    // L4 (+ extension fondateur) — questionnaire d'appel : occupation en
    // journée + équipements (piscine/VE/clim/chauffe-eau), regroupés avec un
    // renvoi vers les autres questions du même appel (raccordement, factures)
    // déjà portées ailleurs. Compose la courbe de consommation journalière
    // montrée au client.
    { id: 'equipements', label: "Questionnaire d'appel", Icon: Phone, Comp: SectionEquipements },
    ...(agricole ? [{ id: 'pompage', label: 'Pompage', Icon: Droplet, Comp: SectionPompage }] : []),
    { id: 'toiture', label: 'Toiture & site', Icon: Home, Comp: SectionSite },
    { id: 'visite', label: 'Visite technique', Icon: ClipboardList, Comp: SectionVisite },
    ...(hasWebOrigin ? [{ id: 'origine', label: 'Origine web', Icon: Globe, Comp: SectionOrigine }] : []),
    ...(hasWebQuestionnaire
      ? [{
        id: 'questionnaire', label: 'Réponses du questionnaire web',
        Icon: ClipboardCheck, Comp: SectionWebQuestionnaire,
      }]
      : []),
    { id: 'divers', label: 'Compléments', Icon: FileText, Comp: SectionDivers },
  ]

  const [active, setActive] = useState(registry[0]?.id ?? 'contact')
  // Tête de registre, tenue à jour à chaque rendu : le scroll-spy la lit sans
  // en dépendre (voir `onScroll`).
  const premiereSectionRef = useRef(registry[0]?.id ?? 'contact')
  const premiereSection = registry[0]?.id ?? 'contact'
  useEffect(() => { premiereSectionRef.current = premiereSection })

  /* ROUND 5 — LE BANDEAU « À COMPLÉTER ».
     ---------------------------------------------------------------------
     L'ordre des sections ne bouge JAMAIS (mémoire spatiale : un formulaire
     qui se réorganise se relit à chaque ouverture au lieu de s'apprendre).
     L'intuition « voir d'abord ce qui manque » est livrée par un bandeau
     qui POINTE — les sections, elles, restent à leur place.
     Calculé 100 % côté client à partir de la charge déjà reçue : zéro appel
     réseau. Vide = AUCUN chrome rendu (voir plus bas) : pas de boîte « tout
     est complet » qui occuperait la place en permanence pour ne rien dire —
     la leçon de la « case grise » retirée au round 3. */
  const chips = useMemo(() => chipsAComplete(state), [state])
  const pointees = useMemo(() => sectionsPointees(chips), [chips])

  /* ROUND 5 — REPLI AUTOMATIQUE, uniquement À L'OUVERTURE.
     Jamais pendant la session : replier une section sous les doigts de
     l'utilisatrice serait pire que ne rien faire. D'où l'initialiseur
     paresseux — il ne s'exécute qu'au montage, et la suite de la session est
     à elle seule.
     Deux garanties sur SES choix : `stored` (le localStorage) est appliqué EN
     DERNIER, donc ni un dépli qu'elle a persisté ne se referme, ni un repli
     qu'elle a choisi ne s'ouvre ; et l'auto-repli n'ÉCRIT PAS dans
     localStorage — c'est un état d'ouverture, pas une préférence. */
  const [collapsed, setCollapsed] = useState(() => {
    const stored = readCollapsed()
    // « Origine web » et « Réponses du questionnaire web » repliées par
    // défaut (blueprint + décision fondateur 2026-08-18) : deux sections de
    // consultation pure, jamais le premier écran qu'on regarde.
    const auto = { origine: true, questionnaire: true }
    if (mode === 'edit') {
      for (const s of registry) {
        if (s.id === 'origine' || s.id === 'questionnaire') continue
        auto[s.id] = sectionAutoRepliee(state, s.id, { porteUnManquant: pointees.has(s.id) })
      }
    }
    return { ...auto, ...stored }
  })

  const toggle = useCallback((id) => {
    setCollapsed((prev) => {
      const next = { ...prev, [id]: !prev[id] }
      writeCollapsed(next)
      return next
    })
  }, [])

  // ROUND 5 — un SEUL saut, celui que partage l'onglet Devis : il déplie
  // toujours la section cible (via son en-tête, l'affordance publique) avant
  // de scroller. `jumpTo(target)` reste le geste, à l'identique.
  const jumpTo = useCallback((id, field = null) => {
    const box = scrollRef.current
    if (!box) return
    jumpToField({ section: id, field, root: box })
  }, [])

  // Scroll-spy throttlé rAF (corrige le smell recon 01 §6.11 : itération non
  // throttlée à chaque tick de scroll). Ligne de référence = le BAS de la
  // nav sticky (.lw-secnav) : elle colle en haut de la zone visible dans LES
  // DEUX gabarits (desktop : .lw-center scrolle ; <768px : .lw-body--edit
  // scrolle et .lw-center glisse avec le contenu — comparer au top de
  // .lw-center donnait alors un offset CONSTANT, le spy était mort).
  const onScroll = useCallback(() => {
    if (rafRef.current) return
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null
      const box = scrollRef.current
      if (!box) return
      const nav = box.querySelector('.lw-secnav')
      const ref = (nav ? nav.getBoundingClientRect().bottom : box.getBoundingClientRect().top)
      // ROUND 5 (hygiène) — le repli valait 'contact' EN DUR : une deuxième
      // vérité sur « quelle est la première section », qui mentirait le jour
      // où le registre changerait de tête. On lit le registre, via une ref
      // pour garder ce callback sans dépendance (le spy ne doit pas se
      // ré-attacher à chaque rendu).
      let current = premiereSectionRef.current
      for (const el of box.querySelectorAll('[data-nav-id]')) {
        if (el.getBoundingClientRect().top - ref <= 90) current = el.dataset.navId
      }
      setActive(current)
    })
  }, [])

  // <768px, le scrolleur est .lw-body--edit (un ANCÊTRE — l'événement scroll
  // ne bulle pas, le onScroll React de .lw-center ne tire jamais) : écouteur
  // natif en phase CAPTURE sur cet ancêtre — il reçoit aussi les scrolls de
  // .lw-center, donc UN écouteur couvre les deux gabarits sans ré-attache au
  // resize. Le onScroll React reste en place (idempotent, rAF dédupliqué).
  useEffect(() => {
    const body = scrollRef.current?.closest('.lw-body')
    if (!body) return undefined
    body.addEventListener('scroll', onScroll, true)
    return () => body.removeEventListener('scroll', onScroll, true)
  }, [onScroll])

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
      {/* ROUND 5 — bandeau « À compléter », épinglé SOUS le rail de sections
          et rendu SEULEMENT s'il a quelque chose à dire. Zéro chrome quand
          tout va bien : une boîte permanente qui affiche « rien à signaler »
          coûte de la place à chaque ouverture et n'apprend rien (leçon de la
          « case grise » du fondateur). Les chips ne déplacent RIEN — elles
          pointent : chaque clic déplie la section concernée et focalise le
          champ, l'ordre des sections reste immuable. */}
      {mode === 'edit' && chips.length > 0 && (
        <div className="lw-todo" role="group" aria-label="Informations à compléter">
          <span className="lw-todo-label">À compléter</span>
          {chips.map((c) => (
            <button
              key={c.id}
              type="button"
              className="lw-todo-chip"
              aria-label={`Compléter : ${c.label}`}
              onClick={() => jumpTo(c.section, c.field)}
            >
              {c.label}
            </button>
          ))}
        </div>
      )}
      <div className="lw-sections">
        {registry.map(({ id, label, Icon, Comp }) => (
          <WorkspaceSection
            key={id}
            id={id}
            title={label}
            Icon={Icon}
            collapsed={!!collapsed[id]}
            complete={!pointees.has(id) && sectionAutoRepliee(state, id, {})}
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
