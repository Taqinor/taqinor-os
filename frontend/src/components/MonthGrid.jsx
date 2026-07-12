// VX25 — MonthGrid : grille mensuelle partagée (cellules lundi-dimanche,
// navigation mois, « Aujourd'hui »), extraite de `CalendarView.jsx` (vue
// calendrier des leads CRM) pour que `CalendarPage.jsx` (calendrier
// transverse poses/interventions/maintenance) tourne sur les MÊMES
// primitives — au lieu de deux implémentations de grille mensuelle, deux
// générations de design dans la même app.
//
// Composant contrôlé en présentation : possède SA PROPRE navigation de mois
// (état interne), mais délègue tout le contenu de chaque cellule à
// `renderCell(cell)` — { key, date, dayNumber, inMonth, isToday } — et le
// contenu additionnel de l'en-tête (filtres, boutons page-spécifiques) à
// `headerExtra`. Zéro dépendance de données : aucune notion de « lead » ni
// d'« événement » ici.
import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button, IconButton } from '../ui'

const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

const pad2 = (n) => String(n).padStart(2, '0')

// Clé locale 'YYYY-MM-DD' d'une date (jamais via toISOString → pas d'UTC).
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé (dev HMR only)
export const localKey = (y, m, d) => `${y}-${pad2(m)}-${pad2(d)}`

// Titre « Juin 2026 » : locale fr puis majuscule initiale.
function monthTitle(monthStart) {
  const raw = monthStart.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

/**
 * @param {Date} [initialMonth]  Mois initialement affiché (défaut : mois courant).
 * @param {(cell) => ReactNode} renderCell  Contenu d'une cellule jour.
 * @param {ReactNode} [headerExtra]  Outils additionnels dans l'en-tête (droite).
 * @param {(monthStart: Date) => void} [onMonthChange]  Notifié à chaque navigation.
 */
export default function MonthGrid({ initialMonth, renderCell, headerExtra, onMonthChange }) {
  const [monthStart, setMonthStart] = useState(() => {
    if (initialMonth) return new Date(initialMonth.getFullYear(), initialMonth.getMonth(), 1)
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })

  const setMonth = (next) => {
    setMonthStart(next)
    onMonthChange?.(next)
  }
  const goMonth = (delta) =>
    setMonth(new Date(monthStart.getFullYear(), monthStart.getMonth() + delta, 1))
  const goToday = () => {
    const now = new Date()
    setMonth(new Date(now.getFullYear(), now.getMonth(), 1))
  }

  const title = monthTitle(monthStart)

  // Grille : semaines complètes (lundi → dimanche), jours voisins inclus.
  const cells = useMemo(() => {
    const year = monthStart.getFullYear()
    const month = monthStart.getMonth()
    const mondayOffset = (monthStart.getDay() + 6) % 7 // lundi = 0
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const total = Math.ceil((mondayOffset + daysInMonth) / 7) * 7
    const now = new Date()
    const todayKey = localKey(now.getFullYear(), now.getMonth() + 1, now.getDate())
    const out = []
    for (let i = 0; i < total; i += 1) {
      const date = new Date(year, month, 1 - mondayOffset + i)
      const key = localKey(date.getFullYear(), date.getMonth() + 1, date.getDate())
      out.push({
        key,
        date,
        dayNumber: date.getDate(),
        inMonth: date.getMonth() === month,
        isToday: key === todayKey,
      })
    }
    return out
  }, [monthStart])

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
          {headerExtra}
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
        {cells.map((cell) => renderCell(cell))}
      </div>
    </div>
  )
}
