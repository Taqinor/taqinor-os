import { useEffect, useState } from 'react'
import { BookOpen, Plus, Sprout, Pencil, RotateCcw } from 'lucide-react'
import api from '../../api/axios'
import {
  Button, Card, Badge, Spinner, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Checkbox, DataTable,
} from '../../ui'

/* ============================================================================
   NTPAY3 — Plan comptable paie (schéma de ventilation).
   ----------------------------------------------------------------------------
   Surface l'interface comptable paramétrable NTPAY2 (`SchemaComptablePaie`,
   `/paie/schemas-comptables-paie/`) : chaque ligne route UN poste système
   (brut, charges patronales, organismes, IR, CIMR, net) OU UNE rubrique du
   catalogue vers ses comptes de débit/crédit et sa section analytique.

   Sans aucune ligne, l'écriture de paie reste celle d'avant (comptes CGNC
   historiques) — le bouton « Réinitialiser au plan standard » rejoue ce jeu
   de référence.
   ========================================================================== */

const listOf = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

const POSTES_SYSTEME = [
  { value: 'brut', label: 'Brut (rémunérations)' },
  { value: 'charges_patronales', label: 'Charges sociales patronales' },
  { value: 'cnss_organismes', label: 'Organismes sociaux (CNSS/AMO/AF/TFP)' },
  { value: 'ir', label: 'IR retenu à la source' },
  { value: 'cimr', label: 'CIMR' },
  { value: 'net', label: 'Net à payer (dû au personnel)' },
]

const LIBELLE_POSTE = Object.fromEntries(
  POSTES_SYSTEME.map((p) => [p.value, p.label]),
)

const cible = (r) => (
  r.rubrique
    ? `Rubrique — ${r.rubrique_code || ''}`.trim()
    : (LIBELLE_POSTE[r.code_systeme] || r.code_systeme || '—')
)

export default function PlanComptablePaie() {
  const [rows, setRows] = useState([])
  const [rubriques, setRubriques] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null) // null = création

  const load = () =>
    Promise.all([
      api.get('/paie/schemas-comptables-paie/'),
      api.get('/paie/rubriques/'),
    ])
      .then(([schema, cat]) => {
        setRows(listOf(schema.data))
        setRubriques(listOf(cat.data))
      })
      .catch(() => toast.error('Chargement du plan comptable paie impossible.'))
      .finally(() => setLoading(false))

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const seed = async () => {
    setBusy(true)
    try {
      await api.post('/paie/schemas-comptables-paie/seed-standard/')
      toast.success('Plan standard provisionné.')
      await load()
    } catch {
      toast.error('Semis impossible.')
    } finally { setBusy(false) }
  }

  const reinitialiser = async () => {
    setBusy(true)
    try {
      await api.post('/paie/schemas-comptables-paie/reinitialiser/')
      toast.success('Postes système réinitialisés au plan standard.')
      await load()
    } catch {
      toast.error('Réinitialisation impossible.')
    } finally { setBusy(false) }
  }

  const ouvrirCreation = () => { setEditing(null); setDialogOpen(true) }
  const ouvrirEdition = (row) => { setEditing(row); setDialogOpen(true) }

  const columns = [
    { id: 'cible', header: 'Cible', accessor: cible },
    {
      id: 'compte_debit', header: 'Compte de débit', width: 150,
      accessor: (r) => r.compte_debit || '—',
    },
    {
      id: 'compte_credit', header: 'Compte de crédit', width: 150,
      accessor: (r) => r.compte_credit || '—',
    },
    {
      id: 'section', header: 'Section analytique', width: 160,
      accessor: (r) => (r.section_analytique_id ? `#${r.section_analytique_id}` : '—'),
    },
    { id: 'ordre', header: 'Ordre', width: 80, accessor: (r) => r.ordre },
    {
      id: 'actif', header: 'Statut', width: 110, accessor: (r) => r.actif,
      cell: (_v, r) => (
        <Badge tone={r.actif ? 'success' : 'neutral'}>
          {r.actif ? 'Actif' : 'Inactif'}
        </Badge>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Plan comptable paie
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Ventilation de l’écriture de paie : chaque poste ou rubrique vers ses
          comptes. Sans ligne, l’écriture garde les comptes CGNC standards.
        </p>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={reinitialiser} loading={busy} variant="outline">
          <RotateCcw size={16} aria-hidden="true" /> Réinitialiser au plan standard
        </Button>
        <Button onClick={seed} loading={busy} variant="outline">
          <Sprout size={16} aria-hidden="true" /> Plan standard
        </Button>
        <Button onClick={ouvrirCreation}>
          <Plus size={16} aria-hidden="true" /> Nouvelle ligne
        </Button>
      </div>

      <Card className="p-4 sm:p-5">
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-muted-foreground">
            <Spinner className="size-4" /> Chargement…
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="Aucune ligne de plan comptable paie"
            description="Provisionnez le plan standard ou ajoutez une ligne." />
        ) : (
          <DataTable data={rows} columns={columns} searchable
            exportName="plan-comptable-paie"
            rowActions={(r) => [
              { id: 'editer', label: 'Éditer la ligne', icon: Pencil, onClick: () => ouvrirEdition(r) },
            ]} />
        )}
      </Card>

      {dialogOpen && (
        <LigneDialog
          ligne={editing}
          rubriques={rubriques}
          onClose={() => setDialogOpen(false)}
          onSaved={() => { setDialogOpen(false); load() }}
        />
      )}
    </div>
  )
}

