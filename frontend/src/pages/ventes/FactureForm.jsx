import { useState, useEffect, useRef } from 'react'
import { useDispatch } from 'react-redux'
import { Plus, Trash2, AlertTriangle } from 'lucide-react'
import {
  createFacture,
  updateFacture,
  addLigneFacture,
  updateLigneFacture,
  removeLigneFacture,
} from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import {
  Button, IconButton,
  Dialog, DialogContent, DialogHeader, DialogTitle,
  Form, FormField, FormActions, useDirtyGuard, confirmLeaveIfDirty,
  Input, Textarea, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import ProduitPicker from '../../components/ProduitPicker'
import ClientQuickCreateModal from './ClientQuickCreateModal'
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
  taux_tva: '',  // vide = taux global de la facture (N37)
})

const today = new Date().toISOString().slice(0, 10)

export default function FactureForm({ facture = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const isEdit = !!facture

  const [clients, setClients]           = useState([])
  const [produits, setProduits]         = useState([])
  const [bonsCommande, setBonsCommande] = useState([])
  const [saving, setSaving]             = useState(false)
  const [errors, setErrors]             = useState({})
  const [dirty, setDirty]               = useState(false)
  const [clientQuickCreateOpen, setClientQuickCreateOpen] = useState(false)
  useDirtyGuard(dirty)

  const [fields, setFields] = useState({
    client:          facture?.client          ?? '',
    bon_commande:    facture?.bon_commande     ?? '',
    statut:          facture?.statut           ?? 'brouillon',
    date_echeance:   facture?.date_echeance    ?? '',
    date_livraison:  facture?.date_livraison    ?? '',
    conditions_paiement: facture?.conditions_paiement ?? '',
    taux_tva:        String(facture?.taux_tva        ?? '20.00'),
    remise_globale:  String(facture?.remise_globale  ?? '0'),
    statut_teledeclaration: facture?.statut_teledeclaration ?? 'non_soumise',
    note:            facture?.note             ?? '',
  })

  const [lines, setLines] = useState(
    facture?.lignes?.length
      ? facture.lignes.map(l => ({
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
  // VX90 — focus la nouvelle ligne (sélecteur produit) après « Ajouter ligne ».
  const linesTableRef = useRef(null)
  const [pendingFocusKey, setPendingFocusKey] = useState(null)

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
    stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => {})
    ventesApi.getBonsCommande().then(r => setBonsCommande(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // VX90 — après ajout d'une ligne, focaliser son sélecteur produit + défiler.
  useEffect(() => {
    if (pendingFocusKey == null) return
    const row = linesTableRef.current
      ?.querySelector(`[data-line-key="${pendingFocusKey}"]`)
    if (row) {
      row.querySelector('button[type="button"]')?.focus()
      row.scrollIntoView({ block: 'nearest' })
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset one-shot du focus (VX90)
    setPendingFocusKey(null)
  }, [pendingFocusKey, lines])

  // Live totals
  const remGlobal   = parseFloat(fields.remise_globale) || 0
  const tva         = parseFloat(fields.taux_tva) || 0

  const subtotalHT = lines.reduce((sum, l) => {
    const qte = parseFloat(l.quantite)      || 0
    const pu  = parseFloat(l.prix_unitaire) || 0
    const rem = parseFloat(l.remise)        || 0
    return sum + qte * pu * (1 - rem / 100)
  }, 0)

  const totalHT  = subtotalHT * (1 - remGlobal / 100)
  // Ventilation TVA par taux : chaque ligne utilise son taux propre (N37),
  // sinon le taux global de la facture. La remise globale s'applique au prorata.
  const remFactor = subtotalHT > 0 ? totalHT / subtotalHT : (1 - remGlobal / 100)
  const tvaParTaux = lines.reduce((acc, l) => {
    const qte = parseFloat(l.quantite)      || 0
    const pu  = parseFloat(l.prix_unitaire) || 0
    const rem = parseFloat(l.remise)        || 0
    const ligneHT = qte * pu * (1 - rem / 100) * remFactor
    const taux = l.taux_tva !== '' && l.taux_tva != null
      ? (parseFloat(l.taux_tva) || 0)
      : tva
    acc[taux] = (acc[taux] || 0) + ligneHT
    return acc
  }, {})
  const totalTVA = Object.entries(tvaParTaux)
    .reduce((sum, [taux, ht]) => sum + ht * (parseFloat(taux) / 100), 0)
  const totalTTC = totalHT + totalTVA
  const tauxDistincts = Object.keys(tvaParTaux).filter(t => Number(t) > 0)

  const setField = (k, v) => { setDirty(true); setFields(f => ({ ...f, [k]: v })) }

  const onBcChange = async (bcId) => {
    setField('bon_commande', bcId)
    if (!bcId) return
    const bc = bonsCommande.find(b => String(b.id) === String(bcId))
    if (bc) setField('client', String(bc.client))
    // Source unique devis → BC → facture : recopie les lignes du devis lié
    // (produit/désignation/qté/PU/remise/taux_tva) à la création seulement,
    // pour ne pas écraser des lignes déjà saisies en édition.
    if (!isEdit && bc?.devis) {
      try {
        const res = await ventesApi.getDevisById(bc.devis)
        const devisLignes = res.data?.lignes ?? []
        if (devisLignes.length) {
          setDirty(true)
          setLines(devisLignes.map(l => ({
            _key: newKey(),
            id: null,
            produit: String(l.produit),
            designation: l.designation,
            quantite: String(l.quantite),
            prix_unitaire: String(l.prix_unitaire),
            remise: String(l.remise),
            taux_tva: l.taux_tva != null ? String(l.taux_tva) : '',
          })))
        }
      } catch { /* prefill best-effort */ }
    }
  }

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
            // Pré-remplit le taux TVA depuis le produit (10 % panneaux PV,
            // 20 % le reste). Vide si le produit n'a pas de taux → taux global.
            taux_tva: p?.tva != null ? String(p.tva) : l.taux_tva,
          }
        : l
    ))
  }

  const addLine    = () => {
    setDirty(true)
    setLines(ls => {
      const line = emptyLine()
      setPendingFocusKey(line._key) // VX90
      return [...ls, line]
    })
  }
  const removeLine = key => {
    setDirty(true)
    const line = lines.find(l => l._key === key)
    if (line?.id) setRemovedLineIds(ids => [...ids, line.id])
    setLines(ls => ls.filter(l => l._key !== key))
  }

  const validate = () => {
    const e = {}
    if (!fields.client)          e.client = 'Client requis'
    if (lines.length === 0)      e.lines  = 'Au moins une ligne est requise'
    else if (lines.some(l => !l.produit)) e.lines = 'Chaque ligne doit avoir un produit'
    else if (lines.some(l => !(parseFloat(l.quantite) > 0))) e.lines = 'Quantité invalide (doit être > 0)'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        client:         parseInt(fields.client),
        bon_commande:   fields.bon_commande ? parseInt(fields.bon_commande) : null,
        statut:         fields.statut,
        date_echeance:  fields.date_echeance  || null,
        date_livraison: fields.date_livraison || null,
        conditions_paiement: fields.conditions_paiement || '',
        taux_tva:       fields.taux_tva,
        remise_globale: fields.remise_globale,
        statut_teledeclaration: fields.statut_teledeclaration,
        note:           fields.note || null,
      }

      let factureId
      if (isEdit) {
        const res = await dispatch(updateFacture({ id: facture.id, data: payload })).unwrap()
        factureId = res.id
      } else {
        const res = await dispatch(createFacture(payload)).unwrap()
        factureId = res.id
      }

      // Lignes supprimées
      await Promise.all(
        removedLineIds.map(id => dispatch(removeLigneFacture(id)).unwrap())
      )
      // Lignes existantes → update
      await Promise.all(
        lines.filter(l => l.id).map(l =>
          dispatch(updateLigneFacture({
            id: l.id,
            data: {
              facture:       factureId,
              produit:       parseInt(l.produit),
              designation:   l.designation,
              quantite:      l.quantite,
              prix_unitaire: l.prix_unitaire,
              remise:        l.remise,
              taux_tva:      l.taux_tva !== '' ? l.taux_tva : null,
            },
          })).unwrap()
        )
      )
      // Nouvelles lignes → create
      await Promise.all(
        lines.filter(l => !l.id).map(l =>
          dispatch(addLigneFacture({
            facture:       factureId,
            produit:       parseInt(l.produit),
            designation:   l.designation,
            quantite:      l.quantite,
            prix_unitaire: l.prix_unitaire,
            remise:        l.remise,
            taux_tva:      l.taux_tva !== '' ? l.taux_tva : null,
          })).unwrap()
        )
      )

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
    <Dialog open onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose() }}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Éditer — ${facture.reference}` : 'Nouvelle facture'}</DialogTitle>
        </DialogHeader>

        <Form onSubmit={handleSubmit} className="gap-5">
          {/* ── Conformité Article 145 CGI (N29) — AVERTISSEMENT, jamais bloquant ── */}
          {isEdit && Array.isArray(facture.mentions_manquantes)
            && facture.mentions_manquantes.length > 0 && (
            <div role="alert" className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
              <p className="flex items-center gap-1.5 font-semibold">
                <AlertTriangle className="size-4 shrink-0" />
                Conformité Article 145 — mentions légales manquantes :
              </p>
              <ul className="ml-6 mt-1.5 list-disc space-y-0.5">
                {facture.mentions_manquantes.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
              <p className="mt-1.5 text-xs">
                Vous pouvez tout de même émettre la facture — complétez ces
                mentions (Paramètres → Identité, fiche client, lignes) pour
                une facture pleinement conforme.
              </p>
            </div>
          )}

          {/* ── Infos générales ── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FormField label="Client" required htmlFor="fc-client" error={errors.client}>
              <div className="flex gap-2">
                <div className="flex-1">
                  <Select value={fields.client ? String(fields.client) : undefined}
                          onValueChange={v => setField('client', v)}>
                    <SelectTrigger id="fc-client" invalid={!!errors.client}>
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
                </div>
                {/* VX91 — création rapide client (QG3), sans quitter la facture */}
                <Button type="button" variant="outline" onClick={() => setClientQuickCreateOpen(true)}>
                  <Plus /> Nouveau client
                </Button>
              </div>
            </FormField>

            <FormField label="Bon de commande (optionnel)" htmlFor="fc-bc">
              <Select value={fields.bon_commande ? String(fields.bon_commande) : undefined}
                      onValueChange={v => onBcChange(v)}>
                <SelectTrigger id="fc-bc">
                  <SelectValue placeholder="— Aucun BC —" />
                </SelectTrigger>
                <SelectContent>
                  {bonsCommande.map(bc => (
                    <SelectItem key={bc.id} value={String(bc.id)}>
                      {bc.reference} — {bc.client_nom}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>

            <FormField label="Date d'échéance" htmlFor="fc-echeance">
              <Input id="fc-echeance" type="date" value={fields.date_echeance}
                     onChange={e => setField('date_echeance', e.target.value)} />
              {fields.date_echeance && fields.date_echeance < today && (
                <p className="mt-1 text-xs text-warning">
                  Échéance déjà dépassée.
                </p>
              )}
            </FormField>

            <FormField label="Date de livraison/prestation" htmlFor="fc-livraison"
                       hint="Mention Art. 145 — date de la livraison ou prestation">
              <Input id="fc-livraison" type="date" value={fields.date_livraison}
                     onChange={e => setField('date_livraison', e.target.value)} />
            </FormField>

            {isEdit && (
              <FormField label="Statut" htmlFor="fc-statut">
                <Select value={fields.statut} onValueChange={v => setField('statut', v)}>
                  <SelectTrigger id="fc-statut"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="brouillon">Brouillon</SelectItem>
                    <SelectItem value="emise">Émise</SelectItem>
                    <SelectItem value="payee">Payée</SelectItem>
                    <SelectItem value="en_retard">En retard</SelectItem>
                    <SelectItem value="annulee">Annulée</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
            )}

            {isEdit && (
              <FormField label="Télédéclaration DGI" htmlFor="fc-teledecl"
                         hint="Statut DGI — informatif, posé à la main">
                <Select value={fields.statut_teledeclaration}
                        onValueChange={v => setField('statut_teledeclaration', v)}>
                  <SelectTrigger id="fc-teledecl"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="non_soumise">Non soumise</SelectItem>
                    <SelectItem value="soumise">Soumise</SelectItem>
                    <SelectItem value="validee">Validée</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
            )}

            <FormField label="TVA (%)" htmlFor="fc-tva"
                       hint="Taux global (par défaut 20 %). Le taux par ligne prime quand renseigné.">
              <Input id="fc-tva" type="number" min="0" max="100" step="0.01"
                     value={fields.taux_tva} onChange={e => setField('taux_tva', e.target.value)} />
              <div className="mt-1 flex gap-1">
                {['20', '10'].map(t => (
                  <Button key={t} type="button" size="sm"
                          variant={fields.taux_tva === `${t}.00` || fields.taux_tva === t ? 'default' : 'outline'}
                          onClick={() => setField('taux_tva', t)}>
                    {t} %
                  </Button>
                ))}
              </div>
            </FormField>

            <FormField label="Remise globale (%)" htmlFor="fc-remise">
              <Input id="fc-remise" type="number" min="0" max="100" step="0.01"
                     value={fields.remise_globale} onChange={e => setField('remise_globale', e.target.value)} />
            </FormField>
          </div>

          {/* ── Lignes ── */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-base font-semibold text-foreground">Lignes de la facture</h3>
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
              <table className="lines-table" ref={linesTableRef}>
                <thead>
                  <tr>
                    <th style={{ minWidth: 160 }}>Produit</th>
                    <th>Désignation</th>
                    <th className="col-num">Qté</th>
                    <th className="col-num">Prix HT (DH)</th>
                    <th className="col-num">Rem. %</th>
                    <th className="col-num">TVA %</th>
                    <th className="col-num">Total HT</th>
                    <th className="col-del" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map(l => {
                    const lineTotal =
                      (parseFloat(l.quantite)      || 0) *
                      (parseFloat(l.prix_unitaire) || 0) *
                      (1 - (parseFloat(l.remise)   || 0) / 100)
                    return (
                      <tr key={l._key} data-line-key={l._key}>
                        <td data-label="Produit">
                          {/* VX91 — picker partagé (recherche + prix), même
                              composant que DevisForm/DevisGenerator : fin du
                              <Select> natif non filtrable sur 50+ SKU. */}
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
                                 value={l.taux_tva}
                                 placeholder={String(tva)}
                                 title="Vide = taux global de la facture"
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
            {tauxDistincts.length > 1 ? (
              <>
                {tauxDistincts
                  .sort((a, b) => Number(a) - Number(b))
                  .map(taux => (
                    <div key={taux} className="flex justify-between py-0.5">
                      <span className="text-muted-foreground">
                        TVA {Number(taux)} %
                      </span>
                      <span className="tabular-nums">
                        {formatMAD(tvaParTaux[taux] * Number(taux) / 100, { withSymbol: false })} DH
                      </span>
                    </div>
                  ))}
                <div className="flex justify-between py-0.5">
                  <span className="text-muted-foreground">TVA totale</span>
                  <span className="tabular-nums">{formatMAD(totalTVA, { withSymbol: false })} DH</span>
                </div>
              </>
            ) : (
              <div className="flex justify-between py-0.5">
                <span className="text-muted-foreground">TVA ({tva}%)</span>
                <span className="tabular-nums">{formatMAD(totalTVA, { withSymbol: false })} DH</span>
              </div>
            )}
            <div className="mt-1 flex justify-between border-t border-border pt-1.5 text-base">
              <span className="font-semibold">Total TTC</span>
              <strong className="tabular-nums text-primary">{formatMAD(totalTTC, { withSymbol: false })} DH</strong>
            </div>
          </div>

          {/* ── Conditions et mode de paiement (mention Art. 145) ── */}
          <div className="grid gap-1.5">
            <Label htmlFor="fc-conditions">Conditions et mode de paiement</Label>
            <Textarea id="fc-conditions" rows={2} value={fields.conditions_paiement}
                      onChange={e => setField('conditions_paiement', e.target.value)}
                      placeholder="Ex. Virement à 30 jours, RIB…" />
          </div>

          {/* ── Note ── */}
          <div className="grid gap-1.5">
            <Label htmlFor="fc-note">Note interne</Label>
            <Textarea id="fc-note" rows={3} value={fields.note}
                      onChange={e => setField('note', e.target.value)}
                      placeholder="Conditions de paiement, remarques..." />
          </div>

          {errors.submit && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </p>
          )}

          {isEdit && facture?.id && (
            <div className="border-t border-border pt-4">
              <p className="mb-2 text-sm font-semibold text-foreground">Pièces jointes</p>
              <AttachmentsPanel model="ventes.facture" id={facture.id} />
            </div>
          )}

          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>
              {isEdit ? 'Mettre à jour' : 'Créer la facture'}
            </Button>
          </FormActions>
        </Form>

        {/* VX91 — création rapide client (QG3) ; sélectionne le nouveau client */}
        <ClientQuickCreateModal
          open={clientQuickCreateOpen}
          onClose={() => setClientQuickCreateOpen(false)}
          onCreated={(c) => {
            setClients(cs => [...cs, c])
            setField('client', String(c.id))
            setClientQuickCreateOpen(false)
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
