import { useState } from 'react'
import {
  Plus, LogOut, AlertTriangle, Reply, ShieldCheck,
} from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { ListShell } from '../../ui/module'
import {
  Button, Badge, Dialog, DialogContent, DialogTitle, Input, Label, Textarea,
  toast, Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { FieldSelect } from './QhseForm'
import { formatDate } from '../../lib/format'
import { useQhseList } from './useQhseList'

/* ============================================================================
   WIR115/WIR201 — Check-in sécurité (technicien seul sur site à risque) + SCAR.
   ----------------------------------------------------------------------------
   Donne enfin un écran aux deux backends jusqu'ici sombres :
   • Check-ins : le technicien pointe son arrivée sur un site à risque avec une
     heure de check-out prévue ; la tâche beat d'escalade escalade toute absence
     de check-out passé le délai. Bouton « Check-out » pour clôturer le cycle.
   • SCAR : demandes d'action corrective fournisseur — WIR201 sort l'onglet de
     la lecture seule : création (« Nouvelle SCAR »), puis le cycle
     émise→répondue→vérifiée/close entièrement pilotable depuis l'écran
     (rowActions Répondre/Vérifier, visibles seulement sur les statuts
     autorisés — le serveur reste la seule autorité sur les transitions).
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

function ScarCreateDialog({ onClose, onDone }) {
  const [fournisseur, setFournisseur] = useState('')
  const [ncrSource, setNcrSource] = useState('')
  const [descriptionDefaut, setDescriptionDefaut] = useState('')
  const [echeanceReponse, setEcheanceReponse] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!fournisseur || !ncrSource) {
      toast.error('Fournisseur et NCR source sont requis.')
      return
    }
    setSaving(true)
    try {
      await qhseApi.demandesActionFournisseur.create({
        fournisseur: Number(fournisseur),
        ncr_source: Number(ncrSource),
        description_defaut: descriptionDefaut,
        echeance_reponse: echeanceReponse || undefined,
      })
      toast.success('SCAR créée.')
      onDone()
      onClose()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création de la SCAR impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Nouvelle SCAR</DialogTitle>
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="scar-fournisseur">Fournisseur (id)</Label>
              <Input id="scar-fournisseur" inputMode="numeric" value={fournisseur}
                onChange={(e) => setFournisseur(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="scar-ncr">NCR source (id)</Label>
              <Input id="scar-ncr" inputMode="numeric" value={ncrSource}
                onChange={(e) => setNcrSource(e.target.value)} />
            </div>
          </div>
          <div>
            <Label htmlFor="scar-defaut">Description du défaut</Label>
            <Textarea id="scar-defaut" rows={3} value={descriptionDefaut}
              onChange={(e) => setDescriptionDefaut(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="scar-echeance">Échéance de réponse</Label>
            <Input id="scar-echeance" type="date" value={echeanceReponse}
              onChange={(e) => setEcheanceReponse(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Créer la SCAR'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ScarRepondreDialog({ scar, onClose, onDone }) {
  const [causeRacine, setCauseRacine] = useState('')
  const [actionFournisseur, setActionFournisseur] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.demandesActionFournisseur.repondre(scar.id, {
        cause_racine_fournisseur: causeRacine,
        action_fournisseur: actionFournisseur,
      })
      toast.success('Réponse fournisseur enregistrée.')
      onDone()
      onClose()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Réponse impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Réponse fournisseur — {scar.fournisseur_nom}</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label htmlFor="scar-cause">Cause racine</Label>
            <Textarea id="scar-cause" rows={2} value={causeRacine}
              onChange={(e) => setCauseRacine(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="scar-action">Action corrective</Label>
            <Textarea id="scar-action" rows={2} value={actionFournisseur}
              onChange={(e) => setActionFournisseur(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer la réponse'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

const EFFICACE_OPTS = [
  { value: 'oui', label: 'Efficace — clore la SCAR' },
  { value: 'non', label: 'Non efficace — rester vérifiée' },
]

function ScarVerifierDialog({ scar, onClose, onDone }) {
  const [efficace, setEfficace] = useState('oui')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await qhseApi.demandesActionFournisseur.verifier(scar.id, {
        efficace: efficace === 'oui',
      })
      toast.success('Vérification enregistrée.')
      onDone()
      onClose()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Vérification impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Vérifier l'efficacité — {scar.fournisseur_nom}</DialogTitle>
        <div className="flex flex-col gap-3">
          <div>
            <Label htmlFor="scar-efficace">Verdict</Label>
            <FieldSelect id="scar-efficace" value={efficace} onValueChange={setEfficace}
              options={EFFICACE_OPTS} />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer la vérification'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ScarTab() {
  const [creating, setCreating] = useState(false)
  const [responding, setResponding] = useState(null)
  const [verifying, setVerifying] = useState(null)
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
        subtitle="Actions correctives demandées à un fournisseur après une non-conformité — cycle émise→répondue→vérifiée/close."
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
        rowActions={r => {
          const actions = []
          // WIR201 — boutons SEULEMENT sur les statuts autorisés (le serveur
          // refuse déjà les transitions hors ordre, l'écran évite juste de
          // proposer un clic qui échouerait à coup sûr).
          if (r.statut === 'emise') {
            actions.push({
              id: 'repondre', label: 'Répondre', icon: Reply,
              onClick: () => setResponding(r),
            })
          }
          if (r.statut === 'repondue' || r.statut === 'verifiee') {
            actions.push({
              id: 'verifier', label: 'Vérifier', icon: ShieldCheck,
              onClick: () => setVerifying(r),
            })
          }
          return actions
        }}
      />
      {creating && (
        <ScarCreateDialog
          onClose={() => setCreating(false)}
          onDone={reload}
        />
      )}
      {responding && (
        <ScarRepondreDialog
          scar={responding}
          onClose={() => setResponding(null)}
          onDone={reload}
        />
      )}
      {verifying && (
        <ScarVerifierDialog
          scar={verifying}
          onClose={() => setVerifying(null)}
          onDone={reload}
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
