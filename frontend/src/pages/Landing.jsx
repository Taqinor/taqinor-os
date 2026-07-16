import { useRef, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useInView, useCounter } from '../hooks/useInView'
import './landing.css'
import axios from 'axios'

// VX57 — Sora n'est utilisée que par cette page. Le <link> historique dans
// index.html bloquait le rendu de CHAQUE écran (dont /login) pour une police
// dont seul /landing a besoin. On l'injecte ici, au montage du composant lazy
// (`fonts/sora.css` reste servi tel quel depuis `public/` — un <link> POSÉ
// depuis le chunk lazy plutôt qu'un <link> statique dans le HTML racine).
const SORA_HREF = '/fonts/sora.css'

// Public contact form is PARKED by default. Set VITE_CONTACT_FORM_ENABLED=1 at
// build time (see CLAUDE.md) to show it again. While off, the CTA buttons send
// visitors to the app login instead of opening the (disabled) contact modal.
const CONTACT_FORM_ENABLED = import.meta.env.VITE_CONTACT_FORM_ENABLED === '1'

// ── Modal formulaire de contact ───────────────────────────────────────────────
function ContactModal({ onClose }) {
  const [form, setForm]     = useState({ nom: '', numero: '', societe: '', email: '', message: '' })
  const [status, setStatus] = useState(null) // null | 'loading' | 'success' | 'error'
  const [errMsg, setErrMsg] = useState('')

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('loading')
    setErrMsg('')
    try {
      await axios.post('/api/django/contact/', form)
      setStatus('success')
    } catch (err) {
      setErrMsg(err.response?.data?.detail ?? 'Une erreur est survenue. Réessayez.')
      setStatus('error')
    }
  }

  const inputStyle = {
    width: '100%', padding: '10px 14px', borderRadius: 8, fontSize: 14,
    border: '1.5px solid #e2e8f0', outline: 'none', boxSizing: 'border-box',
    fontFamily: 'inherit', transition: 'border-color 0.2s',
  }
  const labelStyle = { fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 5, display: 'block' }

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9999, padding: '1rem',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: '#fff', borderRadius: 18, padding: '2rem',
        width: '100%', maxWidth: 500, boxShadow: '0 25px 60px rgba(0,0,0,0.18)',
        position: 'relative', maxHeight: '90vh', overflowY: 'auto',
      }}>
        {/* Fermer */}
        <button onClick={onClose} style={{
          position: 'absolute', top: 14, right: 14,
          background: '#f1f5f9', border: 'none', borderRadius: 8,
          width: 32, height: 32, cursor: 'pointer', fontSize: 18,
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b',
        }}>×</button>

        <h2 style={{ margin: '0 0 0.25rem', fontSize: '1.3rem', fontWeight: 700, color: '#0f172a' }}>
          Démarrer gratuitement
        </h2>
        <p style={{ margin: '0 0 1.5rem', fontSize: 13.5, color: '#64748b' }}>
          Laissez-nous vos coordonnées, nous vous contacterons sous 24h.
        </p>

        {status === 'success' ? (
          <div style={{
            background: '#f0fdf4', border: '1px solid #bbf7d0',
            borderRadius: 12, padding: '1.5rem', textAlign: 'center',
          }}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>✅</div>
            <p style={{ fontWeight: 700, color: '#15803d', margin: '0 0 6px', fontSize: 15 }}>
              Message envoyé !
            </p>
            <p style={{ color: '#166534', fontSize: 13, margin: 0 }}>
              Nous vous contacterons très bientôt.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label style={labelStyle}>Nom complet *</label>
                <input style={inputStyle} placeholder="Karim Benhadou" value={form.nom} onChange={set('nom')} required />
              </div>
              <div>
                <label style={labelStyle}>Numéro de téléphone</label>
                <input style={inputStyle} placeholder="+212 6xx xxx xxx" value={form.numero} onChange={set('numero')} />
              </div>
            </div>
            <div>
              <label style={labelStyle}>Nom de l'entreprise</label>
              <input style={inputStyle} placeholder="Mon Entreprise SARL" value={form.societe} onChange={set('societe')} />
            </div>
            <div>
              <label style={labelStyle}>Adresse email *</label>
              <input style={inputStyle} type="email" placeholder="vous@entreprise.ma" value={form.email} onChange={set('email')} required />
            </div>
            <div>
              <label style={labelStyle}>Message *</label>
              <textarea
                style={{ ...inputStyle, minHeight: 100, resize: 'vertical' }}
                placeholder="Décrivez votre besoin..."
                value={form.message}
                onChange={set('message')}
                required
              />
            </div>

            {status === 'error' && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#dc2626',
              }}>
                {errMsg}
              </div>
            )}

            <button type="submit" disabled={status === 'loading'} style={{
              background: status === 'loading' ? '#93c5fd' : '#2563eb',
              color: '#fff', border: 'none', borderRadius: 10,
              padding: '12px 0', fontSize: 15, fontWeight: 700,
              cursor: status === 'loading' ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}>
              {status === 'loading' ? 'Envoi en cours…' : 'Envoyer ma demande'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ── Utilitaire : observe un conteneur et anime ses enfants .lp-anim* ────────
function useStagger(threshold = 0.1) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const children = el.querySelectorAll('.lp-anim, .lp-anim-left, .lp-anim-right')
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          children.forEach((c) => c.classList.add('lp-visible'))
          obs.unobserve(el)
        }
      },
      { threshold }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return ref
}

