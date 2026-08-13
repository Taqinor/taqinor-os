import { useState } from 'react'
import { Plus, Copy } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, toast,
} from '../../../ui'
import { formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'

/* ============================================================================
   PACT39 — Catalogue public à jeton.
   ----------------------------------------------------------------------------
   FG214 : génère un catalogue public en prix TTC derrière un jeton opaque —
   lien partageable sans connexion. Le rendu réel (JSON, jamais `prix_achat`
   ni marge) est servi par `apps.ventes.public_views.ecatalogue_public`
   (route /api/django/public/ecatalogue/<token>/, hors périmètre compta —
   lue via `compta.selectors`, jamais un import de modèle cross-app). Cet
   écran gère le CÔTÉ ADMIN : créer un catalogue, choisir ses produits
   (ids stock), l'activer/désactiver, et copier son lien public.
   Endpoint /compta/ecatalogues/.
   ========================================================================== */

function NouveauCatalogueDialog({ onClose, onSaved }) {
  const [titre, setTitre] = useState('Catalogue')
  const [produitIds, setProduitIds] = useState('')
  const [expireLe, setExpireLe] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const ids = produitIds.split(',').map((s) => Number(s.trim())).filter((n) => Number.isFinite(n))
      await comptaApi.ecatalogues.create({
        titre, produit_ids: ids, expire_le: expireLe || undefined,
      })
      toast.success('Catalogue public créé.')
      onSaved?.()
      onClose?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Création impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouveau catalogue public</DialogTitle></DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="ec-titre" required>Titre</Label>
            <Input id="ec-titre" value={titre} onChange={(e) => setTitre(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="ec-produits">Produits exposés (ids stock, séparés par des virgules)</Label>
            <Input id="ec-produits" value={produitIds} onChange={(e) => setProduitIds(e.target.value)} placeholder="12, 45, 78" />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="ec-expire">Expire le (optionnel)</Label>
            <Input id="ec-expire" type="date" value={expireLe} onChange={(e) => setExpireLe(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// Lien public réel — le token public n'expose que le titre + le prix TTC
// (jamais prix_achat/marge), voir apps/ventes/public_views.ecatalogue_public.
function lienPublic(token) {
  return `${window.location.origin}/api/django/public/ecatalogue/${token}/`
}

export default function ECataloguePage() {
  const [dialog, setDialog] = useState(false)
  const list = useComptaList(comptaApi.ecatalogues.list, undefined)

  const toggleActif = async (row) => {
    try {
      await comptaApi.ecatalogues.update(row.id, { actif: !row.actif })
      toast.success(row.actif ? 'Catalogue désactivé.' : 'Catalogue activé.')
      list.reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  const copierLien = async (row) => {
    const lien = lienPublic(row.token)
    try {
      await navigator.clipboard.writeText(lien)
      toast.success('Lien public copié — prix TTC uniquement, jamais le prix d’achat.')
    } catch {
      toast(lien)
    }
  }

  const columns = [
    { id: 'titre', header: 'Titre', accessor: (r) => r.titre },
    { id: 'produits', header: 'Produits', accessor: (r) => (r.produit_ids || []).length, width: 100 },
    { id: 'expire', header: 'Expire le', accessor: (r) => r.expire_le, searchable: false,
      cell: (v) => (v ? formatDate(v) : 'Jamais') },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'copier', label: 'Copier le lien public', icon: Copy, onClick: () => copierLien(row) },
    { id: 'toggle', label: row.actif ? 'Désactiver' : 'Activer', onClick: () => toggleActif(row) },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Catalogue public</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog(true)}><Plus /> Nouveau catalogue</Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Catalogues publics"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="ecatalogues"
        emptyTitle="Aucun catalogue"
        emptyDescription="Aucun catalogue public généré pour l'instant."
      />

      {dialog && <NouveauCatalogueDialog onClose={() => setDialog(false)} onSaved={list.reload} />}
    </div>
  )
}
