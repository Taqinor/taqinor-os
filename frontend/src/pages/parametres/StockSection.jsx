// Onglet « Stock » de la page Paramètres (marques, catégories, fournisseurs).
// JSX, champs, libellés et styles identiques à l'ancien bloc monolithique.
import {
  createCategorie, updateCategorie, deleteCategorie,
  createFournisseur, updateFournisseur, deleteFournisseur,
} from '../../features/stock/store/stockSlice'
import { SectionTitle, ReferentielBlock } from './peComponents'
import { inputBase, cardStyle } from './peConstants'

export default function StockSection({
  categories, fournisseurs, dispatch,
  marques, newMarque, setNewMarque, addMarque, delMarque,
}) {
  return (
    <>
      {/* Stock — Marques */}
      <div style={cardStyle}>
        <SectionTitle color="#b45309" label="Stock — Marques" icon={<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Marques proposées sur les produits (ajout libre possible). Une
          marque utilisée par des produits ne peut pas être supprimée.
        </p>
        {marques.map(m => (
          <div key={m.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
            <input style={{ ...inputBase, flex: 1 }} defaultValue={m.nom} readOnly />
            <button type="button" onClick={() => delMarque(m)}
                    disabled={m.en_usage > 0}
                    title={m.en_usage > 0 ? `${m.en_usage} produit(s)` : 'Supprimer'}
                    style={{ border: 'none', background: m.en_usage > 0 ? '#e2e8f0' : '#fee2e2', color: m.en_usage > 0 ? '#94a3b8' : '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: m.en_usage > 0 ? 'not-allowed' : 'pointer' }}>✕</button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6 }}>
          <input style={{ ...inputBase, flex: 1 }} placeholder="Nouvelle marque" value={newMarque}
                 onChange={e => setNewMarque(e.target.value)}
                 onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMarque() } }} />
          <button type="button" onClick={addMarque}
                  style={{ border: 'none', background: '#b45309', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
        </div>
      </div>
      <div className="pe-grid-2">
        <ReferentielBlock
          title="Catégories produit"
          color="#1d4ed8"
          icon={<><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></>}
          items={categories}
          onCreate={nom => dispatch(createCategorie({ nom })).unwrap()}
          onUpdate={(id, nom) => dispatch(updateCategorie({ id, data: { nom } })).unwrap()}
          onDelete={id => dispatch(deleteCategorie(id)).unwrap()}
        />
        <ReferentielBlock
          title="Fournisseurs"
          color="#059669"
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
