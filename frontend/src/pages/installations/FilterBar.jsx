import { useMemo } from 'react'
import { Search } from 'lucide-react'
import {
  EMPTY_FILTERS,
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  TYPE_LABELS,
  REGIME_8221_LABELS,
} from '../../features/installations/statuses'
import {
  Input,
  Button,
  Segmented,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '../../ui'

// Barre de recherche/filtres partagée par les vues (façon Odoo), portée sur le
// système de design (J43) : champ de recherche, sélecteurs accessibles,
// segments « annulés », bascule Article 33. Comportement de filtrage identique.
// `items` = liste NON filtrée, pour dériver les techniciens disponibles.
//
// Les Select du système de design n'autorisent pas la valeur vide '' ; on
// utilise donc le sentinelle '__all__' pour « tous », mappé sur '' côté filtre.
const ALL = '__all__'
const toSel = (v) => (v ? v : ALL)
const fromSel = (v) => (v === ALL ? '' : v)

export default function FilterBar({ filters, setFilters, items }) {
  const techniciens = useMemo(() => {
    const set = new Set()
    for (const it of items ?? []) {
      if (it.technicien_nom) set.add(it.technicien_nom)
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'fr'))
  }, [items])

  const setKey = (key, value) => setFilters({ ...filters, [key]: value })
  const setAnnule = (value) => setFilters({ ...filters, annule: value })

  const isDirty = Object.keys(EMPTY_FILTERS).some((k) => filters[k] !== EMPTY_FILTERS[k])

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="min-w-[14rem] flex-1">
        <Input
          type="search"
          leading={<Search />}
          placeholder="Rechercher référence, client, ville…"
          value={filters.q}
          onChange={(e) => setKey('q', e.target.value)}
          aria-label="Rechercher un chantier"
        />
      </div>

      <Select value={toSel(filters.statut)} onValueChange={(v) => setKey('statut', fromSel(v))}>
        <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par statut">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les statuts</SelectItem>
          {INSTALLATION_STATUSES.map((k) => (
            <SelectItem key={k} value={k}>{STATUS_LABELS[k]}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={toSel(filters.type_installation)}
        onValueChange={(v) => setKey('type_installation', fromSel(v))}
      >
        <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par type d'installation">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les types</SelectItem>
          {Object.entries(TYPE_LABELS).map(([k, v]) => (
            <SelectItem key={k} value={k}>{v}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={toSel(filters.technicien)} onValueChange={(v) => setKey('technicien', fromSel(v))}>
        <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par technicien">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les techniciens</SelectItem>
          {techniciens.map((t) => (
            <SelectItem key={t} value={t}>{t}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={toSel(filters.regime)} onValueChange={(v) => setKey('regime', fromSel(v))}>
        <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par régime loi 82-21">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Tous les régimes</SelectItem>
          {Object.entries(REGIME_8221_LABELS).map(([k, v]) => (
            <SelectItem key={k} value={k}>{v}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        type="button"
        size="sm"
        variant={filters.art33 === 'seuls' ? 'default' : 'outline'}
        onClick={() => setKey('art33', filters.art33 === 'seuls' ? '' : 'seuls')}
        title="Régularisation Article 33"
        aria-pressed={filters.art33 === 'seuls'}
      >
        Art. 33
      </Button>

      <Segmented
        size="sm"
        value={filters.annule}
        onChange={setAnnule}
        aria-label="Filtre chantiers annulés"
        options={[
          { value: 'avec', label: 'Avec annulés' },
          { value: 'sans', label: 'Sans annulés' },
          { value: 'seuls', label: 'Annulés seuls' },
        ]}
      />

      {isDirty && (
        <Button type="button" size="sm" variant="ghost" onClick={() => setFilters(EMPTY_FILTERS)}>
          Effacer les filtres
        </Button>
      )}
    </div>
  )
}
