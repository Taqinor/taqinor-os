import { useMemo } from 'react'
import { Search } from 'lucide-react'
import {
  EMPTY_FILTERS,
  CANAL_LABELS,
  PRIORITE_LABELS,
  STAGE_LABELS,
  PIPELINE_STAGES,
  TYPE_INSTALLATION_LABELS,
  tagList,
} from '../../../features/crm/stages'
import {
  Input, Button, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'

// Sentinelle « tous » : Radix Select interdit la valeur chaîne vide, donc on
// mappe "" (= aucun filtre) vers cette clé interne, transparente côté état.
const ALL = '__all'
const toSel = (v) => (v ? v : ALL)
const fromSel = (v) => (v === ALL ? '' : v)

// Barre de recherche/filtres partagée par les quatre vues (façon Odoo).
// `leads` = liste NON filtrée, pour dériver les options disponibles.
export default function FilterBar({ filters, setFilters, leads }) {
  const owners = useMemo(() => {
    const set = new Set()
    for (const l of leads ?? []) {
      if (l.owner_nom) set.add(l.owner_nom)
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'fr'))
  }, [leads])

  const tags = useMemo(() => {
    const set = new Set()
    for (const l of leads ?? []) {
      for (const t of tagList(l)) set.add(t)
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'fr'))
  }, [leads])

  const setKey = (key) => (value) => setFilters({ ...filters, [key]: value })
  const setPerdus = (value) => setFilters({ ...filters, perdus: value })
  const setArchived = (value) => setFilters({ ...filters, archived: value })

  const isDirty = Object.keys(EMPTY_FILTERS).some(k => filters[k] !== EMPTY_FILTERS[k])

  return (
    <div className="fb-bar">
      <div className="fb-search">
        <Input
          type="search"
          leading={<Search />}
          placeholder="Rechercher nom, téléphone, email…"
          value={filters.q}
          onChange={(e) => setFilters({ ...filters, q: e.target.value })}
        />
      </div>

      <Select value={toSel(filters.stage)} onValueChange={(v) => setKey('stage')(fromSel(v))}>
        <SelectTrigger className="fb-select" aria-label="Filtrer par étape">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Toutes les étapes</SelectItem>
          {PIPELINE_STAGES.map((k) => (
            <SelectItem key={k} value={k}>{STAGE_LABELS[k] ?? k}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={toSel(filters.type_installation)}
        onValueChange={(v) => setKey('type_installation')(fromSel(v))}
      >
        <SelectTrigger className="fb-select" aria-label="Filtrer par type d'installation">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les marchés</SelectItem>
          {Object.entries(TYPE_INSTALLATION_LABELS).map(([k, v]) => (
            <SelectItem key={k} value={k}>{v}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={toSel(filters.canal)} onValueChange={(v) => setKey('canal')(fromSel(v))}>
        <SelectTrigger className="fb-select" aria-label="Filtrer par canal">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les canaux</SelectItem>
          {Object.entries(CANAL_LABELS).map(([k, v]) => (
            <SelectItem key={k} value={k}>{v}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={toSel(filters.owner)} onValueChange={(v) => setKey('owner')(fromSel(v))}>
        <SelectTrigger className="fb-select" aria-label="Filtrer par responsable">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les responsables</SelectItem>
          {owners.map(o => (
            <SelectItem key={o} value={o}>{o}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={toSel(filters.priorite)} onValueChange={(v) => setKey('priorite')(fromSel(v))}>
        <SelectTrigger className="fb-select" aria-label="Filtrer par priorité">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Toutes priorités</SelectItem>
          {Object.entries(PRIORITE_LABELS).map(([k, v]) => (
            <SelectItem key={k} value={k}>{v}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={toSel(filters.tag)} onValueChange={(v) => setKey('tag')(fromSel(v))}>
        <SelectTrigger className="fb-select" aria-label="Filtrer par tag">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les tags</SelectItem>
          {tags.map(t => (
            <SelectItem key={t} value={t}>{t}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Segmented
        size="sm"
        aria-label="Filtre relance"
        value={filters.relance || ''}
        onChange={setKey('relance')}
        options={[
          { value: '', label: 'Toutes relances' },
          { value: 'retard', label: 'En retard' },
          { value: 'semaine', label: 'Cette semaine' },
        ]}
      />

      <Segmented
        size="sm"
        aria-label="Filtre leads perdus"
        value={filters.perdus}
        onChange={setPerdus}
        options={[
          { value: 'avec', label: 'Avec perdus' },
          { value: 'sans', label: 'Sans perdus' },
          { value: 'seuls', label: 'Perdus seuls' },
        ]}
      />

      <Segmented
        size="sm"
        aria-label="Filtre leads archivés"
        value={filters.archived ?? 'actifs'}
        onChange={setArchived}
        options={[
          { value: 'actifs', label: 'Actifs' },
          { value: 'tous', label: 'Tous' },
          { value: 'seuls', label: 'Archivés' },
        ]}
      />

      {isDirty && (
        <Button
          type="button"
          variant="link"
          size="sm"
          className="fb-clear"
          onClick={() => setFilters(EMPTY_FILTERS)}
        >
          Effacer les filtres
        </Button>
      )}
    </div>
  )
}
