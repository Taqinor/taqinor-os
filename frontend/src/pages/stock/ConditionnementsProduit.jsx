import { useEffect, useMemo, useState } from 'react'
import {
  Plus, PackagePlus,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import fetchAllPages from '../../utils/fetchAllPages'
import {
  Button, FormField, Input, Select, SelectTrigger, SelectValue, SelectContent,
} from '../../ui'
import { TableauStock, OptionsProduits, BoutonsModifierSupprimer } from './ComposantsStock'

import { EnteteStock } from './EnteteStock'
import { AlerteErreurStock } from './BandeauxListeStock'
import usePeutEcrireStock from './usePeutEcrireStock'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
// ASTK231 — confirmations par l'AlertDialog commune (aucune boîte native).
import { useConfirmation } from '../../features/stock/useConfirmation'
import { frErrChamps as frErr } from '../../lib/frErr'
import DialogueFormulaireStock from './DialogueFormulaireStock'
import { soumettreDialogue } from './dialogueStock'

/* WIR109 — XSTK15 : conditionnements d'ACHAT d'un produit (« Touret 100 m »,
   « Carton 50 ») avec leur facteur de conversion vers l'unité de stock. Le
   stock reste stocké dans UNE SEULE unité (jamais de double comptage) :
   recevoir « 2 tourets de 100 m » incrémente 200 m via `facteur`. CRUD
   complet côté serveur, jusqu'ici sans écran. */

function ConditionnementForm({ produits, conditionnement, onClose, onSaved }) {
  const isNew = !conditionnement?.id
  const [fields, setFields] = useState({
    produit: conditionnement?.produit != null ? String(conditionnement.produit) : '',
    nom: conditionnement?.nom ?? '',
    facteur: conditionnement?.facteur != null ? String(conditionnement.facteur) : '',
    code_barres: conditionnement?.code_barres ?? '',
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    if (!fields.produit) { setError('Un produit est requis.'); return }
    if (!fields.nom.trim()) { setError('Le nom est requis.'); return }
    const facteur = Number(fields.facteur)
    if (!facteur || facteur <= 0) { setError('Le facteur doit être positif.'); return }
    await soumettreDialogue({
      setSaving, setError, onSaved, onClose,
      erreur: (err) => frErr(err, "L'enregistrement a échoué."),
      action: async () => {
        const payload = {
          produit: Number(fields.produit),
          nom: fields.nom.trim(),
          facteur,
          code_barres: fields.code_barres.trim() || null,
        }
        if (isNew) await stockApi.createConditionnementProduit(payload)
        else await stockApi.updateConditionnementProduit(conditionnement.id, payload)
      },
    })
  }

  return (
    <DialogueFormulaireStock title={isNew ? 'Nouveau conditionnement' : `Conditionnement — ${conditionnement.nom}`}
      description={<>
            Conditionnement d&apos;achat (touret, carton…), converti vers l&apos;unité de stock du produit.
          </>}
      onClose={onClose}
      onSubmit={submit}
      error={error}
      saving={saving}>
        <FormField label="Produit" required htmlFor="cond-produit" fullWidth>
          <Select value={fields.produit} onValueChange={(v) => setField('produit', v)}>
            <SelectTrigger id="cond-produit"><SelectValue placeholder="Choisir un produit…" /></SelectTrigger>
            <SelectContent>
              <OptionsProduits produits={produits} />
            </SelectContent>
          </Select>
        </FormField>
        <FormField label="Nom" required htmlFor="cond-nom" fullWidth>
          <Input id="cond-nom" placeholder="Ex. Touret 100 m" value={fields.nom}
                 onChange={(e) => setField('nom', e.target.value)} />
        </FormField>
        <FormField label="Facteur (→ unité de stock)" required htmlFor="cond-facteur">
          <Input id="cond-facteur" type="number" step="any" value={fields.facteur}
                 onChange={(e) => setField('facteur', e.target.value)} />
        </FormField>
        <FormField label="Code-barres" htmlFor="cond-code">
          <Input id="cond-code" value={fields.code_barres}
                 onChange={(e) => setField('code_barres', e.target.value)} />
        </FormField>
    </DialogueFormulaireStock>
  )
}

export default function ConditionnementsProduit() {
  const [confirmer, dialogueConfirmation] = useConfirmation()
  const canWrite = usePeutEcrireStock()

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [produits, setProduits] = useState([])
  const [selected, setSelected] = useState(null)

  const reload = () => {
    fetchAllPages((page) => stockApi.getConditionnementsProduit({ ordering: 'produit__nom', page }).then((r) => r.data), { concurrency: 3 })
      .then((rows) => setItems(Array.isArray(rows) ? rows : (rows?.results ?? [])))
      .catch(() => setError('Chargement des conditionnements impossible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
    fetchAllPages((page) => stockApi.getProduits({ ordering: 'nom', page }).then((r) => r.data), { concurrency: 3 })
      .then((rows) => setProduits(Array.isArray(rows) ? rows : (rows?.results ?? [])))
      .catch(() => {})
  }, [])

  const supprimer = async (c) => {
    if (!(await confirmer({ title: `Supprimer le conditionnement « ${c.nom} » ?`, confirmLabel: 'Supprimer' }))) return
    try {
      await stockApi.deleteConditionnementProduit(c.id)
      reload()
    } catch (err) {
      setError(frErr(err, 'Suppression impossible.'))
    }
  }

  const columns = useMemo(() => [
    { id: 'nom', header: 'Conditionnement', minWidth: 160, accessor: (c) => c.nom ?? '' },
    { id: 'produit_nom', header: 'Produit', minWidth: 160, accessor: (c) => c.produit_nom ?? '' },
    { id: 'facteur', header: 'Facteur', align: 'right', width: 100, searchable: false,
      accessor: (c) => c.facteur ?? 0,
      cell: (v, c) => `${v} ${c.unite_stock ?? ''}`.trim() },
    { id: 'code_barres', header: 'Code-barres', minWidth: 120,
      accessor: (c) => c.code_barres ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'actions', header: '', width: 90, searchable: false, sortable: false,
      cell: (_v, c) => (
        canWrite ? (
          <div className="flex items-center justify-end gap-1">
            <BoutonsModifierSupprimer onModifier={() => setSelected(c)}
                                      onSupprimer={() => supprimer(c)} />
          </div>
        ) : null
      ) },
  // canWrite stable au sein d'une session ; reload via closure stable.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `canWrite` stable au sein d'une session ; reload via closure stable (D-ENF22)
  ], [canWrite])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <EnteteStock
        icon={PackagePlus}
        title="Conditionnements produit"
        subtitle="Conditionnements d'achat (touret, carton…) — le stock reste dans une seule unité."
        actions={canWrite ? (
          <Button onClick={() => setSelected({})}>
            <Plus className="size-4" /> Nouveau conditionnement
          </Button>
        ) : null}
      />

      <AlerteErreurStock error={error} />

      <TableauStock items={items} columns={columns} loading={loading}
        searchPlaceholder="Rechercher (conditionnement, produit)…"
        globalColumns={['nom', 'produit_nom']}
        emptyTitle="Aucun conditionnement"
        emptyDescription="Créez-en un avec « Nouveau conditionnement »."
        emptyAction={canWrite
          ? <Button size="sm" onClick={() => setSelected({})}><Plus className="size-4" /> Nouveau conditionnement</Button>
          : undefined}
        aria-label="Conditionnements produit"
      />

      {selected && (
        <ConditionnementForm produits={produits} conditionnement={selected.id ? selected : null}
                             onClose={() => setSelected(null)} onSaved={reload} />
      )}
      {dialogueConfirmation}
    </div>
  )
}
