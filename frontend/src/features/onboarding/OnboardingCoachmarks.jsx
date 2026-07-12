// FG16 — Guide d'accueil in-app (coachmarks), 100 % maison, SANS dépendance.
// Séquence de bulles d'aide qui ne s'affiche qu'une fois (drapeau localStorage),
// est dismissible, et re-déclenchable depuis les Paramètres via un événement
// window. Monté une seule fois dans le Layout ; rend `null` tant que le guide
// n'a pas à s'afficher.
//
// Chaque étape peut « éclairer » (spotlight) un élément ciblé par un sélecteur
// `data-coach` : on mesure sa position et on dessine un halo + une bulle à côté.
// Si la cible est absente de l'écran courant (rôle/onglet/mobile), l'étape
// dégrade proprement en carte centrée — le guide n'échoue jamais.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useSelector } from 'react-redux'
import { X, ArrowRight, ArrowLeft, Check } from 'lucide-react'
// VX185/wave-3 perf: import direct (jamais le barrel `../../ui`) — monté
// statiquement par Layout.jsx (Layout -> router/index.jsx -> main.jsx), donc
// tout ce que le barrel touche (dont datatable -> recharts/pdfjs-dist)
// finirait en `<link rel="modulepreload">` sur chaque page, `/login` inclus.
import { Button } from '../../ui/Button'
import { GLOBAL_SHORTCUTS } from '../../providers/shortcuts'
import {
  shouldAutoOpenCoachmarks, markCoachmarksSeen, REPLAY_EVENT,
} from './onboardingHelpers'

// VX247(a) — le tour montrait la MÊME séquence à tout le monde : un compte
// Technicien voyait « Invitez votre équipe » sans jamais pouvoir le faire.
// `roles` (optionnel, tableau de paliers 'normal'/'responsable'/'admin')
// filtre l'étape ; son absence = visible pour TOUS les rôles.
// Étapes du guide (texte 100 % français). `target` = sélecteur CSS optionnel.
const STEPS = [
  {
    target: null,
    title: 'Bienvenue sur TAQINOR OS',
    body: "Voici un tour rapide pour configurer l'essentiel en quelques étapes. "
      + 'Vous pourrez le revoir à tout moment depuis les Paramètres.',
  },
  {
    target: '[data-coach="parametres"]',
    title: 'Complétez le profil de votre entreprise',
    body: "Depuis les Paramètres, renseignez le nom, l'adresse et le contact "
      + "de votre société : ces informations apparaissent en en-tête de vos "
      + 'devis et factures.',
    roles: ['admin'],
  },
  {
    target: '[data-coach="produits"]',
    title: 'Créez votre premier produit',
    body: 'Ajoutez au catalogue vos panneaux, onduleurs et autres articles '
      + 'pour composer vos devis en quelques clics.',
    roles: ['admin', 'responsable'],
  },
  {
    target: '[data-coach="equipe"]',
    title: 'Invitez votre équipe',
    body: "Créez les comptes de vos collaborateurs et attribuez-leur un rôle "
      + "pour travailler à plusieurs en toute sécurité.",
    roles: ['admin'],
  },
  // VX247(a) — étape dédiée aux rôles non-admin (le tour ne parlait jamais
  // directement du quotidien d'un Commercial/Technicien).
  {
    target: '[data-coach="ma-file"]',
    title: 'Votre file de travail',
    body: 'Retrouvez chaque jour vos activités, leads et tâches à traiter '
      + 'dans « Ma file » — rien ne se perd, tout est classé par échéance.',
    roles: ['normal', 'responsable'],
  },
  {
    target: null,
    title: 'Tout est prêt',
    body: "Suivez votre progression dans l'onglet « Prise en main » des "
      + 'Paramètres. Bon démarrage !',
  },
  // VX247(b) — le tour ne mentionnait jamais ⌘K/Ctrl K ni « ? » : ÉTAPE
  // FINALE, sourcée de GLOBAL_SHORTCUTS (jamais un raccourci littéral dupliqué).
  {
    target: null,
    title: 'Deux raccourcis à retenir',
    body: GLOBAL_SHORTCUTS
      .map((s) => `${s.keys} — ${s.label}`)
      .join(' · '),
  },
]

const PAD = 8 // marge du halo autour de la cible

