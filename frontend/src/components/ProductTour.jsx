// NTDMO15 — visite guidée PAR ÉCRAN (« product tour »), une par écran
// money-path (NTDMO14 : devis, leads, factures, chantiers, stock, dashboard).
// Réutilise les primitives Popover du design system (aucune nouvelle lib de
// tour type Pendo/Appcues) : la bulle reprend le style de `ui/Popover`
// (`PopoverContent`), positionnée à côté de l'élément ciblé — même technique
// de mesure/spotlight que le guide global FG16 (`OnboardingCoachmarks`), mais
// suivi côté SERVEUR (jamais localStorage) pour ne jamais redemander à
// l'utilisateur après une reconnexion.
//
// Se déclenche automatiquement à la première visite d'un écran cible pour un
// utilisateur récent (< 30 jours, `isNewUser`), jamais s'il a déjà vu/fermé ce
// tour. Jamais bloquant : Échap ferme, un clic sur le voile ferme, aucun
// fond opaque plein écran qui empêcherait d'utiliser l'écran réel en dessous.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { X, ArrowRight, ArrowLeft, Check } from 'lucide-react'
import { Button } from '../ui/Button'
import {
  fetchTours, findTourForPath, isNewUser, markTourSeen,
} from '../features/onboarding/productTours'

const PAD = 8

