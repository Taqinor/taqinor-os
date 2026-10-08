import { useContext, useEffect, useRef, useState } from 'react'
import { ReactReduxContext } from 'react-redux'
import TaqinorMark from './TaqinorMark'
import { celebrateDealSigned, PARTY_DURATION_MS } from './celebrate'
import { voice } from '../lib/voice'
import { formatMAD } from '../lib/format'

/* La fête « affaire signée » — le moment le plus important de l'ERP (un devis
   SIGNÉ). VX155 posait une carte sobre ; demande du fondateur (08/10/2026) :
   une VRAIE fête de plus de 30 s, au-delà du « rainbow man » d'Odoo. Plein
   écran nuit étoilée, soleil rayonnant + couronne qui tombe, « Bravo <prénom> ! »
   en or, montant qui défile jusqu'au TTC réel, messages qui tournent, et
   derrière : feux d'artifice, canons à confettis, licorne, pluie d'émojis et
   son (celebrate.js). Montant + kWc restent les chiffres RÉELS transmis par
   l'appelant (jamais inventés). Sous `prefers-reduced-motion` : LA MÊME carte,
   SANS mouvement ni son — jamais moins d'information. */

// Hypothèses marocaines par défaut, identiques à celles du rapport de
// production estimée (`installations/energy_report.py` :
// DEFAULT_RENDEMENT_KWH_PAR_KWC_AN=1600 × DEFAULT_CO2_KG_PAR_KWH=0.81).
const CO2_TONNES_PAR_KWC_AN = 1.3

const CHEERS = [
  'La reine du closing 👑',
  'Affaire signée !',
  voice.dealSigned,
  'Standing ovation 👏👏👏',
  'Encore une victoire pour l\'équipe ☀️',
  'Le soleil brille pour toi aujourd\'hui',
  'Signature en or ✨',
  'Personne ne t\'arrête 🚀',
]

const MUTE_KEY = 'taqinor.party.muted'

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function readMuted() {
  try { return window.localStorage.getItem(MUTE_KEY) === '1' } catch { return false }
}

// Prénom de l'utilisateur connecté, sans exiger de <Provider> (la carte est
// aussi rendue seule dans ses tests).
function useFirstName() {
  const redux = useContext(ReactReduxContext)
  try {
    return redux?.store?.getState()?.auth?.user?.first_name?.trim() || ''
  } catch {
    return ''
  }
}

// Montant qui défile de 0 au TTC réel (≈ 3 s, ease-out).
function useCountUp(target, enabled, ms = 3200) {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    if (!enabled) return undefined
    const t0 = performance.now()
    const id = window.setInterval(() => {
      const p = Math.min(1, (performance.now() - t0) / ms)
      setProgress(p)
      if (p >= 1) window.clearInterval(id)
    }, 33)
    return () => window.clearInterval(id)
  }, [enabled, ms])
  return enabled ? target * (1 - (1 - progress) ** 4) : target
}

export default function DealSignedCelebration({
  open, reference, montantTtc, kwc, onClose,
}) {
  const reduced = prefersReducedMotion()
  const prenom = useFirstName()
  const party = useRef(null)
  const stage = useRef(null)
  const [muted, setMuted] = useState(readMuted)
  const [cheer, setCheer] = useState(0)
  const [partyOver, setPartyOver] = useState(reduced)

  // La fête (celebrate.js) ne se lance qu'UNE fois par ouverture et s'arrête
  // net à la fermeture.
  useEffect(() => {
    if (!open) return undefined
    party.current = celebrateDealSigned({ muted: readMuted(), mount: stage.current })
    party.current?.done.then(() => setPartyOver(true))
    if (!party.current) setPartyOver(true)
    return () => { party.current?.stop(); party.current = null }
  }, [open])

  useEffect(() => {
    if (!open || reduced) return undefined
    const id = window.setInterval(() => setCheer((c) => (c + 1) % CHEERS.length), 3500)
    return () => window.clearInterval(id)
  }, [open, reduced])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const montant = useCountUp(Number(montantTtc) || 0, open && !reduced)

  if (!open) return null

  const co2 = kwc != null ? Math.round(kwc * CO2_TONNES_PAR_KWC_AN * 10) / 10 : null
  const toggleMute = () => {
    const next = !muted
    setMuted(next)
    party.current?.setMuted(next)
    try { window.localStorage.setItem(MUTE_KEY, next ? '1' : '0') } catch { /* stockage bloqué */ }
  }

  return (
    <div
      className={`deal-party fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center overflow-hidden p-4${reduced ? ' deal-party--still' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="deal-signed-title"
      data-testid="deal-signed-celebration"
      ref={stage}
    >
      {!reduced && <div className="deal-party__flash" aria-hidden="true" />}
      {!reduced && <div className="deal-party__rays" aria-hidden="true" />}
      {!reduced && (
        <div className="deal-party__ticker" aria-hidden="true">
          <span>
            {'🎉 FÉLICITATIONS 👑 AFFAIRE SIGNÉE ☀️ BRAVO 🥂 '.repeat(6)}
          </span>
        </div>
      )}

      <div className="deal-party__card relative z-10 w-full max-w-lg text-center">
        <div className="deal-party__crown" aria-hidden="true">👑</div>
        <div className="mb-3 flex justify-center">
          <TaqinorMark size={72} animate={!reduced} />
        </div>
        <p className="deal-party__eyebrow">
          Affaire signée{reference ? ` — ${reference}` : ''}
        </p>
        <h2 id="deal-signed-title" className="deal-party__title font-display">
          Bravo{prenom ? ` ${prenom}` : ''} !
        </h2>
        <p className="deal-party__cheer" key={cheer} aria-live="polite">
          {reduced ? voice.dealSigned : CHEERS[cheer]}
        </p>
        <p className="deal-party__amount tabular-nums">
          {formatMAD(reduced ? montantTtc : montant)}
        </p>
        {kwc != null && (
          <p className="deal-party__meta tabular-nums">
            ≈ {kwc} kWc{co2 != null ? ` · ≈ ${co2} t CO₂ évitées/an` : ''}
          </p>
        )}
        <div className="mt-7 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={onClose}
            className="deal-party__cta btn inline-flex items-center justify-center rounded-full px-8 py-3 text-sm font-bold"
          >
            Continuer
          </button>
          {!reduced && (
            <button
              type="button"
              onClick={toggleMute}
              className="deal-party__mute rounded-full px-3 py-3 text-sm"
              aria-label={muted ? 'Activer le son' : 'Couper le son'}
              title={muted ? 'Activer le son' : 'Couper le son'}
            >
              {muted ? '🔇' : '🔊'}
            </button>
          )}
        </div>
        {!reduced && !partyOver && (
          <p className="deal-party__hint">
            La fête dure {Math.round(PARTY_DURATION_MS / 1000)} secondes — profite 🥳
          </p>
        )}
      </div>
    </div>
  )
}
