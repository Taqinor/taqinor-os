import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { useIsAdmin } from '../../hooks/useHasPermission'
import { Lock, Download, Snowflake } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import {
  Button, Spinner, Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormField,
} from '../../ui'

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
  const anneeActuelle = new Date().getFullYear()
  const [exercice, setExercice] = useState(String(anneeActuelle))
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    const annee = Number(exercice)
    if (!annee) { setError('Année invalide.'); return }
    if (!window.confirm(
      `Figer l'inventaire de l'exercice ${annee} ? Cette action est IRRÉVERSIBLE (le snapshot ne pourra plus être modifié).`,
    )) return
    setSaving(true)
    setError(null)
    try {
      await stockApi.figerInventaireAnnuel({ exercice: annee })
      onDone?.()
      onClose()
    } catch (err) {
      setError(frErr(err, 'Le figement a échoué.'))
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
          <FormField label="Exercice (année)" required htmlFor="inv-exercice" fullWidth>
            <Input id="inv-exercice" type="number" step="1" value={exercice}
                   onChange={(e) => setExercice(e.target.value)} />
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
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Inventaires annuels</h1>
          <p className="text-sm text-muted-foreground">
            Snapshot légal figé de la valorisation du stock (CGNC). Interne, jamais client-facing.
          </p>
        </div>
        <Button onClick={() => setShowFiger(true)}>
          <Snowflake className="size-4" /> Figer un exercice
        </Button>
      </header>

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
