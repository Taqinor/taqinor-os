import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { useIsAdmin } from '../../hooks/useHasPermission'
import { Lock, Download, Snowflake,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import {
  Button, Spinner, Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormField,
} from '../../ui'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'
// ASTK231 — confirmations par l'AlertDialog commune (aucune boîte native).
import { useConfirmation } from '../../features/stock/useConfirmation'

/* WIR109 — XSTK13 : inventaire annuel légal FIGÉ (CGNC, support du bilan).
   LECTURE SEULE côté modèle : un snapshot n'est créé QUE par l'action
   `figer` (jamais réécrit ensuite) — écran admin-only, jamais client-facing
   (les coûts d'achat sont internes). */

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

function FigerDialog({ onClose, onDone }) {
  const [confirmer, dialogueConfirmation] = useConfirmation()
  // ASTK203 — seul un exercice CLOS se fige : l'année précédente est proposée.
  const anneePrecedente = new Date().getFullYear() - 1
  const [exercice, setExercice] = useState(String(anneePrecedente))
  const [error, setError] = useState(null)
  const [exerciceError, setExerciceError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    const annee = Number(exercice)
    if (!annee) { setError('Année invalide.'); return }
    if (!(await confirmer({
      title: `Figer l'inventaire de l'exercice ${annee} ?`,
      description: 'Cette action est IRRÉVERSIBLE (le snapshot ne pourra plus être modifié).',
      confirmLabel: 'Figer',
    }))) return
    setSaving(true)
    setError(null)
    setExerciceError(null)
    try {
      await stockApi.figerInventaireAnnuel({ exercice: annee })
      onDone?.()
      onClose()
    } catch (err) {
      // ASTK203 — le refus « exercice non clos » s'affiche SOUS le champ.
      const surChamp = err?.response?.data?.exercice
      if (surChamp) setExerciceError(Array.isArray(surChamp) ? surChamp[0] : String(surChamp))
      else setError(frErr(err, 'Le figement a échoué.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Figer un exercice</DialogTitle>
          <DialogDescription>
            Snapshot immuable de la valorisation du stock au 31/12. Un exercice
            déjà figé pour cette société ne peut pas être re-figé.
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Exercice (année)" required htmlFor="inv-exercice" fullWidth
                     error={exerciceError}>
            <Input id="inv-exercice" type="number" step="1" value={exercice} invalid={!!exerciceError}
                   onChange={(e) => { setExercice(e.target.value); setExerciceError(null) }} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Figement…' : 'Figer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
      {dialogueConfirmation}
    </Dialog>
  )
}

export default function InventairesAnnuels() {
  const isAdmin = useIsAdmin()
  const societe = useSelector((s) => s.parametres?.profile?.nom)

  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [showFiger, setShowFiger] = useState(false)
  const [exportingId, setExportingId] = useState(null)

  const reload = () => {
    stockApi.getInventairesAnnuels({ ordering: '-exercice' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des inventaires impossible.'))
  }

  useEffect(() => { reload() }, [])

  const exporter = async (inv) => {
    setExportingId(inv.id)
    try {
      const res = await stockApi.exportInventaireAnnuelXlsx(inv.id)
      downloadBlob(res.data, stampedFilename(`inventaire-${inv.exercice}`, 'xlsx', societe))
    } catch {
      setError('Export indisponible.')
    } finally { setExportingId(null) }
  }

  if (!isAdmin) {
    return (
      <div className="ui-root px-4 py-5 sm:px-5">
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          Réservé à l&apos;administrateur (coûts d&apos;achat internes).
        </div>
      </div>
    )
  }

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        headingAs="h1"
        icon={Lock}
        title="Inventaires annuels"
        subtitle="Snapshot légal figé de la valorisation du stock (CGNC). Interne, jamais client-facing."
        actions={(
          <Button onClick={() => setShowFiger(true)}>
            <Snowflake className="size-4" /> Figer un exercice
          </Button>
        )}
      />

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {items === null ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun exercice figé pour l&apos;instant.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((inv) => (
            <li key={inv.id} className="flex items-center justify-between rounded-lg border border-border p-3 text-sm">
              <span className="flex items-center gap-2">
                <Lock className="size-4 text-muted-foreground" aria-hidden="true" />
                Exercice {inv.exercice} — {inv.nb_lignes} ligne(s)
              </span>
              <span className="flex items-center gap-3">
                <span className="font-semibold tabular-nums">{formatMAD(inv.total_valeur)}</span>
                <Button size="sm" variant="outline" loading={exportingId === inv.id}
                        onClick={() => exporter(inv)}>
                  <Download className="size-4" /> Export .xlsx
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {showFiger && (
        <FigerDialog onClose={() => setShowFiger(false)} onDone={reload} />
      )}
    </div>
  )
}
