// Édition « en place » (Odoo-style) d'UN champ dans une liste, sans ouvrir la
// fiche. Click → input/select/date ; Entrée ou perte de focus → enregistre ce
// seul champ via onSave(value) (qui renvoie une promesse) ; Échap → annule.
// La validation reste SERVEUR : si onSave rejette, on restaure l'ancienne
// valeur et on affiche le message. Présentation pure et réutilisable.
import { useEffect, useRef, useState } from 'react'

export default function InlineEdit({
  value, type = 'text', options = null, display = null,
  onSave, disabled = false, placeholder = '—', align = 'left',
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(false)
  const ref = useRef(null)
  // VX164 — verrou de RÉ-ENTRANCE (pas seulement d'affichage — `saving` ne
  // pilote que le rendu et n'empêche rien) : Enter appelle `commit()` PUIS
  // sort du mode édition, ce qui démonte l'input et déclenche un `blur`
  // NATIF (retrait d'un élément focalisé) qui rappelle CE MÊME `commit` une
  // seconde fois avant que `saving` (état React, asynchrone) n'ait pu se
  // propager — Enter+blur synchrone déclenchait donc deux `onSave`.
  const committingRef = useRef(false)

  // On capte la valeur courante AU MOMENT d'entrer en édition (pas via un
  // effet) — évite tout rendu en cascade et garde le brouillon isolé.
  const startEdit = () => { setDraft(value ?? ''); setEditing(true) }

  useEffect(() => { if (editing && ref.current) ref.current.focus() }, [editing])

  const shown = display != null
    ? display
    : (options
      ? (options.find((o) => String(o.value) === String(value))?.label ?? value)
      : value)

  const commit = async () => {
    // VX164 — verrou EN TÊTE : un second appel (blur déclenché par le
    // démontage de l'input juste en dessous) est un no-op immédiat.
    if (committingRef.current) return
    committingRef.current = true
    setEditing(false)
    const next = draft === '' ? null : draft
    if (String(next ?? '') === String(value ?? '')) {
      committingRef.current = false
      return // rien changé
    }
    setSaving(true)
    setErr(false)
    try {
      await onSave(next)
    } catch {
      // ERR105 — Échec d'enregistrement : on est déjà sorti du mode édition, donc
      // l'affichage repasse sur `shown` (dérivé de la prop `value` = valeur
      // serveur), ce qui restaure bien l'ancienne valeur. On ne touche PAS à
      // `draft` ici (état mort hors édition) : `startEdit` le ré-initialisera
      // depuis `value` à la prochaine entrée en édition.
      setErr(true)
    } finally {
      setSaving(false)
      committingRef.current = false
    }
  }

  if (disabled) {
    return <span className={`ie-display ie-${align}`}>{shown || placeholder}</span>
  }

  if (!editing) {
    return (
      <button
        type="button"
        className={`ie-cell ie-${align}${err ? ' ie-err' : ''}${saving ? ' ie-saving' : ''}`}
        title={err ? 'Échec de l’enregistrement — réessayez' : 'Cliquer pour modifier'}
        onClick={(e) => { e.stopPropagation(); startEdit() }}
      >
        {saving ? '…' : (shown || <span className="ie-placeholder">{placeholder}</span>)}
      </button>
    )
  }

  const stop = (e) => e.stopPropagation()
  const onKey = (e) => {
    if (e.key === 'Enter' && type !== 'textarea') { e.preventDefault(); commit() }
    if (e.key === 'Escape') { e.preventDefault(); setDraft(value ?? ''); setEditing(false) }
  }

  if (options) {
    return (
      <select
        ref={ref} className="form-control ie-input" value={draft ?? ''}
        onClick={stop} onChange={(e) => setDraft(e.target.value)}
        onBlur={commit} onKeyDown={onKey}
      >
        {options.map((o) => (
          <option key={String(o.value)} value={o.value ?? ''}>{o.label}</option>
        ))}
      </select>
    )
  }

  return (
    <input
      ref={ref} className="form-control ie-input"
      type={type === 'number' ? 'number' : type === 'date' ? 'date' : 'text'}
      step={type === 'number' ? 'any' : undefined}
      value={draft ?? ''} onClick={stop}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit} onKeyDown={onKey}
    />
  )
}