function LigneDialog({ ligne, rubriques, onClose, onSaved }) {
  const isEdit = !!ligne
  const [mode, setMode] = useState(ligne?.rubrique ? 'rubrique' : 'systeme')
  const [codeSysteme, setCodeSysteme] = useState(ligne?.code_systeme || 'brut')
  const [rubrique, setRubrique] = useState(
    ligne?.rubrique ? String(ligne.rubrique) : '')
  const [compteDebit, setCompteDebit] = useState(ligne?.compte_debit || '')
  const [compteCredit, setCompteCredit] = useState(ligne?.compte_credit || '')
  const [section, setSection] = useState(
    ligne?.section_analytique_id ? String(ligne.section_analytique_id) : '')
  const [ordre, setOrdre] = useState(String(ligne?.ordre ?? 0))
  const [actif, setActif] = useState(ligne ? Boolean(ligne.actif) : true)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (mode === 'rubrique' && !rubrique) {
      setErr('Rubrique : choisissez la rubrique à router.')
      return
    }
    if (!compteDebit.trim() && !compteCredit.trim()) {
      setErr('Renseignez au moins un compte (débit ou crédit).')
      return
    }
    setSaving(true)
    setErr(null)
    const data = {
      code_systeme: mode === 'systeme' ? codeSysteme : '',
      rubrique: mode === 'rubrique' ? Number(rubrique) : null,
      compte_debit: compteDebit.trim(),
      compte_credit: compteCredit.trim(),
      section_analytique_id: section.trim() ? Number(section) : null,
      ordre: Number(ordre) || 0,
      actif,
    }
    try {
      if (isEdit) {
        await api.patch(`/paie/schemas-comptables-paie/${ligne.id}/`, data)
        toast.success('Ligne mise à jour.')
      } else {
        await api.post('/paie/schemas-comptables-paie/', data)
        toast.success('Ligne créée.')
      }
      onSaved()
    } catch (e2) {
      const payload = e2?.response?.data
      setErr(
        payload?.detail
        || payload?.code_systeme?.[0]
        || payload?.rubrique?.[0]
        || 'Enregistrement impossible.',
      )
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Ligne de plan comptable paie' : 'Nouvelle ligne de ventilation'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pcp-mode">Cible</Label>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger id="pcp-mode"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="systeme">Poste système</SelectItem>
                <SelectItem value="rubrique">Rubrique du catalogue</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {mode === 'systeme' ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pcp-poste" required>Poste système</Label>
              <Select value={codeSysteme} onValueChange={setCodeSysteme}>
                <SelectTrigger id="pcp-poste"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {POSTES_SYSTEME.map((p) => (
                    <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pcp-rubrique" required>Rubrique</Label>
              <Select value={rubrique} onValueChange={setRubrique}>
                <SelectTrigger id="pcp-rubrique">
                  <SelectValue placeholder="Choisir une rubrique" />
                </SelectTrigger>
                <SelectContent>
                  {rubriques.map((r) => (
                    <SelectItem key={r.id} value={String(r.id)}>
                      {r.code} — {r.libelle}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="pcp-debit">Compte de débit</Label>
              <Input id="pcp-debit" value={compteDebit}
                onChange={(e) => setCompteDebit(e.target.value)}
                placeholder="ex. 6171" />
            </div>
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="pcp-credit">Compte de crédit</Label>
              <Input id="pcp-credit" value={compteCredit}
                onChange={(e) => setCompteCredit(e.target.value)}
                placeholder="ex. 4432" />
            </div>
          </div>

          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="pcp-section">Section analytique (ID)</Label>
              <Input id="pcp-section" value={section}
                onChange={(e) => setSection(e.target.value)}
                placeholder="centre de coût" />
            </div>
            <div className="flex w-28 flex-col gap-1.5">
              <Label htmlFor="pcp-ordre">Ordre</Label>
              <Input id="pcp-ordre" value={ordre}
                onChange={(e) => setOrdre(e.target.value)} />
            </div>
          </div>

          {isEdit && (
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={actif} onCheckedChange={(v) => setActif(Boolean(v))} />
              Actif
            </label>
          )}

          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Enregistrement…' : (isEdit ? 'Mettre à jour' : 'Créer la ligne')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