// ── Logo TAQINOR ─────────────────────────────────────────────────────────────
function TaqinorLogo({ size = 28, theme = 'light' }) {
  const textColor   = theme === 'dark' ? '#ffffff' : '#0d1b3e'
  const sunBg       = '#F5C100'
  const boltColor   = '#0d1b3e'
  const sunDiam     = Math.round(size * 0.92)
  const fontStyle   = {
    fontFamily: "'Arial Black', 'Arial Bold', Impact, sans-serif",
    fontWeight: 900,
    fontSize:   size,
    color:      textColor,
    lineHeight:  1,
    letterSpacing: '0.03em',
  }
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <span style={fontStyle}>TAQIN</span>
        {/* O remplacé par le soleil / éclair */}
        <div style={{
          width: sunDiam, height: sunDiam,
          borderRadius: '50%',
          backgroundColor: sunBg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 1px', flexShrink: 0,
        }}>
          <svg viewBox="0 0 24 24" width={sunDiam * 0.54} height={sunDiam * 0.54} fill={boltColor}>
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </div>
        <span style={fontStyle}>R</span>
      </div>
    </div>
  )
}

// ── SVG Icons ────────────────────────────────────────────────────────────────
const IconAI = () => (
  <svg className="lp-icon lp-icon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24A2.5 2.5 0 0 1 9.5 2Z"/>
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24A2.5 2.5 0 0 0 14.5 2Z"/>
  </svg>
)
const IconOCR = () => (
  <svg className="lp-icon lp-icon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <line x1="10" y1="9"  x2="8" y2="9"/>
  </svg>
)
const IconChart = () => (
  <svg className="lp-icon lp-icon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/>
    <line x1="12" y1="20" x2="12" y2="4"/>
    <line x1="6"  y1="20" x2="6"  y2="14"/>
    <line x1="2"  y1="20" x2="22" y2="20"/>
  </svg>
)
const IconShield = () => (
  <svg className="lp-icon lp-icon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    <polyline points="9 12 11 14 15 10"/>
  </svg>
)
const IconAuto = () => (
  <svg className="lp-icon lp-icon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
  </svg>
)
const IconBox = () => (
  <svg className="lp-icon lp-icon-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
    <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
    <line x1="12" y1="22.08" x2="12" y2="12"/>
  </svg>
)
const IconBriefcase = () => (
  <svg className="lp-icon lp-icon-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
  </svg>
)
const IconBot = () => (
  <svg className="lp-icon lp-icon-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2"/>
    <path d="M12 11V7"/>
    <circle cx="12" cy="5" r="2"/>
    <path d="M8 15h.01M12 15h.01M16 15h.01"/>
  </svg>
)
const IconScan = () => (
  <svg className="lp-icon lp-icon-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/>
    <line x1="7" y1="12" x2="17" y2="12" strokeWidth="2"/>
  </svg>
)

