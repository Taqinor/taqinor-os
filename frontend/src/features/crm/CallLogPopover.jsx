// VX87 — Journal d'appel en un geste : ressusciter `crmApi.logInteraction`
// (mort UI, ZÉRO site d'appel avant cette tâche) + poser la prochaine
// relance dans le MÊME geste. L'action la plus fréquente du commercial
// (15-30 appels/jour) coûtait ~6 interactions dans 3 zones de la modale ;
// ce popover réduit ça à : issue (1 clic) + note (facultative) + prochaine
// action (1 clic optionnel) → 1 requête, journalisé au chatter.
import { useEffect, useRef, useState } from 'react'
import { Phone, Mail } from 'lucide-react'
import crmApi from '../../api/crmApi'
import { OUTCOME_LABELS } from '../../components/ChatterTimeline'
import {
  Button, Popover, PopoverTrigger, PopoverContent, Textarea,
} from '../../ui'
import { toastError, toastSuccess } from '../../lib/toast'

// Choix d'issue proposés (miroir de LeadActivity.OUTCOMES côté serveur, hors
// la clé vide '—' qui ne fait pas sens comme choix explicite ici).
const OUTCOME_CHOICES = Object.entries(OUTCOME_LABELS).filter(([k]) => k !== '')

// « Prochaine action » : J+0 (aujourd'hui même), J+1, J+3, J+7 — les délais
// de relance les plus fréquents observés côté commercial.
const NEXT_ACTION_DAYS = [
  { key: 0, label: "Aujourd'hui" },
  { key: 1, label: 'Demain' },
  { key: 3, label: 'Dans 3 j' },
  { key: 7, label: 'Dans 7 j' },
]

function dateInDays(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/**
 * @param {number} leadId
 * @param {'appel'|'email'} [kind]  Type d'interaction journalisée (défaut 'appel').
 * @param {ReactNode} [trigger]  Élément déclencheur custom (défaut : bouton compact).
 * @param {boolean} [open]  Contrôlé (nudge post-appel) — sinon non contrôlé.
 * @param {(open: boolean) => void} [onOpenChange]
 * @param {() => void} [onLogged]  Notifié après journalisation réussie (rafraîchir le chatter).
 */
export default function CallLogPopover({
  leadId, kind = 'appel', trigger, open, onOpenChange, onLogged,
}) {
  const [internalOpen, setInternalOpen] = useState(false)
  const isControlled = open !== undefined
  const isOpen = isControlled ? open : internalOpen
  const setOpen = (next) => {
    if (!isControlled) setInternalOpen(next)
    onOpenChange?.(next)
  }

  const [outcome, setOutcome] = useState('')
  const [note, setNote] = useState('')
  const [nextActionDays, setNextActionDays] = useState(null)
  const [busy, setBusy] = useState(false)

  const reset = () => {
    setOutcome('')
    setNote('')
    setNextActionDays(null)
  }

  const submit = async () => {
    if (!outcome) return
    setBusy(true)
    try {
      await crmApi.logInteraction(leadId, {
        kind, outcome, body: note.trim() || undefined,
      })
      if (nextActionDays !== null) {
        await crmApi.updateLead(leadId, { relance_date: dateInDays(nextActionDays) })
      }
      toastSuccess('Appel journalisé.')
      reset()
      setOpen(false)
      onLogged?.()
    } catch {
      toastError("L'appel n'a pas pu être journalisé — réessayez.")
    } finally {
      setBusy(false)
    }
  }

  const Icon = kind === 'email' ? Mail : Phone

  return (
    <Popover open={isOpen} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        {trigger ?? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            data-call-log-trigger
            title="Journaliser un appel"
          >
            <Icon size={14} aria-hidden="true" /> Journaliser
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent align="start" data-call-log-popover>
        <div className="clp-body">
          <p className="clp-title">Journaliser {kind === 'email' ? 'un e-mail' : 'un appel'}</p>

          <div className="clp-outcomes" role="group" aria-label="Résultat de l'appel">
            {OUTCOME_CHOICES.map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`clp-outcome-btn${outcome === key ? ' clp-outcome-btn-active' : ''}`}
                onClick={() => setOutcome(key)}
                data-outcome={key}
              >
                {label}
              </button>
            ))}
          </div>

          <Textarea
            className="clp-note"
            placeholder="Note (facultative)…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
          />

          <div className="clp-next-action">
            <span className="clp-next-action-label">Prochaine action :</span>
            <div className="clp-next-action-btns">
              {NEXT_ACTION_DAYS.map((n) => (
                <button
                  key={n.key}
                  type="button"
                  className={`clp-next-btn${nextActionDays === n.key ? ' clp-next-btn-active' : ''}`}
                  onClick={() => setNextActionDays((cur) => (cur === n.key ? null : n.key))}
                >
                  {n.label}
                </button>
              ))}
            </div>
          </div>

          <div className="clp-actions">
            <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
              Annuler
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!outcome || busy}
              loading={busy}
              onClick={submit}
            >
              Enregistrer
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

// VX87 — nudge post-appel : après un tap `tel:` sur LeadCard/ListView, au
// retour dans l'onglet (`visibilitychange`), proposer « Appel terminé —
// noter le résultat ? ». Armé par `armCallNudge()` juste avant d'ouvrir le
// lien tel: (l'OS bascule sur l'app Téléphone, revient au navigateur au
// raccroché) ; se désarme automatiquement après déclenchement ou 10 minutes
// (un onglet resté en fond des heures ne doit pas surprendre au retour).
const NUDGE_TIMEOUT_MS = 10 * 60 * 1000

// eslint-disable-next-line react-refresh/only-export-components -- hook co-localisé (dev HMR only)
export function useCallEndedNudge() {
  const [nudgeVisible, setNudgeVisible] = useState(false)
  const armedAt = useRef(null)

  const armCallNudge = () => { armedAt.current = Date.now() }
  const dismissNudge = () => { setNudgeVisible(false); armedAt.current = null }

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return
      if (!armedAt.current) return
      const elapsed = Date.now() - armedAt.current
      armedAt.current = null
      if (elapsed <= NUDGE_TIMEOUT_MS) setNudgeVisible(true)
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [])

  return { nudgeVisible, armCallNudge, dismissNudge }
}
