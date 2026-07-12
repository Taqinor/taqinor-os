import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, LayoutTemplate, Trash2, PlayCircle } from 'lucide-react'
import stockApi from '../../api/stockApi'
import BcfProduitPicker from './BcfProduitPicker'
import {
  Button, IconButton, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

// ZPUR3 — Modèles de bon de commande fournisseur (« purchase templates ») :
// un nom + fournisseur optionnel + lignes produit/quantité par défaut.
// L'action « Générer » matérialise un BCF BROUILLON pré-rempli, éditable
// avant envoi. Le modèle lui-même ne bouge jamais aucun stock/mouvement.

function frErr(err, fallback = 'Une erreur est survenue. Réessayez.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

// ── Modal de création / édition d'un modèle ─────────────────────────────────
export function ModeleDetail({ modele, fournisseurs, produits, onClose, onSaved }) {
  const isNew = !modele?.id
  const [nom, setNom] = useState(modele?.nom ?? '')
  const [fournisseur, setFournisseur] = useState(modele?.fournisseur ?? '')
  const [note, setNote] = useState(modele?.note ?? '')
  const [lignes, setLignes] = useState((modele?.lignes ?? []).map((l) => ({ ...l })))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const setLigne = (idx, patch) =>
    setLignes((ls) => ls.map((l, i) => (i === idx ? { ...l, ...patch } : l)))
  const addLigne = () => setLignes((ls) => [...ls, { produit: '', quantite: 1 }])
  const removeLigne = (idx) => setLignes((ls) => ls.filter((_, i) => i !== idx))

  const save = async () => {
    setError(null)
    if (!nom.trim()) { setError('Le nom du modèle est requis.'); return }
    const payloadLignes = lignes
      .filter((l) => l.produit)
      .map((l) => ({ produit: Number(l.produit), quantite: Number(l.quantite) || 1 }))
    if (payloadLignes.length === 0) { setError('Ajoutez au moins une ligne.'); return }
    const payload = {
      nom: nom.trim(),
      fournisseur: fournisseur || null,
      note: note || null,
      lignes: payloadLignes,
    }
    setBusy(true)
    try {
      if (isNew) await stockApi.createModeleBcf(payload)
      else await stockApi.updateModeleBcf(modele.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frErr(err, "L'enregistrement du modèle a échoué."))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Nouveau modèle de BCF' : `Modèle — ${modele.nom}`}</DialogTitle>
          <DialogDescription>
            Un modèle réutilisable de bon de commande fournisseur : lignes produit/
            quantité par défaut, matérialisées en un BCF brouillon via « Générer ».
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="modele-nom">Nom du modèle</label>
            <Input id="modele-nom" value={nom} onChange={(e) => setNom(e.target.value)}
                   placeholder="ex. Réassort mensuel panneaux" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="modele-fou">Fournisseur par défaut (optionnel)</label>
            <Select value={fournisseur ? String(fournisseur) : '__none'}
                    onValueChange={(v) => setFournisseur(v === '__none' ? '' : v)}>
              <SelectTrigger id="modele-fou"><SelectValue placeholder="— Aucun —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Aucun —</SelectItem>
                {fournisseurs.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold">Lignes</span>
            <Button type="button" variant="outline" size="sm" onClick={addLigne}>
              <Plus /> Ajouter une ligne
            </Button>
          </div>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold" style={{ minWidth: 220 }}>Produit</th>
                  <th className="px-3 py-2 text-left font-semibold">Quantité par défaut</th>
                  <th className="w-10 px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {lignes.length === 0 && (
                  <tr><td colSpan={3} className="px-3 py-3 text-sm text-muted-foreground">Aucune ligne.</td></tr>
                )}
                {lignes.map((l, idx) => (
                  <tr key={l.id ?? `new-${idx}`} className="border-t border-border">
                    <td className="px-3 py-2">
                      <BcfProduitPicker produits={produits} value={l.produit}
                                        onChange={(v) => setLigne(idx, { produit: v })} />
                    </td>
                    <td className="px-3 py-2">
                      <Input type="number" step="1" min="1" inputMode="numeric" className="h-9 w-24"
                             value={l.quantite ?? ''}
                             onChange={(e) => setLigne(idx, { quantite: e.target.value })} />
                    </td>
                    <td className="px-3 py-2">
                      <IconButton label="Retirer la ligne" variant="ghost" size="icon" className="size-8"
                                  onClick={() => removeLigne(idx)}>
                        <Trash2 className="text-destructive" />
                      </IconButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="modele-note">Note</label>
          <Textarea id="modele-note" rows={2} value={note ?? ''} onChange={(e) => setNote(e.target.value)} />
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          <Button type="button" loading={busy} onClick={save}>
            {busy ? '…' : 'Enregistrer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Modal de génération : choisit un fournisseur si le modèle n'en a pas ────
function GenererModal({ modele, fournisseurs, onClose, onGenere }) {
  const [fournisseur, setFournisseur] = useState(modele?.fournisseur ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const generer = async () => {
    setError(null)
    if (!fournisseur) { setError('Choisissez un fournisseur.'); return }
    setBusy(true)
    try {
      const r = await stockApi.genererModeleBcf(modele.id, fournisseur)
      onGenere?.(r.data)
      onClose()
    } catch (err) {
      setError(frErr(err, 'La génération du bon de commande a échoué.'))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Générer un BCF depuis « {modele?.nom} »</DialogTitle>
          <DialogDescription>
            Matérialise un bon de commande BROUILLON pré-rempli depuis les lignes du modèle,
            éditable avant envoi.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="gen-fou">Fournisseur</label>
          <Select value={fournisseur ? String(fournisseur) : '__none'}
                  onValueChange={(v) => setFournisseur(v === '__none' ? '' : v)}>
            <SelectTrigger id="gen-fou"><SelectValue placeholder="— Choisir un fournisseur —" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none">— Choisir un fournisseur —</SelectItem>
              {fournisseurs.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
          <Button type="button" loading={busy} onClick={generer}>
            {busy ? '…' : 'Générer le BCF'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ModelesBcf() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [fournisseurs, setFournisseurs] = useState([])
  const [produits, setProduits] = useState([])
  const [selected, setSelected] = useState(null)
  const [genererFor, setGenererFor] = useState(null)
  const [info, setInfo] = useState(null)

  const reload = () => {
    stockApi.getModelesBcf()
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
    stockApi.getFournisseurs().then((r) => setFournisseurs(r.data?.results ?? r.data ?? [])).catch(() => {})
    stockApi.getProduits({ page_size: 1000 }).then((r) => setProduits(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  const openModele = async (m) => {
    try {
      const r = await stockApi.getModeleBcf(m.id)
      setSelected(r.data)
    } catch { setSelected(m) }
  }

  const supprimer = useCallback(async (m) => {
    if (!window.confirm(`Supprimer le modèle « ${m.nom} » ?`)) return
    try {
      await stockApi.deleteModeleBcf(m.id)
      reload()
    } catch { setInfo('La suppression a échoué.') }
  }, [])

  const columns = useMemo(() => [
    { id: 'nom', header: 'Nom', minWidth: 200, accessor: (m) => m.nom ?? '' },
    { id: 'fournisseur_nom', header: 'Fournisseur par défaut', minWidth: 160,
      accessor: (m) => m.fournisseur_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'lignes', header: 'Lignes', align: 'right', width: 90, searchable: false,
      accessor: (m) => (m.lignes ?? []).length },
    { id: 'actions', header: '', width: 220, searchable: false, sortable: false,
      accessor: () => '',
      cell: (_v, m) => (
        <div className="flex items-center justify-end gap-1.5">
          <Button type="button" variant="outline" size="sm"
                  onClick={(e) => { e.stopPropagation(); setGenererFor(m) }}>
            <PlayCircle /> Générer un BCF
          </Button>
          <IconButton label="Supprimer le modèle" variant="ghost" size="icon" className="size-8"
                      onClick={(e) => { e.stopPropagation(); supprimer(m) }}>
            <Trash2 className="text-destructive" />
          </IconButton>
        </div>
      ) },
  ], [supprimer])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          <LayoutTemplate className="size-5 text-muted-foreground" aria-hidden="true" />
          <div>
            <h1 className="font-display text-xl font-semibold tracking-tight">Modèles de bon de commande</h1>
            <p className="text-sm text-muted-foreground">{items.length} modèle(s)</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => navigate('/stock/bons-commande-fournisseur')}>
            Bons de commande
          </Button>
          <Button onClick={() => setSelected({})}>
            <Plus /> Nouveau modèle
          </Button>
        </div>
      </header>

      {info && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {info}
        </div>
      )}

      <DataTable
        data={items}
        columns={columns}
        loading={loading}
        getRowId={(m) => m.id}
        searchPlaceholder="Rechercher (nom, fournisseur)…"
        globalColumns={['nom', 'fournisseur_nom']}
        onRowClick={openModele}
        emptyTitle="Aucun modèle de bon de commande"
        emptyDescription="Créez-en un pour réutiliser rapidement une liste d'articles récurrente."
        emptyAction={<Button size="sm" onClick={() => setSelected({})}><Plus className="size-4" /> Nouveau modèle</Button>}
        aria-label="Modèles de bon de commande fournisseur"
      />

      {selected && (
        <ModeleDetail modele={selected} fournisseurs={fournisseurs} produits={produits}
                      onClose={() => setSelected(null)} onSaved={reload} />
      )}
      {genererFor && (
        <GenererModal modele={genererFor} fournisseurs={fournisseurs}
                      onClose={() => setGenererFor(null)}
                      onGenere={(bcf) => {
                        // Le BCF brouillon généré s'ouvre directement dans l'écran
                        // des bons de commande (édition avant envoi).
                        navigate('/stock/bons-commande-fournisseur', {
                          state: { ouvrirBcfId: bcf?.id ?? null },
                        })
                      }} />
      )}
    </div>
  )
}
