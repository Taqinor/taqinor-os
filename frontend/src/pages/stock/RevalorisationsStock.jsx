import { useEffect, useState } from 'react'
import { useIsAdmin } from '../../hooks/useHasPermission'
import { Plus, CheckCircle2, Trash2, TrendingUp,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import {
  Button, IconButton, Badge, FormField, Input, Textarea, Select, SelectTrigger,
  SelectValue, SelectContent,
} from '../../ui'
import { EnteteStock, ReserveAdminStock } from './EnteteStock'
import { ListeStock } from './BandeauxListeStock'
import { OptionsProduits } from './ComposantsStock'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
// ASTK231 — confirmations par l'AlertDialog commune (aucune boîte native).
import { useConfirmation } from '../../features/stock/useConfirmation'
import { frErrDetail as frErr } from '../../lib/frErr'
import DialogueFormulaireStock from './DialogueFormulaireStock'

/* WIR109 — XSTK14 : revalorisation manuelle du stock (document tracé,
   admin-only, jamais client-facing). Corrige le COÛT MOYEN d'un produit sans
   bidouiller les réceptions ; à la validation le document est VERROUILLÉ
   (jamais modifié/supprimé ensuite). */

const STATUT_LABELS = { brouillon: 'Brouillon', validee: 'Validée' }
const STATUT_TONE = { brouillon: 'muted', validee: 'success' }

function RevalorisationForm({ produits, onClose, onSaved }) {
  const [produitId, setProduitId] = useState('')
  const [nouveauCout, setNouveauCout] = useState('')
  const [motif, setMotif] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    if (!produitId) { setError('Un produit est requis.'); return }
    if (!motif.trim()) { setError('Le motif est requis.'); return }
    const cout = Number(nouveauCout)
    if (nouveauCout === '' || Number.isNaN(cout) || cout < 0) {
      setError('Le nouveau coût doit être un nombre positif ou nul.'); return
    }
    setSaving(true)
    setError(null)
    try {
      await stockApi.createRevalorisationStock({
        produit: Number(produitId), nouveau_cout: cout, motif: motif.trim(),
      })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frErr(err, "La création a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <DialogueFormulaireStock title="Nouvelle revalorisation"
      description={<>
            Corrige le coût moyen d&apos;un produit (dépréciation, baisse de prix
            mondiale…). Donnée interne, jamais sur un document client.
          </>}
      onClose={onClose}
      onSubmit={submit}
      error={error}
      saving={saving}
      libelle="Créer">
        <FormField label="Produit" required htmlFor="revalo-produit" fullWidth>
          <Select value={produitId} onValueChange={setProduitId}>
            <SelectTrigger id="revalo-produit"><SelectValue placeholder="Choisir un produit…" /></SelectTrigger>
            <SelectContent>
              <OptionsProduits produits={produits} />
            </SelectContent>
          </Select>
        </FormField>
        <FormField label="Nouveau coût (MAD)" required htmlFor="revalo-cout">
          <Input id="revalo-cout" type="number" step="any" value={nouveauCout}
                 onChange={(e) => setNouveauCout(e.target.value)} />
        </FormField>
        <FormField label="Motif" required htmlFor="revalo-motif" fullWidth>
          <Textarea id="revalo-motif" rows={2} value={motif}
                    onChange={(e) => setMotif(e.target.value)} />
        </FormField>
    </DialogueFormulaireStock>
  )
}

export default function RevalorisationsStock() {
  const [confirmer, dialogueConfirmation] = useConfirmation()
  const isAdmin = useIsAdmin()

  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [produits, setProduits] = useState([])
  const [showForm, setShowForm] = useState(false)

  const reload = () => {
    stockApi.getRevalorisationsStock({ ordering: '-date_creation' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des revalorisations impossible.'))
  }

  useEffect(() => {
    reload()
    stockApi.getProduits({ ordering: 'nom' })
      .then((r) => setProduits(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const valider = async (r) => {
    if (!(await confirmer({
      title: 'Valider cette revalorisation ?', description: 'Le document sera verrouillé.',
      confirmLabel: 'Valider', severity: 'low',
    }))) return
    try {
      await stockApi.validerRevalorisationStock(r.id)
      reload()
    } catch (err) {
      setError(frErr(err, 'La validation a échoué.'))
    }
  }

  const supprimer = async (r) => {
    if (!(await confirmer({ title: 'Supprimer ce brouillon de revalorisation ?', confirmLabel: 'Supprimer' }))) return
    try {
      await stockApi.deleteRevalorisationStock(r.id)
      reload()
    } catch (err) {
      setError(frErr(err, 'Suppression impossible.'))
    }
  }

  if (!isAdmin) return <ReserveAdminStock />

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <EnteteStock
        icon={TrendingUp}
        title="Revalorisations de stock"
        subtitle="Document tracé — corrige le coût moyen d'un produit. Interne, jamais client-facing."
        actions={(
          <Button onClick={() => setShowForm(true)}>
            <Plus className="size-4" /> Nouvelle revalorisation
          </Button>
        )}
      />

      <ListeStock error={error} items={items} vide="Aucune revalorisation.">
        {() => (
        <ul className="flex flex-col gap-2">
          {items.map((r) => (
            <li key={r.id} className="flex flex-col gap-1.5 rounded-lg border border-border p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
              <span className="flex items-center gap-2">
                {r.produit_nom}
                <Badge tone={STATUT_TONE[r.statut] ?? 'muted'}>{STATUT_LABELS[r.statut] ?? r.statut}</Badge>
              </span>
              <span className="flex items-center gap-3 tabular-nums text-muted-foreground">
                {formatMAD(r.ancien_cout)} → <span className="font-semibold text-foreground">{formatMAD(r.nouveau_cout)}</span>
                <span className={Number(r.delta_valeur) < 0 ? 'text-destructive' : 'text-success'}>
                  ({Number(r.delta_valeur) >= 0 ? '+' : ''}{formatMAD(r.delta_valeur)})
                </span>
                {r.statut === 'brouillon' && (
                  <>
                    <IconButton size="sm" variant="ghost" label="Valider" onClick={() => valider(r)}>
                      <CheckCircle2 className="size-4" aria-hidden="true" />
                    </IconButton>
                    <IconButton size="sm" variant="ghost" label="Supprimer"
                                className="text-destructive hover:text-destructive"
                                onClick={() => supprimer(r)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
        )}
      </ListeStock>

      {showForm && (
        <RevalorisationForm produits={produits}
                            onClose={() => setShowForm(false)} onSaved={reload} />
      )}
      {dialogueConfirmation}
    </div>
  )
}
