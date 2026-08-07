import { useCallback, useMemo, useState } from 'react'
import { RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react'
import veilleAoApi from '../../api/veilleAoApi'
import coreApi from '../../api/coreApi'
import useResource from '../../hooks/useResource'
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'
import { unwrapList } from '../../api/resource'
import {
  Button, Card, Switch, Progress, toast,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

/* ============================================================================
   VAO35 — « Paramètres de veille » (Directeur) : mots-clés, sources,
   exclusions, cadence — et LE BOUTON.
   ----------------------------------------------------------------------------
   Gated `veille_ao_gerer` au niveau ROUTE (module.config.jsx, VAO32 —
   `roles: ['responsable','admin']` + `perm: 'veille_ao_gerer'`) : un
   utilisateur sans ce palier reçoit le 403 propre standard du routeur avant
   même que cet écran ne monte, comme `journal_activite_voir` (reporting) —
   aucune garde supplémentaire n'est nécessaire ici.

   « Rafraîchir maintenant » (VAO23) appelle EXACTEMENT le même job que le
   beat de nuit (`veilleAoApi.collecte.declencher`) et suit sa progression via
   le sondage générique des jobs de fond de la plateforme
   (`coreApi.jobsStatus`, WIR137/NTPLT29) — jamais un second mécanisme de
   collecte « pour le bouton ». Double clic impossible : le bouton se désactive
   dès le lancement et jusqu'à la fin du job.
   ========================================================================== */

const NIVEAUX_MOT_CLE = [
  { value: 'noyau', label: 'Noyau (précision haute)' },
  { value: 'large', label: 'Large (bruit accepté)' },
]

const PORTEES_REGLE = [
  { value: 'acheteur', label: 'Acheteur' },
  { value: 'mot_libelle', label: 'Mot du libellé' },
  { value: 'categorie', label: 'Catégorie' },
  { value: 'region', label: 'Région' },
]

// Vocabulaire toléré FR/EN (patron `useGenerationJob.js`, AOF177) — seul l'état
// TERMINAL importe ici : tout le reste vaut « en cours ».
const TERMINES = new Set(['done', 'succes', 'termine', 'failed', 'echec', 'erreur'])

function errMsg(e, fallback) { return e?.response?.data?.detail || fallback }

// VAO23/VAO35 — le job de collecte manuelle, suivi via le sondage GÉNÉRIQUE
// des jobs de fond (coreApi.jobsStatus) plutôt qu'un endpoint de statut dédié
// que le texte de tâche ne nomme pas.
function useCollecteJob() {
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [lancement, setLancement] = useState(false)
  const [erreur, setErreur] = useState(null)

  const statutJob = job?.statut ?? job?.status
  const enCours = Boolean(jobId) && !TERMINES.has(statutJob)

  const sonder = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await coreApi.jobsStatus.list()
      const trouve = unwrapList(res).find((j) => j.id === jobId)
      if (trouve) setJob(trouve)
    } catch { /* le prochain sondage réessaiera */ }
  }, [jobId])

  useVisibilityAwarePolling(
    useMemo(() => [{ fn: sonder, intervalMs: 3000 }], [sonder]),
    { enabled: enCours },
  )

  const lancer = useCallback(async () => {
    if (lancement || enCours) return // VAO35 (Done=) — double clic ne lance pas deux collectes.
    setLancement(true)
    setErreur(null)
    try {
      const res = await veilleAoApi.collecte.declencher()
      const id = res?.data?.job_id ?? res?.data?.id ?? null
      setJobId(id)
      setJob(res?.data ?? null)
      toast.success('Collecte lancée.')
    } catch (e) {
      setErreur(errMsg(e, 'Déclenchement impossible.'))
      toast.error(errMsg(e, 'Déclenchement impossible.'))
    } finally {
      setLancement(false)
    }
  }, [lancement, enCours])

  return {
    lancer, lancement, enCours, erreur,
    progression: job?.progress_pct ?? job?.progression ?? 0,
    statutJob,
  }
}

function BandeauArmement({ sante }) {
  const arme = Boolean(sante?.collecte_active)
  return (
    <Card className={`flex items-center gap-3 p-4 ${arme ? 'border-success/40 bg-success/10' : 'border-warning/40 bg-warning/10'}`}>
      {arme ? <ShieldCheck className="size-5 text-success" aria-hidden="true" /> : <ShieldAlert className="size-5 text-warning" aria-hidden="true" />}
      <div>
        <p className="font-medium">
          Collecte automatique : {arme ? 'ARMÉE' : 'DÉSARMÉE — accord fondateur requis'}
        </p>
        <p className="text-sm text-muted-foreground">
          {arme
            ? 'La tâche planifiée de 06h00 collecte réellement les avis.'
            : 'Aucun appel réseau n’est fait tant que l’armement n’est pas explicitement accordé (règle #5).'}
        </p>
      </div>
    </Card>
  )
}

function SourcesSection() {
  const { data: sources, loading, refetch } = useResource(
    () => veilleAoApi.sources.list(), undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Sources indisponibles.' },
  )

  const toggler = async (source) => {
    try {
      await veilleAoApi.sources.update(source.id, { actif: !source.actif })
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Mise à jour impossible.'))
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-display text-base font-semibold">Sources</h2>
      {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {!loading && sources.length === 0 && <p className="text-sm text-muted-foreground">Aucune source.</p>}
      <ul className="flex flex-col divide-y divide-border">
        {sources.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 py-2">
            <div className="min-w-0">
              <p className="truncate font-medium">{s.libelle || s.code}</p>
              <p className="truncate text-xs text-muted-foreground">{s.type_display || s.type}</p>
            </div>
            <Switch
              checked={Boolean(s.actif)}
              onCheckedChange={() => toggler(s)}
              aria-label={`Source active — ${s.libelle || s.code}`}
            />
          </li>
        ))}
      </ul>
    </Card>
  )
}

