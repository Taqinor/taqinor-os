// NTUX3 — Filtres avancés composables ET/OU imbriqués (2 niveaux max).
// `<FilterBuilder columns={[{id,header,type}]} value={group} onChange={group} />`
// Le groupe racine (niveau 1) peut contenir des conditions ET des
// sous-groupes (niveau 2) ; un sous-groupe ne contient QUE des conditions
// (jamais de 3e niveau — bouton « + Groupe » masqué à l'intérieur).
import { Plus, X } from 'lucide-react'
import { Button, IconButton, Input, Segmented } from '..'
import {
  operatorsForType, emptyCondition, emptyGroup, isGroup, leafNeedsValue,
} from './filterLogic'
import { RELATIVE_DATE_PRESETS } from '../../lib/relativeDates'

function columnType(columns, fieldId) {
  return columns.find((c) => c.id === fieldId)?.type || 'text'
}

/** Éditeur de VALEUR d'une condition — dépend de l'opérateur ET du type de
 *  colonne (nombre/date « between » = deux champs, date « relative » = un
 *  select de presets NTUX4, `select`/`in` = texte liste séparée par virgule
 *  en repli minimal). */
function ValueEditor({ type, operator, value, onChange }) {
  if (!leafNeedsValue(operator)) return null
  if (operator === 'relative') {
    return (
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Période relative"
        className="h-8 rounded-md border border-input bg-card px-2 text-xs text-foreground focus-ring"
      >
        <option value="">Choisir une période…</option>
        {RELATIVE_DATE_PRESETS.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>
    )
  }
  if (operator === 'between') {
    const [min, max] = Array.isArray(value) ? value : ['', '']
    const inputType = type === 'date' ? 'date' : 'number'
    return (
      <div className="flex items-center gap-1">
        <Input
          type={inputType} value={min ?? ''} aria-label="Valeur minimum"
          onChange={(e) => onChange([e.target.value, max])}
          className="h-8 w-24 text-xs"
        />
        <span className="text-xs text-muted-foreground">et</span>
        <Input
          type={inputType} value={max ?? ''} aria-label="Valeur maximum"
          onChange={(e) => onChange([min, e.target.value])}
          className="h-8 w-24 text-xs"
        />
      </div>
    )
  }
  if (operator === 'in') {
    const list = Array.isArray(value) ? value.join(', ') : (value || '')
    return (
      <Input
        value={list} aria-label="Valeurs (séparées par des virgules)"
        onChange={(e) => onChange(e.target.value.split(',').map((v) => v.trim()).filter(Boolean))}
        placeholder="Envoyé, Relancé…" className="h-8 w-40 text-xs"
      />
    )
  }
  const inputType = type === 'number' ? 'number' : type === 'date' ? 'date' : 'text'
  return (
    <Input
      type={inputType} value={value ?? ''} aria-label="Valeur"
      onChange={(e) => onChange(e.target.value)}
      className="h-8 w-32 text-xs"
    />
  )
}

/** Une ligne de condition feuille : champ / opérateur / valeur / retirer. */
function ConditionRow({ columns, condition, onChange, onRemove }) {
  const type = columnType(columns, condition.field)
  const ops = operatorsForType(type)
  return (
    <div data-testid="fb-condition-row" className="flex flex-wrap items-center gap-1.5">
      <select
        value={condition.field}
        aria-label="Colonne"
        onChange={(e) => {
          const nextType = columnType(columns, e.target.value)
          onChange(emptyCondition(e.target.value, nextType))
        }}
        className="h-8 rounded-md border border-input bg-card px-2 text-xs text-foreground focus-ring"
      >
        {columns.map((c) => <option key={c.id} value={c.id}>{c.header ?? c.id}</option>)}
      </select>
      <select
        value={condition.operator}
        aria-label="Opérateur"
        onChange={(e) => onChange({ ...condition, operator: e.target.value, value: '' })}
        className="h-8 rounded-md border border-input bg-card px-2 text-xs text-foreground focus-ring"
      >
        {ops.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      <ValueEditor
        type={type} operator={condition.operator} value={condition.value}
        onChange={(value) => onChange({ ...condition, value })}
      />
      <IconButton label="Retirer cette condition" variant="ghost" size="icon" className="size-7" onClick={onRemove}>
        <X />
      </IconButton>
    </div>
  )
}

/** Un GROUPE (niveau 1 = racine, niveau 2 = sous-groupe imbriqué). */
function GroupEditor({ columns, group, onChange, onRemove, nested = false }) {
  const setOp = (op) => onChange({ ...group, op })
  const updateAt = (i, next) => {
    const conditions = group.conditions.slice()
    conditions[i] = next
    onChange({ ...group, conditions })
  }
  const removeAt = (i) => onChange({ ...group, conditions: group.conditions.filter((c1, idx) => idx !== i) })
  const addCondition = () => onChange({
    ...group, conditions: [...group.conditions, emptyCondition(columns[0]?.id, columns[0]?.type)],
  })
  const addGroup = () => onChange({ ...group, conditions: [...group.conditions, emptyGroup('OR')] })

  return (
    <div
      data-testid={nested ? 'fb-subgroup' : 'fb-root-group'}
      className={nested ? 'rounded-lg border border-dashed border-border p-2' : 'flex flex-col gap-2'}
    >
      <div className="flex items-center gap-2">
        <Segmented
          value={group.op}
          onChange={setOp}
          options={[{ value: 'AND', label: 'ET' }, { value: 'OR', label: 'OU' }]}
          aria-label="Opérateur du groupe"
        />
        {nested && (
          <IconButton label="Retirer ce groupe" variant="ghost" size="icon" className="size-7" onClick={onRemove}>
            <X />
          </IconButton>
        )}
      </div>
      <div className="flex flex-col gap-2 pl-1">
        {group.conditions.map((node, i) => (
          isGroup(node) ? (
            <GroupEditor
              key={i} columns={columns} group={node} nested
              onChange={(next) => updateAt(i, next)} onRemove={() => removeAt(i)}
            />
          ) : (
            <ConditionRow
              key={i} columns={columns} condition={node}
              onChange={(next) => updateAt(i, next)} onRemove={() => removeAt(i)}
            />
          )
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={addCondition}>
          <Plus /> Condition
        </Button>
        {/* 2 niveaux max : le bouton « + Groupe » n'existe qu'à la racine. */}
        {!nested && (
          <Button type="button" variant="outline" size="sm" onClick={addGroup}>
            <Plus /> Groupe (OU)
          </Button>
        )}
      </div>
    </div>
  )
}

export default function FilterBuilder({ columns = [], value, onChange }) {
  const group = value && isGroup(value) ? value : emptyGroup('AND')
  if (!columns.length) return null
  return (
    <div data-testid="filter-builder" className="rounded-xl border border-border bg-card p-3">
      <GroupEditor columns={columns} group={group} onChange={onChange} />
    </div>
  )
}
