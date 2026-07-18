import { useEffect, useMemo, useState } from 'react'
import { Check, FileText, Plus } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Segmented, Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import qhseApi from '../../api/qhseApi'
import { GraviteAccident, StatutAccident, StatutAnalyse } from './constants.jsx'

// PresquAccident.GravitePotentielle.choices — côté serveur (distinct de
// GraviteAccident, léger/grave/mortel, réservée à l'accident avéré).
const GRAVITE_POTENTIELLE_OPTIONS = [
  { value: 'faible', label: 'Faible' },
  { value: 'moyenne', label: 'Moyenne' },
  { value: 'elevee', label: 'Élevée' },
]

// XQHS27 — PDF interne bilingue (FR/AR) de la fiche causerie + émargement.
async function telechargerCauseriePdf(causerie, lang = 'fr') {
  try {
    const res = await qhseApi.causerieSecuritePdf(causerie.id, { lang })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `causerie-${causerie.id}-${lang}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch {
    toast.error('Génération du PDF impossible.')
  }
}

/* ============================================================================
   UX27 — HSE RH (registres).
   ----------------------------------------------------------------------------
   Registres Hygiène-Sécurité-Environnement : accidents du travail,
   presqu'accidents, causeries de sécurité, analyses de risques chantier. La
   validation d'une analyse passe par l'@action serveur.
   ========================================================================== */

const VUES = [
  { value: 'accidents', label: 'Accidents du travail' },
  { value: 'presqu', label: 'Presqu’accidents' },
  { value: 'causeries', label: 'Causeries' },
  { value: 'analyses', label: 'Analyses de risques' },
]

export default function Hse() {
  const [vue, setVue] = useState('accidents')
  const [accidents, setAccidents] = useState([])
  const [presqu, setPresqu] = useState([])
  const [causeries, setCauseries] = useState([])
  const [analyses, setAnalyses] = useState([])
  const [employes, setEmployes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // WIR36 — dialogues de déclaration.
  const [accidentOpen, setAccidentOpen] = useState(false)
  const [presquOpen, setPresquOpen] = useState(false)
  const [causerieOpen, setCauserieOpen] = useState(false)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getAccidentsTravail(),
      rhApi.getPresquAccidents(),
      rhApi.getCauseriesSecurite(),
      rhApi.getAnalysesRisques(),
      rhApi.getEmployes(),
    ])
      .then(([ac, pa, ca, an, emp]) => {
        if (!vivant) return
        setAccidents(unwrap(ac.data))
        setPresqu(unwrap(pa.data))
        setCauseries(unwrap(ca.data))
        setAnalyses(unwrap(an.data))
        setEmployes(unwrap(emp.data))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger le registre HSE.')
        toast.error('Impossible de charger le registre HSE.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(recharger, [])

  const validerAnalyse = async (a) => {
    try {
      await rhApi.validerAnalyseRisques(a.id)
      toast.success('Analyse validée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  const accidentColumns = useMemo(() => [
    { id: 'reference', header: 'Référence', width: 140, accessor: (a) => a.reference || '', cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'employe', header: 'Blessé', width: 170, accessor: (a) => a.employe_nom || String(a.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (a) => a.date_accident || '', cell: (v) => formatDate(v) },
    { id: 'lieu', header: 'Lieu', width: 160, accessor: (a) => a.lieu || '', cell: (v) => v || '—' },
    { id: 'gravite', header: 'Gravité', width: 110, accessor: (a) => a.gravite || '', cell: (_v, a) => <GraviteAccident status={a.gravite} label={a.gravite_display} /> },
    { id: 'statut', header: 'Statut', width: 110, accessor: (a) => a.statut || '', cell: (_v, a) => <StatutAccident status={a.statut} label={a.statut_display} /> },
  ], [])

  const presquColumns = useMemo(() => [
    { id: 'reference', header: 'Référence', width: 140, accessor: (p) => p.reference || '', cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'date', header: 'Constaté le', width: 120, searchable: false, accessor: (p) => p.date_constat || '', cell: (v) => formatDate(v) },
    { id: 'lieu', header: 'Lieu', width: 160, accessor: (p) => p.lieu || '', cell: (v) => v || '—' },
    { id: 'gravite', header: 'Gravité potentielle', width: 160, accessor: (p) => p.gravite_potentielle_display || p.gravite_potentielle || '', cell: (v) => v || '—' },
    { id: 'statut', header: 'Statut', width: 110, accessor: (p) => p.statut_display || p.statut || '', cell: (v) => v || '—' },
  ], [])

  const causerieColumns = useMemo(() => [
    { id: 'theme', header: 'Thème', width: 220, accessor: (c) => c.theme || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (c) => c.date_causerie || '', cell: (v) => formatDate(v) },
    { id: 'animateur', header: 'Animateur', width: 160, accessor: (c) => c.animateur_nom || String(c.animateur || ''), cell: (v) => v || '—' },
    { id: 'lieu', header: 'Lieu', width: 160, accessor: (c) => c.lieu || '', cell: (v) => v || '—' },
  ], [])

  const analyseColumns = useMemo(() => [
    { id: 'chantier', header: 'Chantier', width: 140, accessor: (a) => String(a.chantier_id ?? ''), cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (a) => a.date_analyse || '', cell: (v) => formatDate(v) },
    { id: 'redacteur', header: 'Rédacteur', width: 160, accessor: (a) => a.redacteur_nom || String(a.redacteur || ''), cell: (v) => v || '—' },
    { id: 'risques', header: 'Risques', width: 90, align: 'right', searchable: false, accessor: (a) => (Array.isArray(a.risques) ? a.risques.length : 0), cell: (v) => <Badge tone="neutral">{v}</Badge> },
    { id: 'statut', header: 'Statut', width: 120, accessor: (a) => a.statut || '', cell: (_v, a) => <StatutAnalyse status={a.statut} label={a.statut_display} /> },
  ], [])

  const analyseActions = (a) => (a.statut === 'brouillon'
    ? [{ id: 'valider', label: 'Valider', icon: Check, onClick: () => validerAnalyse(a) }]
    : [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>HSE — Hygiène, sécurité & environnement</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue HSE" />

      {vue === 'accidents' && (
        <ListShell title="Accidents du travail" columns={accidentColumns} rows={accidents} loading={loading} error={error}
          searchable exportName="accidents-travail"
          actions={<Button onClick={() => setAccidentOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Déclarer un accident</Button>}
          emptyTitle="Aucun accident" emptyDescription="Aucun accident déclaré." />
      )}
      {vue === 'presqu' && (
        <ListShell title="Presqu’accidents" columns={presquColumns} rows={presqu} loading={loading} error={error}
          searchable exportName="presqu-accidents"
          actions={<Button onClick={() => setPresquOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Signaler un presqu’accident</Button>}
          emptyTitle="Aucun presqu’accident" emptyDescription="Aucun presqu’accident signalé." />
      )}
      {vue === 'causeries' && (
        <ListShell title="Causeries de sécurité" columns={causerieColumns} rows={causeries} loading={loading} error={error}
          searchable exportName="causeries-securite"
          actions={<Button onClick={() => setCauserieOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle causerie</Button>}
          emptyTitle="Aucune causerie" emptyDescription="Aucune causerie enregistrée."
          rowActions={(c) => [
            { id: 'pdf-fr', label: 'PDF (FR)', icon: FileText, onClick: () => telechargerCauseriePdf(c, 'fr') },
            { id: 'pdf-ar', label: 'PDF (AR)', icon: FileText, onClick: () => telechargerCauseriePdf(c, 'ar') },
          ]} />
      )}
      {vue === 'analyses' && (
        <ListShell title="Analyses de risques chantier" columns={analyseColumns} rows={analyses} loading={loading} error={error}
          searchable rowActions={analyseActions} exportName="analyses-risques"
          emptyTitle="Aucune analyse" emptyDescription="Aucune analyse de risques." />
      )}
      {accidentOpen && (
        <AccidentDialog
          employes={employes}
          onClose={() => setAccidentOpen(false)}
          onSaved={() => { setAccidentOpen(false); recharger() }}
        />
      )}
      {presquOpen && (
        <PresquAccidentDialog
          onClose={() => setPresquOpen(false)}
          onSaved={() => { setPresquOpen(false); recharger() }}
        />
      )}
      {causerieOpen && (
        <CauserieDialog
          employes={employes}
          onClose={() => setCauserieOpen(false)}
          onSaved={() => { setCauserieOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

/* ── WIR36 — Déclarer un accident du travail ── */
function AccidentDialog({ employes, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [dateAccident, setDateAccident] = useState('')
  const [lieu, setLieu] = useState('')
  const [gravite, setGravite] = useState('leger')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || dateAccident || lieu || description)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && dateAccident)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createAccidentTravail({
        employe, date_accident: dateAccident, lieu: lieu || '',
        gravite, description: description || '',
      })
      toast.success('Accident déclaré.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || 'Déclaration impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Déclarer un accident du travail</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-employe">Employé blessé</Label>
            <select id="ac-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ac-date">Date de l’accident</Label>
              <Input id="ac-date" type="date" value={dateAccident} onChange={(e) => setDateAccident(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ac-gravite">Gravité</Label>
              <select id="ac-gravite" value={gravite} onChange={(e) => setGravite(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                {GraviteAccident.options.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-lieu">Lieu</Label>
            <Input id="ac-lieu" value={lieu} onChange={(e) => setLieu(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-description">Description</Label>
            <Textarea id="ac-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Déclaration…' : 'Déclarer l’accident'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR36 — Signaler un presqu'accident (near-miss) ── */
function PresquAccidentDialog({ onClose, onSaved }) {
  const [dateConstat, setDateConstat] = useState('')
  const [lieu, setLieu] = useState('')
  const [gravitePotentielle, setGravitePotentielle] = useState('faible')
  const [description, setDescription] = useState('')
  const [mesureCorrective, setMesureCorrective] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(dateConstat || lieu || description || mesureCorrective)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(dateConstat)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createPresquAccident({
        date_constat: dateConstat, lieu: lieu || '',
        gravite_potentielle: gravitePotentielle,
        description: description || '', mesure_corrective: mesureCorrective || '',
      })
      toast.success('Presqu’accident signalé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || 'Signalement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Signaler un presqu’accident</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-date">Date du constat</Label>
              <Input id="pa-date" type="date" autoFocus value={dateConstat} onChange={(e) => setDateConstat(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-gravite">Gravité potentielle</Label>
              <select id="pa-gravite" value={gravitePotentielle} onChange={(e) => setGravitePotentielle(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                {GRAVITE_POTENTIELLE_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pa-lieu">Lieu</Label>
            <Input id="pa-lieu" value={lieu} onChange={(e) => setLieu(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pa-description">Ce qui s’est passé</Label>
            <Textarea id="pa-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pa-mesure">Mesure corrective (optionnel)</Label>
            <Textarea id="pa-mesure" value={mesureCorrective} onChange={(e) => setMesureCorrective(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Envoi…' : 'Signaler'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR36 — Nouvelle causerie de sécurité (toolbox talk) ── */
function CauserieDialog({ employes, onClose, onSaved }) {
  const [theme, setTheme] = useState('')
  const [dateCauserie, setDateCauserie] = useState('')
  const [animateur, setAnimateur] = useState('')
  const [lieu, setLieu] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(theme || dateCauserie || animateur || lieu || notes)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(theme.trim() && dateCauserie)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createCauserieSecurite({
        theme: theme.trim(), date_causerie: dateCauserie,
        animateur: animateur || null, lieu: lieu || '', notes: notes || '',
      })
      toast.success('Causerie enregistrée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle causerie de sécurité</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cs-theme">Thème</Label>
            <Input id="cs-theme" autoFocus value={theme} onChange={(e) => setTheme(e.target.value)} placeholder="Ex. Port des EPI, travail en hauteur…" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cs-date">Date</Label>
              <Input id="cs-date" type="date" value={dateCauserie} onChange={(e) => setDateCauserie(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cs-animateur">Animateur</Label>
              <select id="cs-animateur" value={animateur} onChange={(e) => setAnimateur(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Aucun —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cs-lieu">Lieu</Label>
            <Input id="cs-lieu" value={lieu} onChange={(e) => setLieu(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cs-notes">Notes (optionnel)</Label>
            <Textarea id="cs-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
