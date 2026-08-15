import { useEffect, useState } from 'react'
import { Badge, Button, toast } from '../../ui'
import cpqApi from '../../api/cpqApi'
import stockApi from '../../api/stockApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   PACT129 — Prix contractuels négociés par client (NTCPQ5, `apps.cpq`).
   Prix HT négocié par client et par produit, avec fenêtre de validité et
   motif, réservé aux profils élevés (403 serveur sinon — la fiche client
   affiche alors le message exact renvoyé par le serveur, jamais un onglet
   silencieusement vide). Monté en onglet « Tarifs négociés » sur la fiche
   client, plus cohérent qu'un écran autonome (la fiche a déjà des onglets).
   ========================================================================== */

export default function ClientPrixContractuelsTab({ clientId }) {
  const [prix, setPrix] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  // Le client affiché a changé : on remet loading/erreur à zéro PENDANT le
  // rendu (jamais dans l'effet ci-dessous) pour éviter un second rendu en
  // cascade — l'effet ne fait plus que déclencher le fetch.
  const [clientCharge, setClientCharge] = useState(clientId)
  if (clientId !== clientCharge) {
    setClientCharge(clientId)
    setLoading(true)
    setErreur('')
  }

  const fetchPrixContractuels = () => cpqApi.getPrixContractuels()
    .then((res) => {
      const rows = res.data?.results ?? res.data ?? []
      setPrix(rows.filter((p) => Number(p.client) === Number(clientId)))
    })
    .catch((err) => setErreur(frenchError(err, 'Impossible de charger les tarifs négociés.')))
    .finally(() => setLoading(false))

  const charger = () => {
    setLoading(true)
    setErreur('')
    return fetchPrixContractuels()
  }

  useEffect(() => { if (clientId) fetchPrixContractuels() }, [clientId])

  const [produits, setProduits] = useState([])
  useEffect(() => {
    stockApi.getProduits().then((res) => setProduits(res.data?.results ?? res.data ?? [])).catch(() => {})
  }, [])
  const nomProduit = (id) => produits.find((p) => p.id === id)?.nom || `Produit #${id}`

  const [form, setForm] = useState({
    produit: '', prix_ht: '', date_debut: '', date_fin: '', motif: '',
  })
  const [saving, setSaving] = useState(false)

  const creer = async (event) => {
    event.preventDefault()
    if (!form.produit || !form.prix_ht) return
    setSaving(true)
    try {
      await cpqApi.createPrixContractuel({
        client: clientId,
        produit: form.produit,
        prix_ht: form.prix_ht,
        date_debut: form.date_debut || undefined,
        date_fin: form.date_fin || undefined,
        motif: form.motif,
      })
      toast.success('Prix contractuel créé.')
      setForm({ produit: '', prix_ht: '', date_debut: '', date_fin: '', motif: '' })
      charger()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de créer ce prix contractuel.'))
    } finally {
      setSaving(false)
    }
  }

  // WIR184 — édition inline (formulaire pré-rempli) + suppression, réservées
  // aux profils élevés côté serveur (403 affiché en FR, jamais avalé).
  const [editionId, setEditionId] = useState(null)
  const [editForm, setEditForm] = useState({ prix_ht: '', date_debut: '', date_fin: '', motif: '' })
  const [editSaving, setEditSaving] = useState(false)
  const [suppressionId, setSuppressionId] = useState(null)

  const commencerEdition = (p) => {
    setEditionId(p.id)
    setEditForm({
      prix_ht: p.prix_ht ?? '',
      date_debut: p.date_debut ?? '',
      date_fin: p.date_fin ?? '',
      motif: p.motif ?? '',
    })
  }

  const annulerEdition = () => setEditionId(null)

  const enregistrerEdition = async (event, id) => {
    event.preventDefault()
    setEditSaving(true)
    try {
      await cpqApi.updatePrixContractuel(id, {
        prix_ht: editForm.prix_ht,
        date_debut: editForm.date_debut || undefined,
        date_fin: editForm.date_fin || undefined,
        motif: editForm.motif,
      })
      toast.success('Prix contractuel modifié.')
      setEditionId(null)
      charger()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de modifier ce prix contractuel.'))
    } finally {
      setEditSaving(false)
    }
  }

  const supprimer = async (id) => {
    if (!window.confirm('Supprimer ce prix contractuel ? Cette action est irréversible.')) return
    setSuppressionId(id)
    try {
      await cpqApi.deletePrixContractuel(id)
      toast.success('Prix contractuel supprimé.')
      charger()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de supprimer ce prix contractuel.'))
    } finally {
      setSuppressionId(null)
    }
  }

  if (erreur) return <p style={{ color: '#ef4444' }}>{erreur}</p>

  return (
    <div>
      <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          value={form.produit}
          onChange={(e) => setForm({ ...form, produit: e.target.value })}
          aria-label="Produit"
          required
        >
          <option value="">Produit…</option>
          {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
        <input
          type="number" step="0.01"
          placeholder="Prix HT négocié"
          value={form.prix_ht}
          onChange={(e) => setForm({ ...form, prix_ht: e.target.value })}
          aria-label="Prix HT négocié"
          required
        />
        <input
          type="date"
          value={form.date_debut}
          onChange={(e) => setForm({ ...form, date_debut: e.target.value })}
          aria-label="Date de début de validité"
        />
        <input
          type="date"
          value={form.date_fin}
          onChange={(e) => setForm({ ...form, date_fin: e.target.value })}
          aria-label="Date de fin de validité"
        />
        <input
          placeholder="Motif"
          value={form.motif}
          onChange={(e) => setForm({ ...form, motif: e.target.value })}
          aria-label="Motif du prix négocié"
        />
        <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le prix négocié'}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Produit</th><th>Prix HT</th><th>Validité</th><th>Motif</th><th /><th>Actions</th></tr>
          </thead>
          <tbody>
            {prix.map((p) => (
              editionId === p.id ? (
                <tr key={p.id}>
                  <td colSpan={6}>
                    <form onSubmit={(e) => enregistrerEdition(e, p.id)} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <span>{nomProduit(p.produit)}</span>
                      <input
                        type="number" step="0.01"
                        value={editForm.prix_ht}
                        onChange={(e) => setEditForm({ ...editForm, prix_ht: e.target.value })}
                        aria-label="Modifier le prix HT négocié"
                        required
                      />
                      <input
                        type="date"
                        value={editForm.date_debut || ''}
                        onChange={(e) => setEditForm({ ...editForm, date_debut: e.target.value })}
                        aria-label="Modifier la date de début de validité"
                      />
                      <input
                        type="date"
                        value={editForm.date_fin || ''}
                        onChange={(e) => setEditForm({ ...editForm, date_fin: e.target.value })}
                        aria-label="Modifier la date de fin de validité"
                      />
                      <input
                        value={editForm.motif || ''}
                        onChange={(e) => setEditForm({ ...editForm, motif: e.target.value })}
                        aria-label="Modifier le motif du prix négocié"
                      />
                      <Button type="submit" disabled={editSaving}>{editSaving ? 'Enregistrement…' : 'Enregistrer'}</Button>
                      <Button type="button" variant="ghost" onClick={annulerEdition}>Annuler</Button>
                    </form>
                  </td>
                </tr>
              ) : (
                <tr key={p.id}>
                  <td>{nomProduit(p.produit)}</td>
                  <td>{p.prix_ht}</td>
                  <td>
                    {p.date_debut || '…'} → {p.date_fin || '…'}
                  </td>
                  <td>{p.motif || '—'}</td>
                  <td>
                    {p.est_actif ? <Badge tone="success">Actif</Badge> : <Badge tone="neutral">Inactif</Badge>}
                  </td>
                  <td>
                    <Button type="button" variant="ghost" onClick={() => commencerEdition(p)} aria-label={`Modifier le prix négocié ${nomProduit(p.produit)}`}>
                      Modifier
                    </Button>
                    <Button
                      type="button" variant="ghost"
                      onClick={() => supprimer(p.id)}
                      disabled={suppressionId === p.id}
                      aria-label={`Supprimer le prix négocié ${nomProduit(p.produit)}`}
                    >
                      Supprimer
                    </Button>
                  </td>
                </tr>
              )
            ))}
            {prix.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucun prix négocié</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
