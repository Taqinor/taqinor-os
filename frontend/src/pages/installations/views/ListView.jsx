// Vue LISTE des chantiers — moteur DataTable du système de design (J43).
// Le tri PAR DÉFAUT suit l'ordre d'entonnoir des statuts (jamais alphabétique) :
// la colonne « Statut » trie sur statusOrder() et la vue par défaut l'applique.
import { useMemo, useState } from 'react'
import { Eye, GitBranch, UserCog } from 'lucide-react'
import {
  statusLabel,
  statusOrder,
  isPoseEnRetard,
  canMoveStatus,
  INSTALLATION_STATUSES,
  STATUS_LABELS,
} from '../../../features/installations/statuses'
import {
  DataTable, StatusPill, Button, Badge,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../ui'
import { buildCopyTSVAction } from '../../../ui/datatable/BulkActionBar'
import { formatDate } from '../../../lib/format'
import importApi, { downloadXlsx } from '../../../api/importApi'

const NONE = '__none__'

// L10 — modale d'action groupée : choisir une valeur (statut ou installateur)
// appliquée à toutes les lignes sélectionnées. Chaque changement est journalisé
// côté serveur par updateInstallation. Pour le statut, seules les lignes dont le
// mouvement est autorisé (±1 pas sur l'entonnoir) sont modifiées ; les autres
// sont ignorées avec un décompte FR.
function BulkActionDialog({ kind, rows, users, onApply, onClose }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  const isStatut = kind === 'statut'
  const title = isStatut ? 'Changer le statut' : "Réassigner l'installateur"

  // Aperçu : combien de lignes seront effectivement modifiées (statut : gardes
  // d'adjacence ; installateur : toutes les lignes sélectionnées).
  const applicables = useMemo(() => {
    if (!isStatut) return rows.length
    if (!value) return 0
    return rows.filter((r) => canMoveStatus(r.statut, value)).length
  }, [isStatut, rows, value])
  const ignorees = isStatut && value ? rows.length - applicables : 0

  const apply = async () => {
    if (!value && isStatut) return
    setBusy(true)
    let done = 0
    for (const r of rows) {
      if (isStatut) {
        if (!canMoveStatus(r.statut, value)) continue
        await onApply(r, { statut: value })
      } else {
        const tech = value === NONE ? null : value
        await onApply(r, { technicien_responsable: tech })
      }
      done += 1
    }
    setBusy(false)
    setResult(done)
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {rows.length} chantier(s) sélectionné(s).
          </DialogDescription>
        </DialogHeader>

        {result == null ? (
          <div className="flex flex-col gap-3">
            {isStatut ? (
              <Select value={value} onValueChange={setValue}>
                <SelectTrigger aria-label="Nouveau statut"><SelectValue placeholder="Choisir un statut…" /></SelectTrigger>
                <SelectContent>
                  {INSTALLATION_STATUSES.map((k) => (
                    <SelectItem key={k} value={k}>{STATUS_LABELS[k]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Select value={value} onValueChange={setValue}>
                <SelectTrigger aria-label="Installateur"><SelectValue placeholder="Choisir un installateur…" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>— Aucun —</SelectItem>
                  {(users ?? []).map((u) => (
                    <SelectItem key={u.id} value={String(u.id)}>
                      {u.username ?? u.nom ?? `#${u.id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {isStatut && value && (
              <p className="text-xs text-muted-foreground">
                {applicables} chantier(s) seront modifiés.
                {ignorees > 0 && (
                  <span className="text-warning-foreground">
                    {' '}{ignorees} ignoré(s) (saut d&apos;étape non autorisé).
                  </span>
                )}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-foreground">
            {result} chantier(s) mis à jour.
            {isStatut && ignorees > 0 && ` ${ignorees} ignoré(s).`}
          </p>
        )}

        <DialogFooter>
          {result == null ? (
            <>
              <Button variant="ghost" onClick={onClose} disabled={busy}>Annuler</Button>
              <Button
                onClick={apply}
                loading={busy}
                disabled={(isStatut && (!value || applicables === 0)) || (!isStatut && !value)}
              >
                Appliquer
              </Button>
            </>
          ) : (
            <Button onClick={onClose}>Fermer</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ListView({ items, onOpen, users, onChangeStatus, onReassign, nouveauxIds }) {
  // L10 — action groupée en cours ('statut' | 'technicien' | null) + lignes ciblées.
  const [bulk, setBulk] = useState(null) // { kind, rows, clear }
  const canBulk = typeof onChangeStatus === 'function' && typeof onReassign === 'function'

  const columns = useMemo(
    () => [
      {
        id: 'reference',
        header: 'Référence',
        width: 160,
        cell: (value, row) => (
          <span className="flex items-center gap-1.5">
            <span className="font-semibold">{value ?? '—'}</span>
            {/* VX218 — badge « Nouveau » : chantier assigné depuis ma dernière visite. */}
            {nouveauxIds?.has(row.id) && <Badge tone="success">Nouveau</Badge>}
          </span>
        ),
        exportValue: (row) => row.reference ?? '',
      },
      { id: 'client_nom', header: 'Client', width: 180, accessor: (r) => r.client_nom ?? '' },
      { id: 'site_ville', header: 'Ville', width: 140, accessor: (r) => r.site_ville ?? '' },
      {
        id: 'statut',
        header: 'Statut',
        width: 190,
        searchable: false,
        // Tri funnel-aware : on trie sur la position d'entonnoir, pas le libellé.
        accessor: (row) => statusOrder(row.statut),
        cell: (value, row) => (
          <span className="flex flex-wrap items-center gap-1.5">
            <StatusPill status={row.statut} label={statusLabel(row.statut)} />
            {row.annule && <StatusPill tone="danger" label="Annulé" />}
            {isPoseEnRetard(row) && <StatusPill tone="danger" label="Pose en retard" />}
          </span>
        ),
        exportValue: (row) => statusLabel(row.statut) + (row.annule ? ' (annulé)' : ''),
      },
      {
        id: 'type_installation',
        header: 'Type',
        width: 160,
        accessor: (r) => r.type_installation_display ?? '',
      },
      {
        id: 'technicien_nom',
        header: 'Technicien',
        width: 150,
        accessor: (r) => r.technicien_nom ?? '',
      },
      {
        id: 'date_pose_prevue',
        header: 'Pose prévue',
        width: 130,
        searchable: false,
        accessor: (r) => r.date_pose_prevue ?? '',
        cell: (value) => formatDate(value),
        exportValue: (row) => formatDate(row.date_pose_prevue),
      },
    ],
    [nouveauxIds],
  )

  const rowActions = (row) => [
    { id: 'view', label: 'Voir', icon: Eye, onClick: () => onOpen?.(row) },
  ]

  // Vue par défaut : tri par statut dans l'ordre de l'entonnoir.
  const savedViews = [
    { id: 'funnel', label: 'Entonnoir', sorting: [{ id: 'statut', desc: false }], columnFilters: {}, query: '' },
  ]

  // Export Excel serveur (comportement identique à l'ancienne barre d'outils).
  const handleExport = (rows) => {
    importApi
      .exportList('chantiers', rows.map((r) => r.id))
      .then((r) => downloadXlsx(r.data, 'chantiers.xlsx'))
      .catch(() => {})
  }

  // L10 — actions groupées : changement de statut + réassignation en lot.
  const bulkActions = canBulk
    ? (rows, _keys, clear) => [
      // VX246(c) — « Copier » la sélection en TSV (colle en colonnes dans Excel).
      buildCopyTSVAction({ rows, filteredRows: rows, columns }),
      {
        id: 'statut',
        label: 'Changer le statut',
        icon: GitBranch,
        onClick: () => setBulk({ kind: 'statut', rows, clear }),
      },
      {
        id: 'technicien',
        label: "Réassigner l'installateur",
        icon: UserCog,
        onClick: () => setBulk({ kind: 'technicien', rows, clear }),
      },
    ]
    : undefined

  const applyBulk = (row, data) =>
    Promise.resolve(
      'statut' in data ? onChangeStatus(row, data.statut) : onReassign(row, data.technicien_responsable),
    )

  const closeBulk = () => {
    bulk?.clear?.()
    setBulk(null)
  }

  return (
    <>
      <DataTable
        data={items ?? []}
        columns={columns}
        getRowId={(row) => row.id}
        searchable={false}
        savedViews={savedViews}
        selectable={canBulk}
        bulkActions={bulkActions}
        rowActions={rowActions}
        onRowClick={(row) => onOpen?.(row)}
        onExport={handleExport}
        exportName="chantiers"
        pageSize={25}
        emptyTitle="Aucun chantier"
        emptyDescription="Aucun chantier ne correspond aux filtres."
        aria-label="Liste des chantiers"
      />
      {bulk && (
        <BulkActionDialog
          kind={bulk.kind}
          rows={bulk.rows}
          users={users}
          onApply={applyBulk}
          onClose={closeBulk}
        />
      )}
    </>
  )
}