export default function OnboardingCoachmarks() {
  const [open, setOpen] = useState(() => shouldAutoOpenCoachmarks())
  const [step, setStep] = useState(0)
  const [rect, setRect] = useState(null)
  // VX247(a) — palier machine ('normal'/'responsable'/'admin'), même source
  // que useHasRole (ARC47) : lecture d'AFFICHAGE, pas un gating de droits.
  const roleTier = useSelector((s) => s.auth.role)
  const steps = useMemo(
    () => STEPS.filter((s) => !s.roles || s.roles.includes(roleTier)),
    [roleTier],
  )

  // Re-déclenchement depuis les Paramètres (« Revoir le guide »).
  useEffect(() => {
    const onReplay = () => { setStep(0); setOpen(true) }
    window.addEventListener(REPLAY_EVENT, onReplay)
    return () => window.removeEventListener(REPLAY_EVENT, onReplay)
  }, [])

  const current = steps[step]

  // Déclarés avant les effets qui les référencent (évite l'accès en TDZ).
  const finish = () => { markCoachmarksSeen(); setOpen(false); setStep(0) }
  const next = () => { if (step >= steps.length - 1) finish(); else setStep(s => s + 1) }
  const prev = () => setStep(s => Math.max(0, s - 1))

  // Mesure de la cible de l'étape courante (position à l'écran). Recalcule au
  // changement d'étape, au redimensionnement et au défilement.
  const measure = useCallback(() => {
    if (!open || !current?.target) { setRect(null); return }
    const el = document.querySelector(current.target)
    if (!el) { setRect(null); return }
    const r = el.getBoundingClientRect()
    if (r.width === 0 && r.height === 0) { setRect(null); return }
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
  }, [open, current])

  useEffect(() => {
    // Mesure initiale déférée (évite un setState synchrone dans l'effet).
    const raf = requestAnimationFrame(measure)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [measure])

  // Navigation clavier : Échap ferme, flèches naviguent.
  useEffect(() => {
    if (!open) return
    const onKey = (e) => {
      if (e.key === 'Escape') finish()
      else if (e.key === 'ArrowRight') next()
      else if (e.key === 'ArrowLeft') prev()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, step]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!open || !current) return null

  const isLast = step === steps.length - 1
  const isFirst = step === 0

  // Position de la bulle : sous la cible si mesurée, sinon centrée.
  let bubbleStyle
  if (rect) {
    const vw = window.innerWidth
    const width = Math.min(340, vw - 24)
    const top = rect.top + rect.height + PAD + 6
    let left = rect.left
    if (left + width > vw - 12) left = vw - width - 12
    if (left < 12) left = 12
    bubbleStyle = { position: 'fixed', top, left, width, maxWidth: 'calc(100vw - 24px)' }
  } else {
    bubbleStyle = {
      position: 'fixed', top: '50%', left: '50%',
      transform: 'translate(-50%, -50%)', width: 'min(420px, calc(100vw - 32px))',
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[var(--z-modal)]" role="dialog" aria-modal="true"
         aria-label="Guide d'accueil">
      {/* Voile : opaque partout, « trou » lumineux (halo) sur la cible mesurée. */}
      {rect ? (
        /* Cadre-halo mettant la cible en valeur ; l'ombre étalée assombrit tout
           le reste de l'écran (le clic passe au travers du halo). */
        <div className="pointer-events-none fixed rounded-xl ring-2 ring-primary transition-all"
             style={{
               top: rect.top - PAD, left: rect.left - PAD,
               width: rect.width + PAD * 2, height: rect.height + PAD * 2,
               boxShadow: '0 0 0 9999px rgba(15,23,42,0.62)',
             }} />
      ) : (
        <div className="fixed inset-0 bg-nuit/60 backdrop-blur-sm" onClick={finish} />
      )}

      {/* Bulle d'aide */}
      <div style={bubbleStyle}
           className="animate-pop-in rounded-xl border border-border bg-popover p-4 shadow-ui-lg">
        <div className="mb-1.5 flex items-start justify-between gap-3">
          <h3 className="font-display text-base font-bold tracking-tight text-foreground">
            {current.title}
          </h3>
          <button type="button" onClick={finish} aria-label="Fermer le guide"
                  className="-mr-1 -mt-1 shrink-0 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{current.body}</p>

        <div className="mt-4 flex items-center justify-between gap-2">
          {/* Points de progression */}
          <div className="flex items-center gap-1.5" aria-hidden="true">
            {steps.map((_, i) => (
              <span key={i}
                    className={['size-1.5 rounded-full transition-colors',
                      i === step ? 'bg-primary' : 'bg-border'].join(' ')} />
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            {!isFirst && (
              <Button type="button" size="sm" variant="outline" onClick={prev}>
                <ArrowLeft className="size-4" aria-hidden="true" /> Précédent
              </Button>
            )}
            {!isLast && (
              <Button type="button" size="sm" variant="ghost" onClick={finish}>
                Passer
              </Button>
            )}
            <Button type="button" size="sm" onClick={next}>
              {isLast ? (
                <><Check className="size-4" aria-hidden="true" /> Terminer</>
              ) : (
                <>Suivant <ArrowRight className="size-4" aria-hidden="true" /></>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
