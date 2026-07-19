// Vue CALENDRIER des leads CRM — grille mensuelle (VX25 : la grille elle-même
// vit désormais dans components/MonthGrid.jsx, partagée avec CalendarPage.jsx).
// Les leads sont posés sur leur date de relance ET leur date de visite prévue ;
// les étapes viennent EXCLUSIVEMENT de features/crm/stages. Les pastilles se
// colorent par étape OU par responsable.
import { useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import {
  STAGE_LABELS,
  STAGE_COLORS,
  isPerdu,
} from '../../../../features/crm/stages'
import { Segmented } from '../../../../ui'
import MonthGrid, { localKey } from '../../../../components/MonthGrid'

const MAX_CHIPS_PER_DAY = 3
const MAX_UNDATED_CHIPS = 20

// Normalise une date 'YYYY-MM-DD' (ou null) en clé locale, sans jamais passer
// par `new Date('YYYY-MM-DD')` (qui serait interprété en UTC).
function dateKey(raw) {
  if (!raw || typeof raw !== 'string') return null
  const [y, m, d] = raw.split('-').map((p) => parseInt(p, 10))
  if (!y || !m || !d) return null
  return localKey(y, m, d)
}

// LB29 — une relance « en retard » (comparaison de chaînes locales, jamais
// `new Date('YYYY-MM-DD')` qui serait interprété en UTC — même motif que
// `isEnRetard` de LeadCard.jsx, dupliqué ici en pur car les deux fichiers ne
// s'importent jamais entre eux, cf. règle des lanes file-disjointes).
function isRelanceEnRetard(iso) {
  if (!iso) return false
  const t = new Date()
  const aujourdhui = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
  return iso < aujourdhui
}

// Palette déterministe pour colorer par responsable (owner_nom).
// VX26 — dérivée des tokens de marque (design/tokens.css --owner-color-*)
// au lieu de hex locaux.
const OWNER_PALETTE = [
  'var(--owner-color-1)', 'var(--owner-color-2)', 'var(--owner-color-3)',
  'var(--owner-color-4)', 'var(--owner-color-5)', 'var(--owner-color-6)',
  'var(--owner-color-7)', 'var(--owner-color-8)', 'var(--owner-color-9)',
  'var(--owner-color-10)',
]
function ownerColor(name) {
  if (!name) return 'var(--muted-foreground)'
  let h = 0
  for (const c of String(name)) h = (h * 31 + c.charCodeAt(0)) % 997
  return OWNER_PALETTE[h % OWNER_PALETTE.length]
}

const leadName = (lead) =>
  [lead?.nom, lead?.prenom].filter(Boolean).join(' ').trim() || '(Sans nom)'

// Couleur de la pastille selon la dimension choisie (étape ou responsable) ;
// un lead perdu reste rouge quelle que soit la dimension.
function chipColor(lead, colorBy) {
  if (isPerdu(lead)) return 'var(--destructive)'
  if (colorBy === 'owner') return ownerColor(lead.owner_nom)
  return STAGE_COLORS[lead.stage] ?? 'var(--muted-foreground)'
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
  // LB29 — une relance en retard se souligne (destructive) : un lead perdu
  // porte déjà son propre signal (pastille rouge) — pas de double marquage.
  // Ne concerne QUE la relance (kind='visite' reste hors périmètre de cette
  // tâche, le double-affichage relance+visite étant conservé tel quel).
  const enRetard = !perdu && kind === 'relance' && isRelanceEnRetard(lead.relance_date)
  const titre = perdu
    ? `${name} — Perdu (${dim})`
    : `${name} — ${kind === 'visite' ? 'Visite' : 'Relance'}${enRetard ? ' en retard' : ''} · ${dim}`
  return (
    <button
      type="button"
      className={`cal-chip${perdu ? ' cal-chip-perdu' : ''}${enRetard ? ' cal-chip-late' : ''}`}
      title={titre}
      onClick={() => onOpenLead(lead)}
    >
      <span className="cal-chip-dot" style={{ background: dot }} />
      <span className="cal-chip-name">{icon ? `${icon} ` : ''}{name}</span>
    </button>
  )
}

export default function CalendarView({ leads, onOpenLead }) {
  // Jours dont la liste complète est dépliée (clé 'YYYY-MM-DD' → true).
  const [expandedDays, setExpandedDays] = useState({})
  // Dimension de couleur des pastilles : par étape (défaut) ou par responsable.
  const [colorBy, setColorBy] = useState('stage')

  const toggleDay = (key) =>
    setExpandedDays((prev) => ({ ...prev, [key]: !prev[key] }))

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

  const undatedVisible = undated.slice(0, MAX_UNDATED_CHIPS)
  const undatedOverflow = undated.length - undatedVisible.length

  const renderCell = (cell) => {
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
          cell.isToday ? 'cal-cell-today' : '',
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
  }

  return (
    <>
      <MonthGrid
        renderCell={renderCell}
        headerExtra={(
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
        )}
      />

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
    </>
  )
}
