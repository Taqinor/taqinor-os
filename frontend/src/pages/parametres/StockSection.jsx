// Onglet « Stock » de la page Paramètres (marques, catégories, fournisseurs).
// Restylé sur le système de design (@/ui) ; champs, libellés et comportement
// identiques.
import { Plus, Trash2 } from 'lucide-react'
import {
  createCategorie, updateCategorie, deleteCategorie,
  createFournisseur, updateFournisseur, deleteFournisseur,
} from '../../features/stock/store/stockSlice'
import { Card, CardContent, Input, Button, IconButton } from '../../ui'
import { SectionTitle, ReferentielBlock } from './peComponents'

export default function StockSection({
  categories, fournisseurs, dispatch,
  marques, newMarque, setNewMarque, addMarque, delMarque,
}) {
  return (
    <>
      {/* Stock — Marques */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Stock — Marques" icon={<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Marques proposées sur les produits (ajout libre possible). Une
            marque utilisée par des produits ne peut pas être supprimée.
          </p>
          {marques.map(m => (
            <div key={m.id} className="mb-1.5 flex items-center gap-1.5">
              <Input className="flex-1" defaultValue={m.nom} readOnly />
              <IconButton size="md" variant="outline" label="Supprimer la marque"
                          className="text-destructive hover:text-destructive disabled:text-muted-foreground"
                          disabled={m.en_usage > 0}
                          title={m.en_usage > 0 ? `${m.en_usage} produit(s)` : 'Supprimer'}
                          onClick={() => delMarque(m)}>
                <Trash2 className="size-4" aria-hidden="true" />
              </IconButton>
            </div>
          ))}
          <div className="flex gap-1.5">
            <Input className="flex-1" placeholder="Nouvelle marque" value={newMarque}
                   onChange={e => setNewMarque(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMarque() } }} />
            <Button type="button" onClick={addMarque}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>
      <div className="pe-grid-2">
        <ReferentielBlock
          title="Catégories produit"
          icon={<><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></>}
          items={categories}
          onCreate={nom => dispatch(createCategorie({ nom })).unwrap()}
          onUpdate={(id, nom) => dispatch(updateCategorie({ id, data: { nom } })).unwrap()}
          onDelete={id => dispatch(deleteCategorie(id)).unwrap()}
        />
        <ReferentielBlock
          title="Fournisseurs"
          icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}
          items={fournisseurs}
          onCreate={nom => dispatch(createFournisseur({ nom })).unwrap()}
          onUpdate={(id, nom) => dispatch(updateFournisseur({ id, data: { nom } })).unwrap()}
          onDelete={id => dispatch(deleteFournisseur(id)).unwrap()}
        />
      </div>
    </>
  )
}