function MotsClesSection() {
  const { data: mots, loading, refetch } = useResource(
    () => veilleAoApi.motsCles.list(), undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Mots-clés indisponibles.' },
  )
  const [libelle, setLibelle] = useState('')
  const [niveau, setNiveau] = useState('noyau')
  const [poids, setPoids] = useState('1')
  const [saving, setSaving] = useState(false)

  const ajouter = async (e) => {
    e.preventDefault()
    if (!libelle.trim()) return
    setSaving(true)
    try {
      // VAO35/VAO9 (Done=) — un mot-clé ajouté ici change le score des
      // collectes SUIVANTES sans redéploiement (la donnée vit en base).
      await veilleAoApi.motsCles.create({ libelle: libelle.trim(), niveau, poids: Number(poids) || 1, actif: true })
      setLibelle('')
      toast.success('Mot-clé ajouté.')
      refetch()
    } catch (e2) {
      toast.error(errMsg(e2, 'Ajout impossible.'))
    } finally { setSaving(false) }
  }

  const toggler = async (mot) => {
    try {
      await veilleAoApi.motsCles.update(mot.id, { actif: !mot.actif })
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Mise à jour impossible.'))
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-display text-base font-semibold">Mots-clés</h2>
      <form onSubmit={ajouter} className="flex flex-wrap items-end gap-2" noValidate>
        <div className="flex flex-col gap-1">
          <Label htmlFor="mc-libelle">Libellé</Label>
          <Input id="mc-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="ex: pompage solaire" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="mc-niveau">Niveau</Label>
          <Select value={niveau} onValueChange={setNiveau}>
            <SelectTrigger id="mc-niveau" aria-label="Niveau" className="w-48"><SelectValue /></SelectTrigger>
            <SelectContent>
              {NIVEAUX_MOT_CLE.map((n) => <SelectItem key={n.value} value={n.value}>{n.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="mc-poids">Poids</Label>
          <Input id="mc-poids" type="number" step="any" className="w-20" value={poids} onChange={(e) => setPoids(e.target.value)} />
        </div>
        <Button type="submit" size="sm" disabled={saving || !libelle.trim()}>{saving ? 'Ajout…' : 'Ajouter'}</Button>
      </form>
      {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
      <ul className="flex flex-col divide-y divide-border">
        {mots.map((m) => (
          <li key={m.id} className="flex items-center justify-between gap-3 py-2">
            <div className="min-w-0">
              <p className="truncate font-medium">{m.libelle}</p>
              <p className="truncate text-xs text-muted-foreground">
                {NIVEAUX_MOT_CLE.find((n) => n.value === m.niveau)?.label || m.niveau} · poids {m.poids}
              </p>
            </div>
            <Switch checked={Boolean(m.actif)} onCheckedChange={() => toggler(m)} aria-label={`Mot-clé actif — ${m.libelle}`} />
          </li>
        ))}
      </ul>
    </Card>
  )
}

function ReglesExclusionSection() {
  const { data: regles, loading, refetch } = useResource(
    () => veilleAoApi.reglesExclusion.list(), undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Règles indisponibles.' },
  )

  const toggler = async (regle) => {
    try {
      await veilleAoApi.reglesExclusion.update(regle.id, { actif: !regle.actif })
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Mise à jour impossible.'))
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-display text-base font-semibold">Règles d’exclusion</h2>
      {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {!loading && regles.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucune règle — « Ignorer » un avis en propose une.</p>
      )}
      <ul className="flex flex-col divide-y divide-border">
        {regles.map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-3 py-2">
            <div className="min-w-0">
              <p className="truncate font-medium">
                {PORTEES_REGLE.find((p) => p.value === r.portee)?.label || r.portee}{r.valeur ? ` — ${r.valeur}` : ''}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {r.motif || 'sans motif'} · appliquée {r.compteur_application ?? 0} fois
              </p>
            </div>
            <Switch checked={Boolean(r.actif)} onCheckedChange={() => toggler(r)} aria-label={`Règle active — ${r.portee}`} />
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function ParametresVeille() {
  const { data: sante, loading: santeLoading } = useResource(
    () => veilleAoApi.sante(), undefined,
    { select: (res) => res.data, errorMessage: 'État de la veille indisponible.' },
  )
  const { lancer, lancement, enCours, progression } = useCollecteJob()

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Paramètres de veille"
        subtitle="Mots-clés, sources, exclusions, cadence — Directeur uniquement."
        actions={(
          <Button onClick={lancer} disabled={lancement || enCours} loading={lancement || enCours}>
            <RefreshCw aria-hidden="true" />
            {enCours ? `Collecte en cours… ${progression ? `${Math.round(progression)} %` : ''}` : 'Rafraîchir maintenant'}
          </Button>
        )}
      />

      {enCours && <Progress value={progression} aria-label="Avancement de la collecte manuelle" indeterminate={!progression} />}

      {!santeLoading && <BandeauArmement sante={sante} />}

      <MotsClesSection />
      <SourcesSection />
      <ReglesExclusionSection />
    </div>
  )
}
