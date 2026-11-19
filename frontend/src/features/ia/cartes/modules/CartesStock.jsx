import { formatNumber } from '../../../../lib/format'
import { BoutonLien, Geste, Ligne, Rangee, SurTotal, Titre, Vide } from './partsGestion'

/* Copilote vague 2 (CRT-B) — cartes du domaine « stock ». Des QUANTITÉS seulement, telles
   que le serveur les sert : aucun prix, aucune valeur de stock n'est lu ni affiché ici. */

const qte = (n, unite) => `${formatNumber(n, { decimals: 0 })}${unite ? ` ${unite}` : ''}`

// `niveau_stock` — combien en stock, que réapprovisionner (action `stock.produit.niveau`).
// Le chiffre à dire est `disponible` (stock moins réservé), jamais le stock brut.
function CarteNiveauStock({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  if (!lignes.length) return <Vide texte="Aucun produit ne correspond." />
  return (
    <div className="min-w-0">
      <Titre>Niveaux de stock ({d.total ?? lignes.length})</Titre>
      <ul className="space-y-2">
        {lignes.map((p) => (
          <Rangee key={p.produit_id} titre={p.nom}
            detail={[p.marque, p.categorie, p.sku].filter(Boolean).join(' · ')}>
            <p className="mt-1 text-sm font-semibold">Disponible : {qte(p.disponible, p.unite)}</p>
            {p.sous_seuil && (
              <p className="text-xs font-medium text-warning">
                Sous le seuil d’alerte ({qte(p.seuil_alerte, p.unite)}).
              </p>
            )}
            <dl className="mt-1 space-y-0.5 text-xs">
              <Ligne nom="En stock" valeur={qte(p.stock, p.unite)} />
              <Ligne nom="Réservé aux chantiers" valeur={p.reserve > 0 ? qte(p.reserve, p.unite) : ''} />
              <Ligne nom="En commande" valeur={p.en_commande > 0 ? qte(p.en_commande, p.unite) : ''} />
              <Ligne nom="En quarantaine" valeur={p.en_quarantaine > 0 ? qte(p.en_quarantaine, p.unite) : ''} />
              <Ligne nom="Quantité suggérée" valeur={p.quantite_suggeree > 0 ? qte(p.quantite_suggeree, p.unite) : ''} />
            </dl>
            <Geste cle={p.a_faire} />
            <BoutonLien lien={p.lien} texte="Voir les mouvements" />
          </Rangee>
        ))}
      </ul>
      <SurTotal affiches={lignes.length} total={d.total} />
      <BoutonLien lien={d.lien} texte="Ouvrir le stock" />
    </div>
  )
}

const CARTES_STOCK = Object.freeze({
  niveau_stock: CarteNiveauStock,
})
export default CARTES_STOCK
