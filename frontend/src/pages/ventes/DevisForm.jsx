import { useState, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import { History, Plus, Trash2 } from 'lucide-react'
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
  Form, FormField, FormActions, useDirtyGuard, confirmLeaveIfDirty,
  Input, Textarea, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import ProduitPicker from '../../components/ProduitPicker'
import ClientQuickCreateModal from './ClientQuickCreateModal'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import { useHasPermission } from '../../hooks/useHasPermission'
import { useServerFieldErrors } from '../../hooks/useServerFieldErrors'
import { formatMAD, timeAgo } from '../../lib/format'
import QuoteTotalsSummary from '../../features/ventes/QuoteTotalsSummary'

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
  // VX98 — puce de fraîcheur + lien Journal. Le chip reste SILENCIEUX si le
  // dernier auteur est l'utilisateur courant (« mon propre edit ») ou si null.
  const currentUsername = useSelector((s) => s.auth?.user?.username)
  const canViewJournal = useHasPermission('journal_activite_voir')
  const freshBy = devis?.updated_by_nom
  const freshAt = devis?.updated_at
  const showFreshness = !!(freshBy && freshBy !== currentUsername)

  const [clients, setClients] = useState([])
  const [produits, setProduits] = useState([])
  const [saving, setSaving] = useState(false)
  // VX171 — vérité serveur → champ ; le rouge s'efface à la frappe.
  const { errors, setErrors, setFromResponse, clearField } = useServerFieldErrors()
  const [dirty, setDirty] = useState(false)
  const [clientQuickCreateOpen, setClientQuickCreateOpen] = useState(false)
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
  // VX90 — focus la nouvelle ligne (ProduitPicker) après « Ajouter ligne ».
  const linesTableRef = useRef(null)
  const [pendingFocusKey, setPendingFocusKey] = useState(null)

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
    stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // VX90 — après ajout d'une ligne, focaliser son sélecteur produit + la faire
  // défiler dans la vue (ref-walk DOM par data-line-key).
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

  // VX171 — le rouge ne doit jamais mentir pendant que l'utilisateur corrige.
  const setField = (k, v) => { setDirty(true); clearField(k); setFields(f => ({ ...f, [k]: v })) }

  const setLine = (key, k, v) => {
    setDirty(true)
    clearField('lines')
    setLines(ls => ls.map(l => l._key === key ? { ...l, [k]: v } : l))
  }

  const onProduitChange = (key, produitId) => {
    setDirty(true)
    clearField('lines')
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

  const addLine = () => {
    setDirty(true)
    clearField('lines')
    setLines(ls => {
      const line = emptyLine()
      setPendingFocusKey(line._key) // VX90
      return [...ls, line]
    })
  }

  const removeLine = key => {
    setDirty(true)
    clearField('lines')
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
      // VX171 — mapping DRF générique (detail / {champ:[…]} / array) : chaque
      // champ en erreur vire rouge, plus un toast anonyme.
      setFromResponse(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose() }}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Éditer — ${devis.reference}` : 'Nouveau devis'}</DialogTitle>
          {isEdit && (showFreshness || canViewJournal) && (
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs">
              {/* VX98 — puce de fraîcheur : silencieuse sur mon propre edit / si null. */}
              {showFreshness && (
                <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/40 px-2 py-0.5 text-muted-foreground">
                  <History className="size-3" aria-hidden="true" />
                  modifié par {freshBy}{freshAt ? ` ${timeAgo(freshAt)}` : ''}
                </span>
              )}
              {/* VX98 — 1 clic → Journal pré-filtré sur CE devis (permission requise). */}
              {canViewJournal && (
                <Link
                  to={`/journal?model=devis&object_id=${devis.id}`}
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <History className="size-3" aria-hidden="true" /> Historique
                </Link>
              )}
            </div>
          )}
        </DialogHeader>

        <Form onSubmit={handleSubmit} className="gap-5">
          {/* ── Infos générales ── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FormField label="Client" required htmlFor="dv-client" error={errors.client}>
              <div className="flex gap-2">
                <div className="flex-1">
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
                </div>
                {/* VX91 — création rapide client (QG3), sans quitter le devis */}
                <Button type="button" variant="outline" onClick={() => setClientQuickCreateOpen(true)}>
                  <Plus /> Nouveau client
                </Button>
              </div>
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
              <table className="lines-table" ref={linesTableRef}>
                <thead>
                  <tr>
                    <th style={{ minWidth: 160 }}>Produit</th>
                    <th>Désignation</th>
                    <th className="col-num">Qté</th>
                    <th className="col-num">Prix HT</th>
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
                      <tr key={l._key} data-line-key={l._key}>
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
                        <td data-label="Prix HT">
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
                        <td className="line-total" data-label="Total HT">{formatMAD(lineTotal)}</td>
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

          {/* ── Totaux (VX139 — bloc partagé avec le générateur, une seule devise) ── */}
          <QuoteTotalsSummary
            subtotalHT={subtotalHT}
            remiseLabel={`Remise globale (${remGlobal}%)`}
            remiseMontant={remGlobal > 0 ? subtotalHT * remGlobal / 100 : 0}
            totalHT={totalHT}
            tauxTva={tva}
            totalTVA={totalTVA}
            totalTTC={totalTTC}
          />

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
