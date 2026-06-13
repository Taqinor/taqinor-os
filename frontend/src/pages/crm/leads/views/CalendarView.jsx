// Vue CALENDRIER des leads CRM — grille mensuelle construite à la main
// (aucune librairie de calendrier). Les leads sont posés sur leur date de
// relance ; les étapes viennent EXCLUSIVEMENT de features/crm/stages.
import { useMemo, useState } from 'react'
import {
  STAGE_LABELS,
  STAGE_COLORS,
  isPerdu,
} from '../../../../features/crm/stages'
import './calendar.css'

// Semaine française : lundi en premier.
const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MAX_CHIPS_PER_DAY = 3
const MAX_UNDATED_CHIPS = 20

const pad2 = (n) => String(n).padStart(2, '0')

// Clé locale 'YYYY-MM-DD' d'une date (jamais via toISOString → pas d'UTC).
const localKey = (y, m, d) => `${y}-${pad2(m)}-${pad2(d)}`

// Normalise relance_date ('YYYY-MM-DD' ou null) en clé locale, sans jamais
// passer par `new Date('YYYY-MM-DD')` (qui serait interprété en UTC).
function relanceKey(lead) {
  const raw = lead?.relance_date
  if (!raw || typeof raw !== 'string') return null
  const [y, m, d] = raw.split('-').map((p) => parseInt(p, 10))
  if (!y || !m || !d) return null
  return localKey(y, m, d)
}

const leadName = (lead) =>
  [lead?.nom, lead?.prenom].filter(Boolean).join(' ').trim() || '(Sans nom)'

function LeadChip({ lead, onOpenLead }) {
  const perdu = isPerdu(lead)
  const dot = perdu ? '#dc2626' : STAGE_COLORS[lead.stage] ?? '#64748b'
  const name = leadName(lead)
  const stageLabel = STAGE_LABELS[lead.stage] ?? lead.stage ?? ''
  return (
    <button
      type="button"
      className={`cal-chip${perdu ? ' cal-chip-perdu' : ''}`}
      title={perdu ? `${name} — Perdu (${stageLabel})` : `${name} — ${stageLabel}`}
      onClick={() => onOpenLead(lead)}
    >
      <span className="cal-chip-dot" style={{ background: dot }} />
      <span className="cal-chip-name">{name}</span>
    </button>
  )
}

export default function CalendarView({ leads, onOpenLead }) {
  // Premier jour du mois affiché (initialement : le mois courant).
  const [monthStart, setMonthStart] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  // Jours dont la liste complète est dépliée (clé 'YYYY-MM-DD' → true).
  const [expandedDays, setExpandedDays] = useState({})

  const goToday = () => {
    const now = new Date()
    setMonthStart(new Date(now.getFullYear(), now.getMonth(), 1))
  }
  const goMonth = (delta) =>
    setMonthStart((d) => new Date(d.getFullYear(), d.getMonth() + delta, 1))

  const toggleDay = (key) =>
    setExpandedDays((prev) => ({ ...prev, [key]: !prev[key] }))

  // Titre « Juin 2026 » : locale fr puis majuscule initiale.
  const rawTitle = monthStart.toLocaleDateString('fr-FR', {
    month: 'long',
    year: 'numeric',
  })
  const title = rawTitle.charAt(0).toUpperCase() + rawTitle.slice(1)

  // Index relance → leads, plus la liste des leads sans date de relance.
  const { byDay, undated } = useMemo(() => {
    const map = new Map()
    const none = []
    for (const lead of leads ?? []) {
      const key = relanceKey(lead)
      if (!key) {
        none.push(lead)
        continue
      }
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(lead)
    }
    return { byDay: map, undated: none }
  }, [leads])

  // Grille : semaines complètes (lundi → dimanche), jours voisins inclus.
  const cells = useMemo(() => {
    const year = monthStart.getFullYear()
    const month = monthStart.getMonth()
    const mondayOffset = (monthStart.getDay() + 6) % 7 // lundi = 0
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const total = Math.ceil((mondayOffset + daysInMonth) / 7) * 7
    const out = []
    for (let i = 0; i < total; i += 1) {
      const date = new Date(year, month, 1 - mondayOffset + i)
      out.push({
        key: localKey(date.getFullYear(), date.getMonth() + 1, date.getDate()),
        dayNumber: date.getDate(),
        inMonth: date.getMonth() === month,
      })
    }
    return out
  }, [monthStart])

  const now = new Date()
  const todayKey = localKey(now.getFullYear(), now.getMonth() + 1, now.getDate())

  const undatedVisible = undated.slice(0, MAX_UNDATED_CHIPS)
  const undatedOverflow = undated.length - undatedVisible.length

  return (
    <div className="cal-root">
      <div className="cal-header">
        <div className="cal-nav">
          <button
            type="button"
            className="btn btn-sm btn-outline cal-nav-btn"
            onClick={() => goMonth(-1)}
            aria-label="Mois précédent"
          >
            ◀
          </button>
          <button
            type="button"
            className="btn btn-sm btn-outline cal-nav-btn"
            onClick={() => goMonth(1)}
            aria-label="Mois suivant"
          >
            ▶
          </button>
        </div>
        <h3 className="cal-title">{title}</h3>
        <button
          type="button"
          className="btn btn-sm btn-outline cal-today-btn"
          onClick={goToday}
        >
          Aujourd&apos;hui
        </button>
      </div>

      <div className="cal-grid" role="grid" aria-label={`Calendrier ${title}`}>
        {WEEKDAYS.map((day) => (
          <div key={day} className="cal-weekday">
            {day}
          </div>
        ))}
        {cells.map((cell) => {
          const dayLeads = byDay.get(cell.key) ?? []
          const expanded = Boolean(expandedDays[cell.key])
          const visible =
            expanded || dayLeads.length <= MAX_CHIPS_PER_DAY
              ? dayLeads
              : dayLeads.slice(0, MAX_CHIPS_PER_DAY)
          const hidden = dayLeads.length - visible.length
          return (
            <div
              key={cell.key}
              className={[
                'cal-cell',
                cell.inMonth ? '' : 'cal-cell-out',
                cell.key === todayKey ? 'cal-cell-today' : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              <span className="cal-day-number">{cell.dayNumber}</span>
              <div className="cal-chips">
                {visible.map((lead) => (
                  <LeadChip key={lead.id} lead={lead} onOpenLead={onOpenLead} />
                ))}
                {hidden > 0 && (
                  <button
                    type="button"
                    className="cal-more"
                    onClick={() => toggleDay(cell.key)}
                  >
                    +{hidden} autres
                  </button>
                )}
                {expanded && dayLeads.length > MAX_CHIPS_PER_DAY && (
                  <button
                    type="button"
                    className="cal-more"
                    onClick={() => toggleDay(cell.key)}
                  >
                    Réduire
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {undated.length > 0 && (
        <div className="cal-undated">
          <p className="cal-undated-label">
            {undated.length} lead{undated.length > 1 ? 's' : ''} sans date de
            relance
          </p>
          <div className="cal-undated-chips">
            {undatedVisible.map((lead) => (
              <LeadChip key={lead.id} lead={lead} onOpenLead={onOpenLead} />
            ))}
            {undatedOverflow > 0 && (
              <span className="cal-more cal-more-static">
                +{undatedOverflow}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
