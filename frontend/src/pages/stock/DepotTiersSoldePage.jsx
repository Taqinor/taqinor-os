import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import NoIndex from '../../components/NoIndex'
import publicStockApi from '../../features/stock/publicStockApi'
import { messageServeur } from '../../features/stock/api/erreurs'

/* ASTK223 — page PUBLIQUE « solde du dépositaire » (/depot-tiers/:token).

   Aucun login, aucun layout ERP. Le jeton identifie UN dépositaire : la page
   n'affiche que SON solde (produit, référence, emplacement, quantité) — jamais
   de prix, jamais un autre dépositaire. Seules les quatre colonnes ci-dessous
   sont rendues : une clé inattendue de la réponse n'apparaît donc jamais. Un
   lien révoqué ou expiré affiche le 404 du serveur tel quel. */

export default function DepotTiersSoldePage() {
  const { token } = useParams()
  const [solde, setSolde] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let vivant = true
    publicStockApi.tiersSolde(token)
      .then((r) => { if (vivant) setSolde(r.data) })
      .catch((err) => {
        if (vivant) setErreur(messageServeur(err, 'Ce lien est introuvable ou a expiré.'))
      })
    return () => { vivant = false }
  }, [token])

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-6">
      <NoIndex />
      <h1 className="text-2xl font-semibold">Solde de votre stock</h1>
      {erreur && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {erreur}
        </div>
      )}
      {solde && (
        <section className="space-y-3">
          <p className="text-lg font-medium">{solde.tiers_nom}</p>
          {solde.lignes.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">Aucun article en dépôt pour le moment.</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
              <table className="w-full min-w-[28rem] text-sm">
                <thead className="bg-[var(--muted)] text-xs uppercase tracking-wide">
                  <tr>
                    <th className="px-3 py-2 text-left">Produit</th>
                    <th className="px-3 py-2 text-left">Référence</th>
                    <th className="px-3 py-2 text-left">Emplacement</th>
                    <th className="px-3 py-2 text-right">Quantité</th>
                  </tr>
                </thead>
                <tbody>
                  {solde.lignes.map((l, i) => (
                    <tr key={`${l.sku}-${i}`} className="border-t border-[var(--border)]">
                      <td className="px-3 py-2">{l.produit}</td>
                      <td className="px-3 py-2">{l.sku}</td>
                      <td className="px-3 py-2">{l.emplacement}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.quantite}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-sm">Total : <strong>{solde.total_unites}</strong> unité(s)</p>
        </section>
      )}
    </main>
  )
}
