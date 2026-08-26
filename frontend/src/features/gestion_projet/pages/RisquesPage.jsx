import { useCallback, useEffect, useRef, useState } from 'react'
import { Link2, FileDown, Plus, Pencil, Trash2, Upload, History } from 'lucide-react'
import {
  Card, Button, IconButton, Spinner, EmptyState, Badge, DataTable, Tabs,
  TabsList, TabsTrigger, TabsContent, toast, Textarea,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Form, FormField, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { useConfirmDialog } from '../../../ui/confirm'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { formatMAD, formatDate } from '../../../lib/format'
import { filenameFromResponse } from '../../../utils/downloadBlob'
import gestionProjetApi from '../../../api/gestionProjetApi'
import {
  errMessage, StatutRisque, StatutAction, PrioriteAction, StatutLot,
  CATEGORIES_RISQUE, TYPES_DOC,
} from '../constants'
import ProjetPicker from '../components/ProjetPicker'
import RiskHeatmap from '../components/RiskHeatmap'
import { TextField, TextAreaField, SelectField } from '../components/fields'

// WIR87 — le carnet lit/écrit désormais le référentiel sous-traitant UNIFIÉ
// DC34 (`installations/sous-traitants/` = stock.Fournisseur type=service +
// SousTraitantProfile), jamais `gestion_projet.SousTraitant` (régression DC34
// constatée par ARC22). Miroir de `stock.SousTraitantProfile.Metier`.
// source-choix: stock.SousTraitantProfile.metier
const METIERS_SOUS_TRAITANT = [
  { value: 'terrassement', label: 'Terrassement' },
  { value: 'genie_civil', label: 'Génie civil' },
  { value: 'electricite', label: 'Électricité' },
  { value: 'levage', label: 'Levage' },
  { value: 'transport', label: 'Transport' },
  { value: 'autre', label: 'Autre' },
]

// Risque.probabilite / Risque.impact — échelle fermée 1–5 (miroir backend).
const ECHELLE_1_5 = [1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: String(n) }))

