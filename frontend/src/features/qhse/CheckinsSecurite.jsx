import { useState } from 'react'
import { Plus, LogOut, AlertTriangle, Reply, CheckCircle2 } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { ListShell } from '../../ui/module'
import {
  Button, Badge, Dialog, DialogContent, DialogTitle, Input, Label, Textarea,
  toast, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { useQhseList } from './useQhseList'

/* ============================================================================
   WIR115 — Check-in sécurité (technicien seul sur site à risque) + SCAR.
   ----------------------------------------------------------------------------
   Donne enfin un écran aux deux backends jusqu'ici sombres :
   • Check-ins : le technicien pointe son arrivée sur un site à risque avec une
     heure de check-out prévue ; la tâche beat d'escalade escalade toute absence
     de check-out passé le délai. Bouton « Check-out » pour clôturer le cycle.
   • SCAR : demandes d'action corrective fournisseur (lecture — le cycle de
     réponse/vérification se pilote côté NCR fournisseur).
   Rôles : ['responsable','admin'] (gaté par la config du module).
   ========================================================================== */

function CheckinDialog({ onClose, onDone }) {
  const [site, setSite] = useState('')
  const [prevue, setPrevue] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.checkinsSecurite.create({
        site_ref: site,
        heure_checkout_prevue: prevue || null,
      })
      toast.success('Check-in enregistré.')
      onDone()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Check-in impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Nouveau check-in</DialogTitle>
        <div className="space-y-3 pt-2">
          <div>
            <Label htmlFor="ci-site">Site</Label>
            <Input id="ci-site" value={site}
              onChange={e => setSite(e.target.value)}
              placeholder="Toiture villa Anfa…" />
          </div>
          <div>
            <Label htmlFor="ci-prevue">Check-out prévu</Label>
            <Input id="ci-prevue" type="datetime-local" value={prevue}
              onChange={e => setPrevue(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>Check-in</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function CheckinsTab() {
  const [dialog, setDialog] = useState(false)
  const { rows, loading, error, reload } = useQhseList(
    () => qhseApi.checkinsSecurite.list())

  async function checkout(row) {
    try {
      await qhseApi.checkinsSecurite.checkout(row.id)
      toast.success('Check-out enregistré.')
      reload()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Check-out impossible.')
    }
  }

  const columns = [
    { id: 'technicien_nom', header: 'Technicien', accessor: r => r.technicien_nom },
    { id: 'site_ref', header: 'Site', accessor: r => r.site_ref || '—' },
    {
      id: 'heure_checkin', header: 'Check-in',
      accessor: r => r.heure_checkin, cell: v => formatDate(v),
    },
    {
      id: 'heure_checkout_prevue', header: 'Check-out prévu',
      accessor: r => r.heure_checkout_prevue, cell: v => formatDate(v),
    },
    {
      id: 'statut', header: 'État',
      accessor: r => r,
      cell: r => (
        r.heure_checkout_reelle
          ? <Badge tone="success">Terminé</Badge>
          : r.en_retard
            ? <Badge tone="danger">
              <AlertTriangle size={12} /> En retard
            </Badge>
            : <Badge tone="info">En cours</Badge>
      ),
    },
  ]

  return (
    <>
      <ListShell
        title="Check-ins sécurité"
        subtitle="Techniciens seuls sur site à risque — escalade automatique si le check-out dépasse le délai."
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchable
        exportName="checkins-securite"
        actions={
          <Button onClick={() => setDialog(true)}>
            <Plus size={16} /> Check-in
          </Button>
        }
        rowActions={r => (!r.heure_checkout_reelle
          ? [{
            id: 'checkout', label: 'Check-out', icon: LogOut,
            onClick: () => checkout(r),
          }]
          : [])}
      />
      {dialog && (
        <CheckinDialog
          onClose={() => setDialog(false)}
          onDone={() => { setDialog(false); reload() }}
        />
      )}
    </>
  )
}

// WIR201 — création d'une SCAR (fournisseur/NCR saisis en id : aucun
// sélecteur cross-app sur cet écran QHSE, cf. ScarDemandeDialog de
// NonConformites.jsx dont c'est le même patron).
function ScarCreateDialog({ onClose, onDone }) {
  const [fournisseur, setFournisseur] = useState('')
  const [ncrSource, setNcrSource] = useState('')
  const [description, setDescription] = useState('')
  const [echeance, setEcheance] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!fournisseur || !ncrSource) {
      toast.error('ID fournisseur et ID NCR source requis.')
      return
    }
    setSaving(true)
    try {
      await qhseApi.demandesActionFournisseur.create({
        fournisseur: Number(fournisseur),
        ncr_source: Number(ncrSource),
        description_defaut: description,
        echeance_reponse: echeance || undefined,
      })
      toast.success('SCAR créée.')
      onDone()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Nouvelle SCAR</DialogTitle>
        <div className="flex flex-col gap-3 pt-2">
          <div>
            <Label htmlFor="scar-fournisseur">ID fournisseur</Label>
            <Input id="scar-fournisseur" value={fournisseur}
              onChange={e => setFournisseur(e.target.value)} inputMode="numeric" />
          </div>
          <div>
            <Label htmlFor="scar-ncr">ID NCR source</Label>
            <Input id="scar-ncr" value={ncrSource}
              onChange={e => setNcrSource(e.target.value)} inputMode="numeric" />
          </div>
          <div>
            <Label htmlFor="scar-desc">Description du défaut</Label>
            <Textarea id="scar-desc" rows={3} value={description}
              onChange={e => setDescription(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="scar-echeance">Échéance de réponse</Label>
            <Input id="scar-echeance" type="date" value={echeance}
              onChange={e => setEcheance(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>Créer</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// WIR201 — réponse fournisseur (émise → répondue).
function ScarRepondreDialog({ scar, onClose, onDone }) {
  const [causeRacine, setCauseRacine] = useState('')
  const [action, setAction] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.demandesActionFournisseur.repondre(scar.id, {
        cause_racine_fournisseur: causeRacine,
        action_fournisseur: action,
      })
      toast.success('Réponse fournisseur enregistrée.')
      onDone()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Réponse impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Réponse fournisseur — SCAR</DialogTitle>
        <div className="flex flex-col gap-3 pt-2">
          <div>
            <Label htmlFor="scar-cause">Cause racine (fournisseur)</Label>
            <Textarea id="scar-cause" rows={2} value={causeRacine}
              onChange={e => setCauseRacine(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="scar-action">Action corrective (fournisseur)</Label>
            <Textarea id="scar-action" rows={2} value={action}
              onChange={e => setAction(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>Enregistrer la réponse</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// WIR201 — vérification d'efficacité (répondue → vérifiée/close).
function ScarVerifierDialog({ scar, onClose, onDone }) {
  const [efficace, setEfficace] = useState('true')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.demandesActionFournisseur.verifier(scar.id, { efficace })
      toast.success('Vérification enregistrée.')
      onDone()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Vérification impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Vérifier l’efficacité — SCAR</DialogTitle>
        <div className="flex flex-col gap-3 pt-2">
          <div>
            <Label htmlFor="scar-efficace">Action efficace ?</Label>
            <Select value={efficace} onValueChange={setEfficace}>
              <SelectTrigger id="scar-efficace"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="true">Oui — clôturer</SelectItem>
                <SelectItem value="false">Non — rester ouverte</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>Vérifier</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ScarTab() {
  const [creating, setCreating] = useState(false)
  const [repondant, setRepondant] = useState(null)
  const [verifiant, setVerifiant] = useState(null)
  const { rows, loading, error, reload } = useQhseList(
    () => qhseApi.demandesActionFournisseur.list())
  const columns = [
    { id: 'fournisseur_nom', header: 'Fournisseur', accessor: r => r.fournisseur_nom },
    { id: 'description_defaut', header: 'Défaut', accessor: r => r.description_defaut || '—' },
    {
      id: 'echeance_reponse', header: 'Échéance',
      accessor: r => r.echeance_reponse, cell: v => formatDate(v),
    },
    { id: 'statut_display', header: 'Statut', accessor: r => r.statut_display },
  ]
  return (
    <>
      <ListShell
        title="Demandes d'action fournisseur (SCAR)"
        subtitle="Actions correctives demandées à un fournisseur après une non-conformité."
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchable
        exportName="scar-fournisseur"
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} /> Nouvelle SCAR
          </Button>
        }
        rowActions={r => [
          ...(r.statut === 'emise'
            ? [{ id: 'repondre', label: 'Répondre', icon: Reply, onClick: () => setRepondant(r) }]
            : []),
          ...(r.statut === 'repondue'
            ? [{ id: 'verifier', label: 'Vérifier', icon: CheckCircle2, onClick: () => setVerifiant(r) }]
            : []),
        ]}
      />
      {creating && (
        <ScarCreateDialog
          onClose={() => setCreating(false)}
          onDone={() => { setCreating(false); reload() }}
        />
      )}
      {repondant && (
        <ScarRepondreDialog
          scar={repondant}
          onClose={() => setRepondant(null)}
          onDone={() => { setRepondant(null); reload() }}
        />
      )}
      {verifiant && (
        <ScarVerifierDialog
          scar={verifiant}
          onClose={() => setVerifiant(null)}
          onDone={() => { setVerifiant(null); reload() }}
        />
      )}
    </>
  )
}

export default function CheckinsSecurite() {
  return (
    <Tabs defaultValue="checkins">
      <TabsList>
        <TabsTrigger value="checkins">Check-ins sécurité</TabsTrigger>
        <TabsTrigger value="scar">SCAR fournisseur</TabsTrigger>
      </TabsList>
      <TabsContent value="checkins"><CheckinsTab /></TabsContent>
      <TabsContent value="scar"><ScarTab /></TabsContent>
    </Tabs>
  )
}
