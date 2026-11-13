import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { frenchError } from '../../lib/frenchError'
import { useConfirmation } from '../../features/stock/useConfirmation'

/* AERR80 — retrait d'un prix fournisseur de la fiche produit : confirmation
   maison qui NOMME le fournisseur et le prix, échec dit (jamais avalé).
   Module frère de ProduitForm.jsx (fichier-mur ≥ 2 000 lignes : il ne grossit
   pas). Renvoie `[retirer(ligne), dialogue]` — `dialogue` est à rendre. */
export function useRetraitPrixFournisseur({ load, setError }) {
  const [confirmer, dialogue] = useConfirmation()
  const retirer = async (r) => {
    const prix = `${formatMAD(r.prix_achat, { withSymbol: false })} DH`
    if (!(await confirmer({
      title: `Supprimer le prix de « ${r.fournisseur_nom} » (${prix}) ?`,
      confirmLabel: 'Supprimer',
    }))) return
    try {
      await stockApi.deletePrixFournisseur(r.id)
      await load()
    } catch (e) {
      setError(frenchError(e, 'La suppression du prix a échoué.'))
    }
  }
  return [retirer, dialogue]
}

/* Date du dernier achat au format JJ/MM/AAAA (sinon « — ») — sortie de
   ProduitForm.jsx avec AERR80 (même rendu). */
export function fmtAchatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
