import { useEffect, useState } from 'react'
import { Label } from '../../../ui'
import gestionProjetApi from '../../../api/gestionProjetApi'

/* UX39–UX42 — Sélecteur de projet partagé (charge la liste des projets une
   fois, <select> natif). `value` = id projet (chaîne), `onChange(id)`. */

export default function ProjetPicker({ value, onChange, label = 'Projet' }) {
  const [projets, setProjets] = useState([])

  useEffect(() => {
    let alive = true
    gestionProjetApi.getProjets()
      .then((res) => {
        if (!alive) return
        setProjets(Array.isArray(res.data) ? res.data : res.data?.results ?? [])
      })
      .catch(() => {})
    return () => { alive = false }
  }, [])

  return (
    <div className="flex flex-col gap-1">
      {label && <Label htmlFor="gp-projet-picker">{label}</Label>}
      <select
        id="gp-projet-picker"
        className="h-9 min-w-56 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        value={value ?? ''}
        onChange={(e) => onChange?.(e.target.value)}
      >
        <option value="">— Choisir un projet —</option>
        {projets.map((p) => (
          <option key={p.id} value={p.id}>
            {p.code ? `${p.code} · ` : ''}{p.nom}
          </option>
        ))}
      </select>
    </div>
  )
}
