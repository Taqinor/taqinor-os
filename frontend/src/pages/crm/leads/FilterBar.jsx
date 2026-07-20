import { useEffect, useMemo, useState } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import {
  EMPTY_FILTERS,
  PRIORITE_LABELS,
  STAGE_LABELS,
  PIPELINE_STAGES,
  TYPE_INSTALLATION_LABELS,
  tagList,
} from '../../../features/crm/stages'
import useCanaux from '../../../features/crm/useCanaux'
import {
  Input, Button, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Popover, PopoverTrigger, PopoverContent,
} from '../../../ui'

// Sentinelle « tous » : Radix Select interdit la valeur chaîne vide, donc on
// mappe "" (= aucun filtre) vers cette clé interne, transparente côté état.
const ALL = '__all'
const toSel = (v) => (v ? v : ALL)
const fromSel = (v) => (v === ALL ? '' : v)

const RELANCE_LABELS = {
  aujourdhui: "Aujourd'hui",
  retard: 'En retard',
  semaine: 'Cette semaine',
}

// Barre de recherche/filtres partagée par les quatre vues — LB43 (retour
// fondateur) : anatomie Odoo 17 vérifiée à la source (SearchBar +
// SearchBarMenu). UNE ligne : recherche → « facettes » des filtres actifs
// (chip par dimension, ✕ pour la retirer) → chips fréquentes → UN SEUL
// bouton « Filtres ▾ » (Popover) portant TOUTES les dimensions — plus
// jamais 9 selects étalés sur plusieurs rangées.
// `leads` = liste NON filtrée, pour dériver les options disponibles.
export default function FilterBar({ filters, setFilters, leads }) {
  // LB23 — recherche débouncée (blueprint D5/I7) : l'input reste un état
  // LOCAL (frappe instantanée, jamais bloquée) qui ne pousse `setFilters`
  // qu'après 250ms de pause — combiné à LB6 (viewProps mémoïsé), une frappe
  // ne recalcule/re-rend plus aucune carte tant que l'utilisatrice tape.
  // `useDeferredValue` (LeadsPage.jsx, VX187) reste un second étage : lui
  // absorbe le coût du RECALCUL une fois `filters.q` mis à jour.
  const [searchLocal, setSearchLocal] = useState(filters.q)
  // Resynchronise l'input quand `filters.q` change depuis L'EXTÉRIEUR
  // (« Effacer les filtres », vue enregistrée appliquée, URL collée — LB22) :
  // motif « adjust state during render » (lint v7 interdit le setState
  // synchrone en effet) — même pattern que SectionContact/ContextRail.
  const [prevQ, setPrevQ] = useState(filters.q)
  if (prevQ !== filters.q) {
    setPrevQ(filters.q)
    setSearchLocal(filters.q)
  }
  useEffect(() => {
    if (searchLocal === filters.q) return undefined
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: searchLocal })), 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne réagit qu'à la frappe locale, `filters`/`setFilters` lus au déclenchement
  }, [searchLocal])

  // Libellés de canaux depuis le référentiel géré (Paramètres → CRM) + statiques.
  const { options: canalOptions } = useCanaux()
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

  // VX223 — chip « Rappels demandés » : le signal le plus chaud
  // (`contact_preference==='phone_ok'`, badge passif sur LeadCard), toujours
  // visible — jamais replié derrière « Filtres ».
  const rappelsActifs = filters.contact_preference === 'phone_ok'
  const toggleRappels = () => setKey('contact_preference')(rappelsActifs ? '' : 'phone_ok')

  // VX224 — chip « Mes leads » : défaut ON pour le rôle `normal` (posé une
  // seule fois par LeadsPage.jsx à l'ouverture initiale, jamais ici).
  const mesLeadsActif = !!filters.mesLeads
  const toggleMesLeads = () => setKey('mesLeads')(!mesLeadsActif)

  const isDirty = Object.keys(EMPTY_FILTERS).some(k => filters[k] !== EMPTY_FILTERS[k])

  const [open, setOpen] = useState(false)
  // Nombre de filtres actifs (hors recherche libre) — pastille sur le bouton.
  const activeCount = Object.keys(EMPTY_FILTERS)
    .filter((k) => k !== 'q' && filters[k] !== EMPTY_FILTERS[k]).length

  // LB43 — facettes Odoo : une chip « Dimension : valeur ✕ » par filtre actif,
  // dans la barre même (web.SearchBar.Facets). Exclues : `q` (déjà dans
  // l'input) et les dimensions portées par une chip dédiée toujours visible
  // (mesLeads ; contact_preference quand c'est le mode « ☎ Rappels »).
  const facets = []
  if (filters.stage) facets.push({ key: 'stage', dim: 'Étape', label: STAGE_LABELS[filters.stage] ?? filters.stage })
  if (filters.type_installation) facets.push({ key: 'type_installation', dim: 'Marché', label: TYPE_INSTALLATION_LABELS[filters.type_installation] ?? filters.type_installation })
  if (filters.canal) facets.push({ key: 'canal', dim: 'Canal', label: canalOptions.find((o) => o.value === filters.canal)?.label ?? filters.canal })
  if (filters.contact_preference === 'whatsapp_only') facets.push({ key: 'contact_preference', dim: 'Contact', label: 'WhatsApp uniquement' })
  if (filters.owner) facets.push({ key: 'owner', dim: 'Responsable', label: filters.owner })
  if (filters.priorite) facets.push({ key: 'priorite', dim: 'Priorité', label: PRIORITE_LABELS[filters.priorite] ?? filters.priorite })
  if (filters.tag) facets.push({ key: 'tag', dim: 'Tag', label: filters.tag })
  if (filters.relance) facets.push({ key: 'relance', dim: 'Relance', label: RELANCE_LABELS[filters.relance] ?? filters.relance })
  if (filters.perdus !== EMPTY_FILTERS.perdus) facets.push({ key: 'perdus', dim: 'Perdus', label: filters.perdus === 'sans' ? 'Sans' : 'Seuls' })
  if ((filters.archived ?? 'actifs') !== EMPTY_FILTERS.archived) facets.push({ key: 'archived', dim: 'Archivés', label: filters.archived === 'tous' ? 'Inclus' : 'Seuls' })

  return (
    <div className="fb-bar">
      <div className="fb-search">
        <Input
          type="search"
          leading={<Search />}
          placeholder="Rechercher nom, téléphone, email…"
          value={searchLocal}
          onChange={(e) => setSearchLocal(e.target.value)}
        />
      </div>

      {/* LB43 — l'unique panneau de dimensions (Odoo SearchBarMenu) : le même
          Popover partout (desktop ET mobile) — plus de gabarit qui étale les
          selects en rangées. */}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-expanded={open}
          >
            <SlidersHorizontal /> Filtres
            {activeCount > 0 && <span className="count-badge">{activeCount}</span>}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="fb-panel w-80">
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
          {canalOptions.map(({ value, label }) => (
            <SelectItem key={value} value={value}>{label}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={toSel(filters.contact_preference)}
        onValueChange={(v) => setKey('contact_preference')(fromSel(v))}
      >
        <SelectTrigger className="fb-select" aria-label="Filtrer par préférence de contact">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Toute préférence de contact</SelectItem>
          <SelectItem value="phone_ok">☎ Rappel demandé</SelectItem>
          <SelectItem value="whatsapp_only">WhatsApp uniquement</SelectItem>
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

      {/* LB24 — le Segmented relance gagne « Aujourd'hui » (miroir de la
          tuile KPI « Dû aujourd'hui », même clé de filtre — un seul état de
          filtres, KPI et FilterBar restent parfaitement synchronisés). */}
      <Segmented
        size="sm"
        aria-label="Filtre relance"
        value={filters.relance || ''}
        onChange={setKey('relance')}
        options={[
          { value: '', label: 'Toutes relances' },
          { value: 'aujourdhui', label: "Aujourd'hui" },
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
        </PopoverContent>
      </Popover>

      {facets.map((f) => (
        <span key={f.key} className="fb-facet">
          <span className="fb-facet-dim">{f.dim}</span>
          <span className="fb-facet-val">{f.label}</span>
          <button
            type="button"
            className="fb-facet-x"
            aria-label={`Retirer le filtre ${f.dim} : ${f.label}`}
            onClick={() => setKey(f.key)(EMPTY_FILTERS[f.key])}
          ><X aria-hidden="true" /></button>
        </span>
      ))}

      {/* VX224 — chip « Mes leads », toujours visible. */}
      <Button
        type="button"
        variant={mesLeadsActif ? 'default' : 'outline'}
        size="sm"
        className="fb-chip-mes-leads"
        aria-pressed={mesLeadsActif}
        onClick={toggleMesLeads}
      >
        Mes leads
      </Button>

      {/* VX223 — chip « Rappels demandés », toujours visible. */}
      <Button
        type="button"
        variant={rappelsActifs ? 'default' : 'outline'}
        size="sm"
        className="fb-chip-rappels"
        aria-pressed={rappelsActifs}
        onClick={toggleRappels}
      >
        ☎ Rappels demandés
      </Button>

    </div>
  )
}