// ── Data ─────────────────────────────────────────────────────────────────────
const NAV_LINKS = [
  { label: 'Fonctionnalités', href: '#features' },
  { label: 'Modules',         href: '#modules' },
  { label: 'Témoignages',     href: '#testimonials' },
  { label: 'Contact',         href: '#contact' },
]

const STATS = [
  { display: '5+',   numeric: 5,  suffix: '+',  label: 'Entreprises actives' },
  { display: '98%',  numeric: 98, suffix: '%',  label: 'Satisfaction client' },
  { display: '40%',  numeric: 40, suffix: '%',  label: 'Gain de productivité' },
  { display: '24/7', numeric: null,              label: 'Support disponible' },
]

const FEATURES = [
  { Icon: IconAI,     title: 'IA Agentique',        desc: 'Un assistant intelligent qui comprend vos données et interagit avec votre ERP en langage naturel. Posez vos questions, obtenez des réponses en secondes.' },
  { Icon: IconOCR,    title: 'OCR Intelligent',      desc: 'Automatisez la saisie de vos documents. TAQINOR extrait et structure automatiquement les informations depuis vos factures, bons et reçus.' },
  { Icon: IconChart,  title: 'Dashboard Temps Réel', desc: 'Visualisez vos performances instantanément. Chiffre d\'affaires, stocks, marges — tous vos indicateurs clés mis à jour en temps réel.' },
  { Icon: IconShield, title: 'Sécurité & RBAC',      desc: 'Système sécurisé avec gestion des rôles avancée. Chaque utilisateur accède uniquement aux données qui lui sont autorisées.' },
  { Icon: IconAuto,   title: 'Automatisation',       desc: 'Automatisez vos workflows : commandes, relances, facturation et notifications. TAQINOR travaille pour vous sans intervention manuelle.' },
]

const MODULES = [
  { Icon: IconBox,        title: 'Stock & Inventaire', desc: 'Gérez vos produits, catégories et mouvements de stock avec des alertes automatiques.', items: ['Mouvements ENTRÉE / SORTIE / TRANSFERT', 'Alertes seuil critique configurable', 'Lots et variantes produits', 'Codes-barres & QR codes'] },
  { Icon: IconBriefcase,  title: 'Ventes & Achats',    desc: 'Devis, bons de commande et factures avec calcul HT/TVA/TTC automatique.',             items: ['Suivi des commandes multi-étapes', 'Calcul automatique HT / TVA / TTC', 'Gestion des fournisseurs', 'Historique complet'] },
  { Icon: IconBot,        title: 'Console IA',         desc: 'Obtenez des analyses, rapports et recommandations générées par l\'intelligence artificielle.', items: ['Chat en langage naturel', 'Analyse prédictive des ventes', 'Recommandations de réapprovisionnement', 'Rapports auto-générés'] },
  { Icon: IconScan,       title: 'OCR Documents',      desc: 'Glissez-déposez vos documents, TAQINOR extrait et intègre les données automatiquement.',    items: ['Support PDF, PNG, JPG', 'Extraction fournisseur, montants, dates', 'Validation et correction assistées', 'Intégration directe stock/ventes'] },
]

const TESTIMONIALS = [
  { text: 'TAQINOR a transformé notre gestion. En 2 semaines, notre équipe a réduit le temps de traitement des commandes de 60%. L\'IA est vraiment bluffante.', name: 'Karim Benhaddou', role: 'Directeur Commercial, Casablanca', avatar: 'KB' },
  { text: 'L\'OCR nous économise 3h par jour. On scanne les bons de livraison et tout est dans le système instantanément. Fini la saisie manuelle !',             name: 'Samira Ouled',    role: 'Responsable Stock, Marrakech',    avatar: 'SO' },
  { text: 'Enfin un ERP conçu pour les entreprises marocaines. Interface claire, support réactif, et les tableaux de bord en temps réel sont exactement ce qu\'il me fallait.', name: 'Youssef Alami', role: 'PDG, Rabat', avatar: 'YA' },
]

