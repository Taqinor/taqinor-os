import {
  Download, Plus, FileText, Search, AlertTriangle, Printer, LayoutList, LayoutGrid,
} from 'lucide-react'
import {
  Button, StatusPill, Spinner,
  // APX12 — le langage UNIQUE des KPI d'argent.
  Stat,
  Input, Segmented,
} from '../../../ui/index.js'
import { formatMAD } from '../../../lib/format.js'
import { downloadBlobInGesture } from '../../../utils/downloadBlob.js'
import ViewsManagerPopover from '../../../features/uxviews/ViewsManagerPopover'
import importApi from '../../../api/importApi.js'
// APX11 — l'en-tête UNIQUE de l'app (VX28) remplace l'idiome legacy.
import { PageHeader } from '../../../ui/PageHeader'
// APX11 — identité Ventes : accent brass posé sur l'en-tête des écrans de flux.
import { VENTES_ACCENT_STYLE } from '../../../features/ventes/accent.js'
import { STATUT_DEVIS_FILTRES } from '../../../features/ventes/devisStatuts.js'
import { STATUT_DISPLAY, DL_ECRAN } from './devisListConstants.js'

// SPL206 — en-tête de page de la liste des devis (titre + actions, synthèse
// KPI T6, T16, T15, filtres T5, barre de lot T7), déplacé VERBATIM de
// DevisList.jsx (move only). L'état (statutFilter, query, showSuperseded,
// viewMode, selectedIds) RESTE dans DevisList.jsx et arrive en props NOMMÉES.

// Filtres segmentés (statut) : « Tous » + les 5 statuts visibles.
const STATUT_FILTERS = STATUT_DEVIS_FILTRES

export function DevisPageHeader({
  devis,
  expiringSoon,
  loading,
  error,
  xlsxBusy,
  setXlsxBusy,
  openNew,
}) {
  return (
    <PageHeader
      style={VENTES_ACCENT_STYLE}
      className="app-accent-rail"
      icon={FileText}
      title="Devis"
      subtitle={
        expiringSoon.length > 0
          ? `${devis.length} devis · ${expiringSoon.length} à relancer (validité ≤ 7 jours)`
          : `${devis.length} devis`
      }
      actions={(
        <>
          <Button size="sm" variant="outline" disabled={loading || !!error || xlsxBusy}
                  onClick={() => {
                    const pending = downloadBlobInGesture()
                    setXlsxBusy(true)
                    importApi.exportList('devis', devis.map(d => d.id))
                      .then(r => pending.deliver(r.data, 'devis.xlsx'))
                      .catch(() => {})
                      .finally(() => setXlsxBusy(false))
                  }}>
            {xlsxBusy ? <Spinner /> : <Download />} Exporter Excel
          </Button>
          {/* VX80 — impression navigateur (feuille print.css : chrome masqué,
              noir-sur-blanc, table complète). Distinct des PDF WeasyPrint. */}
          <Button size="sm" variant="outline" onClick={() => window.print()}>
            <Printer /> Imprimer
          </Button>
          <Button onClick={openNew}><Plus /> Nouveau devis</Button>
        </>
      )}
    />
  )
}

