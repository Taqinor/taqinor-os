/* APX33 — LE tableau de la compta : triable et exportable, une seule fois.
   ---------------------------------------------------------------------------
   Six tables étaient encore écrites à la main dans `features/compta/pages/`,
   exactement là où le comptable a le plus besoin de trier et d'exporter :
   Position consolidée, Prévisionnel 13 semaines, Journal de caisse (la 6ᵉ,
   non documentée avant), Provisions FNP/FAE, et les deux tables de dialogue
   (suggestions d'appariement, plan d'amortissement).

   Ce composant enveloppe le primitif PARTAGÉ `pages/reporting/Table` (15
   consommateurs réels) et lui ajoute les deux choses qui manquaient :
     - un tri au clic sur l'en-tête (même grammaire que `EtatsPage`) ;
     - un export CSV construit dans le NAVIGATEUR à partir des lignes déjà
       chargées — aucun endpoint nouveau.

   La logique de tri et de CSV vit dans `comptaTableData.js` (pure, testable
   sans DOM). Les colonnes de montants passent `align: 'right'` (le primitif
   leur pose `tabular-nums`) + `numeric` (classe `.num`, data typography VX5)
   pour que les chiffres s'alignent en colonne. */
import { useMemo, useState } from 'react'
import { ArrowUp, ArrowDown, ChevronsUpDown, Download } from 'lucide-react'
import { Table as SharedTable } from '../../pages/reporting/Table'
import { Button } from '../../ui'
import { sortRows, toCsv } from './comptaTableData'

export default function ComptaTable({
  columns,
  rows = [],
  getRowKey,
  caption,
  exportName,
  footer,
  'aria-label': ariaLabel,
}) {
  const [sort, setSort] = useState({ key: null, dir: 'asc' })

  const sorted = useMemo(() => sortRows(columns, rows, sort), [columns, rows, sort])

  const toggleSort = (key) => setSort((prev) => (
    prev.key === key
      ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: 'asc' }))

  const telecharger = () => {
    const blob = new Blob([toCsv(columns, sorted)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${exportName || 'export'}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  }

  const cols = columns.map((c) => ({
    key: c.key,
    align: c.align,
    cellClassName: c.numeric ? 'num' : c.cellClassName,
    cell: c.cell,
    header: (
      <button
        type="button"
        onClick={() => toggleSort(c.key)}
        className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-foreground"
        aria-label={`Trier par ${c.label ?? c.key}`}
      >
        {c.label ?? c.key}
        {sort.key === c.key
          ? (sort.dir === 'asc'
            ? <ArrowUp className="size-3" aria-hidden="true" />
            : <ArrowDown className="size-3" aria-hidden="true" />)
          : <ChevronsUpDown className="size-3 opacity-40" aria-hidden="true" />}
      </button>
    ),
  }))

  return (
    <div className="flex flex-col gap-2">
      {exportName && rows.length > 0 && (
        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={telecharger}>
            <Download /> Exporter CSV
          </Button>
        </div>
      )}
      <SharedTable
        columns={cols}
        rows={sorted}
        getRowKey={getRowKey}
        caption={caption}
        footer={footer}
        aria-label={ariaLabel}
      />
    </div>
  )
}
