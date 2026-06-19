import { useState, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Plus, X, Star, Trash2, Pencil } from 'lucide-react'
import {
  createProduit,
  updateProduit,
  fetchCategories,
  fetchFournisseurs,
  createCategorie,
  createFournisseur,
} from '../../features/stock/store/stockSlice'
import stockApi from '../../api/stockApi'
import {
  Button, Badge,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormSection, FormField, useDirtyGuard,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { isDirty } from '../../ui/form-utils'

// Traduit une erreur serveur DRF en phrase française lisible (jamais de JSON brut).
function frSubmitError(err) {
  if (!err) return 'Une erreur est survenue. Réessayez.'
  if (typeof err === 'string') return err
  if (err.detail) return err.detail
  if (err.non_field_errors?.[0]) return err.non_field_errors[0]
  if (err.sku?.[0]) {
    return /unique|already exists|existe/i.test(err.sku[0])
      ? 'Ce SKU est déjà utilisé par un autre produit.'
      : `SKU : ${err.sku[0]}`
  }
  // Premier message de champ disponible, sinon repli générique (jamais de JSON).
  for (const v of Object.values(err)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return "L'enregistrement a échoué. Vérifiez les champs et réessayez."
}

// N17 — listes de prix multi-fournisseurs par SKU. Le prix d'achat est INTERNE
// (jamais sur un document client). Le moins cher est proposé en rédigeant un
// bon de commande. Section éditable seulement en mode édition d'un produit.
function PrixFournisseursSection({ produitId, fournisseurs }) {
  const [rows, setRows] = useState([])
  const [fId, setFId] = useState('')
  const [prix, setPrix] = useState('')
  const [error, setError] = useState(null)
  const [editId, setEditId] = useState(null)   // ligne en édition
  const [editPrix, setEditPrix] = useState('')

  const load = () => stockApi.getProduitPrixFournisseurs(produitId)
    .then((r) => setRows(r.data ?? [])).catch(() => {})
  useEffect(() => { load() }, [produitId])  // eslint-disable-line react-hooks/exhaustive-deps

  const sorted = [...rows].sort((a, b) => Number(a.prix_achat) - Number(b.prix_achat))
  const used = new Set(rows.map((r) => String(r.fournisseur)))
  const dispo = (fournisseurs ?? []).filter((f) => !used.has(String(f.id)))
  const moinsCher = sorted.length ? Number(sorted[0].prix_achat) : 0

  const add = () => {
    setError(null)
    const p = parseFloat(prix)
    if (!fId) { setError('Choisissez un fournisseur.'); return }
    if (!Number.isFinite(p) || p <= 0) { setError('Prix d\'achat invalide.'); return }
    // Doublon de fournisseur : interdit (unicité ('produit','fournisseur')).
    if (used.has(String(fId))) {
      setError('Ce fournisseur a déjà un prix pour ce produit — modifiez-le.'); return
    }
    stockApi.createPrixFournisseur({ produit: produitId, fournisseur: fId, prix_achat: p })
      .then(() => { setFId(''); setPrix(''); return load() })
      .catch((e) => setError(e.response?.data?.detail
        ?? (e.response?.data?.fournisseur?.[0] && 'Ce fournisseur a déjà un prix pour ce produit.')
        ?? 'Échec de l\'ajout.'))
  }
  const remove = (id) => stockApi.deletePrixFournisseur(id).then(load).catch(() => {})

  const startEdit = (r) => { setEditId(r.id); setEditPrix(String(r.prix_achat)); setError(null) }
  const cancelEdit = () => { setEditId(null); setEditPrix('') }
  const saveEdit = (id) => {
    const p = parseFloat(editPrix)
    if (!Number.isFinite(p) || p <= 0) { setError('Prix d\'achat invalide.'); return }
    stockApi.updatePrixFournisseur(id, { prix_achat: p })
      .then(() => { cancelEdit(); return load() })
      .catch((e) => setError(e.response?.data?.detail ?? 'Échec de la modification.'))
  }

  // Date du dernier achat au format JJ/MM/AAAA (sinon « — »).
  const fmtAchatDate = (iso) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return Number.isNaN(d.getTime())
      ? '—'
      : d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }

  return (
    <section className="sm:col-span-2 flex flex-col gap-2 border-t border-border pt-4">
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium text-foreground">Prix fournisseurs (interne)</p>
        <p className="text-xs text-muted-foreground">
          Plusieurs fournisseurs possibles ; le moins cher est proposé à la commande.
          Mis à jour automatiquement à la réception d&apos;un bon de commande.
        </p>
      </div>
      {sorted.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[30rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Fournisseur</th>
                <th className="px-3 py-2 text-left font-semibold">Prix d&apos;achat HT</th>
                <th className="px-3 py-2 text-left font-semibold">Dernier achat</th>
                <th className="w-10 px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => {
                const ecart = (i > 0 && moinsCher > 0)
                  ? ((Number(r.prix_achat) - moinsCher) / moinsCher) * 100
                  : null
                return (
                  <tr key={r.id} className="border-t border-border">
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1">
                        {r.fournisseur_nom}
                        {i === 0 && <Star className="size-3.5 fill-warning text-warning" aria-label="Le moins cher" />}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      {editId === r.id ? (
                        <Input type="number" min="0" step="any" inputMode="decimal" className="h-8 w-28"
                               value={editPrix} onChange={(e) => setEditPrix(e.target.value)} />
                      ) : (
                        <span className="inline-flex items-center gap-1.5">
                          {Number(r.prix_achat).toFixed(2)} DH
                          {ecart != null && ecart > 0 && (
                            <span className="text-xs text-warning">+{ecart.toFixed(0)} % vs le moins cher</span>
                          )}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{fmtAchatDate(r.date_dernier_achat)}</td>
                    <td className="px-3 py-2">
                      {editId === r.id ? (
                        <span className="flex gap-1">
                          <Button type="button" variant="outline" size="sm" onClick={() => saveEdit(r.id)}>OK</Button>
                          <Button type="button" variant="ghost" size="sm" onClick={cancelEdit}>×</Button>
                        </span>
                      ) : (
                        <span className="flex gap-0.5">
                          <Button type="button" variant="ghost" size="icon" className="size-7"
                                  aria-label="Modifier le prix" onClick={() => startEdit(r)}>
                            <Pencil className="size-3.5" />
                          </Button>
                          <Button type="button" variant="ghost" size="icon" className="size-7"
                                  aria-label="Supprimer" onClick={() => remove(r.id)}>
                            <Trash2 className="text-destructive" />
                          </Button>
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <Select value={fId || '__none'} onValueChange={(v) => setFId(v === '__none' ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="— Fournisseur —" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none">— Fournisseur —</SelectItem>
              {dispo.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Input type="number" min="0" step="any" inputMode="decimal" className="w-40"
               placeholder="Prix d'achat HT" value={prix} onChange={(e) => setPrix(e.target.value)} />
        <Button type="button" variant="outline" onClick={add}>Ajouter</Button>
      </div>
      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      )}
    </section>
  )
}

export default function ProduitForm({ produit = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const { categories, fournisseurs, produits } = useSelector(s => s.stock)
  const isEdit = !!produit

  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  const [newCatName, setNewCatName] = useState('')
  const [showNewCat, setShowNewCat] = useState(false)
  const [catSaving, setCatSaving] = useState(false)
  const [catError, setCatError] = useState(null)
  const newCatRef = useRef(null)

  const [newFouName, setNewFouName] = useState('')
  const [showNewFou, setShowNewFou] = useState(false)
  const [fouSaving, setFouSaving] = useState(false)
  const [fouError, setFouError] = useState(null)
  const newFouRef = useRef(null)

  const initialFields = {
    nom:            produit?.nom            ?? '',
    sku:            produit?.sku            ?? '',
    description:    produit?.description    ?? '',
    prix_vente:     String(produit?.prix_vente  ?? ''),
    prix_achat:     String(produit?.prix_achat  ?? '0'),
    // Nouveau produit : TVA 20 % par défaut (cas le plus courant) ;
    // l'édition conserve la valeur existante (y compris « Sans TVA »).
    tva:            produit?.tva != null ? String(produit.tva) : (isEdit ? '' : '20'),
    quantite_stock: String(produit?.quantite_stock ?? '0'),
    seuil_alerte:   String(produit?.seuil_alerte  ?? '0'),
    categorie_id:   produit?.categorie?.id  ? String(produit.categorie.id) : '',
    fournisseur_id: produit?.fournisseur?.id ? String(produit.fournisseur.id) : '',
    garantie_mois:            produit?.garantie_mois != null ? String(produit.garantie_mois) : '',
    garantie_production_mois: produit?.garantie_production_mois != null ? String(produit.garantie_production_mois) : '',
  }
  const [initialFieldsSnapshot] = useState(initialFields)
  const [fields, setFields] = useState(initialFields)

  const dirty = isDirty(initialFieldsSnapshot, fields)
  useDirtyGuard(dirty)

  useEffect(() => {
    dispatch(fetchCategories())
    dispatch(fetchFournisseurs())
  }, [dispatch])

  useEffect(() => {
    if (showNewCat) newCatRef.current?.focus()
  }, [showNewCat])

  useEffect(() => {
    if (showNewFou) newFouRef.current?.focus()
  }, [showNewFou])

  const handleCreateCategorie = async () => {
    const nom = newCatName.trim()
    if (!nom) return
    setCatSaving(true)
    setCatError(null)
    try {
      const result = await dispatch(createCategorie({ nom })).unwrap()
      setField('categorie_id', String(result.id))
      setNewCatName('')
      setShowNewCat(false)
    } catch (err) {
      setCatError(err?.nom?.[0] ?? err?.detail ?? 'Erreur lors de la création.')
    } finally {
      setCatSaving(false)
    }
  }

  const handleCreateFournisseur = async () => {
    const nom = newFouName.trim()
    if (!nom) return
    setFouSaving(true)
    setFouError(null)
    try {
      const result = await dispatch(createFournisseur({ nom })).unwrap()
      setField('fournisseur_id', String(result.id))
      setNewFouName('')
      setShowNewFou(false)
    } catch (err) {
      setFouError(err?.nom?.[0] ?? err?.detail ?? 'Erreur lors de la création.')
    } finally {
      setFouSaving(false)
    }
  }

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  // Doublon de SKU détecté localement (unicité ('company','sku') côté serveur).
  // Le serveur reste l'autorité ; ceci évite un aller-retour pour un cas courant.
  const skuTrimmed = fields.sku.trim().toLowerCase()
  const skuDuplicate = skuTrimmed
    ? (produits ?? []).find(
        (p) => p.id !== produit?.id
          && (p.sku ?? '').trim().toLowerCase() === skuTrimmed,
      )
    : null

  const validate = () => {
    const e = {}
    if (!fields.nom.trim())               e.nom        = 'Nom requis'
    if (!fields.prix_vente || isNaN(parseFloat(fields.prix_vente)))
                                           e.prix_vente = 'Prix de vente requis'
    if (skuDuplicate)
      e.sku = `SKU déjà utilisé par « ${skuDuplicate.nom} »`
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        nom:            fields.nom.trim(),
        sku:            fields.sku.trim() || null,
        description:    fields.description.trim() || null,
        prix_vente:     fields.prix_vente,
        prix_achat:     fields.prix_achat,
        tva:            fields.tva !== '' ? parseFloat(fields.tva) : null,
        quantite_stock: parseInt(fields.quantite_stock) || 0,
        seuil_alerte:   parseInt(fields.seuil_alerte)   || 0,
        categorie_id:   fields.categorie_id   ? parseInt(fields.categorie_id)   : null,
        fournisseur_id: fields.fournisseur_id ? parseInt(fields.fournisseur_id) : null,
        garantie_mois:            fields.garantie_mois            !== '' ? parseInt(fields.garantie_mois)            : null,
        garantie_production_mois: fields.garantie_production_mois !== '' ? parseInt(fields.garantie_production_mois) : null,
      }
      if (isEdit) {
        await dispatch(updateProduit({ id: produit.id, data: payload })).unwrap()
      } else {
        await dispatch(createProduit(payload)).unwrap()
      }
      onSaved?.()
      onClose()
    } catch (err) {
      setErrors(prev => ({ ...prev, submit: frSubmitError(err) }))
    } finally {
      setSaving(false)
    }
  }

  // Indicateur de marge — GÉNÉRATEUR/INTERNE uniquement (jamais client-facing).
  const venteN = parseFloat(fields.prix_vente)
  const achatN = parseFloat(fields.prix_achat)
  const tvaN   = fields.tva !== '' ? parseFloat(fields.tva) : null
  const marge  = (venteN > 0 && achatN > 0) ? ((venteN - achatN) / venteN) * 100 : null
  const margeNegative = venteN > 0 && achatN > 0 && venteN < achatN

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Éditer — ${produit.nom}` : 'Nouveau produit'}</DialogTitle>
          <DialogDescription>
            Les prix d&apos;achat et la marge sont internes — jamais sur un document client.
          </DialogDescription>
        </DialogHeader>

        <Form onSubmit={handleSubmit} className="gap-6">
          <FormSection>
            <FormField label="Nom" required htmlFor="pf-nom" error={errors.nom}>
              <Input id="pf-nom" invalid={!!errors.nom} value={fields.nom}
                     onChange={e => setField('nom', e.target.value)} placeholder="Nom du produit" />
            </FormField>
            <FormField label="SKU / Référence" htmlFor="pf-sku" error={errors.sku}>
              <Input id="pf-sku" invalid={!!errors.sku} value={fields.sku}
                     onChange={e => setField('sku', e.target.value)} placeholder="REF-001" />
            </FormField>

            {/* Catégorie (avec création inline) */}
            <FormField label="Catégorie" htmlFor="pf-cat" error={catError}>
              {showNewCat ? (
                <div className="flex gap-1.5">
                  <Input
                    ref={newCatRef}
                    value={newCatName}
                    onChange={e => setNewCatName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreateCategorie() } }}
                    placeholder="Nom de la catégorie"
                  />
                  <Button type="button" loading={catSaving} disabled={!newCatName.trim()}
                          onClick={handleCreateCategorie}>Créer</Button>
                  <Button type="button" variant="outline" size="icon" aria-label="Annuler"
                          onClick={() => { setShowNewCat(false); setNewCatName(''); setCatError(null) }}>
                    <X />
                  </Button>
                </div>
              ) : (
                <div className="flex gap-1.5">
                  <div className="flex-1">
                    <Select value={fields.categorie_id || '__none'}
                            onValueChange={v => setField('categorie_id', v === '__none' ? '' : v)}>
                      <SelectTrigger id="pf-cat"><SelectValue placeholder="— Aucune catégorie —" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none">— Aucune catégorie —</SelectItem>
                        {categories.map(c => <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button type="button" variant="outline" size="icon"
                          aria-label="Créer une nouvelle catégorie" title="Créer une nouvelle catégorie"
                          onClick={() => setShowNewCat(true)}>
                    <Plus />
                  </Button>
                </div>
              )}
            </FormField>

            {/* Fournisseur (avec création inline) */}
            <FormField label="Fournisseur" htmlFor="pf-fou" error={fouError}>
              {showNewFou ? (
                <div className="flex gap-1.5">
                  <Input
                    ref={newFouRef}
                    value={newFouName}
                    onChange={e => setNewFouName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreateFournisseur() } }}
                    placeholder="Nom du fournisseur"
                  />
                  <Button type="button" loading={fouSaving} disabled={!newFouName.trim()}
                          onClick={handleCreateFournisseur}>Créer</Button>
                  <Button type="button" variant="outline" size="icon" aria-label="Annuler"
                          onClick={() => { setShowNewFou(false); setNewFouName(''); setFouError(null) }}>
                    <X />
                  </Button>
                </div>
              ) : (
                <div className="flex gap-1.5">
                  <div className="flex-1">
                    <Select value={fields.fournisseur_id || '__none'}
                            onValueChange={v => setField('fournisseur_id', v === '__none' ? '' : v)}>
                      <SelectTrigger id="pf-fou"><SelectValue placeholder="— Aucun fournisseur —" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none">— Aucun fournisseur —</SelectItem>
                        {fournisseurs.map(f => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button type="button" variant="outline" size="icon"
                          aria-label="Créer un nouveau fournisseur" title="Créer un nouveau fournisseur"
                          onClick={() => setShowNewFou(true)}>
                    <Plus />
                  </Button>
                </div>
              )}
            </FormField>

            <FormField label="Description" htmlFor="pf-desc" fullWidth>
              <Textarea id="pf-desc" rows={2} value={fields.description}
                        onChange={e => setField('description', e.target.value)}
                        placeholder="Description optionnelle…" />
            </FormField>
          </FormSection>

          <FormSection title="Prix & TVA">
            <FormField label="Prix de vente HT" required htmlFor="pf-vente" error={errors.prix_vente}>
              {/* step="any" + saisie libre : ne jamais snapper/rejeter un nombre tapé. */}
              <Input id="pf-vente" type="number" min="0" step="any" inputMode="decimal"
                     invalid={!!errors.prix_vente} value={fields.prix_vente}
                     onChange={e => setField('prix_vente', e.target.value)} />
              {/* Avertissement marge négative — interne, jamais bloquant. */}
              {margeNegative && (
                <p className="mt-1 text-xs text-warning">
                  Marge négative : le prix de vente est inférieur au prix d&apos;achat (interne).
                </p>
              )}
            </FormField>
            <FormField label="Prix d'achat HT" htmlFor="pf-achat" hint="Interne — jamais sur un document client.">
              <Input id="pf-achat" type="number" min="0" step="any" inputMode="decimal"
                     value={fields.prix_achat} onChange={e => setField('prix_achat', e.target.value)} />
            </FormField>
            <FormField label="TVA (%)" htmlFor="pf-tva">
              <Select value={fields.tva || '__none'} onValueChange={v => setField('tva', v === '__none' ? '' : v)}>
                <SelectTrigger id="pf-tva"><SelectValue placeholder="— Sans TVA —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Sans TVA —</SelectItem>
                  <SelectItem value="0">0%</SelectItem>
                  <SelectItem value="7">7%</SelectItem>
                  <SelectItem value="10">10%</SelectItem>
                  <SelectItem value="14">14%</SelectItem>
                  <SelectItem value="20">20%</SelectItem>
                </SelectContent>
              </Select>
            </FormField>

            {/* Récap TVA TTC + marge interne */}
            {(tvaN !== null && venteN > 0) || marge !== null ? (
              <div className="sm:col-span-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {tvaN !== null && venteN > 0 && (
                  <span>
                    Vente TTC : <strong className="text-foreground">{(venteN * (1 + tvaN / 100)).toFixed(2)} DH</strong>
                    {achatN > 0 && <> · Achat TTC : {(achatN * (1 + tvaN / 100)).toFixed(2)} DH</>}
                  </span>
                )}
                {marge !== null && (
                  <Badge tone={marge >= 0 ? 'success' : 'danger'}>
                    Marge {(venteN - achatN).toFixed(2)} DH · {marge.toFixed(1)} % (interne)
                  </Badge>
                )}
              </div>
            ) : null}
          </FormSection>

          <FormSection title="Stock & alerte">
            <FormField
              label="Quantité en stock" htmlFor="pf-qte"
              hint={isEdit ? 'Modifiez via un mouvement de stock' : undefined}
            >
              <Input id="pf-qte" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.quantite_stock}
                     onChange={e => setField('quantite_stock', e.target.value)}
                     disabled={isEdit}
                     title={isEdit ? 'Utilisez un mouvement de stock pour modifier la quantité' : ''} />
            </FormField>
            <FormField label="Seuil d'alerte" htmlFor="pf-seuil">
              <Input id="pf-seuil" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.seuil_alerte}
                     onChange={e => setField('seuil_alerte', e.target.value)} />
            </FormField>
          </FormSection>

          <FormSection
            title="Garantie structurée"
            description="Alimente les horloges de garantie du parc d'équipements. Optionnel."
          >
            <FormField label="Garantie équipement (mois)" htmlFor="pf-gar"
                       hint="Laisser vide si non renseignée.">
              <Input id="pf-gar" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.garantie_mois}
                     onChange={e => setField('garantie_mois', e.target.value)}
                     placeholder="ex : 120 (10 ans)" />
            </FormField>
            <FormField label="Garantie production (mois)" htmlFor="pf-garprod"
                       hint="Pour les panneaux. Optionnel.">
              <Input id="pf-garprod" type="number" min="0" step="1" inputMode="numeric"
                     value={fields.garantie_production_mois}
                     onChange={e => setField('garantie_production_mois', e.target.value)}
                     placeholder="ex : 300 (panneaux, 25 ans)" />
            </FormField>
          </FormSection>

          {isEdit && (
            <PrixFournisseursSection produitId={produit.id} fournisseurs={fournisseurs} />
          )}

          {errors.submit && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </div>
          )}

          <DialogFooter>
            {dirty && <span className="mr-auto text-xs text-warning">Modifications non enregistrées</span>}
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>
              {saving ? 'Enregistrement…' : (isEdit ? 'Mettre à jour' : 'Créer le produit')}
            </Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
