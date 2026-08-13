// PACT123 — Onglet « Exports planifiés » de la page Paramètres (FG383).
//
// `core.ScheduledExport` planifie un extrait de données vers une destination
// EXTERNE (SFTP / bucket S3) : le modèle et son ViewSet existaient depuis FG383
// sans aucun appelant frontend.
//
// À NE PAS CONFONDRE avec l'export manuel ponctuel déjà présent dans Paramètres
// (onglet « Données ») : celui-là télécharge un fichier tout de suite dans le
// navigateur et n'a aucun lien avec ce modèle ; celui-ci DÉCLARE une livraison
// récurrente vers un système tiers.
//
// ⚠ SANS IDENTIFIANTS PROVISIONNÉS, l'exécution reste sans effet et le serveur
// renvoie le statut « non_configure ». L'écran l'affiche EXPLICITEMENT (jamais
// une erreur, jamais un plantage, jamais un faux « ok ») — c'est le
// comportement attendu tant que le fondateur n'a pas fourni les accès SFTP/S3.
//
// Sécurité : lecture ouverte à tout utilisateur authentifié, écriture réservée
// au palier admin/responsable — le SERVEUR re-vérifie
// (IsAdminOrResponsableTier). `company` n'est JAMAIS envoyée : imposée côté
// serveur (TenantMixin).
import { useEffect, useState } from 'react'
import { CalendarClock, Play, Plus, Trash2 } from 'lucide-react'
import api from '../../api/axios'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { toast } from '../../ui/confirm'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'
import { formatDateTime } from '../../lib/format'

// Miroir de ScheduledExport.FORMAT_CHOICES / DEST_CHOICES.
const FORMATS = [['csv', 'CSV'], ['parquet', 'Parquet']]
const DESTINATIONS = [['sftp', 'SFTP'], ['s3', 'Bucket S3']]

// Statuts renvoyés par le runner `core.scheduled_export` (+ le cas « jamais
// exécuté », qui n'est pas un statut mais une absence).
const STATUT_LABELS = {
  ok: 'Livré',
  non_configure: 'Non configuré',
  erreur: 'Erreur',
}
const STATUT_TONES = { ok: 'success', non_configure: 'warning', erreur: 'danger' }

const VIDE = {
  titre: '', dataset: '', format: 'csv', destination: 'sftp', cron: '',
}

