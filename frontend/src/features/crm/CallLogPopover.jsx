// VX87 — Journal d'appel en un geste : ressusciter `crmApi.logInteraction`
// (mort UI, ZÉRO site d'appel avant cette tâche) + poser la prochaine
// relance dans le MÊME geste. L'action la plus fréquente du commercial
// (15-30 appels/jour) coûtait ~6 interactions dans 3 zones de la modale ;
// ce popover réduit ça à : issue (1 clic) + note (facultative) + prochaine
// action (1 clic optionnel) → 1 requête, journalisé au chatter.
// EZ1 — ce popover devient LE planificateur rapide (fondateur 2026-08-01,
// « l'ERP le plus facile »).
// ----------------------------------------------------------------------------
// État vérifié : trois mécanismes RIVAUX se disputaient « planifier la suite »
//   • ici : 4 offsets figés (J+0/1/3/7) qui écrasaient EN SILENCE une relance
//     déjà posée — jamais lue, jamais affichée ;
//   • `LeadsPage.onPlanifierRelance` : ouvrait simplement la fiche ;
//   • `PlanActiviteDialog` : applique un GABARIT de plan prédéfini, sans date
//     libre.
// EZ1 en fait UNE seule surface rapide : date LIBRE + objet optionnel, et
// PLUS AUCUN écrasement silencieux. `PlanActiviteDialog` garde son rôle —
// appliquer un gabarit multi-étapes — qui est autre chose.
//
// PAS D'HEURE : `Lead.relance_date` et `records.Activity.due_date` sont des
// DateField. Poser une heure ici demanderait une tâche SCHEMA dédiée ; on ne
// fait pas semblant.
import { useEffect, useRef, useState } from 'react'
import { Phone, Mail } from 'lucide-react'
import crmApi from '../../api/crmApi'
import recordsApi from '../../api/recordsApi'
import { OUTCOME_LABELS } from '../../components/ChatterTimeline'
import {
  Button, Input, Label, Popover, PopoverTrigger, PopoverContent, Textarea,
} from '../../ui'
import { DatePicker } from '../../ui/DatePicker'
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

/** Date JS → 'YYYY-MM-DD' (jamais un ISO UTC : `relance_date` est une DATE
    locale, et `toISOString()` décale d'un jour le soir en heure marocaine). */
