import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import {
  Badge, Button, Checkbox, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, Label, Input, toast, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import tiersApi from '../../api/tiersApi'

/* ============================================================================
   WIR152 — Écran « Tiers » (`/tiers`) : répertoire unifié.
   ----------------------------------------------------------------------------
   `TiersViewSet` (ARC17, CRUD complet + recherche nom/email/ice/rc/if/cin)
   n'était consommé qu'en resolver de nom par deux écrans compta
   (`CockpitPage.jsx`/`EngagementsPage.jsx`). Cet écran offre la navigation
   (liste/filtre/édition) sur le répertoire d'une société — la fondation
   identité (`res.partner`-like) que les domaines (crm.Client, stock.
   Fournisseur…) référenceront via bridges (ARC18/19).
   ========================================================================== */

const TYPE_OPTIONS = [
  ['particulier', 'Particulier'],
  ['entreprise', 'Entreprise'],
]

const ROLE_TONE = {
  client: 'success',
  fournisseur: 'info',
  partenaire: 'warning',
  soustraitant: 'neutral',
}
const ROLE_LABEL = {
  client: 'Client', fournisseur: 'Fournisseur',
  partenaire: 'Partenaire', soustraitant: 'Sous-traitant',
}

function rolesOf(t) {
  const roles = []
  if (t.is_client) roles.push('client')
  if (t.is_fournisseur) roles.push('fournisseur')
  if (t.is_partenaire) roles.push('partenaire')
  if (t.is_soustraitant) roles.push('soustraitant')
  return roles
}

function TiersDialog({ record, onClose, onSaved }) {
  const isEdit = Boolean(record)
  const [typeTiers, setTypeTiers] = useState(record?.type_tiers || 'particulier')
  const [nom, setNom] = useState(record?.nom || '')
  const [prenom, setPrenom] = useState(record?.prenom || '')
  const [raisonSociale, setRaisonSociale] = useState(record?.raison_sociale || '')
  const [telephone, setTelephone] = useState(record?.telephone || '')
  const [whatsapp, setWhatsapp] = useState(record?.whatsapp || '')
  const [email, setEmail] = useState(record?.email || '')
  const [adresse, setAdresse] = useState(record?.adresse || '')
  const [ville, setVille] = useState(record?.ville || '')
  const [ice, setIce] = useState(record?.ice || '')
  const [rc, setRc] = useState(record?.rc || '')
  const [identifiantFiscal, setIdentifiantFiscal] = useState(record?.identifiant_fiscal || '')
  const [cin, setCin] = useState(record?.cin || '')
  const [rib, setRib] = useState(record?.rib || '')
  const [isClient, setIsClient] = useState(record?.is_client || false)
  const [isFournisseur, setIsFournisseur] = useState(record?.is_fournisseur || false)
  const [isPartenaire, setIsPartenaire] = useState(record?.is_partenaire || false)
  const [isSoustraitant, setIsSoustraitant] = useState(record?.is_soustraitant || false)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || prenom || raisonSociale || telephone || email)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const peutEnregistrer = Boolean(nom)

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    const payload = {
      type_tiers: typeTiers, nom, prenom, raison_sociale: raisonSociale,
      telephone, whatsapp, email, adresse, ville,
      ice, rc, identifiant_fiscal: identifiantFiscal, cin, rib,
      is_client: isClient, is_fournisseur: isFournisseur,
      is_partenaire: isPartenaire, is_soustraitant: isSoustraitant,
    }
    try {
      if (isEdit) {
        await tiersApi.tiers.update(record.id, payload)
      } else {
        await tiersApi.tiers.create(payload)
      }
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.nom || data?.email || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Modifier — ${record.nom_complet || record.nom}` : 'Nouveau tiers'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-type">Type</Label>
              <select
                id="tiers-type" value={typeTiers}
                onChange={(e) => setTypeTiers(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {TYPE_OPTIONS.map(([v, label]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-nom">Nom / Raison sociale</Label>
              <Input id="tiers-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-prenom">Prénom (option.)</Label>
              <Input id="tiers-prenom" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-raison">Raison sociale (option.)</Label>
              <Input id="tiers-raison" value={raisonSociale} onChange={(e) => setRaisonSociale(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-tel">Téléphone (option.)</Label>
              <Input id="tiers-tel" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-whatsapp">WhatsApp (option.)</Label>
              <Input id="tiers-whatsapp" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-email">Email (option.)</Label>
              <Input id="tiers-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-ville">Ville (option.)</Label>
              <Input id="tiers-ville" value={ville} onChange={(e) => setVille(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tiers-adresse">Adresse (option.)</Label>
            <Input id="tiers-adresse" value={adresse} onChange={(e) => setAdresse(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-ice">ICE (option.)</Label>
              <Input id="tiers-ice" value={ice} onChange={(e) => setIce(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-rc">RC (option.)</Label>
              <Input id="tiers-rc" value={rc} onChange={(e) => setRc(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-if">IF (option.)</Label>
              <Input id="tiers-if" value={identifiantFiscal} onChange={(e) => setIdentifiantFiscal(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="tiers-cin">CIN (option.)</Label>
              <Input id="tiers-cin" value={cin} onChange={(e) => setCin(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tiers-rib">RIB (option.)</Label>
            <Input id="tiers-rib" value={rib} onChange={(e) => setRib(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Rôles</Label>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={isClient} onCheckedChange={setIsClient} aria-label="Client" />
                Client
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={isFournisseur} onCheckedChange={setIsFournisseur} aria-label="Fournisseur" />
                Fournisseur
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={isPartenaire} onCheckedChange={setIsPartenaire} aria-label="Partenaire" />
                Partenaire
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={isSoustraitant} onCheckedChange={setIsSoustraitant} aria-label="Sous-traitant" />
                Sous-traitant
              </label>
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : (isEdit ? 'Enregistrer' : 'Créer le tiers')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function TiersPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [dialog, setDialog] = useState(null) // { record? } | null

  // Rechargement après création/modification (handler `onSaved` ci-dessous) —
  // `loading`/`error` sont reposés synchronement, mais depuis un gestionnaire
  // d'événement, jamais depuis un effet.
  const load = () => {
    setLoading(true)
    setError(null)
    return tiersApi.tiers.list()
      .then((r) => {
        const data = r?.data
        setRows(Array.isArray(data) ? data : (data?.results ?? []))
      })
      .catch(() => setError('Chargement impossible.'))
      .finally(() => setLoading(false))
  }

  // Chargement au montage : `loading`/`error` démarrent déjà à leurs valeurs
  // de chargement (true/null), donc aucun reset synchrone n'est nécessaire
  // ici (react-hooks/set-state-in-effect — même motif que
  // PatrimoineTree.jsx, pages/immobilier). Les rechargements ultérieurs
  // passent par `load` ci-dessus, jamais par cet effet.
  useEffect(() => {
    tiersApi.tiers.list()
      .then((r) => {
        const data = r?.data
        setRows(Array.isArray(data) ? data : (data?.results ?? []))
      })
      .catch(() => setError('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [])

  const columns = useMemo(() => [
    {
      id: 'nom', header: 'Nom / Raison sociale', width: 220,
      accessor: (r) => r.nom_complet || r.nom, cell: (v) => v || '—',
    },
    {
      id: 'type', header: 'Type', width: 110,
      accessor: (r) => (r.type_tiers_display || r.type_tiers),
      cell: (v) => v || '—',
    },
    {
      id: 'roles', header: 'Rôles', width: 220, searchable: false,
      accessor: (r) => rolesOf(r), cell: (v) => (
        <div className="flex flex-wrap gap-1">
          {v.length === 0 && '—'}
          {v.map((role) => (
            <Badge key={role} tone={ROLE_TONE[role]}>{ROLE_LABEL[role]}</Badge>
          ))}
        </div>
      ),
    },
    {
      id: 'telephone', header: 'Téléphone', width: 130,
      accessor: (r) => r.telephone, cell: (v) => v || '—',
    },
    {
      id: 'email', header: 'Email', width: 180,
      accessor: (r) => r.email, cell: (v) => v || '—',
    },
    {
      id: 'ville', header: 'Ville', width: 130,
      accessor: (r) => r.ville, cell: (v) => v || '—',
    },
  ], [])

  const rowActions = (row) => [{
    id: 'modifier', label: 'Modifier',
    onClick: () => setDialog({ record: row }),
  }]

  const actions = (
    <Button onClick={() => setDialog({})}>
      <Plus /> Nouveau tiers
    </Button>
  )

  return (
    <div className="page flex flex-col gap-4">
      <ListShell
        title="Tiers"
        subtitle="Répertoire unifié des parties prenantes de la société (clients, fournisseurs, partenaires, sous-traitants)."
        actions={actions}
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="tiers"
        emptyTitle="Aucun tiers"
        emptyDescription="Aucun tiers enregistré pour l’instant."
      />

      {dialog && (
        <TiersDialog
          record={dialog.record}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null)
            load()
            toast.success(dialog.record ? 'Tiers modifié.' : 'Tiers créé.')
          }}
        />
      )}
    </div>
  )
}