// ── Dialog création/édition — carnet de sous-traitants (master DC34) ───────
function SousTraitantForm({ sousTraitant, onClose, onSaved }) {
  const isNew = !sousTraitant?.id
  const [fields, setFields] = useState({
    raison_sociale: sousTraitant?.raison_sociale ?? '',
    metier: sousTraitant?.metier ?? 'autre',
    contact_nom: sousTraitant?.contact_nom ?? '',
    telephone: sousTraitant?.telephone ?? '',
    email: sousTraitant?.email ?? '',
    actif: sousTraitant?.actif ?? true,
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    if (!fields.raison_sociale.trim()) { setError('La raison sociale est requise.'); return }
    setSaving(true)
    setError(null)
    try {
      const payload = {
        raison_sociale: fields.raison_sociale.trim(),
        metier: fields.metier,
        contact_nom: fields.contact_nom.trim() || null,
        telephone: fields.telephone.trim() || null,
        email: fields.email.trim() || null,
        actif: fields.actif,
      }
      if (isNew) await gestionProjetApi.createSousTraitantMaster(payload)
      else await gestionProjetApi.updateSousTraitantMaster(sousTraitant.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Nouveau sous-traitant' : `Sous-traitant — ${sousTraitant.raison_sociale}`}</DialogTitle>
          <DialogDescription>
            Référentiel unifié (DC34) — le même que la fiche fournisseur stock. Donnée interne.
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Raison sociale" required htmlFor="st-nom" fullWidth>
            <Input id="st-nom" value={fields.raison_sociale}
                   onChange={(e) => setField('raison_sociale', e.target.value)} />
          </FormField>
          <FormField label="Métier" htmlFor="st-metier">
            <Select value={fields.metier} onValueChange={(v) => setField('metier', v)}>
              <SelectTrigger id="st-metier"><SelectValue /></SelectTrigger>
              <SelectContent>
                {METIERS_SOUS_TRAITANT.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Contact" htmlFor="st-contact">
            <Input id="st-contact" value={fields.contact_nom}
                   onChange={(e) => setField('contact_nom', e.target.value)} />
          </FormField>
          <FormField label="Téléphone" htmlFor="st-tel">
            <Input id="st-tel" value={fields.telephone}
                   onChange={(e) => setField('telephone', e.target.value)} />
          </FormField>
          <FormField label="Email" htmlFor="st-email">
            <Input id="st-email" type="email" value={fields.email}
                   onChange={(e) => setField('email', e.target.value)} />
          </FormField>
          <FormField label="Statut" htmlFor="st-actif">
            <Select value={fields.actif ? '1' : '0'} onValueChange={(v) => setField('actif', v === '1')}>
              <SelectTrigger id="st-actif"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="1">Actif</SelectItem>
                <SelectItem value="0">Inactif</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

// ── WIR203 — Dialog création/édition d'un risque ────────────────────────────
function RisqueForm({ projetId, risque, onClose, onSaved }) {
  const isEdit = !!risque?.id
  const [form, setForm] = useState({
    libelle: risque?.libelle ?? '',
    description: risque?.description ?? '',
    categorie: risque?.categorie ?? 'autre',
    probabilite: String(risque?.probabilite ?? 1),
    impact: String(risque?.impact ?? 1),
    statut: risque?.statut ?? 'ouvert',
    mitigation: risque?.mitigation ?? '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.libelle.trim()) { toast.error('Le libellé est obligatoire.'); return }
    setSaving(true)
    const payload = {
      projet: projetId,
      libelle: form.libelle.trim(),
      description: form.description,
      categorie: form.categorie,
      probabilite: Number(form.probabilite),
      impact: Number(form.impact),
      statut: form.statut,
      mitigation: form.mitigation,
    }
    try {
      if (isEdit) await gestionProjetApi.updateRisque(risque.id, payload)
      else await gestionProjetApi.createRisque(payload)
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title={isEdit ? 'Modifier le risque' : 'Nouveau risque'}
      description="La criticité (probabilité × impact) est recalculée côté serveur."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <TextField id="risque-libelle" label="Libellé" required autoFocus value={form.libelle} onChange={set('libelle')} />
        <TextAreaField id="risque-description" label="Description" rows={2} value={form.description} onChange={set('description')} />
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField id="risque-categorie" label="Catégorie" options={CATEGORIES_RISQUE} value={form.categorie} onChange={set('categorie')} />
          <SelectField id="risque-statut" label="Statut" options={StatutRisque.options} value={form.statut} onChange={set('statut')} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField id="risque-proba" label="Probabilité (1–5)" options={ECHELLE_1_5} value={form.probabilite} onChange={set('probabilite')} />
          <SelectField id="risque-impact" label="Impact (1–5)" options={ECHELLE_1_5} value={form.impact} onChange={set('impact')} />
        </div>
        <TextAreaField id="risque-mitigation" label="Plan de mitigation" rows={2} value={form.mitigation} onChange={set('mitigation')} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

// ── WIR203 — Dialog création/édition d'une action de suivi ──────────────────
function ActionForm({ projetId, risques, action, onClose, onSaved }) {
  const isEdit = !!action?.id
  const [form, setForm] = useState({
    libelle: action?.libelle ?? '',
    description: action?.description ?? '',
    risque: action?.risque ? String(action.risque) : '',
    statut: action?.statut ?? 'a_faire',
    priorite: action?.priorite ?? 'moyenne',
    echeance: action?.echeance ?? '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const risqueOptions = risques.map((r) => ({ value: String(r.id), label: r.libelle }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.libelle.trim()) { toast.error('Le libellé est obligatoire.'); return }
    setSaving(true)
    const payload = {
      projet: projetId,
      libelle: form.libelle.trim(),
      description: form.description,
      risque: form.risque ? Number(form.risque) : null,
      statut: form.statut,
      priorite: form.priorite,
      echeance: form.echeance || null,
    }
    try {
      if (isEdit) await gestionProjetApi.updateAction(action.id, payload)
      else await gestionProjetApi.createAction(payload)
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title={isEdit ? "Modifier l'action" : 'Nouvelle action'}
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <TextField id="action-libelle" label="Libellé" required autoFocus value={form.libelle} onChange={set('libelle')} />
        <TextAreaField id="action-description" label="Description" rows={2} value={form.description} onChange={set('description')} />
        {risqueOptions.length > 0 && (
          <SelectField id="action-risque" label="Risque lié (optionnel)" options={risqueOptions} value={form.risque} onChange={set('risque')} />
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField id="action-statut" label="Statut" options={StatutAction.options} value={form.statut} onChange={set('statut')} />
          <SelectField id="action-priorite" label="Priorité" options={PrioriteAction.options} value={form.priorite} onChange={set('priorite')} />
        </div>
        <TextField id="action-echeance" label="Échéance" type="date" value={form.echeance} onChange={set('echeance')} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

// ── WIR203 — Dialog création/édition d'un compte-rendu de réunion ──────────
function CompteRenduForm({ projetId, cr, onClose, onSaved }) {
  const isEdit = !!cr?.id
  const [form, setForm] = useState({
    titre: cr?.titre ?? '',
    date_reunion: cr?.date_reunion ?? '',
    lieu: cr?.lieu ?? '',
    participants: cr?.participants ?? '',
    ordre_du_jour: cr?.ordre_du_jour ?? '',
    decisions: cr?.decisions ?? '',
    points_bloquants: cr?.points_bloquants ?? '',
    date_prochaine_reunion: cr?.date_prochaine_reunion ?? '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.titre.trim()) { toast.error('Le titre est obligatoire.'); return }
    if (!form.date_reunion) { toast.error('La date de réunion est obligatoire.'); return }
    setSaving(true)
    const payload = {
      projet: projetId,
      titre: form.titre.trim(),
      date_reunion: form.date_reunion,
      lieu: form.lieu,
      participants: form.participants,
      ordre_du_jour: form.ordre_du_jour,
      decisions: form.decisions,
      points_bloquants: form.points_bloquants,
      date_prochaine_reunion: form.date_prochaine_reunion || null,
    }
    try {
      if (isEdit) await gestionProjetApi.updateCompteRendu(cr.id, payload)
      else await gestionProjetApi.createCompteRendu(payload)
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title={isEdit ? 'Modifier le compte-rendu' : 'Nouveau compte-rendu'}
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="cr-titre" label="Titre" required autoFocus value={form.titre} onChange={set('titre')} />
          <TextField id="cr-date" label="Date de la réunion" required type="date" value={form.date_reunion} onChange={set('date_reunion')} />
        </div>
        <TextField id="cr-lieu" label="Lieu" value={form.lieu} onChange={set('lieu')} />
        <TextAreaField id="cr-participants" label="Participants" rows={2} value={form.participants} onChange={set('participants')} />
        <TextAreaField id="cr-odj" label="Ordre du jour" rows={2} value={form.ordre_du_jour} onChange={set('ordre_du_jour')} />
        <TextAreaField id="cr-decisions" label="Décisions" rows={2} value={form.decisions} onChange={set('decisions')} />
        <TextAreaField id="cr-blocages" label="Points bloquants" rows={2} value={form.points_bloquants} onChange={set('points_bloquants')} />
        <TextField id="cr-prochaine" label="Date de la prochaine réunion" type="date" value={form.date_prochaine_reunion} onChange={set('date_prochaine_reunion')} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

// ── WIR203 — Dialog création d'un document (tête de série, sans fichier) ───
// Le dépôt du fichier (VersionDocument) se fait ensuite via l'action ligne
// « Ajouter une version » (multipart, `deposerVersionDocument`).
function DocumentForm({ projetId, onClose, onSaved }) {
  const [form, setForm] = useState({ nom: '', type_doc: 'autre', description: '' })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.nom.trim()) { toast.error('Le nom du document est obligatoire.'); return }
    setSaving(true)
    try {
      await gestionProjetApi.createDocument({
        projet: projetId, nom: form.nom.trim(), type_doc: form.type_doc,
        description: form.description,
      })
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title="Nouveau document"
      description="Le dépôt d'une première version se fait ensuite via « Ajouter une version »."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <TextField id="doc-nom" label="Nom" required autoFocus value={form.nom} onChange={set('nom')} />
        <SelectField id="doc-type" label="Type de document" options={TYPES_DOC} value={form.type_doc} onChange={set('type_doc')} />
        <TextAreaField id="doc-description" label="Description" rows={2} value={form.description} onChange={set('description')} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

// ── WIR203 — Dialog création/édition d'un lot de sous-traitance ────────────
// `LotSousTraitance.sous_traitant` référence le carnet LOCAL
// (`gestion_projet.SousTraitant`, distinct du master DC34 affiché dans
// l'onglet « Sous-traitance » — voir WIR87) : la liste vient de
// `getSousTraitants()`, chargée à l'ouverture du dialogue.
function LotForm({ projetId, sousTraitants, lot, onClose, onSaved }) {
  const isEdit = !!lot?.id
  const [form, setForm] = useState({
    libelle: lot?.libelle ?? '',
    sous_traitant: lot?.sous_traitant ? String(lot.sous_traitant) : '',
    description: lot?.description ?? '',
    montant: lot?.montant ?? '',
    statut: lot?.statut ?? 'prevu',
    date_debut: lot?.date_debut ?? '',
    date_fin: lot?.date_fin ?? '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const options = sousTraitants.map((s) => ({ value: String(s.id), label: s.nom }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.libelle.trim()) { toast.error('Le libellé du lot est obligatoire.'); return }
    if (!form.sous_traitant) { toast.error('Le sous-traitant est obligatoire.'); return }
    setSaving(true)
    const payload = {
      projet: projetId,
      sous_traitant: Number(form.sous_traitant),
      libelle: form.libelle.trim(),
      description: form.description,
      montant: form.montant === '' ? '0' : form.montant,
      statut: form.statut,
      date_debut: form.date_debut || null,
      date_fin: form.date_fin || null,
    }
    try {
      if (isEdit) await gestionProjetApi.updateLotSousTraitance(lot.id, payload)
      else await gestionProjetApi.createLotSousTraitance(payload)
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title={isEdit ? 'Modifier le lot' : 'Nouveau lot de sous-traitance'}
      description="Le montant est un coût INTERNE — jamais exposé au client."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <TextField id="lot-libelle" label="Libellé du lot" required autoFocus value={form.libelle} onChange={set('libelle')} />
        {options.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Aucun sous-traitant du carnet local disponible pour ce lot (distinct du carnet DC34
            de l'onglet « Sous-traitance »). Créez-en un via l'API du carnet local
            (<code>gestion-projet/sous-traitants/</code>) avant de confier un lot.
          </p>
        ) : (
          <SelectField id="lot-st" label="Sous-traitant" required options={options} value={form.sous_traitant} onChange={set('sous_traitant')} />
        )}
        <TextAreaField id="lot-description" label="Description" rows={2} value={form.description} onChange={set('description')} />
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="lot-montant" label="Montant (interne, MAD)" inputMode="decimal" value={form.montant} onChange={set('montant')} />
          <SelectField id="lot-statut" label="Statut" options={StatutLot.options} value={form.statut} onChange={set('statut')} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="lot-debut" label="Date de début" type="date" value={form.date_debut} onChange={set('date_debut')} />
          <TextField id="lot-fin" label="Date de fin" type="date" value={form.date_fin} onChange={set('date_fin')} />
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving || options.length === 0}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

/* UX42 — Risques, actions & CR : registre des risques, plan d'actions,
   comptes-rendus, documents/commentaires, modèles de projet, sous-traitants &
   lots. Tout est groupé sous onglets. Le `montant` des lots est INTERNE.

   WIR203 — les 16 fonctions CRUD de `gestionProjetApi` pour ces 6 ressources
   (risques/actions/CR/documents+versions/commentaires/lots) étaient orphelines
   (onglet lecture seule) : create/update/delete sont désormais câblés pour
   chacune (dialogues dédiés + rowActions), et `load()` (matrice comprise) est
   rechargé après CHAQUE écriture. */

const CAT_RISQUE = Object.fromEntries(CATEGORIES_RISQUE.map((c) => [c.value, c.label]))
const TYPE_DOC = Object.fromEntries(TYPES_DOC.map((c) => [c.value, c.label]))

export default function RisquesPage() {
  const { confirmDelete } = useConfirmDialog()
  const [projetId, setProjetId] = useState('')
  const [state, setState] = useState({
    risques: [], actions: [], crs: [], documents: [], commentaires: [],
    modeles: [], sousTraitants: [], lots: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [matrice, setMatrice] = useState(null)
  const [csatBusy, setCsatBusy] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  // WIR87 — édition du carnet (master DC34) : null = fermé, {} = création,
  // objet = édition.
  const [stEditing, setStEditing] = useState(null)

  // WIR203 — dialogues des 6 ressources CRUD (même convention : null = fermé,
  // {} = création, objet = édition).
  const [risqueEditing, setRisqueEditing] = useState(null)
  const [actionEditing, setActionEditing] = useState(null)
  const [crEditing, setCrEditing] = useState(null)
  const [documentEditing, setDocumentEditing] = useState(null)
  const [lotEditing, setLotEditing] = useState(null)
  // Carnet LOCAL (distinct du master DC34) — uniquement pour peupler le
  // sélecteur du dialogue Lot (LotSousTraitance.sous_traitant y référence).
  const [sousTraitantsLocaux, setSousTraitantsLocaux] = useState(null)
  const [nouveauCommentaire, setNouveauCommentaire] = useState('')
  const [commentBusy, setCommentBusy] = useState(false)
  const fileInputRef = useRef(null)
  const [uploadDocId, setUploadDocId] = useState(null)
  const [versionsDoc, setVersionsDoc] = useState(null)
  const [versionsLoading, setVersionsLoading] = useState(false)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  // WIR87 — le carnet lit le référentiel UNIFIÉ DC34 (`installations/
  // sous-traitants/`), plus jamais `gestion_projet.SousTraitant` (régression
  // DC34, ARC22) : société-scopé, indépendant du projet, rechargé seul après
  // création/édition (pas besoin de recharger tout le reste de la page).
  const reloadSousTraitants = useCallback(async () => {
    const st = await gestionProjetApi.getSousTraitantsMaster()
    setState((s) => ({ ...s, sousTraitants: asList(st) }))
  }, [])

  const load = useCallback(async (pid) => {
    setLoading(true)
    setError(null)
    try {
      // Modèles & sous-traitants sont société-scopés (indépendants du projet).
      const params = pid ? { projet: pid } : undefined
      const [ri, ac, cr, doc, com, mod, st, lo, mat] = await Promise.all([
        pid ? gestionProjetApi.getRisques(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getActions(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getComptesRendus(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getDocuments(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getCommentaires(params) : Promise.resolve({ data: [] }),
        gestionProjetApi.getModeles(),
        gestionProjetApi.getSousTraitantsMaster(),
        pid ? gestionProjetApi.getLotsSousTraitance(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getMatriceRisques(pid).catch(() => ({ data: null })) : Promise.resolve({ data: null }),
      ])
      setState({
        risques: asList(ri), actions: asList(ac), crs: asList(cr),
        documents: asList(doc), commentaires: asList(com), modeles: asList(mod),
        sousTraitants: asList(st), lots: asList(lo),
      })
      setMatrice(mat.data)
    } catch (err) {
      setError(errMessage(err, 'Chargement impossible.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load(projetId) })()
    return () => { alive = false }
  }, [projetId, load])

  // ZPRJ7 — Lien tokenisé d'évaluation CSAT (idempotent, à envoyer au client
  // à la clôture du projet). Copié au presse-papier.
  const copierLienEvaluation = async () => {
    setCsatBusy(true)
    try {
      const res = await gestionProjetApi.getLienEvaluation(projetId)
      const base = (import.meta.env.VITE_PUBLIC_SITE_URL || 'https://taqinor.ma').replace(/\/+$/, '')
      const url = `${base}/gestion-projet/portail/evaluation/${res.data.token}/`
      try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
      toast.success('Lien d\'évaluation CSAT copié.')
    } catch (err) {
      toast.error(errMessage(err, 'Génération du lien impossible.'))
    } finally {
      setCsatBusy(false)
    }
  }

  // ZPRJ9 — PDF interne « Point d'avancement projet » (WeasyPrint legacy,
  // jamais le moteur premium /proposal réservé aux devis client — règle #4).
  const telechargerRapportPdf = async () => {
    setPdfBusy(true)
    try {
      const res = await gestionProjetApi.getRapportAvancementPdf(projetId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.target = '_blank'
      a.rel = 'noopener'
      a.download = filenameFromResponse(res, `avancement-projet-${projetId}.pdf`)
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 10000)
    } catch (err) {
      toast.error(errMessage(err, 'Génération du PDF impossible.'))
    } finally {
      setPdfBusy(false)
    }
  }

  // ── WIR203 — suppressions (risques/actions/CR/documents/lots/commentaires)
  const supprimerRisque = async (r) => {
    const ok = await confirmDelete({ title: `Supprimer le risque « ${r.libelle} » ?`, description: 'Action irréversible.' })
    if (!ok) return
    try {
      await gestionProjetApi.deleteRisque(r.id)
      toast.success('Risque supprimé.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  const supprimerAction = async (a) => {
    const ok = await confirmDelete({ title: `Supprimer l'action « ${a.libelle} » ?`, description: 'Action irréversible.' })
    if (!ok) return
    try {
      await gestionProjetApi.deleteAction(a.id)
      toast.success('Action supprimée.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  const supprimerCr = async (c) => {
    const ok = await confirmDelete({ title: `Supprimer le compte-rendu « ${c.titre} » ?`, description: 'Action irréversible.' })
    if (!ok) return
    try {
      await gestionProjetApi.deleteCompteRendu(c.id)
      toast.success('Compte-rendu supprimé.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  const supprimerDocument = async (d) => {
    const ok = await confirmDelete({ title: `Supprimer le document « ${d.nom} » ?`, description: 'Toutes ses versions seront supprimées.' })
    if (!ok) return
    try {
      await gestionProjetApi.deleteDocument(d.id)
      toast.success('Document supprimé.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  const supprimerLot = async (l) => {
    const ok = await confirmDelete({ title: `Supprimer le lot « ${l.libelle} » ?`, description: 'Action irréversible.' })
    if (!ok) return
    try {
      await gestionProjetApi.deleteLotSousTraitance(l.id)
      toast.success('Lot supprimé.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  const ajouterCommentaire = async () => {
    const texte = nouveauCommentaire.trim()
    if (!texte || !projetId) return
    setCommentBusy(true)
    try {
      await gestionProjetApi.createCommentaire({ projet: projetId, texte, cible_type: 'projet' })
      setNouveauCommentaire('')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, "Impossible d'ajouter le commentaire."))
    } finally {
      setCommentBusy(false)
    }
  }

  const supprimerCommentaire = async (cm) => {
    const ok = await confirmDelete({ title: 'Supprimer ce commentaire ?' })
    if (!ok) return
    try {
      await gestionProjetApi.deleteCommentaire(cm.id)
      toast.success('Commentaire supprimé.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  // ── WIR203 — dépôt de version (upload) + historique des versions ──────────
  const declencherUpload = (doc) => {
    setUploadDocId(doc.id)
    fileInputRef.current?.click()
  }

  const onFichierChoisi = async (e) => {
    const fichier = e.target.files?.[0]
    e.target.value = ''
    if (!fichier || !uploadDocId) return
    try {
      const fd = new FormData()
      fd.append('fichier', fichier)
      await gestionProjetApi.deposerVersionDocument(uploadDocId, fd)
      toast.success('Version déposée.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Dépôt du fichier impossible.'))
    } finally {
      setUploadDocId(null)
    }
  }

  const voirVersions = async (doc) => {
    setVersionsDoc({ document: doc, versions: [] })
    setVersionsLoading(true)
    try {
      const res = await gestionProjetApi.getDocumentVersions(doc.id)
      setVersionsDoc({ document: doc, versions: asList(res) })
    } catch (err) {
      toast.error(errMessage(err, 'Chargement des versions impossible.'))
      setVersionsDoc(null)
    } finally {
      setVersionsLoading(false)
    }
  }

  // ── WIR203 — dialogue Lot : charge le carnet LOCAL à la première ouverture
  const ouvrirLotForm = async (lot) => {
    if (sousTraitantsLocaux === null) {
      try {
        const res = await gestionProjetApi.getSousTraitants()
        setSousTraitantsLocaux(asList(res))
      } catch {
        setSousTraitantsLocaux([])
      }
    }
    setLotEditing(lot ?? {})
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Risques, actions & CR</h1>
          <p className="text-sm text-muted-foreground">Registre des risques, plan d'actions, réunions, documents, modèles & sous-traitance.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <ProjetPicker value={projetId} onChange={setProjetId} />
          {projetId && (
            <>
              <Button size="sm" variant="outline" disabled={csatBusy} onClick={copierLienEvaluation} title="Copier le lien d'évaluation CSAT (ZPRJ7)">
                <Link2 className="size-3.5" aria-hidden="true" /> Lien CSAT
              </Button>
              <Button size="sm" variant="outline" disabled={pdfBusy} onClick={telechargerRapportPdf} title="Télécharger le rapport d'avancement PDF (ZPRJ9)">
                <FileDown className="size-3.5" aria-hidden="true" /> Rapport PDF
              </Button>
            </>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={() => load(projetId)}>Réessayer</Button>} />
      ) : (
        <Tabs defaultValue="risques">
          <TabsList className="flex-wrap">
            <TabsTrigger value="risques">Risques</TabsTrigger>
            <TabsTrigger value="heatmap">Matrice P × I</TabsTrigger>
            <TabsTrigger value="actions">Actions</TabsTrigger>
            <TabsTrigger value="cr">Comptes-rendus</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="modeles">Modèles</TabsTrigger>
            <TabsTrigger value="sous-traitance">Sous-traitance</TabsTrigger>
          </TabsList>

          <TabsContent value="risques">
            <Card className="p-4 sm:p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Registre des risques</h3>
                <Button size="sm" disabled={!projetId} onClick={() => setRisqueEditing({})}>
                  <Plus className="size-4" /> Nouveau risque
                </Button>
              </div>
              <DataTable
                data={state.risques}
                getRowId={(r) => r.id}
                columns={[
                  { id: 'libelle', header: 'Risque', accessor: (r) => r.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'categorie', header: 'Catégorie', searchable: false, accessor: (r) => CAT_RISQUE[r.categorie] ?? r.categorie },
                  { id: 'proba', header: 'P', align: 'right', numeric: true, searchable: false, accessor: (r) => r.probabilite },
                  { id: 'impact', header: 'I', align: 'right', numeric: true, searchable: false, accessor: (r) => r.impact },
                  { id: 'criticite', header: 'Criticité', align: 'right', numeric: true, searchable: false, accessor: (r) => r.criticite, cell: (v) => <Badge tone={v >= 15 ? 'danger' : v >= 8 ? 'warning' : 'neutral'}>{v}</Badge> },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (r) => r.statut, cell: (v) => <StatutRisque status={v} /> },
                ]}
                rowActions={(r) => [
                  { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => setRisqueEditing(r) },
                  { id: 'del', label: 'Supprimer', icon: Trash2, destructive: true, separatorBefore: true, onClick: () => supprimerRisque(r) },
                ]}
                exportName="risques"
                emptyTitle="Aucun risque"
                emptyDescription={projetId ? 'Aucun risque enregistré pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>

          <TabsContent value="heatmap">
            <Card className="p-4 sm:p-5">
              {!projetId ? (
                <EmptyState title="Aucun projet sélectionné" description="Choisissez un projet pour afficher sa matrice des risques." />
              ) : (
                <RiskHeatmap grille={matrice?.grille ?? []} topRisques={matrice?.top_risques ?? []} />
              )}
            </Card>
          </TabsContent>

          <TabsContent value="actions">
            <Card className="p-4 sm:p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Plan d'actions</h3>
                <Button size="sm" disabled={!projetId} onClick={() => setActionEditing({})}>
                  <Plus className="size-4" /> Nouvelle action
                </Button>
              </div>
              <DataTable
                data={state.actions}
                getRowId={(a) => a.id}
                columns={[
                  { id: 'libelle', header: 'Action', accessor: (a) => a.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'priorite', header: 'Priorité', searchable: false, accessor: (a) => a.priorite, cell: (v) => <PrioriteAction status={v} /> },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (a) => a.statut, cell: (v) => <StatutAction status={v} /> },
                  { id: 'echeance', header: 'Échéance', searchable: false, accessor: (a) => a.echeance || '', cell: (v) => v ? formatDate(v) : '—' },
                ]}
                rowActions={(a) => [
                  { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => setActionEditing(a) },
                  { id: 'del', label: 'Supprimer', icon: Trash2, destructive: true, separatorBefore: true, onClick: () => supprimerAction(a) },
                ]}
                exportName="actions"
                emptyTitle="Aucune action"
                emptyDescription={projetId ? 'Aucune action pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>

          <TabsContent value="cr">
            <Card className="p-4 sm:p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Comptes-rendus de réunion</h3>
                <Button size="sm" disabled={!projetId} onClick={() => setCrEditing({})}>
                  <Plus className="size-4" /> Nouveau compte-rendu
                </Button>
              </div>
              {state.crs.length ? (
                <ul className="flex flex-col gap-2">
                  {state.crs.map((c) => (
                    <li key={c.id} className="rounded-md border border-border p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{c.titre}</span>
                        <span className="ml-auto text-xs text-muted-foreground">{c.date_reunion ? formatDate(c.date_reunion) : ''}</span>
                        <IconButton size="sm" variant="ghost" label="Modifier" onClick={() => setCrEditing(c)}>
                          <Pencil className="size-4" aria-hidden="true" />
                        </IconButton>
                        <IconButton size="sm" variant="ghost" label="Supprimer" onClick={() => supprimerCr(c)}>
                          <Trash2 className="size-4" aria-hidden="true" />
                        </IconButton>
                      </div>
                      {c.lieu && <p className="text-xs text-muted-foreground">Lieu : {c.lieu}</p>}
                      {c.decisions && <p className="mt-1 whitespace-pre-wrap text-sm">{c.decisions}</p>}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Aucun compte-rendu" description={projetId ? 'Aucune réunion enregistrée.' : 'Sélectionnez un projet.'} />}
            </Card>
          </TabsContent>

          <TabsContent value="documents">
            <Card className="p-4 sm:p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Documents du projet</h3>
                <Button size="sm" disabled={!projetId} onClick={() => setDocumentEditing({})}>
                  <Plus className="size-4" /> Nouveau document
                </Button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                className="sr-only"
                aria-label="Déposer une version de document"
                onChange={onFichierChoisi}
              />
              <DataTable
                data={state.documents}
                getRowId={(d) => d.id}
                columns={[
                  { id: 'nom', header: 'Document', accessor: (d) => d.nom, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'type', header: 'Type', searchable: false, accessor: (d) => TYPE_DOC[d.type_doc] ?? d.type_doc, cell: (v) => <Badge tone="info">{v}</Badge> },
                  { id: 'version', header: 'Version', align: 'right', numeric: true, searchable: false, accessor: (d) => d.derniere_version ?? 0 },
                  { id: 'nb', header: 'Révisions', align: 'right', numeric: true, searchable: false, accessor: (d) => (d.versions ?? []).length },
                ]}
                rowActions={(d) => [
                  { id: 'upload', label: 'Ajouter une version', icon: Upload, onClick: () => declencherUpload(d) },
                  { id: 'hist', label: 'Historique des versions', icon: History, onClick: () => voirVersions(d) },
                  { id: 'del', label: 'Supprimer', icon: Trash2, destructive: true, separatorBefore: true, onClick: () => supprimerDocument(d) },
                ]}
                exportName="documents"
                emptyTitle="Aucun document"
                emptyDescription={projetId ? 'Aucun document versionné.' : 'Sélectionnez un projet.'}
              />
              <div className="mt-4 border-t border-border pt-3">
                <p className="mb-2 text-sm font-medium">Commentaires</p>
                {state.commentaires.length > 0 && (
                  <ul className="mb-2 flex flex-col gap-1 text-sm">
                    {state.commentaires.slice(0, 8).map((cm) => (
                      <li key={cm.id} className="flex items-start gap-2">
                        <span className="text-muted-foreground">{cm.auteur_nom || '—'} :</span>
                        <span className="flex-1">{cm.texte}</span>
                        <IconButton size="sm" variant="ghost" label="Supprimer" onClick={() => supprimerCommentaire(cm)}>
                          <Trash2 className="size-3.5" aria-hidden="true" />
                        </IconButton>
                      </li>
                    ))}
                  </ul>
                )}
                {projetId && (
                  <div className="flex items-end gap-2">
                    <Textarea
                      className="min-h-9 flex-1"
                      rows={2}
                      placeholder="Ajouter un commentaire…"
                      aria-label="Nouveau commentaire"
                      value={nouveauCommentaire}
                      onChange={(e) => setNouveauCommentaire(e.target.value)}
                      disabled={commentBusy}
                    />
                    <Button size="sm" disabled={commentBusy || !nouveauCommentaire.trim()} onClick={ajouterCommentaire}>
                      Ajouter
                    </Button>
                  </div>
                )}
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="modeles">
            <Card className="p-4 sm:p-5">
              <DataTable
                data={state.modeles}
                getRowId={(m) => m.id}
                columns={[
                  { id: 'nom', header: 'Modèle', accessor: (m) => m.nom, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'type', header: 'Type installation', searchable: false, accessor: (m) => m.type_installation_display || m.type_installation },
                  { id: 'nb', header: 'Tâches-types', align: 'right', numeric: true, searchable: false, accessor: (m) => m.nb_taches ?? (m.taches ?? []).length },
                  { id: 'actif', header: 'Actif', searchable: false, accessor: (m) => m.actif, cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge> },
                ]}
                exportName="modeles-projet"
                emptyTitle="Aucun modèle"
                emptyDescription="Créez des modèles de projet par type d'installation."
              />
            </Card>
          </TabsContent>

          <TabsContent value="sous-traitance">
            <Card className="p-4 sm:p-5">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Carnet de sous-traitants</h3>
                <Button size="sm" onClick={() => setStEditing({})}>
                  <Plus className="size-4" /> Nouveau sous-traitant
                </Button>
              </div>
              {/* WIR87 — référentiel unifié DC34 (stock.Fournisseur type=service +
                  SousTraitantProfile) : plus jamais `gestion_projet.SousTraitant`
                  (régression DC34 constatée par ARC22). Le champ `metier` (enum
                  fermé côté master) remplace le `specialite` texte libre local. */}
              <DataTable
                data={state.sousTraitants}
                getRowId={(s) => s.id}
                onRowClick={(s) => setStEditing(s)}
                columns={[
                  { id: 'raison_sociale', header: 'Sous-traitant', accessor: (s) => s.raison_sociale, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'metier', header: 'Métier', accessor: (s) => s.metier_display || s.metier || '—' },
                  { id: 'contact', header: 'Contact', accessor: (s) => s.contact_nom || '—' },
                  { id: 'tel', header: 'Téléphone', searchable: false, accessor: (s) => s.telephone || '—' },
                  { id: 'actif', header: 'Actif', searchable: false, accessor: (s) => s.actif, cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge> },
                  { id: 'actions', header: '', searchable: false, sortable: false,
                    cell: (_v, s) => (
                      <IconButton size="sm" variant="ghost" label="Modifier"
                                  onClick={(e) => { e.stopPropagation(); setStEditing(s) }}>
                        <Pencil className="size-4" aria-hidden="true" />
                      </IconButton>
                    ) },
                ]}
                exportName="sous-traitants"
                emptyTitle="Aucun sous-traitant"
                emptyDescription="Ajoutez des sous-traitants avec « Nouveau sous-traitant »."
              />
              <div className="mb-2 mt-5 flex items-center justify-between">
                <h3 className="font-display text-base font-semibold">Lots de sous-traitance</h3>
                <Button size="sm" disabled={!projetId} onClick={() => ouvrirLotForm({})}>
                  <Plus className="size-4" /> Nouveau lot
                </Button>
              </div>
              <DataTable
                data={state.lots}
                getRowId={(l) => l.id}
                columns={[
                  { id: 'libelle', header: 'Lot', accessor: (l) => l.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'st', header: 'Sous-traitant', accessor: (l) => l.sous_traitant_nom || `#${l.sous_traitant}` },
                  { id: 'montant', header: 'Montant (interne)', align: 'right', numeric: true, searchable: false, accessor: (l) => Number(l.montant ?? 0), cell: (_v, l) => (l.montant ? formatMAD(l.montant) : '—') },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (l) => l.statut, cell: (v) => <StatutLot status={v} /> },
                ]}
                rowActions={(l) => [
                  { id: 'edit', label: 'Modifier', icon: Pencil, onClick: () => ouvrirLotForm(l) },
                  { id: 'del', label: 'Supprimer', icon: Trash2, destructive: true, separatorBefore: true, onClick: () => supprimerLot(l) },
                ]}
                exportName="lots-sous-traitance"
                emptyTitle="Aucun lot"
                emptyDescription={projetId ? 'Aucun lot confié pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>
        </Tabs>
      )}

      {stEditing && (
        <SousTraitantForm sousTraitant={stEditing.id ? stEditing : null}
                          onClose={() => setStEditing(null)}
                          onSaved={reloadSousTraitants} />
      )}

      {risqueEditing && (
        <RisqueForm projetId={projetId} risque={risqueEditing.id ? risqueEditing : null}
                    onClose={() => setRisqueEditing(null)} onSaved={() => load(projetId)} />
      )}
      {actionEditing && (
        <ActionForm projetId={projetId} risques={state.risques} action={actionEditing.id ? actionEditing : null}
                    onClose={() => setActionEditing(null)} onSaved={() => load(projetId)} />
      )}
      {crEditing && (
        <CompteRenduForm projetId={projetId} cr={crEditing.id ? crEditing : null}
                         onClose={() => setCrEditing(null)} onSaved={() => load(projetId)} />
      )}
      {documentEditing && (
        <DocumentForm projetId={projetId}
                      onClose={() => setDocumentEditing(null)} onSaved={() => load(projetId)} />
      )}
      {lotEditing && (
        <LotForm projetId={projetId} sousTraitants={sousTraitantsLocaux ?? []} lot={lotEditing.id ? lotEditing : null}
                onClose={() => setLotEditing(null)} onSaved={() => load(projetId)} />
      )}
      {versionsDoc && (
        <ResponsiveDialog
          open
          onOpenChange={(o) => { if (!o) setVersionsDoc(null) }}
          title={`Versions — ${versionsDoc.document.nom}`}
        >
          {versionsLoading ? (
            <div className="flex justify-center p-6"><Spinner /></div>
          ) : versionsDoc.versions.length ? (
            <ul className="flex flex-col gap-2 text-sm">
              {versionsDoc.versions.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2 rounded-md border border-border p-2">
                  <div>
                    <span className="font-medium">v{v.version}</span>
                    {v.commentaire && <span className="ml-2 text-muted-foreground">{v.commentaire}</span>}
                    <div className="text-xs text-muted-foreground">{v.auteur_nom || '—'} · {v.date_creation ? formatDate(v.date_creation) : '—'}</div>
                  </div>
                  {v.fichier && (
                    <a href={v.fichier} target="_blank" rel="noopener noreferrer" className="text-xs font-medium text-primary hover:underline">
                      Télécharger
                    </a>
                  )}
                </li>
              ))}
            </ul>
          ) : <EmptyState title="Aucune version" description="Aucune version déposée pour ce document." />}
        </ResponsiveDialog>
      )}
    </div>
  )
}
