import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, ShieldCheck } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Card, CardContent, Button, Input, Label, Switch, Badge, Spinner, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTP2P32 — Paramètres → Achats → Règles d'approbation des demandes d'achat.
   ----------------------------------------------------------------------------
   CRUD complet (créer/modifier/désactiver) sur `installations.
   RegleApprobationAchat` (NTP2P2, endpoint EXISTANT `regles-approbation-
   achat/`) — même UX que l'écran `contrats.RegleApprobation`
   (`EcheancesPage.jsx` onglet « Règles ») : liste + dialogue de création/
   édition, seuil de montant + nombre d'approbateurs + périmètre chantier
   optionnel. Aucun nouveau modèle ni endpoint côté serveur.
   ========================================================================== */

const NIVEAUX = [
  { value: 'responsable', label: 'Responsable' },
  { value: 'administrateur', label: 'Administrateur' },
  { value: 'direction', label: 'Direction' },
]

function errMsg(e, fallback) {
  const data = e?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const first = Object.values(data)[0]
  return (Array.isArray(first) ? first[0] : first) || fallback
}

function RegleDialog({ regle, chantiers, onClose, onDone }) {
  const [libelle, setLibelle] = useState(regle?.libelle || '')
  const [montantMin, setMontantMin] = useState(regle?.montant_min ?? '')
  const [montantMax, setMontantMax] = useState(regle?.montant_max ?? '')
  const [chantier, setChantier] = useState(regle?.chantier ?? '')
  const [niveau, setNiveau] = useState(regle?.niveau_approbation || 'responsable')
  const [nbApprobateurs, setNbApprobateurs] = useState(regle?.nombre_approbateurs ?? 1)
  const [priorite, setPriorite] = useState(regle?.priorite ?? 0)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!libelle.trim()) { setErr('Le libellé est requis.'); return }
    setErr(null)
    setSaving(true)
    const data = {
      libelle: libelle.trim(),
      montant_min: montantMin === '' ? null : Number(montantMin),
      montant_max: montantMax === '' ? null : Number(montantMax),
      chantier: chantier === '' ? null : Number(chantier),
      niveau_approbation: niveau,
      nombre_approbateurs: Number(nbApprobateurs) || 1,
      priorite: Number(priorite) || 0,
    }
    try {
      await installationsApi.saveRegleApprobationAchat(regle?.id, data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{regle ? "Modifier la règle d'approbation" : "Nouvelle règle d'approbation"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="raa-libelle" required>Libellé</Label>
            <Input id="raa-libelle" value={libelle}
              onChange={(e) => setLibelle(e.target.value)}
              placeholder="ex. Achats grands montants" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="raa-min">Seuil minimum (MAD)</Label>
              <Input id="raa-min" type="number" step="any" noValidate
                value={montantMin} onChange={(e) => setMontantMin(e.target.value)}
                placeholder="Optionnel" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="raa-max">Seuil maximum (MAD)</Label>
              <Input id="raa-max" type="number" step="any" noValidate
                value={montantMax} onChange={(e) => setMontantMax(e.target.value)}
                placeholder="Optionnel" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="raa-chantier">Chantier ciblé (optionnel)</Label>
            <select id="raa-chantier" value={chantier}
              onChange={(e) => setChantier(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">Tous chantiers (règle générique)</option>
              {chantiers.map((c) => (
                <option key={c.id} value={c.id}>{c.reference || `Chantier #${c.id}`}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="raa-niveau">Niveau d&apos;approbation</Label>
              <select id="raa-niveau" value={niveau}
                onChange={(e) => setNiveau(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                {NIVEAUX.map((n) => <option key={n.value} value={n.value}>{n.label}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="raa-nb-approbateurs">Nombre d&apos;approbateurs</Label>
              <Input id="raa-nb-approbateurs" type="number" step="1" min="1" noValidate
                value={nbApprobateurs}
                onChange={(e) => setNbApprobateurs(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="raa-priorite">Priorité (départage entre règles concurrentes)</Label>
            <Input id="raa-priorite" type="number" step="1" noValidate
              value={priorite} onChange={(e) => setPriorite(e.target.value)} />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Enregistrement…' : (regle ? 'Enregistrer' : 'Créer la règle')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function ReglesApprobationAchatSection() {
  const [regles, setRegles] = useState([])
  const [chantiers, setChantiers] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogRegle, setDialogRegle] = useState(undefined) // undefined=fermé, null=création, objet=édition
  const [aSupprimer, setASupprimer] = useState(null)
  const [busy, setBusy] = useState(false)

  const charger = () => {
    installationsApi.getReglesApprobationAchat()
      .then((r) => setRegles(r.data?.results ?? r.data ?? []))
      .catch(() => toast.error('Chargement des règles impossible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    charger()
    installationsApi.getInstallations({ page_size: 200 })
      .catch(() => ({ data: [] }))
      .then((r) => setChantiers(r.data?.results ?? r.data ?? []))
  }, [])

  const toggleActif = async (regle) => {
    try {
      await installationsApi.saveRegleApprobationAchat(regle.id, { actif: !regle.actif })
      charger()
    } catch {
      toast.error("La mise à jour a échoué.")
    }
  }

  const confirmerSuppression = async () => {
    if (!aSupprimer) return
    setBusy(true)
    try {
      await installationsApi.deleteRegleApprobationAchat(aSupprimer.id)
      setASupprimer(null)
      charger()
    } catch {
      toast.error('La suppression a échoué.')
    } finally { setBusy(false) }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" />
            Règles d&apos;approbation des demandes d&apos;achat (NTP2P2)
          </h2>
          <Button type="button" size="sm" variant="outline"
            onClick={() => setDialogRegle(null)}>
            <Plus className="size-4" aria-hidden="true" /> Nouvelle règle
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          La règle ACTIVE la plus spécifique (seuil + chantier) s&apos;applique
          aux nouvelles demandes d&apos;achat dépassant son seuil.
        </p>

        {loading && (
          <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Spinner /> Chargement…
          </p>
        )}

        {!loading && regles.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune règle pour l&apos;instant.</p>
        )}

        {!loading && regles.length > 0 && (
          <div className="flex flex-col gap-2">
            {regles.map((r) => (
              <div key={r.id} data-testid={`regle-achat-${r.id}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{r.libelle}</span>
                    <Badge tone={r.actif ? 'success' : 'neutral'}>
                      {r.actif ? 'Active' : 'Inactive'}
                    </Badge>
                    {r.chantier && (
                      <Badge tone="info">
                        {chantiers.find((c) => c.id === r.chantier)?.reference || `Chantier #${r.chantier}`}
                      </Badge>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {r.montant_min != null || r.montant_max != null
                      ? [
                        r.montant_min != null ? `≥ ${formatMAD(r.montant_min)}` : null,
                        r.montant_max != null ? `≤ ${formatMAD(r.montant_max)}` : null,
                      ].filter(Boolean).join(' · ')
                      : 'Tout montant'}
                    {' · '}{r.niveau_approbation_display || r.niveau_approbation}
                    {' · '}{r.nombre_approbateurs} approbateur(s)
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Switch checked={r.actif} onCheckedChange={() => toggleActif(r)}
                    aria-label={`Activer/désactiver ${r.libelle}`} />
                  <Button type="button" size="sm" variant="ghost" aria-label={`Modifier ${r.libelle}`}
                    onClick={() => setDialogRegle(r)}>
                    <Pencil className="size-4" aria-hidden="true" />
                  </Button>
                  <Button type="button" size="sm" variant="ghost" aria-label={`Supprimer ${r.libelle}`}
                    onClick={() => setASupprimer(r)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      {dialogRegle !== undefined && (
        <RegleDialog
          regle={dialogRegle}
          chantiers={chantiers}
          onClose={() => setDialogRegle(undefined)}
          onDone={() => {
            setDialogRegle(undefined)
            toast.success(dialogRegle ? 'Règle mise à jour.' : 'Règle créée.')
            charger()
          }}
        />
      )}

      <ConfirmDialog
        open={!!aSupprimer}
        onOpenChange={(o) => { if (!o) setASupprimer(null) }}
        severity="medium"
        title="Supprimer cette règle d'approbation ?"
        description={aSupprimer
          ? `« ${aSupprimer.libelle} » sera définitivement supprimée.`
          : ''}
        confirmLabel="Supprimer"
        loading={busy}
        onConfirm={confirmerSuppression}
      />
    </Card>
  )
}
