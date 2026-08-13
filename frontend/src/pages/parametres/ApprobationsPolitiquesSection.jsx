// PACT147 — Onglet « Politiques d'approbation » de la page Paramètres (FG25).
//
// `parametres.ApprovalPolicy` DÉCLARE, par société, quelles actions à fort
// impact — remise, montant de devis, bon de commande, dépense, contrat, avoir —
// exigent une approbation, à partir de quel seuil et vers quel palier
// approbateur. Le modèle et son CRUD (`/parametres/approbations/`) existaient
// sans aucun écran : la configuration en amont n'existait NULLE PART.
//
// À NE PAS CONFONDRE avec l'écran d'approbations déjà construit : celui-là est
// la BOÎTE DE RÉCEPTION des approbations en attente — il consomme des
// décisions ; il ne configure pas ce qui les déclenche. Cet écran fait
// l'inverse.
//
// OPT-IN STRICT : sans politique activée, rien ne change (le serveur renvoie
// `requires_approval = False`). Chaque écriture est tracée au Journal d'audit
// (section « approbations »), rappelé en bas de l'écran.
//
// Sécurité : lecture tout rôle, écriture Administrateur/Responsable — le
// SERVEUR re-vérifie (IsAdminOrResponsableTier). `company` n'est JAMAIS
// envoyée : imposée côté serveur (TenantMixin).
import { useEffect, useMemo, useState } from 'react'
import { ShieldAlert, Plus, Trash2 } from 'lucide-react'
import api from '../../api/axios'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { toast } from '../../ui/confirm'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'
import SettingsAuditFeed from './SettingsAuditFeed'

// Miroir de ApprovalPolicy.ActionType / ApproverTier (backend). Le serveur
// renvoie aussi les libellés (`action_type_label`) : on ne les invente pas,
// cette table sert au FORMULAIRE de création (avant tout aller-retour).
const ACTION_TYPES = [
  ['discount', 'Remise sur devis'],
  ['quote_amount', 'Montant de devis'],
  ['purchase_order', 'Bon de commande fournisseur'],
  ['expense', 'Dépense / frais'],
  ['contract', 'Contrat'],
  ['refund', 'Avoir / remboursement'],
]
const APPROVER_TIERS = [
  ['responsable', 'Responsable (ou plus)'],
  ['admin', 'Administrateur uniquement'],
]
const TIER_LABELS = Object.fromEntries(APPROVER_TIERS)

const VIDE = { action_type: '', seuil: '', approver_tier: 'admin', note: '' }