export default function ExportsPlanifiesSection() {
  const canManage = useIsAdminOrResponsable()

  const [rows, setRows] = useState([])
  const [datasets, setDatasets] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [runningId, setRunningId] = useState(null)
  const [draft, setDraft] = useState(VIDE)

  const charger = () => api.get('/core/scheduled-exports/')
    .then((res) => {
      setRows(res.data?.results ?? res.data ?? [])
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => { charger() }, [])

  // Catalogue des jeux de données interrogeables (explorateur FG382). Son
  // absence ne casse rien : le champ reste saisissable librement.
  useEffect(() => {
    let annule = false
    api.get('/core/saved-queries/datasets/')
      .then((res) => {
        if (annule) return
        const list = res.data?.results ?? res.data ?? []
        setDatasets(Array.isArray(list) ? list : [])
      })
      .catch(() => { if (!annule) setDatasets([]) })
    return () => { annule = true }
  }, [])

  const creer = async () => {
    const titre = draft.titre.trim()
    const dataset = draft.dataset.trim()
    if (!titre || !dataset) return
    setBusy(true)
    try {
      await api.post('/core/scheduled-exports/', {
        titre, dataset, format: draft.format,
        destination: draft.destination, cron: draft.cron.trim(),
      })
      setDraft(VIDE)
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    } finally { setBusy(false) }
  }

  // Exécution immédiate : le serveur renvoie l'extrait mis à jour (statut
  // compris). Un extrait non configuré revient « non_configure » — c'est un
  // résultat NORMAL, affiché tel quel et jamais transformé en erreur.
  const executer = async (row) => {
    setRunningId(row.id)
    try {
      const res = await api.post(`/core/scheduled-exports/${row.id}/executer/`)
      const maj = res.data ?? null
      if (maj && maj.id) {
        setRows((current) => current.map((r) => (r.id === maj.id ? maj : r)))
      } else {
        charger()
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Exécution impossible.')
    } finally { setRunningId(null) }
  }

  const basculerActif = async (row) => {
    try {
      await api.patch(`/core/scheduled-exports/${row.id}/`, { actif: !row.actif })
      charger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Modification impossible.')
    }
  }

  const supprimer = async (row) => {
    if (!window.confirm(`Supprimer l'export planifié « ${row.titre} » ?`)) return
    try {
      await api.delete(`/core/scheduled-exports/${row.id}/`)
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
      <EmptyState title="Impossible de charger les exports planifiés"
        description="Une erreur est survenue lors du chargement." className="py-6" />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11.5px] text-muted-foreground">
        Livraison récurrente d'un jeu de données vers un système externe (SFTP
        ou bucket S3). Différent de l'export manuel de l'onglet « Données », qui
        télécharge un fichier immédiatement. Tant que les accès à la destination
        n'ont pas été fournis, l'exécution reste sans effet et le statut affiché
        est « Non configuré ».
      </p>

      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Exports planifiés"
            icon={<><path d="M8 2v4"/><path d="M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18"/></>} />

          {rows.length === 0 && (
            <EmptyState icon={CalendarClock} title="Aucun export planifié"
              description="Déclarez votre premier export récurrent ci-dessous."
              className="py-6" />
          )}

          <div className="flex flex-col gap-2">
            {rows.map((row) => {
              const statut = row.dernier_statut || ''
              const jamais = !statut
              return (
                <div key={row.id} data-testid={`export-planifie-${row.id}`}
                  className="rounded-lg border border-border p-3">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={['min-w-[140px] flex-[1_1_140px] font-medium text-sm',
                      row.actif ? '' : 'opacity-50'].join(' ')}>{row.titre}</span>
                    <Badge tone="neutral">{row.dataset}</Badge>
                    <Badge tone="neutral">{(row.format || '').toUpperCase()}</Badge>
                    <Badge tone="info">
                      {DESTINATIONS.find(([v]) => v === row.destination)?.[1] ?? row.destination}
                    </Badge>
                    <div className="ml-auto flex items-center gap-1">
                      {canManage && (
                        <Button type="button" size="sm"
                          variant={row.actif ? 'success' : 'secondary'}
                          onClick={() => basculerActif(row)}>
                          {row.actif ? 'Actif' : 'Inactif'}
                        </Button>
                      )}
                      {canManage && (
                        <Button type="button" size="sm" variant="outline"
                          disabled={runningId === row.id}
                          onClick={() => executer(row)}>
                          <Play className="size-4" aria-hidden="true" />
                          {runningId === row.id ? 'Exécution…' : 'Exécuter maintenant'}
                        </Button>
                      )}
                      {canManage && (
                        <IconButton size="sm" variant="outline" label="Supprimer l'export planifié"
                          className="text-destructive hover:text-destructive"
                          onClick={() => supprimer(row)}>
                          <Trash2 className="size-4" aria-hidden="true" />
                        </IconButton>
                      )}
                    </div>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2"
                    data-testid={`export-statut-${row.id}`}>
                    {/* Statut TOUJOURS affiché explicitement — y compris
                        « Non configuré » et « Jamais exécuté ». */}
                    <Badge tone={jamais ? 'neutral' : (STATUT_TONES[statut] ?? 'neutral')}>
                      {jamais ? 'Jamais exécuté' : (STATUT_LABELS[statut] ?? statut)}
                    </Badge>
                    {row.derniere_execution_le && (
                      <span className="text-xs text-muted-foreground">
                        Dernière exécution : {formatDateTime(row.derniere_execution_le)}
                      </span>
                    )}
                    {row.cron && (
                      <span className="text-xs text-muted-foreground">
                        Planification : {row.cron}
                      </span>
                    )}
                    {statut === 'non_configure' && (
                      <span className="text-xs text-muted-foreground">
                        Les accès à la destination ne sont pas encore fournis :
                        rien n'a été envoyé.
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {canManage && (
            <div className="mt-3 rounded-lg border border-dashed border-border p-3">
              <div className="flex flex-wrap gap-1.5">
                <Input className="min-w-[160px] flex-[2_1_160px]"
                  placeholder="Titre (ex. Ventes du mois vers le comptable)"
                  value={draft.titre}
                  onChange={(e) => setDraft((d) => ({ ...d, titre: e.target.value }))} />
                <Input className="min-w-[140px] flex-[1_1_140px]"
                  list="exports-planifies-datasets"
                  placeholder="Jeu de données"
                  value={draft.dataset}
                  onChange={(e) => setDraft((d) => ({ ...d, dataset: e.target.value }))} />
                <datalist id="exports-planifies-datasets">
                  {datasets.map((d) => (
                    <option key={d.name} value={d.name}>{d.label ?? d.name}</option>
                  ))}
                </datalist>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                <div className="min-w-[120px] flex-1">
                  <Select value={draft.format}
                    onValueChange={(v) => setDraft((d) => ({ ...d, format: v }))}>
                    <SelectTrigger aria-label="Format du fichier"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FORMATS.map(([v, label]) => (
                        <SelectItem key={v} value={v}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="min-w-[120px] flex-1">
                  <Select value={draft.destination}
                    onValueChange={(v) => setDraft((d) => ({ ...d, destination: v }))}>
                    <SelectTrigger aria-label="Destination"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {DESTINATIONS.map(([v, label]) => (
                        <SelectItem key={v} value={v}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input className="min-w-[160px] flex-[1_1_160px]"
                  placeholder="Planification cron (ex. 0 6 * * 1)"
                  value={draft.cron}
                  onChange={(e) => setDraft((d) => ({ ...d, cron: e.target.value }))} />
                <Button type="button" onClick={creer} disabled={busy}>
                  <Plus className="size-4" aria-hidden="true" /> Créer l'export
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