export default function DevisListChrome({
  devis,
  summary,
  batteryInsight,
  expiringSoon,
  statutFilter,
  setStatutFilter,
  query,
  setQuery,
  saveCurrentDevisView,
  applyDevisView,
  supersededCount,
  showSuperseded,
  setShowSuperseded,
  viewMode,
  setViewMode,
  selectedIds,
  setSelectedIds,
  openBatchPdfModal,
}) {
  return (
    <>
    {/* ── T6 — Résumé par statut (nombre + total TTC des devis chargés) ──
        APX12 — les 5 cartes étaient des `<div>` nus : elles passent au
        langage UNIQUE des KPI d'argent (`<Stat>`, chiffres `.num`
        tabulaires), comme le cockpit trésorerie et le rail du générateur. */}
    {devis.length > 0 && (
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {Object.keys(STATUT_DISPLAY).map(key => (
          <Stat
            key={key}
            className="p-3 sm:p-3"
            label={(
              // `normal-case` : le libellé de Stat est en majuscules, la
              // pastille de statut garde sa casse d'origine (« Brouillon »).
              <StatusPill status={key} label={STATUT_DISPLAY[key]} className="normal-case tracking-normal" />
            )}
            value={summary[key]?.count ?? 0}
            hint={formatMAD(summary[key]?.total ?? 0)}
          />
        ))}
      </div>
    )}

    {/* ── T16 — Répartition batterie sur les devis acceptés ── */}
    {(batteryInsight.avec > 0 || batteryInsight.sans > 0) && (
      <p className="mt-2 text-xs text-muted-foreground">
        Devis acceptés — option choisie :{' '}
        <span className="font-medium text-success">{batteryInsight.avec} avec batterie</span>
        {' · '}
        <span className="font-medium text-foreground">{batteryInsight.sans} sans batterie</span>
      </p>
    )}

    {/* ── T15 — Rappel : devis envoyés expirant dans ≤ 7 jours ── */}
    {expiringSoon.length > 0 && (
      <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          <strong>{expiringSoon.length} devis expirant bientôt</strong> (validité ≤ 7 jours) :{' '}
          {expiringSoon.map(d => d.reference).join(', ')}.
        </div>
      </div>
    )}

    {/* ── T5 — Filtre statut + recherche (référence / client) ── */}
    {devis.length > 0 && (
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Segmented
          options={STATUT_FILTERS}
          value={statutFilter}
          onChange={setStatutFilter}
          size="sm"
        />
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            type="search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Rechercher (référence ou client)…"
            className="pl-8 sm:w-64"
            aria-label="Rechercher un devis"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <Button type="button" variant="link" size="sm" onClick={saveCurrentDevisView}>
            ⭐ Enregistrer cette vue
          </Button>
          <ViewsManagerPopover ecran={DL_ECRAN} onApply={applyDevisView} />
        </div>
        {/* U7 — bascule pour réafficher les révisions remplacées (masquées
            par défaut). N'apparaît que s'il y en a au moins une. */}
        {supersededCount > 0 && (
          <Button type="button" variant="link" size="sm"
                  onClick={() => setShowSuperseded(s => !s)}>
            {showSuperseded
              ? `Masquer les versions remplacées (${supersededCount})`
              : `Voir les versions remplacées (${supersededCount})`}
          </Button>
        )}
        {/* APX15(b) — bascule Liste/Board, parité exacte avec celle des
            factures (ZFAC9). Le board consomme `filteredDevis`, déjà en
            mémoire : aucune donnée nouvelle, aucun appel réseau. */}
        <div className="ml-auto flex items-center gap-1 rounded-md border border-border p-0.5"
             role="group" aria-label="Mode d’affichage">
          <Button
            type="button" size="sm"
            variant={viewMode === 'liste' ? 'secondary' : 'ghost'}
            aria-pressed={viewMode === 'liste'}
            onClick={() => setViewMode('liste')}
          >
            <LayoutList className="size-4" aria-hidden="true" /> Liste
          </Button>
          <Button
            type="button" size="sm"
            variant={viewMode === 'board' ? 'secondary' : 'ghost'}
            aria-pressed={viewMode === 'board'}
            onClick={() => setViewMode('board')}
          >
            <LayoutGrid className="size-4" aria-hidden="true" /> Board
          </Button>
        </div>
      </div>
    )}

    {/* ── T7 — Barre d'action du lot sélectionné ── */}
    {selectedIds.length > 0 && (
      <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-2 text-sm">
        <span className="font-medium">{selectedIds.length} devis sélectionné(s)</span>
        <Button size="sm" onClick={openBatchPdfModal}>
          <FileText /> Générer les PDF
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setSelectedIds([])}>
          Effacer la sélection
        </Button>
      </div>
    )}
    </>
  )
}
