import { useState } from 'react'
import { CalendarClock } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD, todayLocalIso } from '../../lib/format'
import { frErrDetail as frErr } from '../../lib/frErr'
import { useIsAdmin } from '../../hooks/useHasPermission'
import useVoitPrixAchat from '../../features/stock/useVoitPrixAchat'
import { Button, DataTable, Input, FormField } from '../../ui'
import { AlerteErreurStock } from './BandeauxListeStock'

/* ENF15 (D-ENF15-STOCK-22) — XSTK13 : valeur du stock reconstruite à une date
   passée (CGNC). Réservé à l'administrateur ; le coût moyen et la valeur sont
   des coûts d'achat : masqués sans le droit « prix d'achat ». À la demande. */

const COLONNES = [
  { id: 'sku', header: 'Réf.', width: 120, accessor: (l) => l.sku ?? '' },
  { id: 'designation', header: 'Produit', minWidth: 180, accessor: (l) => l.designation ?? '' },
  { id: 'quantite', header: 'Quantité', align: 'right', width: 100, searchable: false,
    accessor: (l) => l.quantite ?? 0 },
  { id: 'cout_moyen', header: 'Coût moyen', align: 'right', width: 130, searchable: false,
    accessor: (l) => Number(l.cout_moyen ?? 0), cell: (_v, l) => formatMAD(l.cout_moyen) },
  { id: 'valeur', header: 'Valeur', align: 'right', width: 140, searchable: false,
    accessor: (l) => Number(l.valeur ?? 0), cell: (_v, l) => formatMAD(l.valeur) },
]

export default function ValorisationADate() {
  const admin = useIsAdmin()
  const voitCouts = useVoitPrixAchat()
  const [date, setDate] = useState(todayLocalIso())
  const [releve, setReleve] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  if (!admin || !voitCouts) return null

  const calculer = async () => {
    if (!date) { setError('Choisissez une date.'); return }
    setLoading(true)
    setError(null)
    try {
      const r = await stockApi.getValorisationADate(date)
      setReleve(r.data)
    } catch (err) {
      setReleve(null)
      setError(frErr(err, 'Valorisation indisponible.'))
    } finally { setLoading(false) }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3"
             aria-labelledby="val-titre">
      <h2 id="val-titre" className="flex items-center gap-1.5 text-sm font-semibold">
        <CalendarClock className="size-4" aria-hidden="true" /> Valeur du stock à une date
      </h2>
      <p className="text-xs text-muted-foreground">
        Reconstruite depuis les mouvements, hors marchandise appartenant à un tiers. Interne.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <FormField label="Date" htmlFor="val-date">
          <Input id="val-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </FormField>
        <Button type="button" onClick={calculer} loading={loading}>Valoriser</Button>
      </div>
      <AlerteErreurStock error={error} />
      {releve && (
        <>
          <p className="text-sm">
            Valeur au {new Date(releve.date).toLocaleDateString('fr-FR')} :{' '}
            <strong className="tabular-nums">{formatMAD(releve.total)}</strong>
          </p>
          <DataTable
            data={releve.lignes ?? []}
            columns={COLONNES}
            getRowId={(l) => l.produit_id}
            searchPlaceholder="Rechercher (réf., produit)…"
            globalColumns={['sku', 'designation']}
            emptyTitle="Aucun stock à cette date"
            emptyDescription="Aucun produit n'avait de quantité à cette date."
            aria-label="Valorisation du stock à une date"
          />
        </>
      )}
    </section>
  )
}