export default function ApprobationsPolitiquesSection() {
  const canManage = useIsAdminOrResponsable()

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState(VIDE)
  const [erreur, setErreur] = useState('')

  const charger = () => api.get('/parametres/approbations/')
    .then((res) => {
      setRows(res.data?.results ?? res.data ?? [])
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => { charger() }, [])

  // Une seule politique par type d'action (contrainte serveur) : on ne propose
  // que les types encore libres, plutôt que de laisser l'utilisateur se prendre
  // un 400.
  const typesDisponibles = useMemo(() => {
    const pris = new Set(rows.map((r) => r.action_type))
    return ACTION_TYPES.filter(([v]) => !pris.has(v))
  }, [rows])

  const creer = async () => {
    if (!draft.action_type) return
    setBusy(true)
    setErreur('')
    try {
      await api.post('/parametres/approbations/', {
        action_type: draft.action_type,
        // Seuil vide = la politique s'applique TOUJOURS (null côté serveur).
        seuil: draft.seuil === '' ? null : draft.seuil,
        approver_tier: draft.approver_tier,
        enabled: true,
        note: draft.note.trim(),
      })
      setDraft(VIDE)
      charger()
    } catch (e) {
      const data = e?.response?.data
      setErreur(data?.action_type?.[0] ?? data?.seuil?.[0] ?? data?.detail
        ?? 'Création impossible.')
    } finally { setBusy(false) }
  }

  const patcher = async (row, patch) => {
    try {
      await api.patch(`/parametres/approbations/${row.id}/`, patch)
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Modification impossible.')
    }
  }

  const supprimer = async (row) => {
    const libelle = row.action_type_label || row.action_type
    if (!window.confirm(`Supprimer la politique « ${libelle} » ?`)) return
    try {
      await api.delete(`/parametres/approbations/${row.id}/`)
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (loadError) {
    return (
      <EmptyState title="Impossible de charger les politiques d'approbation"
        description="Une erreur est survenue lors du chargement." className="py-6" />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11.5px] text-muted-foreground">
        Déclare ce qui DÉCLENCHE une approbation : le type d'action, le seuil
        au-delà duquel elle s'applique et le palier habilité à approuver. La
        boîte de réception des approbations en attente est un autre écran — ici,
        on configure en amont. Rien ne change tant qu'aucune politique n'est
        activée.
      </p>

      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Politiques d'approbation"
            icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M12 8v4"/><path d="M12 16h.01"/></>} />

          {rows.length === 0 && (
            <EmptyState icon={ShieldAlert} title="Aucune politique d'approbation"
              description="Aucune action n'exige d'approbation pour le moment."
              className="py-6" />
          )}

          <div className="flex flex-col gap-2">
            {rows.map((row) => (
              <div key={row.id} data-testid={`politique-${row.action_type}`}
                className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className={['min-w-[160px] flex-[1_1_160px] font-medium text-sm',
                    row.enabled ? '' : 'opacity-50'].join(' ')}>
                    {row.action_type_label || row.action_type}
                  </span>
                  <Badge tone="info">
                    {row.approver_tier_label
                      || TIER_LABELS[row.approver_tier]
                      || row.approver_tier}
                  </Badge>
                  <Badge tone="neutral">
                    {row.seuil === null || row.seuil === undefined || row.seuil === ''
                      ? 'Toujours'
                      : `À partir de ${row.seuil}`}
                  </Badge>
                  <div className="ml-auto flex items-center gap-1">
                    {canManage && (
                      <Button type="button" size="sm"
                        variant={row.enabled ? 'success' : 'secondary'}
                        onClick={() => patcher(row, { enabled: !row.enabled })}>
                        {row.enabled ? 'Activée' : 'Désactivée'}
                      </Button>
                    )}
                    {canManage && (
                      <IconButton size="sm" variant="outline"
                        label="Supprimer la politique"
                        className="text-destructive hover:text-destructive"
                        onClick={() => supprimer(row)}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </IconButton>
                    )}
                  </div>
                </div>
                {row.note && (
                  <p className="mt-1 text-xs text-muted-foreground">{row.note}</p>
                )}
              </div>
            ))}
          </div>

          {canManage && typesDisponibles.length > 0 && (
            <div className="mt-3 rounded-lg border border-dashed border-border p-3">
              <div className="flex flex-wrap gap-1.5">
                <div className="min-w-[180px] flex-[2_1_180px]">
                  <Select value={draft.action_type}
                    onValueChange={(v) => setDraft((d) => ({ ...d, action_type: v }))}>
                    <SelectTrigger aria-label="Type d'action">
                      <SelectValue placeholder="Type d'action à approuver" />
                    </SelectTrigger>
                    <SelectContent>
                      {typesDisponibles.map(([v, label]) => (
                        <SelectItem key={v} value={v}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input className="min-w-[140px] flex-[1_1_140px]"
                  type="number" step="any"
                  placeholder="Seuil (vide = toujours)"
                  value={draft.seuil}
                  onChange={(e) => setDraft((d) => ({ ...d, seuil: e.target.value }))} />
                <div className="min-w-[180px] flex-[1_1_180px]">
                  <Select value={draft.approver_tier}
                    onValueChange={(v) => setDraft((d) => ({ ...d, approver_tier: v }))}>
                    <SelectTrigger aria-label="Palier approbateur"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {APPROVER_TIERS.map(([v, label]) => (
                        <SelectItem key={v} value={v}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Input className="min-w-[200px] flex-1" placeholder="Note (facultatif)"
                  value={draft.note}
                  onChange={(e) => setDraft((d) => ({ ...d, note: e.target.value }))} />
                <Button type="button" onClick={creer} disabled={busy || !draft.action_type}>
                  <Plus className="size-4" aria-hidden="true" /> Activer la politique
                </Button>
              </div>
              {erreur && <p className="mt-1.5 text-xs text-destructive">{erreur}</p>}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Traçabilité : chaque création/modification/suppression de politique est
          écrite au Journal d'audit des paramètres, section « approbations ». */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Journal d'audit des approbations"
            icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/></>} />
          <SettingsAuditFeed section="approbations" />
        </CardContent>
      </Card>
    </div>
  )
}
