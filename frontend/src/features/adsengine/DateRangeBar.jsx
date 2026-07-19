import { Calendar } from 'lucide-react'
import { DATE_RANGE_PRESETS, presetRange } from './dateRange'

/* ============================================================================
   PUB40 — Barre de sélection de période, PARTAGÉE par les 4 écrans-données
   de la console (Dashboard/Cockpit/Campagnes/Journal).
   ----------------------------------------------------------------------------
   Composant CONTRÔLÉ : ``value = {preset, debut, fin, compare}``, chaque
   interaction appelle ``onChange(next)`` — l'écran appelant possède l'état et
   déclenche son propre re-fetch (même pattern que le reste de la console :
   pas de state ni d'appel réseau ici). Presets hier/7j/30j résolvent leurs
   dates immédiatement (`dateRange.presetRange`) ; « Personnalisé » laisse les
   deux champs de date à la saisie. La case « Comparer à la période
   précédente » n'a de sens qu'une fois ``debut``/``fin`` résolus — désactivée
   sinon (jamais un état incohérent envoyé au parent).
   ========================================================================== */

export default function DateRangeBar({ value, onChange }) {
  const { preset = '30j', debut = '', fin = '', compare = false } = value || {}
  const hasRange = !!(debut && fin)

  const selectPreset = (key) => {
    if (key === 'personnalise') {
      onChange({ preset: key, debut, fin, compare })
      return
    }
    const resolved = presetRange(key)
    onChange({ preset: key, debut: resolved.debut, fin: resolved.fin, compare })
  }

  const setCustomDebut = (e) => onChange({ preset: 'personnalise', debut: e.target.value, fin, compare })
  const setCustomFin = (e) => onChange({ preset: 'personnalise', debut, fin: e.target.value, compare })
  const toggleCompare = (e) => onChange({ preset, debut, fin, compare: e.target.checked })

  return (
    <div className="ae-daterange" data-testid="ae-daterange" role="group"
      aria-label="Sélecteur de période"
      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
        flexWrap: 'wrap', marginBottom: '1rem' }}>
      <Calendar size={16} aria-hidden="true" style={{ color: '#64748b' }} />
      {DATE_RANGE_PRESETS.map(p => (
        <button key={p.key} type="button"
          className={`btn ${preset === p.key ? 'btn-primary' : 'btn-light'}`}
          data-testid={`ae-daterange-preset-${p.key}`}
          aria-pressed={preset === p.key}
          onClick={() => selectPreset(p.key)}>
          {p.label}
        </button>
      ))}
      {preset === 'personnalise' && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          <input type="date" className="form-input" data-testid="ae-daterange-debut"
            value={debut} onChange={setCustomDebut} aria-label="Date de début" />
          <span aria-hidden="true">→</span>
          <input type="date" className="form-input" data-testid="ae-daterange-fin"
            value={fin} onChange={setCustomFin} aria-label="Date de fin" />
        </span>
      )}
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
        fontSize: '0.85rem', color: hasRange ? '#334155' : '#94a3b8', marginLeft: 'auto' }}>
        <input type="checkbox" data-testid="ae-daterange-compare"
          checked={!!compare} disabled={!hasRange} onChange={toggleCompare} />
        Comparer à la période précédente
      </label>
      {hasRange && (
        <span data-testid="ae-daterange-summary" style={{ fontSize: '0.8rem', color: '#64748b' }}>
          {debut === fin ? debut : `${debut} → ${fin}`}
        </span>
      )}
    </div>
  )
}
