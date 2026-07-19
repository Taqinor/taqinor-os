import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { unwrapList } from '../../api/resource'

/* ============================================================================
   PUB51 — Palette de commandes console (Ctrl-K).
   ----------------------------------------------------------------------------
   Saute à un ÉCRAN (catalogue statique, les 17 écrans de `module.config.jsx`),
   une CAMPAGNE ou une AD. Doctrine « déjà chargées + repli API » : campagnes
   et ads sont tirées UNE fois (cache module-level, jamais un refetch tant que
   la session SPA vit) au premier Ctrl-K — « déjà chargées » pour toute
   ouverture suivante, avec un repli API implicite au premier appel. Aucune
   fiche « ad » dédiée n'existe encore (PUB44, non construit) : sélectionner
   une ad ouvre le Cockpit, le meilleur atterrissage disponible aujourd'hui.
   Montée sur les écrans possédés par cette lane (Dashboard/Rules/Reports/
   Approvals) — un montage vraiment console-wide nécessiterait d'envelopper
   les 17 routes dans `module.config.jsx`, hors périmètre de cette lane
   (fichier partagé avec les autres lanes de la vague).
   ========================================================================== */

const SCREENS = [
  { label: 'Tableau de bord', to: '/publicite/tableau-de-bord' },
  { label: 'Cockpit par ad', to: '/publicite/cockpit' },
  { label: "Boîte d'approbation", to: '/publicite/approbations' },
  { label: 'Campagnes', to: '/publicite/campagnes' },
  { label: 'Bibliothèque créative', to: '/publicite/creatifs' },
  { label: 'Commentaires', to: '/publicite/commentaires' },
  { label: 'Instagram', to: '/publicite/instagram' },
  { label: 'Expérimentations', to: '/publicite/experimentations' },
  { label: 'Plan de vol', to: '/publicite/plan-de-vol' },
  { label: 'Backlog créatif', to: '/publicite/backlog' },
  { label: 'Règles & anomalies', to: '/publicite/regles' },
  { label: 'Simulation', to: '/publicite/simulation' },
  { label: 'Reporting', to: '/publicite/reporting' },
  { label: 'Brief hebdomadaire', to: '/publicite/brief' },
  { label: "Journal d'actions", to: '/publicite/journal' },
  { label: 'Connexion & garde-fous', to: '/publicite/connexion' },
  { label: "L'Arbre", to: '/publicite/arbre' },
]

const KIND_LABELS = { screen: 'Écran', campaign: 'Campagne', ad: 'Ad' }

// Cache module-level : « données déjà chargées » réutilisées entre chaque
// ouverture de la palette dans la même session SPA (jamais un refetch).
let campaignsCache = null
let adsCache = null

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [campaigns, setCampaigns] = useState(campaignsCache || [])
  const [ads, setAds] = useState(adsCache || [])
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const ensureLoaded = useCallback(() => {
    if (campaignsCache === null) {
      campaignsCache = []
      adsengineApi.campaigns.list()
        .then(r => { campaignsCache = unwrapList(r); setCampaigns(campaignsCache) })
        .catch(() => { campaignsCache = []; setCampaigns([]) })
    }
    if (adsCache === null) {
      adsCache = []
      adsengineApi.metrics.adsCockpit()
        .then(r => { adsCache = unwrapList(r); setAds(adsCache) })
        .catch(() => { adsCache = []; setAds([]) })
    }
  }, [])

  // Raccourci global Ctrl-K / Cmd-K (jamais bloqué par un champ focus — même
  // convention que la majorité des palettes de commandes).
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        setOpen(o => {
          const next = !o
          if (next) ensureLoaded()
          return next
        })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [ensureLoaded])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setActiveIndex(0)
    const t = setTimeout(() => inputRef.current?.focus(), 0)
    return () => clearTimeout(t)
  }, [open])

  const q = query.trim().toLowerCase()
  const matchedScreens = (q ? SCREENS.filter(s => s.label.toLowerCase().includes(q)) : SCREENS)
    .map(s => ({ kind: 'screen', label: s.label, to: s.to }))
  const matchedCampaigns = q
    ? campaigns
      .filter(c => (c.name || c.nom || '').toLowerCase().includes(q))
      .slice(0, 8)
      .map(c => ({ kind: 'campaign', label: c.name || c.nom, to: '/publicite/campagnes' }))
    : []
  const matchedAds = q
    ? ads
      .filter(a => (a.ad_name || a.nom || a.name || '').toLowerCase().includes(q))
      .slice(0, 8)
      .map(a => ({ kind: 'ad', label: a.ad_name || a.nom || a.name, to: '/publicite/cockpit' }))
    : []
  const results = [...matchedScreens, ...matchedCampaigns, ...matchedAds]

  const go = (item) => {
    setOpen(false)
    navigate(item.to)
  }

  const onInputKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex(i => Math.min(i + 1, Math.max(results.length - 1, 0)))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (results[activeIndex]) go(results[activeIndex])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  if (!open) return null

  return (
    <div className="ae-command-palette-overlay" data-testid="ae-command-palette-overlay"
      onClick={() => setOpen(false)}
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.4)', zIndex: 100,
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '10vh' }}>
      <div className="ae-command-palette" data-testid="ae-command-palette" role="dialog"
        aria-label="Palette de commandes" onClick={e => e.stopPropagation()}
        style={{ width: 480, maxWidth: '92vw', maxHeight: '60vh', background: '#fff', borderRadius: 10,
          boxShadow: '0 16px 48px rgba(0,0,0,0.25)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 0.8rem',
          borderBottom: '1px solid #e2e8f0' }}>
          <Search size={16} aria-hidden="true" />
          <input ref={inputRef} type="text" className="ae-command-palette-input"
            data-testid="ae-command-palette-input"
            placeholder="Sauter à un écran, une campagne, une ad…"
            aria-label="Sauter à un écran, une campagne, une ad"
            value={query}
            onChange={e => { setQuery(e.target.value); setActiveIndex(0) }}
            onKeyDown={onInputKeyDown}
            style={{ flex: 1, border: 'none', outline: 'none', fontSize: '0.95rem' }} />
        </div>
        <div style={{ overflowY: 'auto' }}>
          {results.length === 0
            ? <p data-testid="ae-command-palette-empty" style={{ padding: '0.75rem', color: '#64748b' }}>
                Aucun résultat.</p>
            : (
              <ul style={{ listStyle: 'none', margin: 0, padding: '0.3rem' }}>
                {results.map((r, i) => (
                  <li key={`${r.kind}-${r.label}-${i}`}>
                    <button type="button" className="ae-command-palette-item"
                      data-testid="ae-command-palette-item"
                      aria-selected={i === activeIndex}
                      onMouseEnter={() => setActiveIndex(i)}
                      onClick={() => go(r)}
                      style={{ width: '100%', textAlign: 'left', padding: '0.5rem 0.7rem', borderRadius: 6,
                        background: i === activeIndex ? '#eef2ff' : 'transparent', border: 'none', cursor: 'pointer',
                        display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <span>{r.label}</span>
                      <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>{KIND_LABELS[r.kind]}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
        </div>
      </div>
    </div>
  )
}
