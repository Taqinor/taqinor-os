import { useState, useEffect } from 'react'
import { useDispatch } from 'react-redux'
import { Plus, Trash2 } from 'lucide-react'
import {
  createDevis,
  updateDevis,
  addLigneDevis,
  updateLigneDevis,
  removeLigneDevis,
} from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import {
  Button, IconButton,
  Dialog, DialogContent, DialogHeader, DialogTitle,
  Form, FormField, FormActions, useDirtyGuard,
  Input, Textarea, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import ProduitPicker from '../../components/ProduitPicker'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import { formatMAD } from '../../lib/format'

let _keyCounter = 0
const newKey = () => ++_keyCounter

const emptyLine = () => ({
  _key: newKey(),
  id: null,
  produit: '',
  designation: '',
  quantite: '1',
  prix_unitaire: '0',
  remise: '0',
  // TVA par ligne (parité avec le générateur) ; vide = taux par défaut du devis.
  taux_tva: '',
})

export default function DevisForm({ devis = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const isEdit = !!devis

  const [clients, setClients] = useState([])
  const [produits, setProduits] = useState([])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const [dirty, setDirty] = useState(false)
  useDirtyGuard(dirty)

  const [fields, setFields] = useState({
    client: devis?.client ?? '',
    statut: devis?.statut ?? 'brouillon',
    date_validite: devis?.date_validite ?? '',
    taux_tva: String(devis?.taux_tva ?? '20.00'),
    remise_globale: String(devis?.remise_globale ?? '0'),
    note: devis?.note ?? '',
  })

  const [lines, setLines] = useState(
    devis?.lignes?.length
      ? devis.lignes.map(l => ({
          _key: newKey(),
          id: l.id,
          produit: String(l.produit),
          designation: l.designation,
          quantite: String(l.quantite),
          prix_unitaire: String(l.prix_unitaire),
          remise: String(l.remise),
          taux_tva: l.taux_tva != null ? String(l.taux_tva) : '',
        }))
      : [emptyLine()]
  )

  const [removedLineIds, setRemovedLineIds] = useState([])

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
    stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // Live totals
  const remGlobal = parseFloat(fields.remise_globale) || 0
  const tva = parseFloat(fields.taux_tva) || 0

  // HT net par ligne (après remise de ligne).
  const lineNetHT = (l) => {
    const qte = parseFloat(l.quantite) || 0
    const pu = parseFloat(l.prix_unitaire) || 0
    const rem = parseFloat(l.remise) || 0
    return qte * pu * (1 - rem / 100)
  }

  const subtotalHT = lines.reduce((sum, l) => sum + lineNetHT(l), 0)

  const totalHT = subtotalHT * (1 - remGlobal / 100)
  // TVA calculée par ligne : taux de la ligne s'il est renseigné, sinon le taux
  // par défaut du devis (parité avec le générateur multi-taux). La remise
  // globale est appliquée proportionnellement à chaque ligne.
  const totalTVA = lines.reduce((sum, l) => {
    const rate = l.taux_tva !== '' && l.taux_tva != null
      ? (parseFloat(l.taux_tva) || 0)
      : tva
    return sum + lineNetHT(l) * (1 - remGlobal / 100) * (rate / 100)
  }, 0)
  const totalTTC = totalHT + totalTVA

  const setField = (k, v) => { setDirty(true); setFields(f => ({ ...f, [k]: v })) }

  const setLine = (key, k, v) => {
    setDirty(true)
    setLines(ls => ls.map(l => l._key === key ? { ...l, [k]: v } : l))
  }

  const onProduitChange = (key, produitId) => {
    setDirty(true)
    const p = produits.find(p => String(p.id) === String(produitId))
    setLines(ls => ls.map(l =>
      l._key === key
        ? {
            ...l, produit: produitId, designation: p?.nom ?? '',
            prix_unitaire: p ? String(p.prix_vente) : '0',
            // Copie le taux TVA du produit s'il est défini (réforme 10/20 %).
            taux_tva: p?.tva != null ? String(p.tva) : l.taux_tva,
          }
        : l
    ))
  }

  const addLine = () => { setDirty(true); setLines(ls => [...ls, emptyLine()]) }

  const removeLine = key => {
    setDirty(true)
    const line = lines.find(l => l._key === key)
    if (line?.id) setRemovedLineIds(ids => [...ids, line.id])
    setLines(ls => ls.filter(l => l._key !== key))
  }

  const validate = () => {
    const e = {}
    if (!fields.client) e.client = 'Client requis'
    if (lines.length === 0) {
      e.lines = 'Au moins une ligne est requise'
    } else if (lines.some(l => !l.produit)) {
      e.lines = 'Chaque ligne doit avoir un produit sélectionné'
    } else if (lines.some(l => !(parseFloat(l.quantite) > 0))) {
      e.lines = 'La quantité doit être supérieure à 0'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        client: parseInt(fields.client),
        statut: fields.statut,
        date_validite: fields.date_validite || null,
        taux_tva: fields.taux_tva,
        remise_globale: fields.remise_globale,
        note: fields.note || null,
      }

      let devisId
      if (isEdit) {
        const res = await dispatch(updateDevis({ id: devis.id, data: payload })).unwrap()
        devisId = res.id
      } else {
        const res = await dispatch(createDevis(payload)).unwrap()
        devisId = res.id
      }

      // Delete removed lines
      await Promise.all(
        removedLineIds.map(id => dispatch(removeLigneDevis(id)).unwrap())
      )

      // Update existing lines (those that came from server)
      const existingLines = lines.filter(l => l.id)
      await Promise.all(existingLines.map(l =>
        dispatch(updateLigneDevis({
          id: l.id,
          data: {
            devis: devisId,
            produit: parseInt(l.produit),
            designation: l.designation,
            quantite: l.quantite,
            prix_unitaire: l.prix_unitaire,
            remise: l.remise,
            taux_tva: l.taux_tva !== '' ? l.taux_tva : null,
          },
        })).unwrap()
      ))

      // Create new lines
      const newLines = lines.filter(l => !l.id)
      await Promise.all(newLines.map(l =>
        dispatch(addLigneDevis({
          devis: devisId,
          produit: parseInt(l.produit),
          designation: l.designation,
          quantite: l.quantite,
          prix_unitaire: l.prix_unitaire,
          remise: l.remise,
          taux_tva: l.taux_tva !== '' ? l.taux_tva : null,
        })).unwrap()
      ))

      setDirty(false)
      onSaved?.()
      onClose()
    } catch (err) {
      const msg = err?.detail ?? err?.non_field_errors?.[0] ?? JSON.stringify(err)
      setErrors(prev => ({ ...prev, submit: msg }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Éditer — ${devis.reference}` : 'Nouveau devis'}</DialogTitle>
        </DialogHeader>

        <Form onSubmit={handleSubmit} className="gap-5">
          {/* ── Infos générales ── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FormField label="Client" required htmlFor="dv-client" error={errors.client}>
              <Select value={fields.client ? String(fields.client) : undefined}
                      onValueChange={v => setField('client', v)}>
                <SelectTrigger id="dv-client" invalid={!!errors.client}>
                  <SelectValue placeholder="— Sélectionner un client —" />
                </SelectTrigger>
                <SelectContent>
                  {clients.map(c => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>

            <FormField label="Date de validité" htmlFor="dv-validite">
              <Input id="dv-validite" type="date" value={fields.date_validite}
                     onChange={e => setField('date_validite', e.target.value)} />
            </FormField>

            {isEdit && (
              <FormField label="Statut" htmlFor="dv-statut">
                <Select value={fields.statut} onValueChange={v => setField('statut', v)}>
                  <SelectTrigger id="dv-statut"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="brouillon">Brouillon</SelectItem>
                    <SelectItem value="envoye">Envoyé</SelectItem>
                    <SelectItem value="accepte">Accepté</SelectItem>
                    <SelectItem value="refuse">Refusé</SelectItem>
                    <SelectItem value="expire">Expiré</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
            )}

            <FormField label="TVA (%)" htmlFor="dv-tva">
              <Input id="dv-tva" type="number" min="0" max="100" step="0.01"
                     value={fields.taux_tva} onChange={e => setField('taux_tva', e.target.value)} />
            </FormField>

            <FormField label="Remise globale (%)" htmlFor="dv-remise">
              <Input id="dv-remise" type="number" min="0" max="100" step="0.01"
                     value={fields.remise_globale} onChange={e => setField('remise_globale', e.target.value)} />
            </FormField>
          </div>

          {/* ── Lignes ── */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-base font-semibold text-foreground">Lignes du devis</h3>
              <Button type="button" size="sm" variant="outline" onClick={addLine}>
                <Plus /> Ajouter une ligne
              </Button>
            </div>

            {errors.lines && (
              <p role="alert" className="text-xs text-destructive">{errors.lines}</p>
            )}

            {/* VX184 — même comportement mobile que le générateur : `.lines-table`
                bascule en cartes empilées sous 768px via `data-label`
                (index.css ~2264-2296), au lieu du scroll horizontal permanent. */}
            <div className="lines-table-wrap">
              <table className="lines-table">
                <thead>
                  <tr>
                    <th style={{ minWidth: 160 }}>Produit</th>
                    <th>Désignation</th>
                    <th className="col-num">Qté</th>
                    <th className="col-num">Prix HT (DH)</th>
                    <th className="col-num">Rem. %</th>
                    <th className="col-num" title="Taux TVA de la ligne (vide = taux du devis)">TVA %</th>
                    <th className="col-num">Total HT</th>
                    <th className="col-del" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map(l => {
                    const lineTotal =
                      (parseFloat(l.quantite) || 0) *
                      (parseFloat(l.prix_unitaire) || 0) *
                      (1 - (parseFloat(l.remise) || 0) / 100)
                    return (
                      <tr key={l._key}>
                        <td data-label="Produit">
                          {/* Picker partagé (recherche + prix) — même composant
                              que le générateur, fin de la divergence des deux
                              éditeurs sur la sélection produit. */}
                          <ProduitPicker
                            produits={produits}
                            value={l.produit ? String(l.produit) : ''}
                            onChange={v => onProduitChange(l._key, v)}
                          />
                        </td>
                        <td data-label="Désignation">
                          <Input className="h-[var(--control-h-sm)] text-xs" value={l.designation}
                                 onChange={e => setLine(l._key, 'designation', e.target.value)}
                                 placeholder="Désignation" />
                        </td>
                        <td data-label="Qté">
                          <Input type="number" min="0.01" step="0.01"
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 value={l.quantite}
                                 onChange={e => setLine(l._key, 'quantite', e.target.value)} />
                        </td>
                        <td data-label="Prix HT (DH)">
                          <Input type="number" min="0" step="0.01"
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 value={l.prix_unitaire}
                                 onChange={e => setLine(l._key, 'prix_unitaire', e.target.value)} />
                        </td>
                        <td data-label="Rem. %">
                          <Input type="number" min="0" max="100" step="0.01"
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 value={l.remise}
                                 onChange={e => setLine(l._key, 'remise', e.target.value)} />
                        </td>
                        <td data-label="TVA %">
                          <Input type="number" min="0" max="100" step="0.01"
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 placeholder={String(tva)}
                                 value={l.taux_tva}
                                 onChange={e => setLine(l._key, 'taux_tva', e.target.value)} />
                        </td>
                        <td className="line-total" data-label="Total HT">{formatMAD(lineTotal, { withSymbol: false })} DH</td>
                        <td>
                          {lines.length > 1 && (
                            <IconButton type="button" label="Supprimer la ligne" size="sm"
                                        className="text-destructive hover:bg-destructive/10"
                                        onClick={() => removeLine(l._key)}>
                              <Trash2 />
                            </IconButton>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── Totaux ── */}
          <div className="ml-auto w-full max-w-xs rounded-lg border border-border bg-muted/30 p-3 text-sm">
            <div className="flex justify-between py-0.5">
              <span className="text-muted-foreground">Sous-total HT</span>
              <span className="tabular-nums">{formatMAD(subtotalHT, { withSymbol: false })} DH</span>
            </div>
            {remGlobal > 0 && (
              <div className="flex justify-between py-0.5 text-warning">
                <span>Remise globale ({remGlobal}%)</span>
                <span className="tabular-nums">−{formatMAD(subtotalHT * remGlobal / 100, { withSymbol: false })} DH</span>
              </div>
            )}
            <div className="flex justify-between py-0.5">
              <span className="text-muted-foreground">Total HT</span>
              <strong className="tabular-nums">{formatMAD(totalHT, { withSymbol: false })} DH</strong>
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-muted-foreground">TVA ({tva}%)</span>
              <span className="tabular-nums">{formatMAD(totalTVA, { withSymbol: false })} DH</span>
            </div>
            <div className="mt-1 flex justify-between border-t border-border pt-1.5 text-base">
              <span className="font-semibold">Total TTC</span>
              <strong className="tabular-nums text-primary">{formatMAD(totalTTC, { withSymbol: false })} DH</strong>
            </div>
          </div>

          {/* ── Note ── */}
          <div className="grid gap-1.5">
            <Label htmlFor="dv-note">Note interne</Label>
            <Textarea id="dv-note" rows={3} value={fields.note}
                      onChange={e => setField('note', e.target.value)}
                      placeholder="Conditions de paiement, remarques..." />
          </div>

          {errors.submit && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </p>
          )}

          {isEdit && devis?.id && (
            <div className="border-t border-border pt-4">
              <p className="mb-2 text-sm font-semibold text-foreground">Pièces jointes</p>
              <AttachmentsPanel model="ventes.devis" id={devis.id} />
            </div>
          )}

          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>
              {isEdit ? 'Mettre à jour' : 'Créer le devis'}
            </Button>
          </FormActions>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
