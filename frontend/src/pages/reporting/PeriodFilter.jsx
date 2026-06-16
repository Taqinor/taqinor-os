import { useState } from 'react'

// Filtre de période partagé par les rapports. Émet { annee, mois?, trimestre? }
// (ou {} pour « toutes périodes ») au parent via onChange/onApply.
const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

export default function PeriodFilter({ onApply }) {
  const now = new Date()
  const [mode, setMode] = useState('annee') // 'tout' | 'annee' | 'mois' | 'trimestre'
  const [annee, setAnnee] = useState(now.getFullYear())
  const [mois, setMois] = useState(now.getMonth() + 1)
  const [trimestre, setTrimestre] = useState(Math.floor(now.getMonth() / 3) + 1)

  const buildParams = () => {
    if (mode === 'tout') return {}
    const p = { annee }
    if (mode === 'mois') p.mois = mois
    if (mode === 'trimestre') p.trimestre = trimestre
    return p
  }

  const apply = () => onApply?.(buildParams())

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
      background: '#fff', padding: '0.75rem 1rem', borderRadius: 12,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)', marginBottom: '1.25rem',
    }}>
      <span style={{ fontSize: 13, color: '#64748b', fontWeight: 600 }}>Période</span>
      <select value={mode} onChange={e => setMode(e.target.value)}
        style={selStyle}>
        <option value="tout">Toutes périodes</option>
        <option value="annee">Année</option>
        <option value="trimestre">Trimestre</option>
        <option value="mois">Mois</option>
      </select>
      {mode !== 'tout' && (
        <input type="number" value={annee}
          onChange={e => setAnnee(Number(e.target.value))}
          style={{ ...selStyle, width: 90 }} />
      )}
      {mode === 'mois' && (
        <select value={mois} onChange={e => setMois(Number(e.target.value))}
          style={selStyle}>
          {MOIS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
      )}
      {mode === 'trimestre' && (
        <select value={trimestre}
          onChange={e => setTrimestre(Number(e.target.value))}
          style={selStyle}>
          {[1, 2, 3, 4].map(t => <option key={t} value={t}>T{t}</option>)}
        </select>
      )}
      <button className="btn btn-sm" onClick={apply}>Appliquer</button>
    </div>
  )
}

const selStyle = {
  padding: '0.4rem 0.6rem', borderRadius: 8, border: '1px solid #e2e8f0',
  fontSize: 13, background: '#fff', color: '#0f172a',
}
