import { useState } from 'react'
import { Plus, LogOut, AlertTriangle } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { ListShell } from '../../ui/module'
import {
  Button, Badge, Dialog, DialogContent, DialogTitle, Input, Label, toast,
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

function ScarTab() {
  const { rows, loading, error } = useQhseList(
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
    <ListShell
      title="Demandes d'action fournisseur (SCAR)"
      subtitle="Actions correctives demandées à un fournisseur après une non-conformité."
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      exportName="scar-fournisseur"
    />
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
