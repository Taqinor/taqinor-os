// Vue CALENDRIER des leads CRM — grille mensuelle construite à la main
// (aucune librairie de calendrier). Les leads sont posés sur leur date de
// relance ET leur date de visite prévue ; les étapes viennent EXCLUSIVEMENT de
// features/crm/stages. Les pastilles se colorent par étape OU par responsable.
import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react'
import {
  STAGE_LABELS,
  STAGE_COLORS,
  isPerdu,
} from '../../../../features/crm/stages'
import {
  Button, IconButton, Segmented,
} from '../../../../ui'

// Semaine française : lundi en premier.
const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MAX_CHIPS_PER_DAY = 3
const MAX_UNDATED_CHIPS = 20

const pad2 = (n) => String(n).padStart(2, '0')

// Clé locale 'YYYY-MM-DD' d'une date (jamais via toISOString → pas d'UTC).
const localKey = (y, m, d) => `${y}-${pad2(m)}-${pad2(d)}`

// Normalise une date 'YYYY-MM-DD' (ou null) en clé locale, sans jamais passer
// par `new Date('YYYY-MM-DD')` (qui serait interprété en UTC).
function dateKey(raw) {
  if (!raw || typeof raw !== 'string') return null
  const [y, m, d] = raw.split('-').map((p) => parseInt(p, 10))
  if (!y || !m || !d) return null
  return localKey(y, m, d)
}

// Palette déterministe pour colorer par responsable (owner_nom).
const OWNER_PALETTE = [
  '#2563eb', '#16a34a', '#f5a623', '#a21caf', '#dc2626',
  '#0891b2', '#7c3aed', '#ca8a04', '#be185d', '#4d7c0f',
]
function ownerColor(name) {
  if (!name) return '#64748b'
  let h = 0
  for (const c of String(name)) h = (h * 31 + c.charCodeAt(0)) % 997
  return OWNER_PALETTE[h % OWNER_PALETTE.length]
}

const leadName = (lead) =>
  [lead?.nom, lead?.prenom].filter(Boolean).join(' ').trim() || '(Sans nom)'

// Couleur de la pastille selon la dimension choisie (étape ou responsable) ;
// un lead perdu reste rouge quelle que soit la dimension.
function chipColor(lead, colorBy) {
  if (isPerdu(lead)) return '#dc2626'
  if (colorBy === 'owner') return ownerColor(lead.owner_nom)
  return STAGE_COLORS[lead.stage] ?? '#64748b'
}

function LeadChip({ lead, onOpenLead, colorBy, kind = 'relance' }) {
  const perdu = isPerdu(lead)
  const dot = chipColor(lead, colorBy)
  const name = leadName(lead)
  const stageLabel = STAGE_LABELS[lead.stage] ?? lead.stage ?? ''
  const ownerLabel = lead.owner_nom || 'Non assigné'
  const dim = colorBy === 'owner' ? ownerLabel : stageLabel
  // Une visite prévue porte une icône distincte de la relance.
  const icon = kind === 'visite' ? '🔧' : ''
  const titre = perdu
    ? `${name} — Perdu (${dim})`
    : `${name} — ${kind === 'visite' ? 'Visite' : 'Relance'} · ${dim}`
  return (
    <button
      type="button"
      className={`cal-chip${perdu ? ' cal-chip-perdu' : ''}`}
      title={titre}
      onClick={() => onOpenLead(lead)}
    >
      <span className="cal-chip-dot" style={{ background: dot }} />
      <span className="cal-chip-name">{icon ? `${icon} ` : ''}{name}</span>
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
  // Dimension de couleur des pastilles : par étape (défaut) ou par responsable.
  const [colorBy, setColorBy] = useState('stage')

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

  // Index jour → événements {lead, kind}. Un lead peut apparaître DEUX fois :
  // sur sa relance_date (kind 'relance') ET sa visite_prevue_le (kind 'visite').
  // `undated` = leads sans aucune date posée (ni relance ni visite).
  const { byDay, undated } = useMemo(() => {
    const map = new Map()
    const none = []
    const push = (key, lead, kind) => {
      if (!map.has(key)) map.set(key, [])
      map.get(key).push({ lead, kind })
    }
    for (const lead of leads ?? []) {
      const rKey = dateKey(lead?.relance_date)
      const vKey = dateKey(lead?.visite_prevue_le)
      if (rKey) push(rKey, lead, 'relance')
      if (vKey) push(vKey, lead, 'visite')
      if (!rKey && !vKey) none.push(lead)
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
          <IconButton
            variant="outline"
            className="cal-nav-btn"
            onClick={() => goMonth(-1)}
            label="Mois précédent"
          >
            <ChevronLeft />
          </IconButton>
          <IconButton
            variant="outline"
            className="cal-nav-btn"
            onClick={() => goMonth(1)}
            label="Mois suivant"
          >
            <ChevronRight />
          </IconButton>
        </div>
        <h3 className="cal-title">{title}</h3>
        <div className="cal-header-tools">
          <Segmented
            size="sm"
            aria-label="Couleur des pastilles"
            value={colorBy}
            onChange={setColorBy}
            options={[
              { value: 'stage', label: 'Étape' },
              { value: 'owner', label: 'Responsable' },
            ]}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="cal-today-btn"
            onClick={goToday}
          >
            Aujourd&apos;hui
          </Button>
        </div>
      </div>

      <div className="cal-grid" role="grid" aria-label={`Calendrier ${title}`}>
        {WEEKDAYS.map((day) => (
          <div key={day} className="cal-weekday">
            {day}
          </div>
        ))}
        {cells.map((cell) => {
          const dayEvents = byDay.get(cell.key) ?? []
          const expanded = Boolean(expandedDays[cell.key])
          const visible =
            expanded || dayEvents.length <= MAX_CHIPS_PER_DAY
              ? dayEvents
              : dayEvents.slice(0, MAX_CHIPS_PER_DAY)
          const hidden = dayEvents.length - visible.length
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
                {visible.map(({ lead, kind }) => (
                  <LeadChip
                    key={`${kind}-${lead.id}`}
                    lead={lead}
                    kind={kind}
                    colorBy={colorBy}
                    onOpenLead={onOpenLead}
                  />
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
                {expanded && dayEvents.length > MAX_CHIPS_PER_DAY && (
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
            <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
            {undated.length} lead{undated.length > 1 ? 's' : ''} sans date de
            relance ni de visite
          </p>
          <div className="cal-undated-chips">
            {undatedVisible.map((lead) => (
              <LeadChip
                key={lead.id}
                lead={lead}
                colorBy={colorBy}
                onOpenLead={onOpenLead}
              />
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