export default function ProductTour() {
  const { pathname } = useLocation()
  const user = useSelector((s) => s.auth?.user)
  const [tours, setTours] = useState(null)
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)
  const [rect, setRect] = useState(null)
  const [activeKey, setActiveKey] = useState(null)
  const bubbleRef = useRef(null)

  // Chargement du catalogue (un seul appel réseau, mis en cache — NTDMO14).
  useEffect(() => {
    let alive = true
    fetchTours().then((data) => { if (alive) setTours(data) })
    return () => { alive = false }
  }, [])

  const tour = useMemo(() => findTourForPath(tours, pathname), [tours, pathname])

  // Déclenchement automatique : nouvel écran cible, tour jamais vu, utilisateur
  // récent — jamais si un autre tour est déjà ouvert.
  useEffect(() => {
    if (open) return
    if (!tour || tour.vu) return
    if (!isNewUser(user)) return
    const key = tour.tour_key
    // setState différé au prochain microtask (jamais synchrone dans l'effet) —
    // évite react-hooks/set-state-in-effect sans changer le comportement visible.
    queueMicrotask(() => {
      setActiveKey(key)
      setStep(0)
      setOpen(true)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tour, pathname])

  const etapes = useMemo(() => tour?.etapes ?? [], [tour])
  const current = etapes[step]

  const finish = useCallback(() => {
    setOpen(false)
    setStep(0)
    if (activeKey) markTourSeen(activeKey)
  }, [activeKey])

  const next = useCallback(() => {
    if (step >= etapes.length - 1) finish()
    else setStep((s) => s + 1)
  }, [step, etapes.length, finish])

  const prev = useCallback(() => setStep((s) => Math.max(0, s - 1)), [])

  const measure = useCallback(() => {
    if (!open || !current?.selecteur) { setRect(null); return }
    const el = document.querySelector(current.selecteur)
    if (!el) { setRect(null); return }
    const r = el.getBoundingClientRect()
    if (r.width === 0 && r.height === 0) { setRect(null); return }
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
  }, [open, current])

  useEffect(() => {
    const raf = requestAnimationFrame(measure)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [measure])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') finish()
      else if (e.key === 'ArrowRight') next()
      else if (e.key === 'ArrowLeft') prev()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, finish, next, prev])

  // « Un clic sur le voile ferme » (contrat en tête de fichier) SANS que le voile
  // n'intercepte quoi que ce soit : le voile est décoratif (`pointer-events-none`,
  // comme le spotlight), et la fermeture est ÉCOUTÉE au niveau document. Le geste
  // atteint donc l'écran réel en dessous ET ferme la visite, au lieu d'être avalé.
  // Sans cela, une étape sans cible (`selecteur: ''` — la 1re étape de CHAQUE tour
  // du catalogue NTDMO14) rendait un voile plein écran qui bloquait tout l'écran
  // jusqu'à fermeture explicite, en contradiction directe avec « jamais bloquant ».
  // Écoute limitée au cas voile (`!rect`) : la branche spotlight n'a jamais eu de
  // clic-pour-fermer, son comportement reste identique.
  useEffect(() => {
    if (!open || rect) return undefined
    const onPointerDown = (e) => {
      if (bubbleRef.current?.contains(e.target)) return
      finish()
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open, rect, finish])

  if (!open || !current) return null

  const isLast = step === etapes.length - 1
  const isFirst = step === 0

  // Style de la bulle elle-même. Étape AVEC cible (spotlight, branche
  // inchangée) : ancrée sous l'élément mesuré. Étape SANS cible (1re étape de
  // CHAQUE tour) : plus AUCUN `position`/`transform` de centrage ici — voir la
  // note sur le conteneur centreur plus bas pour le pourquoi.
  let bubbleStyle
  if (rect) {
    const vw = window.innerWidth
    const width = Math.min(320, vw - 24)
    const top = rect.top + rect.height + PAD + 6
    let left = rect.left
    if (left + width > vw - 12) left = vw - width - 12
    if (left < 12) left = 12
    bubbleStyle = { position: 'fixed', top, left, width, maxWidth: 'calc(100vw - 24px)' }
  } else {
    bubbleStyle = { width: 'min(380px, calc(100vw - 32px))' }
  }

  // Contenu partagé par les deux branches (spotlight / sans cible) ci-dessous —
  // évite de dupliquer le corps de la bulle.
  const bubbleBody = (
    <>
      <div className="mb-1.5 flex items-start justify-between gap-3">
        <h3 className="font-display text-sm font-bold tracking-tight text-foreground">
          {current.titre}
        </h3>
        <button type="button" onClick={finish} aria-label="Fermer la visite guidée"
                className="-mr-1 -mt-1 shrink-0 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>
      <p className="text-sm leading-relaxed text-muted-foreground">{current.texte}</p>

      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5" aria-hidden="true">
          {etapes.map((s, i) => (
            <span key={s.ordre}
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
    </>
  )

  const bubbleClassName = 'pointer-events-auto animate-pop-in rounded-lg border border-border '
    + 'bg-popover p-3 text-popover-foreground shadow-ui-lg'

  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-[var(--z-popover)]" role="dialog"
         aria-modal="false" aria-label={`Visite guidée — ${tour?.tour_key ?? ''}`}>
      {rect ? (
        <div className="pointer-events-none fixed rounded-xl ring-2 ring-primary transition-all"
             style={{
               top: rect.top - PAD, left: rect.left - PAD,
               width: rect.width + PAD * 2, height: rect.height + PAD * 2,
               boxShadow: '0 0 0 9999px rgba(15,23,42,0.5)',
             }} />
      ) : (
        <div className="pointer-events-none fixed inset-0 bg-nuit/50 backdrop-blur-sm" />
      )}

      {/* Réutilise le style de `ui/Popover` (PopoverContent) pour la bulle. */}
      {rect ? (
        <div ref={bubbleRef} style={bubbleStyle} className={bubbleClassName}>
          {bubbleBody}
        </div>
      ) : (
        // Étape sans cible : le centrage (`position: fixed` + `top/left: 50%` +
        // `transform: translate(-50%, -50%)`) vit sur CE conteneur dédié, inerte
        // (`pointer-events-none`, comme le calque/voile) et JAMAIS animé — pas
        // sur l'enfant qui porte `animate-pop-in`. `animate-pop-in` définit lui
        // aussi un `transform` (keyframes `pop-in`, qui finissent sur
        // `transform: none` avec un fill-mode `both`), et une animation CSS
        // l'emporte sur tout `transform` posé en `style` inline SUR LE MÊME
        // nœud, pendant toute sa durée et au-delà (le `both`) : un centrage posé
        // directement sur l'élément animé était donc écrasé, et la bulle
        // atterrissait décalée en bas-à-droite du centre au lieu d'être centrée
        // — la toute première chose vue par un nouvel utilisateur, sur chacun
        // des 6 tours (leur 1re étape n'a jamais de `selecteur`). Deux nœuds,
        // deux `transform` séparés : plus aucun conflit possible.
        <div className="pointer-events-none fixed"
             style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
          <div ref={bubbleRef} style={bubbleStyle} className={bubbleClassName}>
            {bubbleBody}
          </div>
        </div>
      )}
    </div>,
    document.body,
  )
}
