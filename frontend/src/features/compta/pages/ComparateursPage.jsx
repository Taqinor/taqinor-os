import { useState } from 'react'
import { GitCompare } from 'lucide-react'
import { useTabParam } from '../components/useTabParam'
import { Button, Card, Segmented, EmptyState, Input, Label, toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'

/* ============================================================================
   PACT36 — Comparateurs commerciaux : versions de devis, cash vs financement.
   ----------------------------------------------------------------------------
   Deux ressources de CALCUL PUR, sans aucun stockage (FG212, FG221) : le
   comparateur de devis affiche le diff champ à champ entre deux versions pour
   le back-office ; le comparateur cash/financement sert au commercial en
   rendez-vous pour lever l'objection prix (coût total + payback). Endpoints
   /compta/comparateur-devis/comparer/, /compta/comparateur-financement/comparer/.
   ========================================================================== */

function ComparateurDevisPanel() {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [resultat, setResultat] = useState(null)
  const [loading, setLoading] = useState(false)

  const comparer = async () => {
    if (!a || !b) { toast.error('Renseignez les deux identifiants de devis.'); return }
    setLoading(true)
    try {
      const res = await comptaApi.comparateurDevis.comparer(a, b)
      setResultat(res.data)
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Comparaison impossible.'))
      setResultat(null)
    } finally {
      setLoading(false)
    }
  }

  const diffEntries = resultat ? Object.entries(resultat.diff || {}) : []

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="cd-a" required>Devis A (id)</Label>
          <Input id="cd-a" type="number" value={a} onChange={(e) => setA(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="cd-b" required>Devis B (id)</Label>
          <Input id="cd-b" type="number" value={b} onChange={(e) => setB(e.target.value)} />
        </div>
        <Button onClick={comparer} disabled={loading}>
          <GitCompare className="size-4" /> {loading ? 'Comparaison…' : 'Comparer'}
        </Button>
      </div>

      {resultat && (
        diffEntries.length === 0 ? (
          <EmptyState title="Aucune différence" description="Les deux devis sont identiques champ à champ." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="py-2 pr-3">Champ</th>
                  <th className="py-2 pr-3">Devis A</th>
                  <th className="py-2">Devis B</th>
                </tr>
              </thead>
              <tbody>
                {diffEntries.map(([champ, { a: va, b: vb }]) => (
                  <tr key={champ} className="border-b border-border/60">
                    <td className="py-2 pr-3 font-mono text-xs">{champ}</td>
                    <td className="py-2 pr-3">{String(va ?? '—')}</td>
                    <td className="py-2">{String(vb ?? '—')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </Card>
  )
}

function ComparateurFinancementPanel() {
  const [montant, setMontant] = useState('')
  const [dureeMois, setDureeMois] = useState('')
  const [tauxAnnuel, setTauxAnnuel] = useState('')
  const [economie, setEconomie] = useState('')
  const [resultat, setResultat] = useState(null)
  const [loading, setLoading] = useState(false)

  const comparer = async () => {
    if (!montant || !dureeMois) { toast.error('Renseignez au moins le montant et la durée.'); return }
    setLoading(true)
    try {
      const res = await comptaApi.comparateurFinancement.comparer({
        montant, duree_mois: dureeMois, taux_annuel: tauxAnnuel || 0, economie_annuelle: economie || 0,
      })
      setResultat(res.data)
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Comparaison impossible.'))
      setResultat(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="cf-montant" required>Montant</Label>
          <Input id="cf-montant" type="number" step="any" value={montant} onChange={(e) => setMontant(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="cf-duree" required>Durée (mois)</Label>
          <Input id="cf-duree" type="number" value={dureeMois} onChange={(e) => setDureeMois(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="cf-taux">Taux annuel (%)</Label>
          <Input id="cf-taux" type="number" step="any" value={tauxAnnuel} onChange={(e) => setTauxAnnuel(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="cf-economie">Économie annuelle</Label>
          <Input id="cf-economie" type="number" step="any" value={economie} onChange={(e) => setEconomie(e.target.value)} />
        </div>
        <Button onClick={comparer} disabled={loading}>
          <GitCompare className="size-4" /> {loading ? 'Comparaison…' : 'Comparer'}
        </Button>
      </div>

      {resultat && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border p-3">
            <p className="font-medium">Cash</p>
            <p className="text-sm text-muted-foreground">Coût total : {formatMAD(resultat.cash?.cout_total)}</p>
            <p className="text-sm text-muted-foreground">
              Payback : {resultat.cash?.payback_annees != null ? `${resultat.cash.payback_annees} an(s)` : '—'}
            </p>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="font-medium">Financement</p>
            <p className="text-sm text-muted-foreground">Mensualité : {formatMAD(resultat.financement?.mensualite)}</p>
            <p className="text-sm text-muted-foreground">Coût du crédit : {formatMAD(resultat.financement?.cout_credit)}</p>
            <p className="text-sm text-muted-foreground">Coût total : {formatMAD(resultat.financement?.cout_total)}</p>
            <p className="text-sm text-muted-foreground">
              Payback : {resultat.financement?.payback_annees != null ? `${resultat.financement.payback_annees} an(s)` : '—'}
            </p>
          </div>
          <p className="text-sm sm:col-span-2">
            Surcoût du financement : <strong>{formatMAD(resultat.surcout_financement)}</strong>
          </p>
        </div>
      )}
    </Card>
  )
}

const TABS = [
  { value: 'devis', label: 'Versions de devis' },
  { value: 'financement', label: 'Cash vs financement' },
]

export default function ComparateursPage() {
  const [tab, setTab] = useTabParam('devis')

  return (
    <div className="page">
      <div className="page-header">
        <h2>Comparateurs commerciaux</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet comparateurs" />
      </div>

      {tab === 'devis' && <ComparateurDevisPanel />}
      {tab === 'financement' && <ComparateurFinancementPanel />}
    </div>
  )
}
