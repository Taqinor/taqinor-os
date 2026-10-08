// VX233 — Journal des modifications de paramètres (audit N55, lecture seule),
// EXTRAIT en composant paramétrable par section.
//   • sans prop `section` : filtre dynamique alimenté par l'endpoint
//     `audit/sections/` (≥ 6 sections réelles, dont « tarification ») au lieu
//     d'un <Select> à 2 options codées en dur.
//   • avec prop `section` : le feed est VERROUILLÉ sur cette section (aucun
//     filtre affiché) — utilisé par « Voir l'historique » sur TarificationSection.
import { useEffect, useState } from 'react'
import parametresApi from '../../api/parametresApi'
import { formatDateTime } from '../../lib/format'
import {
  Badge, Button, EmptyState, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

const ALL = '__all__'

const fmtVal = (v) => (v === null || v === undefined || v === ''
  ? '—'
  : (typeof v === 'object' ? JSON.stringify(v) : String(v)))

// VX234 — diff structuré des permissions (JSON { ajoutees, retirees }) vs texte
// brut historique : on tente un parse et on retombe sur le rendu texte.
const parsePermsDiff = (v) => {
  if (typeof v !== 'string' || !v) return null
  try {
    const parsed = JSON.parse(v)
    if (parsed && typeof parsed === 'object'
        && (Array.isArray(parsed.ajoutees) || Array.isArray(parsed.retirees))) {
      return parsed
    }
  } catch { /* pas du JSON — valeur texte brute historique */ }
  return null
}

export default function SettingsAuditFeed({ section = null, limit = 50, className = '' }) {
  const locked = Boolean(section)
  const [audit, setAudit] = useState(null) // null = pas encore chargé
  const [loading, setLoading] = useState(false)
  const [sections, setSections] = useState([]) // [{ value, label }]
  const [filter, setFilter] = useState(locked ? section : ALL)

  // Sections réellement disponibles (mode filtrable uniquement).
  useEffect(() => {
    if (locked) return
    parametresApi.getAuditSections()
      .then(r => setSections(r.data?.sections ?? []))
      .catch(() => setSections([]))
  }, [locked])

  // APAR32 — pagination serveur : `next` = offset de la page suivante (null
  // en fin de journal) ; « Charger plus » ajoute la page suivante.
  const [next, setNext] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const paramsFor = (offset) => {
    const sec = locked ? section : filter
    const params = { limit, offset }
    if (sec && sec !== ALL) params.section = sec
    return params
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    const sec = locked ? section : filter
    const params = { limit, offset: 0 }
    if (sec && sec !== ALL) params.section = sec
    parametresApi.getAudit(params)
      .then(r => {
        setAudit(r.data.results ?? r.data)
        setNext(r.data?.next ?? null)
      })
      .catch(() => { setAudit([]); setNext(null) })
      .finally(() => setLoading(false))
  }, [locked, section, filter, limit])

  const chargerPlus = () => {
    if (next == null) return
    setLoadingMore(true)
    parametresApi.getAudit(paramsFor(next))
      .then(r => {
        setAudit(prev => [...(prev ?? []), ...(r.data.results ?? [])])
        setNext(r.data?.next ?? null)
      })
      .catch(() => setNext(null))
      .finally(() => setLoadingMore(false))
  }

  return (
    <div className={className}>
      {!locked && (
        <div className="mb-3 w-[220px]">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Toutes les sections</SelectItem>
              {sections.map(s => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {loading ? (
        <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </div>
      ) : (audit && audit.length === 0) ? (
        <EmptyState title="Aucune modification"
          description="Les changements de paramètres apparaîtront ici." className="py-6" />
      ) : (
        <div className="flex flex-col gap-1.5">
          {(audit ?? []).map(row => {
            const diff = parsePermsDiff(row.new_value)
            return (
              <div key={row.id} className="rounded-md border border-border px-3 py-2 text-[12px]">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className="font-medium text-foreground">
                    {row.field_label || row.field}
                  </span>
                  <Badge tone="neutral">{row.section}</Badge>
                  <span className="ml-auto text-[11px] text-muted-foreground">
                    {row.user_nom || '—'} · {formatDateTime(row.timestamp)}
                  </span>
                </div>
                {diff ? (
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    {(diff.ajoutees ?? []).map(code => (
                      <Badge key={`+${code}`} tone="success">+{code}</Badge>
                    ))}
                    {(diff.retirees ?? []).map(code => (
                      <Badge key={`-${code}`} tone="danger">-{code}</Badge>
                    ))}
                    {(diff.ajoutees ?? []).length === 0 && (diff.retirees ?? []).length === 0 && (
                      <span className="text-[11.5px] text-muted-foreground">Aucun changement de permission.</span>
                    )}
                  </div>
                ) : (
                  <div className="mt-0.5 text-[11.5px] text-muted-foreground">
                    <span className="line-through">{fmtVal(row.old_value)}</span>
                    {' → '}
                    <span className="text-foreground">{fmtVal(row.new_value)}</span>
                  </div>
                )}
              </div>
            )
          })}
          {next != null && (
            <Button type="button" variant="outline" size="sm" className="self-start"
              loading={loadingMore} disabled={loadingMore} onClick={chargerPlus}>
              Charger plus
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