// ── Dashboard Mockup ─────────────────────────────────────────────────────────
function DashboardMockup() {
  const bars = [
    { h: 45 }, { h: 62, mid: true }, { h: 38 }, { h: 88, hi: true },
    { h: 55, mid: true }, { h: 95, hi: true }, { h: 48 },
    { h: 72, mid: true }, { h: 58 }, { h: 82, hi: true },
    { h: 65, mid: true }, { h: 90, hi: true },
  ]
  const rows = [
    { name: 'Écran Dell 27"',     qty: '66 unités', ok: true },
    { name: 'Câble HDMI 2m',      qty: '7 unités',  ok: false },
    { name: 'Chaisier mécanique', qty: '25 unités', ok: true },
  ]
  return (
    <div className="lp-mockup-wrap">
      <div className="lp-mockup-glow" />
      <div className="lp-mockup">
        <div className="lp-mockup-bar">
          <span className="lp-mockup-dot" style={{ background: '#FF5F57' }} />
          <span className="lp-mockup-dot" style={{ background: '#FFBD2E' }} />
          <span className="lp-mockup-dot" style={{ background: '#28CA42' }} />
          <span className="lp-mockup-bar-title">TAQINOR — Tableau de bord</span>
        </div>
        <div className="lp-mockup-body">
          <div className="lp-mockup-kpis">
            <div className="lp-mockup-kpi">
              <div className="lp-kpi-label">Chiffre d'affaires</div>
              <div className="lp-kpi-value">1 240 000</div>
              <div className="lp-kpi-delta lp-delta-up">&#8593; +12% ce mois</div>
            </div>
            <div className="lp-mockup-kpi">
              <div className="lp-kpi-label">Commandes</div>
              <div className="lp-kpi-value">347</div>
              <div className="lp-kpi-delta lp-delta-up">&#8593; +8%</div>
            </div>
            <div className="lp-mockup-kpi">
              <div className="lp-kpi-label">Alertes stock</div>
              <div className="lp-kpi-value" style={{ color: '#dc2626' }}>5</div>
              <div className="lp-kpi-delta lp-delta-down">critiques</div>
            </div>
          </div>
          <div className="lp-mockup-chart">
            {bars.map((b, i) => (
              <div
                key={i}
                className={`lp-chart-bar${b.hi ? ' lp-chart-bar-hi' : b.mid ? ' lp-chart-bar-mid' : ''}`}
                style={{ height: `${b.h}%` }}
              />
            ))}
          </div>
          <div className="lp-mockup-rows">
            {rows.map((r) => (
              <div key={r.name} className="lp-mockup-row">
                <span className="lp-row-name">{r.name}</span>
                <span className="lp-row-qty">{r.qty}</span>
                <span className={`lp-row-badge ${r.ok ? 'lp-badge-ok' : 'lp-badge-err'}`}>
                  {r.ok ? 'OPTIMAL' : 'CRITIQUE'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Chat Mockup ──────────────────────────────────────────────────────────────
function ChatMockup() {
  return (
    <div className="lp-chat">
      <div className="lp-chat-header">
        <div className="lp-chat-avatar">T</div>
        <div>
          <div className="lp-chat-name">Assistant TAQINOR</div>
          <div className="lp-chat-status">
            <span className="lp-chat-online">&#9679;</span> En ligne — IA active
          </div>
        </div>
      </div>
      <div className="lp-chat-body">
        <div className="lp-chat-msg-user">Quel est mon meilleur produit ce mois ?</div>
        <div className="lp-chat-msg-bot">
          Ce mois, votre produit le plus vendu est <strong>l'Écran Dell 27"</strong> avec
          48 unités vendues (+9%). Je recommande d'augmenter votre commande fournisseur de 30 unités.
        </div>
        <div className="lp-chat-msg-user">Génère un rapport PDF ventes de la semaine</div>
        <div className="lp-chat-msg-bot">
          Rapport généré &#10003;&nbsp; CA : <strong>315 100 MAD</strong>, 30 commandes, marge 41%.{' '}
          <span className="lp-chat-link">Télécharger &#8594; Lundi.pdf</span>
        </div>
      </div>
    </div>
  )
}

// ── Stat item avec compteur animé ────────────────────────────────────────────
function StatItem({ stat, active, delay }) {
  const count = useCounter(stat.numeric, 1800, active)
  return (
    <div className={`lp-stat-item lp-anim lp-${delay}`}>
      <div className="lp-stat-value">
        {stat.numeric != null ? `${count}${stat.suffix}` : stat.display}
      </div>
      <div className="lp-stat-label">{stat.label}</div>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────
export default function Landing() {
  const [modalOpen, setModalOpen] = useState(false)

  // VX57 — Sora n'est chargée que lorsque /landing est réellement monté
  // (voir la constante SORA_HREF ci-dessus). Idempotent : si un <link> avec
  // ce href existe déjà (retour sur /landing sans full reload), on ne le
  // duplique pas.
  useEffect(() => {
    if (document.querySelector(`link[href="${SORA_HREF}"]`)) return
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = SORA_HREF
    document.head.appendChild(link)
  }, [])

  // CTA: open the contact modal when the form is enabled; otherwise (parked)
  // send the visitor to the app login so the button still does something useful.
  const handleCta = () => {
    if (CONTACT_FORM_ENABLED) setModalOpen(true)
    else window.location.assign('/login')
  }

  // Section observers
  const [statsRef, statsVisible]         = useInView(0.3)
  const featuresGrid                     = useStagger(0.08)
  const modulesGrid                      = useStagger(0.08)
  const [iaRef, iaVisible]               = useInView(0.15)
  const testimonialsGrid                 = useStagger(0.08)
  const [ctaRef, ctaVisible]             = useInView(0.2)
  const [sectionFeatRef, sectionFeatVis] = useInView(0.2)
  const [sectionModRef,  sectionModVis]  = useInView(0.2)
  const [sectionTestRef, sectionTestVis] = useInView(0.2)

  // Déclenche lp-visible sur les conteneurs directs quand ils entrent en vue
  useEffect(() => {
    if (statsVisible && statsRef.current)
      statsRef.current.querySelectorAll('.lp-anim').forEach(el => el.classList.add('lp-visible'))
  }, [statsVisible, statsRef])

  useEffect(() => {
    if (iaVisible && iaRef.current)
      iaRef.current.querySelectorAll('.lp-anim-left, .lp-anim-right').forEach(el => el.classList.add('lp-visible'))
  }, [iaVisible, iaRef])

  useEffect(() => {
    if (ctaVisible && ctaRef.current)
      ctaRef.current.querySelectorAll('.lp-anim').forEach(el => el.classList.add('lp-visible'))
  }, [ctaVisible, ctaRef])

  useEffect(() => {
    if (sectionFeatVis && sectionFeatRef.current)
      sectionFeatRef.current.querySelectorAll('.lp-anim').forEach(el => el.classList.add('lp-visible'))
  }, [sectionFeatVis, sectionFeatRef])

  useEffect(() => {
    if (sectionModVis && sectionModRef.current)
      sectionModRef.current.querySelectorAll('.lp-anim').forEach(el => el.classList.add('lp-visible'))
  }, [sectionModVis, sectionModRef])

  useEffect(() => {
    if (sectionTestVis && sectionTestRef.current)
      sectionTestRef.current.querySelectorAll('.lp-anim').forEach(el => el.classList.add('lp-visible'))
  }, [sectionTestVis, sectionTestRef])

  const DELAYS = ['lp-d0', 'lp-d1', 'lp-d2', 'lp-d3', 'lp-d4']

  return (
    <>
    <div className="lp-root">

      {/* ── Navbar ── */}
      <header className="lp-nav">
        <div className="lp-container lp-nav-inner">
          <div className="lp-nav-logo">
            <TaqinorLogo size={26} theme="light" />
          </div>
          <nav className="lp-nav-links">
            {NAV_LINKS.map((l) => (
              <a key={l.label} href={l.href} className="lp-nav-link">{l.label}</a>
            ))}
          </nav>
          <div className="lp-nav-actions">
            <Link to="/login" className="lp-btn-ghost">Se connecter</Link>
            <button onClick={handleCta} className="lp-btn-primary" style={{ cursor: 'pointer' }}>Démarrer gratuitement</button>
          </div>
        </div>
      </header>

      {/* ── Hero — animations CSS au chargement ── */}
      <section className="lp-hero">
        <div className="lp-container lp-hero-inner">
          <div className="lp-hero-content">
            <div className="lp-badge lp-hero-badge">
              <span className="lp-badge-dot" />
              Système ERP Agentique v1.0
            </div>
            <h1 className="lp-h1 lp-hero-title">
              Pilotez votre entreprise<br />
              avec un <span className="lp-gradient-text">ERP intelligent</span>
            </h1>
            <p className="lp-hero-desc lp-hero-desc">
              Conçu pour les PME marocaines, TAQINOR automatise votre gestion
              grâce à l'IA, centralise vos opérations et vous aide à prendre
              des décisions rapides et efficaces, en temps réel.
            </p>
            <div className="lp-hero-actions">
              <button onClick={handleCta} className="lp-btn-primary lp-btn-lg" style={{ cursor: 'pointer' }}>
                Démarrer gratuitement &nbsp;&rarr;
              </button>
              <Link to="/login" className="lp-btn-secondary lp-btn-lg">
                Voir la démo
              </Link>
            </div>
            <div className="lp-hero-trust">
              <span><span className="lp-trust-check">&#10003;</span> Aucune carte requise</span>
              <span><span className="lp-trust-check">&#10003;</span> 7 jours gratuits</span>
              <span><span className="lp-trust-check">&#10003;</span> Support inclus</span>
            </div>
          </div>
          <div className="lp-hero-visual">
            <DashboardMockup />
          </div>
        </div>
      </section>

      {/* ── Stats — compteurs animés ── */}
      <section className="lp-stats-bar">
        <div className="lp-container lp-stats-inner" ref={statsRef}>
          {STATS.map((s, i) => (
            <StatItem key={s.label} stat={s} active={statsVisible} delay={DELAYS[i]} />
          ))}
        </div>
      </section>

      {/* ── Features ── */}
      <section className="lp-features" id="features">
        <div className="lp-container">
          <div className="lp-section-header" ref={sectionFeatRef}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <span className="lp-section-tag lp-anim lp-d0">Fonctionnalités</span>
            </div>
            <h2 className="lp-h2 lp-anim lp-d1">Tout ce qu'il vous faut dans un seul ERP</h2>
            <p className="lp-section-sub lp-anim lp-d2">
              Des outils puissants conçus pour simplifier la gestion et accélérer
              la croissance de votre entreprise.
            </p>
          </div>
          <div className="lp-features-grid" ref={featuresGrid}>
            {FEATURES.map((feat, i) => (
              <div key={feat.title} className={`lp-feature-card lp-anim ${DELAYS[i % 5]}`}>
                <div className="lp-feature-icon-wrap"><feat.Icon /></div>
                <h3 className="lp-h3">{feat.title}</h3>
                <p className="lp-feature-desc">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Modules ── */}
      <section className="lp-modules" id="modules">
        <div className="lp-container">
          <div className="lp-section-header" ref={sectionModRef}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <span className="lp-section-tag lp-anim lp-d0">Modules</span>
            </div>
            <h2 className="lp-h2 lp-anim lp-d1">Tout ce dont vous avez besoin dans un seul système</h2>
          </div>
          <div className="lp-modules-grid" ref={modulesGrid}>
            {MODULES.map((mod, i) => (
              <div key={mod.title} className={`lp-module-card lp-anim ${DELAYS[i % 4]}`}>
                <div className="lp-module-icon-wrap"><mod.Icon /></div>
                <div>
                  <h3 className="lp-h3">{mod.title}</h3>
                  <p className="lp-module-desc">{mod.desc}</p>
                  <ul className="lp-module-list">
                    {mod.items.map((item) => (
                      <li key={item}>
                        <span className="lp-check">&#10003;</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── IA section ── */}
      <section className="lp-ia">
        <div className="lp-container lp-ia-inner" ref={iaRef}>
          <div className="lp-anim-left">
            <div style={{ display: 'flex' }}>
              <span className="lp-section-tag lp-tag-light">Intelligence Artificielle</span>
            </div>
            <h2 className="lp-h2 lp-white" style={{ textAlign: 'left', marginTop: 16 }}>
              Travaillez plus vite<br />avec l'IA
            </h2>
            <p className="lp-ia-desc">
              Notre assistant comprend vos questions en français et agit
              directement dans votre système. Demandez un rapport, une alerte,
              une comparaison — obtenez une réponse en quelques secondes.
            </p>
            <ul className="lp-ia-list">
              {[
                'Posez vos questions en langage naturel',
                'Rapports automatiques sur vos ventes',
                'Alertes intelligentes avant rupture de stock',
                'Prédictions et recommandations IA',
              ].map((item) => (
                <li key={item}>
                  <span className="lp-ia-check">&#10003;</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="lp-ia-visual lp-anim-right">
            <ChatMockup />
          </div>
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section className="lp-testimonials" id="testimonials">
        <div className="lp-container">
          <div className="lp-section-header" ref={sectionTestRef}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <span className="lp-section-tag lp-anim lp-d0">Témoignages</span>
            </div>
            <h2 className="lp-h2 lp-anim lp-d1">Ce que disent nos 500+ clients</h2>
          </div>
          <div className="lp-testimonials-grid" ref={testimonialsGrid}>
            {TESTIMONIALS.map((t, i) => (
              <div key={t.name} className={`lp-testimonial-card lp-anim ${DELAYS[i]}`}>
                <div className="lp-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
                <p className="lp-testimonial-text">{t.text}</p>
                <div className="lp-testimonial-author">
                  <div className="lp-author-avatar">{t.avatar}</div>
                  <div>
                    <div className="lp-author-name">{t.name}</div>
                    <div className="lp-author-role">{t.role}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="lp-final-cta" id="contact">
        <div className="lp-container lp-cta-inner" ref={ctaRef}>
          <h2 className="lp-h2 lp-anim lp-d0">Prêt à transformer votre gestion ?</h2>
          <p className="lp-cta-sub lp-anim lp-d1">
            Rejoignez des centaines d'entreprises qui pilotent leur activité
            avec TAQINOR et l'intelligence artificielle.
          </p>
          <div className="lp-cta-actions lp-anim lp-d2">
            <button onClick={handleCta} className="lp-btn-white" style={{ cursor: 'pointer' }}>
              Démarrer gratuitement &nbsp;&rarr;
            </button>
            <Link to="/login" className="lp-btn-outline-white lp-btn-lg">
              Voir la démo
            </Link>
          </div>
          <div className="lp-cta-trust lp-anim lp-d3">
            <span><span className="lp-cta-check">&#10003;</span> Essai gratuit 7 jours</span>
            <span><span className="lp-cta-check">&#10003;</span> Sans engagement</span>
            <span><span className="lp-cta-check">&#10003;</span> Support inclus</span>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="lp-footer">
        <div className="lp-container">
          <div className="lp-footer-inner">
            <div className="lp-footer-brand">
              <div className="lp-nav-logo">
                <TaqinorLogo size={26} theme="dark" />
              </div>
              <p className="lp-footer-tagline">
                Le premier ERP agentique conçu pour les PME marocaines.
              </p>
            </div>
            <div className="lp-footer-col">
              <div className="lp-footer-col-title">Produit</div>
              <a href="#features">Fonctionnalités</a>
              <a href="#modules">Modules</a>
              <a href="#testimonials">Témoignages</a>
              <a href="#contact">Tarifs</a>
            </div>
            <div className="lp-footer-col">
              <div className="lp-footer-col-title">Entreprise</div>
              <a href="#">À propos</a>
              <a href="#">Blog</a>
              <a href="#">Carrières</a>
              <a href="#">Contact</a>
            </div>
            <div className="lp-footer-col">
              <div className="lp-footer-col-title">Support</div>
              <a href="#">Documentation</a>
              <a href="#">FAQ</a>
              <a href="#">Tutoriels</a>
              <a href="#">Status</a>
            </div>
          </div>
          <div className="lp-footer-bottom">
            <span>&#169; 2025 TAQINOR. Tous droits réservés.</span>
            <span>Conçu avec soin au Maroc.</span>
          </div>
        </div>
      </footer>

    </div>

    {CONTACT_FORM_ENABLED && modalOpen && <ContactModal onClose={() => setModalOpen(false)} />}
    </>
  )
}
