import { useState } from 'react'
import { Percent } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { frErrDetail as frErr } from '../../lib/frErr'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import useVoitPrixAchat from '../../features/stock/useVoitPrixAchat'
import { Button, Input, FormField } from '../../ui'
import { AlerteErreurStock } from './BandeauxListeStock'

/* ENF15 (D-ENF15-STOCK-22) — XPUR17 : relevé des déductions de TVA sur les
   achats, groupé par taux, sur une période. Réservé responsables et admins (le
   serveur refuse les autres) ; montants d'achat : masqué sans le droit « prix
   d'achat ». Chargé à la demande (bouton), jamais au montage. */

export default function ReleveDeductionsTva() {
  const gestionnaire = useIsAdminOrResponsable()
  const voitMontants = useVoitPrixAchat()
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [lignes, setLignes] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  if (!gestionnaire || !voitMontants) return null

  const afficher = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await stockApi.getReleveDeductionsTva({
        ...(debut ? { date_debut: debut } : {}), ...(fin ? { date_fin: fin } : {}),
      })
      setLignes(Array.isArray(r.data) ? r.data : [])
    } catch (err) {
      setLignes(null)
      setError(frErr(err, 'Relevé indisponible.'))
    } finally { setLoading(false) }
  }

  const totalTva = (lignes ?? []).reduce((s, l) => s + Number(l.total_tva || 0), 0)

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3"
             aria-labelledby="rdt-titre">
      <h2 id="rdt-titre" className="flex items-center gap-1.5 text-sm font-semibold">
        <Percent className="size-4" aria-hidden="true" /> Relevé des déductions de TVA (achats)
      </h2>
      <p className="text-xs text-muted-foreground">
        TVA déductible sur les factures fournisseur de la période, par taux — quel que soit leur état de règlement.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <FormField label="Du" htmlFor="rdt-debut">
          <Input id="rdt-debut" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} />
        </FormField>
        <FormField label="Au" htmlFor="rdt-fin">
          <Input id="rdt-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
        </FormField>
        <Button type="button" onClick={afficher} loading={loading}>Afficher le relevé</Button>
      </div>
      <AlerteErreurStock error={error} />
      {lignes && (
        lignes.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune facture fournisseur sur cette période.</p>
        ) : (
          <table className="w-full text-sm">
            <caption className="sr-only">Déductions de TVA par taux</caption>
            <thead>
              <tr className="text-left">
                <th scope="col" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Taux</th>
                <th scope="col" className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">Factures</th>
                <th scope="col" className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">Total HT</th>
                <th scope="col" className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">TVA déductible</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((l) => (
                <tr key={String(l.taux_tva)} className="border-t border-border">
                  <td className="px-2 py-1.5">{Number(l.taux_tva)} %</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{l.nombre_factures}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{formatMAD(l.total_ht)}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{formatMAD(l.total_tva)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-border font-semibold">
                <td className="px-2 py-1.5" colSpan={3}>Total TVA déductible</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{formatMAD(totalTva)}</td>
              </tr>
            </tfoot>
          </table>
        )
      )}
    </section>
  )
}
