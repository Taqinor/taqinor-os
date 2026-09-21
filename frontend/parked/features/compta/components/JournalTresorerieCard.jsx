/* NTTRE21 — Journal de trésorerie imprimable.
   ----------------------------------------------------------------------------
   Tous les mouvements d'un compte de trésorerie sur une période (virements
   internes, effets encaissés/payés, lignes de campagne de règlement postées,
   écritures manuelles du compte 5xxx) avec le solde COURANT ligne à ligne.

   Aucun calcul ici : le solde d'ouverture, les totaux et le solde de clôture
   viennent tous du serveur (`compta/etats/journal-tresorerie/`), qui les
   dérive du grand livre — le solde de clôture affiché EST donc le solde GL du
   compte à la date de fin. Le bouton « Imprimer » télécharge le même état en
   PDF (WeasyPrint, document interne). */
import { useState } from 'react'
import { Download } from 'lucide-react'
import { Button, Card, EmptyState, Input, Label, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'

export default function JournalTresorerieCard({ comptes = [] }) {
  const [compte, setCompte] = useState('')
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const params = () => ({
    compte, debut: debut || undefined, fin: fin || undefined,
  })

  const charger = () => {
    if (!compte) {
      toast.error('Compte de trésorerie : choisissez un compte.')
      return
    }
    setLoading(true)
    comptaApi.etats.journalTresorerie(params())
      .then((res) => setData(res.data))
      .catch(() => toast.error('Journal de trésorerie indisponible.'))
      .finally(() => setLoading(false))
  }

  const exporterPdf = async () => {
    if (!compte) {
      toast.error('Compte de trésorerie : choisissez un compte.')
      return
    }
    try {
      const res = await comptaApi.etats.journalTresoreriePdf(params())
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, 'journal-tresorerie.pdf')
    } catch {
      toast.error('Export du journal indisponible.')
    }
  }

  return (
    <Card className="p-4 sm:p-5">
      <h3 className="mb-3 font-display text-base font-semibold">
        Journal de trésorerie
      </h3>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="jt-compte">Compte</Label>
          <select
            id="jt-compte" value={compte}
            onChange={(e) => { setCompte(e.target.value); setData(null) }}
            className="h-9 rounded-md border border-border bg-card px-3 text-sm"
          >
            <option value="">Choisir un compte…</option>
            {comptes.map((c) => (
              <option key={c.id} value={c.id}>{c.libelle}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="jt-debut">Du</Label>
          <Input id="jt-debut" type="date" value={debut}
                 onChange={(e) => setDebut(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="jt-fin">Au</Label>
          <Input id="jt-fin" type="date" value={fin}
                 onChange={(e) => setFin(e.target.value)} />
        </div>
        <Button variant="outline" size="sm" onClick={charger}>Charger</Button>
        <Button variant="outline" size="sm" onClick={exporterPdf}>
          <Download className="size-4" /> Imprimer (PDF)
        </Button>
      </div>
      {loading ? (
        <p className="py-4 text-center text-sm text-muted-foreground">Chargement…</p>
      ) : !data ? (
        <EmptyState
          title="Aucun journal chargé"
          description="Choisissez un compte et une période, puis cliquez sur Charger."
        />
      ) : (
        <>
          <div className="mb-2 flex flex-wrap gap-4 rounded-lg border px-3 py-2 text-sm">
            <span>
              Solde d’ouverture : <strong>{formatMAD(data.solde_ouverture)}</strong>
            </span>
            <span>
              Solde de clôture : <strong>{formatMAD(data.solde_cloture)}</strong>
            </span>
          </div>
          <ComptaTable
            aria-label="Journal de trésorerie"
            exportName="journal-tresorerie"
            rows={data.mouvements}
            getRowKey={(m) => m.ligne_id}
            columns={[
              { key: 'date', label: 'Date', sortValue: (m) => m.date || '',
                cell: (m) => formatDate(m.date) },
              { key: 'piece', label: 'Pièce', cell: (m) => m.piece || '—' },
              { key: 'libelle', label: 'Libellé', cell: (m) => m.libelle || '—' },
              { key: 'nature', label: 'Nature', cell: (m) => m.nature || '—' },
              { key: 'debit', label: 'Débit', align: 'right', numeric: true,
                sortValue: (m) => Number(m.debit) || 0,
                cell: (m) => formatMAD(m.debit) },
              { key: 'credit', label: 'Crédit', align: 'right', numeric: true,
                sortValue: (m) => Number(m.credit) || 0,
                cell: (m) => formatMAD(m.credit) },
              { key: 'solde', label: 'Solde', align: 'right', numeric: true,
                sortValue: (m) => Number(m.solde) || 0,
                cell: (m) => formatMAD(m.solde) },
            ]}
          />
        </>
      )}
    </Card>
  )
}