function ymd(d) {
  if (!d) return ''
  const date = d instanceof Date ? d : new Date(d)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const dateFromYmd = (s) => (s ? new Date(`${String(s).slice(0, 10)}T00:00:00`) : null)
const formatFr = (s) => (s ? dateFromYmd(s).toLocaleDateString('fr-FR') : '')

/**
 * @param {number} leadId
 * @param {'appel'|'email'} [kind]  Type d'interaction journalisée (défaut 'appel').
 * @param {ReactNode} [trigger]  Élément déclencheur custom (défaut : bouton compact).
 * @param {boolean} [open]  Contrôlé (nudge post-appel) — sinon non contrôlé.
 * @param {(open: boolean) => void} [onOpenChange]
 * @param {() => void} [onLogged]  Notifié après journalisation réussie (rafraîchir le chatter).
 * @param {string|null} [relanceActuelle]  EZ1 — relance DÉJÀ posée sur le lead
 *   (`lead.relance_date`). Fournie, elle est AFFICHÉE et l'utilisateur doit
 *   choisir « Remplacer » ou « Garder » — fin de l'écrasement silencieux.
 * @param {'journal'|'planification'} [mode]  EZ1 — 'planification' = on n'a pas
 *   appelé, on planifie seulement : le choix d'issue disparaît et n'est plus
 *   exigé pour enregistrer.
 */
export default function CallLogPopover({
  leadId, kind = 'appel', trigger, open, onOpenChange, onLogged,
  relanceActuelle = null, mode = 'journal',
}) {
  const planificationSeule = mode === 'planification'
  const [internalOpen, setInternalOpen] = useState(false)
  const isControlled = open !== undefined
  const isOpen = isControlled ? open : internalOpen
  const setOpen = (next) => {
    if (!isControlled) setInternalOpen(next)
    onOpenChange?.(next)
  }

  const [outcome, setOutcome] = useState('')
  const [note, setNote] = useState('')
  // EZ1 — UNE seule valeur de date : les chips J+0/1/3/7 ne sont plus un
  // mécanisme parallèle, ce sont des raccourcis qui REMPLISSENT ce champ.
  const [dateRelance, setDateRelance] = useState('')
  const [objet, setObjet] = useState('')
  // EZ1 — décision explicite quand une relance existe déjà. Défaut 'garder' :
  // on ne peut pas écraser sans avoir dit oui.
  const [conflit, setConflit] = useState('garder')
  const [busy, setBusy] = useState(false)

  const reset = () => {
    setOutcome('')
    setNote('')
    setDateRelance('')
    setObjet('')
    setConflit('garder')
  }

  // EZ1 — y a-t-il un conflit à trancher ? Seulement si une relance existe
  // DÉJÀ, qu'une nouvelle date est choisie, et qu'elle est différente.
  const relanceExistante = relanceActuelle ? String(relanceActuelle).slice(0, 10) : null
  const enConflit = !!relanceExistante && !!dateRelance && dateRelance !== relanceExistante
  const ecrasera = enConflit ? conflit === 'remplacer' : !!dateRelance

  const submit = async () => {
    // En mode journal, l'issue reste obligatoire (on journalise un APPEL).
    // En mode planification, il n'y a pas eu d'appel : il suffit d'une date.
    if (!planificationSeule && !outcome) return
    if (planificationSeule && !dateRelance) return
    setBusy(true)
    try {
      if (!planificationSeule) {
        await crmApi.logInteraction(leadId, {
          kind, outcome, body: note.trim() || undefined,
        })
      }
      if (ecrasera) {
        await crmApi.updateLead(leadId, { relance_date: dateRelance })
      }
      // EZ1 — un OBJET transforme la relance en vraie activité datée
      // (`POST /records/activities/`, cible `crm.lead` déjà déclarée dans
      // `apps/crm/platform.py`) : zéro backend, l'item apparaît dans « Ma
      // file » comme n'importe quelle autre activité.
      if (objet.trim() && dateRelance) {
        await recordsApi.createActivity({
          model: 'crm.lead',
          id: leadId,
          summary: objet.trim(),
          due_date: dateRelance,
        })
      }
      toastSuccess(planificationSeule ? 'Relance planifiée.' : 'Appel journalisé.')
      reset()
      setOpen(false)
      onLogged?.()
    } catch {
      toastError(planificationSeule
        ? "La relance n'a pas pu être planifiée — réessayez."
        : "L'appel n'a pas pu être journalisé — réessayez.")
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
          <p className="clp-title">
            {planificationSeule
              ? 'Planifier une relance'
              : `Journaliser ${kind === 'email' ? 'un e-mail' : 'un appel'}`}
          </p>

          {/* En planification pure, il n'y a pas eu d'appel : pas d'issue. */}
          {!planificationSeule && (
            <>
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
            </>
          )}

          <div className="clp-next-action">
            <span className="clp-next-action-label">Prochaine action :</span>
            {/* EZ1 — les 4 offsets ne sont plus un mécanisme parallèle : ce
                sont des RACCOURCIS qui remplissent la date libre ci-dessous.
                Une seule valeur, donc plus rien à réconcilier. */}
            <div className="clp-next-action-btns">
              {NEXT_ACTION_DAYS.map((n) => {
                const iso = dateInDays(n.key)
                return (
                  <button
                    key={n.key}
                    type="button"
                    className={`clp-next-btn${dateRelance === iso ? ' clp-next-btn-active' : ''}`}
                    onClick={() => setDateRelance((cur) => (cur === iso ? '' : iso))}
                  >
                    {n.label}
                  </button>
                )
              })}
            </div>
            {/* EZ1 — DATE LIBRE. Pas d'heure : `relance_date` et
                `Activity.due_date` sont des DateField (une heure demanderait
                une tâche SCHEMA dédiée). */}
            <div className="clp-free-date">
              <Label htmlFor={`clp-date-${leadId}`}>Ou une date précise</Label>
              <DatePicker
                id={`clp-date-${leadId}`}
                aria-label="Date de relance"
                value={dateFromYmd(dateRelance)}
                onChange={(d) => setDateRelance(ymd(d))}
              />
            </div>
            {/* EZ1 — OBJET optionnel : renseigné, il crée une vraie activité
                datée (records) en plus de la relance — elle apparaît dans
                « Ma file » comme n'importe quelle autre. */}
            <div className="clp-objet">
              <Label htmlFor={`clp-objet-${leadId}`}>Objet (facultatif)</Label>
              <Input
                id={`clp-objet-${leadId}`}
                placeholder="Ex. Rappeler après réception du devis"
                value={objet}
                onChange={(e) => setObjet(e.target.value)}
              />
            </div>
          </div>

          {/* EZ1 — LE correctif du bug d'origine : une relance déjà posée était
              écrasée EN SILENCE, jamais lue ni affichée. Elle est désormais
              montrée, et rien ne bouge sans un choix explicite. */}
          {enConflit && (
            <div className="clp-conflit" role="group" aria-label="Relance déjà planifiée">
              <p className="clp-conflit-texte">
                Une relance est déjà prévue le <strong>{formatFr(relanceExistante)}</strong>.
              </p>
              <div className="clp-conflit-btns">
                <button
                  type="button"
                  className={`clp-next-btn${conflit === 'garder' ? ' clp-next-btn-active' : ''}`}
                  aria-pressed={conflit === 'garder'}
                  onClick={() => setConflit('garder')}
                >
                  Garder le {formatFr(relanceExistante)}
                </button>
                <button
                  type="button"
                  className={`clp-next-btn${conflit === 'remplacer' ? ' clp-next-btn-active' : ''}`}
                  aria-pressed={conflit === 'remplacer'}
                  onClick={() => setConflit('remplacer')}
                >
                  Remplacer par le {formatFr(dateRelance)}
                </button>
              </div>
            </div>
          )}

          <div className="clp-actions">
            <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
              Annuler
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={busy || (planificationSeule ? !dateRelance : !outcome)}
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
