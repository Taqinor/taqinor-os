// F18/F12/F14/F20 — Onglet « Sécurité & terrain » de la page Paramètres :
//   * F18 — checklist des consignes de sécurité (EPI portés, consignation
//     électrique…), éditable, signée par le technicien sur chaque intervention ;
//   * F12 — seuil (%) de dépassement de consommation déclenchant la revue ;
//   * F14/F9/F20 — fournisseurs des interfaces SWAPPABLES (transcription, OCR
//     n° de série, QA photo IA). Vide = no-op total (aucun coût, aucune clé).
// Section autonome (charge/enregistre seule). Texte en français.
import { useEffect, useState } from 'react'
import { Plus, Trash2, ChevronUp, ChevronDown, AlertCircle } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import parametresApi from '../../api/parametresApi'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
  toast,
} from '../../ui'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { SectionTitle } from './peComponents'

const slugify = (s) => s.trim().toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40)

export default function SecuriteTerrainSection() {
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  // ERR62 — un échec de chargement affiche une erreur + Réessayer (au lieu d'un
  // état « vide » trompeur et d'un profil non chargé silencieux).
  const [loadError, setLoadError] = useState(false)
  const [newLibelle, setNewLibelle] = useState('')
  const [profile, setProfile] = useState(null)
  // VX244 — une consigne de sécurité (EPI, consignation électrique…) est
  // signée par le technicien à CHAQUE intervention : suppression à
  // confirmation tapée (severity="high"), plus jamais un `window.confirm`.
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = () => Promise.all([
    installationsApi.getConsignesSecurite(),
    parametresApi.getProfile(),
  ]).then(([cs, pr]) => {
    setSlots(cs.data.results ?? cs.data)
    setProfile(pr.data)
    setLoadError(false)
  }).catch(() => setLoadError(true)).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const add = async () => {
    const libelle = newLibelle.trim()
    if (!libelle) return
    try {
      await installationsApi.saveConsigneSecurite(null, {
        cle: slugify(libelle) || `consigne_${Date.now()}`,
        libelle, ordre: slots.length,
      })
      setNewLibelle(''); load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const rename = async (s, libelle) => {
    if (!libelle.trim() || libelle === s.libelle) return
    try { await installationsApi.saveConsigneSecurite(s.id, { libelle }); load() } catch { /* */ }
  }
  const toggleActif = async (s) => {
    try { await installationsApi.saveConsigneSecurite(s.id, { actif: !s.actif }); load() } catch { /* */ }
  }
  const move = async (idx, dir) => {
    const j = idx + dir
    if (j < 0 || j >= slots.length) return
    const a = slots[idx]; const b = slots[j]
    try {
      await Promise.all([
        installationsApi.saveConsigneSecurite(a.id, { ordre: b.ordre }),
        installationsApi.saveConsigneSecurite(b.id, { ordre: a.ordre }),
      ])
      load()
    } catch { /* */ }
  }
  const del = (s) => setPendingDelete(s)

  const confirmDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await installationsApi.deleteConsigneSecurite(pendingDelete.id)
      setPendingDelete(null)
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Suppression impossible (protégée ?).')
    } finally {
      setDeleting(false)
    }
  }
  const saveProfile = async (patch) => {
    try {
      const r = await parametresApi.updateProfile(patch)
      setProfile(r.data)
      toast.success('Enregistré.')
    } catch { toast.error('Enregistrement impossible.') }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )

  if (loadError) return (
    <div className="flex flex-col items-start gap-2">
      <p className="flex items-center gap-2 text-sm text-destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        Réglages sécurité & terrain indisponibles (serveur ?).
      </p>
      <Button type="button" size="sm" variant="outline" onClick={load}>Réessayer</Button>
    </div>
  )

  return (
    <div className="flex flex-col gap-4">
      {/* ── F18 — Consignes de sécurité ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Consignes de sécurité"
            icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>} />
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Points cochés et signés par le technicien sur chaque intervention
            (EPI portés, consignation électrique…). Désactiver retire le point
            des nouvelles interventions sans toucher à l'historique.
          </p>
          <div className="flex flex-col gap-2">
            {slots.length === 0 && (
              <EmptyState title="Aucune consigne"
                description="Ajoutez votre première consigne ci-dessous." className="py-6" />
            )}
            {slots.map((s, i) => (
              <div key={s.id} className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border p-2">
                {/* ERR102 — re-monte le champ si le serveur normalise le libellé. */}
                <Input key={s.libelle} className={['min-w-[200px] flex-[1_1_200px]', s.actif ? '' : 'opacity-50'].join(' ')}
                  defaultValue={s.libelle} onBlur={(e) => rename(s, e.target.value)} />
                <div className="ml-auto flex items-center gap-1">
                  <IconButton size="sm" variant="ghost" label="Monter"
                    disabled={i === 0} onClick={() => move(i, -1)}>
                    <ChevronUp className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Descendre"
                    disabled={i === slots.length - 1} onClick={() => move(i, 1)}>
                    <ChevronDown className="size-4" aria-hidden="true" />
                  </IconButton>
                  <Button type="button" size="sm"
                    variant={s.actif ? 'success' : 'secondary'}
                    onClick={() => toggleActif(s)}>
                    {s.actif ? 'Actif' : 'Inactif'}
                  </Button>
                  {s.protege ? (
                    <Badge tone="info">système</Badge>
                  ) : (
                    <IconButton size="sm" variant="outline" label="Supprimer"
                      className="text-destructive hover:text-destructive"
                      onClick={() => del(s)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Input className="min-w-[200px] flex-[1_1_200px]"
              placeholder="Nouvelle consigne (ex. Harnais antichute si > 2 m)"
              value={newLibelle} onChange={(e) => setNewLibelle(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
            <Button type="button" onClick={add}>
              <Plus className="size-4" aria-hidden="true" /> Ajouter
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── F12 — Seuil de dépassement de consommation ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Revue des dépassements (F12)"
            icon={<><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></>} />
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Seuil de dépassement de la consommation prévue au-delà duquel une
            intervention est signalée à la revue.
          </p>
          <div className="flex max-w-xs items-center gap-2">
            <Input type="number" step="any" defaultValue={profile?.overage_seuil_pct}
              onBlur={(e) => saveProfile({ overage_seuil_pct: e.target.value })} />
            <span className="text-sm text-muted-foreground">%</span>
          </div>
        </CardContent>
      </Card>

      {/* ── F9/F14/F20 — Fournisseurs des interfaces swappables ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Services optionnels (OCR / transcription / IA photo)"
            icon={<><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/><path d="M12 8v4l3 3"/></>} />
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Laissez vide pour désactiver (aucun coût, aucune clé). Tant qu'un
            champ est vide : la saisie de n° de série reste manuelle, les mémos
            vocaux portent « Non transcrit — service non configuré », et le
            contrôle qualité IA des photos ne signale rien.
          </p>
          <div className="grid max-w-xl gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
              Fournisseur OCR n° de série (F9)
              <Input defaultValue={profile?.ocr_serie_provider}
                placeholder="vide = désactivé"
                onBlur={(e) => saveProfile({ ocr_serie_provider: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
              Fournisseur de transcription (F14)
              <Input defaultValue={profile?.transcription_provider}
                placeholder="vide = désactivé"
                onBlur={(e) => saveProfile({ transcription_provider: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
              Fournisseur QA photo IA (F20)
              <Input defaultValue={profile?.photo_qa_provider}
                placeholder="vide = désactivé"
                onBlur={(e) => saveProfile({ photo_qa_provider: e.target.value })} />
            </label>
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => { if (!o) setPendingDelete(null) }}
        severity="high"
        title="Supprimer cette consigne de sécurité"
        description={
          `« ${pendingDelete?.libelle ?? ''} » sera supprimée définitivement — `
          + 'elle ne sera plus proposée à la signature sur les interventions futures.'
        }
        confirmText={pendingDelete?.libelle}
        confirmLabel="Supprimer définitivement"
        loading={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
