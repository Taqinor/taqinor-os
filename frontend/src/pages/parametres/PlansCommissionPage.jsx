import { useCallback, useEffect, useState } from 'react'
import { Percent } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import coreApi from '../../api/coreApi'
import {
  Card, CardContent, Button, Input, Label, Badge, EmptyState, Spinner, toast,
} from '../../ui'

/* ============================================================================
   WIR282/XSAL6 — Écran « Plans de commission » (Paramètres).
   ----------------------------------------------------------------------------
   Moitié FRONT du lot WIR281/WIR282. Le contrat partagé vit dans
   `backend/django_core/apps/ventes/contract_samples/plan_commission.json`
   (PACT10) : cet écran — et le mock de son test — en DÉRIVENT, ils ne
   l'inventent pas.

   GARDE MARGE : l'endpoint est gaté `prix_achat_voir` côté serveur et ne sert
   NI prix d'achat NI montant de marge. Cet écran n'affiche donc AUCUN montant
   de marge : `base` est une étiquette de mode, `taux_pct` un pourcentage de
   règle, `montant_par_kwc` un barème. Un 403 est dit en français, jamais
   affiché en JSON brut.

   Le badge « plan appliqué » vient de l'action `resoudre/?owner=` : c'est le
   SERVEUR qui tranche la priorité (plan dédié → plan par défaut société →
   mode société) ; l'écran ne la réimplémente pas.
   ========================================================================== */

const BASES = [
  { value: 'ca_devis_signe', label: 'CA des devis signés' },
  { value: 'marge_interne', label: 'Marge interne (admin uniquement)' },
  { value: 'par_kwc', label: 'MAD par kWc installé' },
]
const BASE_LABEL = Object.fromEntries(BASES.map((b) => [b.value, b.label]))

const SOURCE_LABEL = {
  plan_dedie: 'Plan dédié',
  plan_defaut_societe: 'Plan par défaut société',
  mode_societe: 'Aucun plan — mode société',
}

const FORM_VIDE = {
  owner: '', base: 'ca_devis_signe', taux_pct: '', montant_par_kwc: '',
}

// Un palier = un seuil d'atteinte d'objectif + le taux accéléré associé.
const PALIER_VIDE = { seuil_atteinte_pct: '', taux: '' }

function messageErreur(err, repli) {
  if (err?.response?.status === 403) {
    return 'Accès refusé — les plans de commission sont réservés aux profils '
      + 'autorisés à voir les prix d’achat.'
  }
  const data = err?.response?.data
  if (!data) return repli
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  for (const valeur of Object.values(data)) {
    const m = Array.isArray(valeur) ? valeur[0] : valeur
    if (typeof m === 'string') return m
  }
  return repli
}

export default function PlansCommissionPage() {
  const [plans, setPlans] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)
  const [busy, setBusy] = useState(false)

  const [form, setForm] = useState(FORM_VIDE)
  const [paliers, setPaliers] = useState([])
  const [palier, setPalier] = useState(PALIER_VIDE)

  // Badge « plan appliqué » : commercial choisi → résolution SERVEUR.
  const [ownerTest, setOwnerTest] = useState('')
  const [resolution, setResolution] = useState(null)
  const [resolutionBusy, setResolutionBusy] = useState(false)

  const charger = useCallback(() => {
    setLoading(true)
    setErreur(null)
    ventesApi.getPlansCommission()
      .then((r) => {
        const data = r.data
        setPlans(Array.isArray(data) ? data : (data?.results ?? []))
      })
      .catch((err) => setErreur(
        messageErreur(err, 'Plans de commission indisponibles.')))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    charger()
  }, [charger])

  useEffect(() => {
    coreApi.utilisateurs.list()
      .then((r) => {
        const data = r.data
        setUsers(Array.isArray(data) ? data : (data?.results ?? []))
      })
      .catch(() => setUsers([]))
  }, [])

  const set = (cle) => (e) => setForm((p) => ({ ...p, [cle]: e.target.value }))
  const estParKwc = form.base === 'par_kwc'

  const ajouterPalier = () => {
    if (palier.seuil_atteinte_pct === '' || palier.taux === '') return
    setPaliers((p) => [...p, {
      seuil_atteinte_pct: Number(palier.seuil_atteinte_pct),
      taux: Number(palier.taux),
    }])
    setPalier(PALIER_VIDE)
  }

  const retirerPalier = (index) => setPaliers(
    (p) => p.filter((unused, i) => i !== index))

  const creer = (e) => {
    e.preventDefault()
    const payload = {
      owner: form.owner ? Number(form.owner) : null,
      base: form.base,
      // Les nombres tapés partent TELS QUELS : ni arrondis, ni rognés.
      taux_pct: estParKwc || form.taux_pct === '' ? null : form.taux_pct,
      montant_par_kwc: estParKwc && form.montant_par_kwc !== ''
        ? form.montant_par_kwc : null,
      paliers: paliers.length ? paliers : null,
    }
    setBusy(true)
    setErreur(null)
    ventesApi.createPlanCommission(payload)
      .then((r) => {
        setPlans((p) => [r.data, ...p])
        setForm(FORM_VIDE)
        setPaliers([])
        toast.success('Plan de commission créé.')
      })
      .catch((err) => setErreur(messageErreur(err, 'Plan non créé.')))
      .finally(() => setBusy(false))
  }

  const basculerActif = (plan) => {
    setBusy(true)
    ventesApi.updatePlanCommission(plan.id, { actif: !plan.actif })
      .then((r) => setPlans((p) => p.map(
        (x) => (x.id === plan.id ? r.data : x))))
      .catch((err) => setErreur(messageErreur(err, 'Plan non modifié.')))
      .finally(() => setBusy(false))
  }

  const supprimer = (plan) => {
    setBusy(true)
    ventesApi.deletePlanCommission(plan.id)
      .then(() => setPlans((p) => p.filter((x) => x.id !== plan.id)))
      .catch((err) => setErreur(messageErreur(err, 'Plan non supprimé.')))
      .finally(() => setBusy(false))
  }

  const resoudre = () => {
    setResolutionBusy(true)
    setErreur(null)
    ventesApi.resoudrePlanCommission(ownerTest || undefined)
      .then((r) => setResolution(r.data ?? null))
      .catch((err) => setErreur(messageErreur(err, 'Résolution impossible.')))
      .finally(() => setResolutionBusy(false))
  }

  if (loading) {
    return (
      <div className="page flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement des plans de commission…
      </div>
    )
  }

  return (
    <div className="page flex flex-col gap-4">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <Percent className="size-5" aria-hidden="true" />
          Plans de commission
        </h1>
        <p className="page-subtitle">
          Un plan sans commercial est le plan PAR DÉFAUT de la société. Un plan
          dédié à un commercial prime sur lui ; sans aucun plan actif, le mode
          de commission de la société s’applique.
        </p>
      </div>

      {erreur && (
        <p className="form-error" role="alert" data-testid="plans-commission-erreur">
          {erreur}
        </p>
      )}

      {/* ── Badge « plan appliqué » (résolution SERVEUR) ── */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-2 p-4">
          <div className="flex min-w-[12rem] flex-col gap-1.5">
            <Label htmlFor="pc-owner-test">Plan appliqué à</Label>
            <select id="pc-owner-test" className="form-control" value={ownerTest}
                    onChange={(e) => setOwnerTest(e.target.value)}>
              <option value="">— Société (plan par défaut) —</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.username}</option>
              ))}
            </select>
          </div>
          <Button type="button" size="sm" variant="outline"
                  disabled={resolutionBusy} onClick={resoudre}>
            {resolutionBusy ? 'Résolution…' : 'Voir le plan appliqué'}
          </Button>
          {resolution && (
            <span className="flex items-center gap-2" data-testid="plan-applique">
              <Badge tone={resolution.source === 'mode_societe' ? 'neutral' : 'success'}>
                {SOURCE_LABEL[resolution.source] ?? resolution.source}
              </Badge>
              {resolution.plan && (
                <span className="text-sm text-muted-foreground">
                  {BASE_LABEL[resolution.plan.base] ?? resolution.plan.base}
                  {' · '}
                  {resolution.plan.base === 'par_kwc'
                    ? `${resolution.plan.montant_par_kwc} MAD/kWc`
                    : `${resolution.plan.taux_pct} %`}
                </span>
              )}
            </span>
          )}
        </CardContent>
      </Card>

      {/* ── Liste des plans ── */}
      {plans.length === 0 ? (
        <EmptyState
          title="Aucun plan de commission"
          description="Sans plan, le mode de commission de la société s’applique à tous les commerciaux."
          icon={Percent}
        />
      ) : (
        <table className="data-table" data-testid="plans-commission-table">
          <thead>
            <tr>
              <th>Commercial</th><th>Base</th><th>Barème</th><th>Paliers</th>
              <th>Actif</th><th />
            </tr>
          </thead>
          <tbody>
            {plans.map((p) => (
              <tr key={p.id} data-testid="plan-commission-row">
                <td>{p.owner_nom || 'Défaut société'}</td>
                <td>{p.base_display || BASE_LABEL[p.base] || p.base}</td>
                <td>
                  {p.base === 'par_kwc'
                    ? `${p.montant_par_kwc ?? '—'} MAD/kWc`
                    : `${p.taux_pct ?? '—'} %`}
                </td>
                <td>{(p.paliers ?? []).length || '—'}</td>
                <td>
                  <Badge tone={p.actif ? 'success' : 'neutral'}>
                    {p.actif ? 'Actif' : 'Inactif'}
                  </Badge>
                </td>
                <td className="flex flex-wrap gap-1.5">
                  <Button type="button" size="sm" variant="outline"
                          disabled={busy} onClick={() => basculerActif(p)}>
                    {p.actif ? 'Désactiver' : 'Réactiver'}
                  </Button>
                  <Button type="button" size="sm" variant="outline"
                          disabled={busy} onClick={() => supprimer(p)}>
                    Supprimer
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ── Création + éditeur de paliers ── */}
      <Card>
        <CardContent className="p-4">
          <h2 className="mb-2 text-base font-semibold">Nouveau plan</h2>
          {/* Les nombres tapés ne sont ni rognés ni rejetés. */}
          <form noValidate className="flex flex-col gap-3" onSubmit={creer}>
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex min-w-[12rem] flex-col gap-1.5">
                <Label htmlFor="pc-owner">Commercial</Label>
                <select id="pc-owner" className="form-control" value={form.owner}
                        onChange={set('owner')}>
                  <option value="">— Plan par défaut société —</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.username}</option>
                  ))}
                </select>
              </div>
              <div className="flex min-w-[14rem] flex-col gap-1.5">
                <Label htmlFor="pc-base">Base de calcul</Label>
                <select id="pc-base" className="form-control" value={form.base}
                        onChange={set('base')}>
                  {BASES.map((b) => (
                    <option key={b.value} value={b.value}>{b.label}</option>
                  ))}
                </select>
              </div>
              {estParKwc ? (
                <div className="flex w-40 flex-col gap-1.5">
                  <Label htmlFor="pc-montant">MAD par kWc</Label>
                  <Input id="pc-montant" type="number" step="any"
                         value={form.montant_par_kwc}
                         onChange={set('montant_par_kwc')} />
                </div>
              ) : (
                <div className="flex w-32 flex-col gap-1.5">
                  <Label htmlFor="pc-taux">Taux (%)</Label>
                  <Input id="pc-taux" type="number" step="any"
                         value={form.taux_pct} onChange={set('taux_pct')} />
                </div>
              )}
            </div>

            <div className="rounded-lg border border-border p-3">
              <h3 className="mb-1.5 text-sm font-semibold">
                Paliers d’accélération (facultatif)
              </h3>
              <p className="mb-2 text-xs text-muted-foreground">
                Au-delà d’un seuil d’atteinte d’objectif, le taux passe à la
                valeur du palier.
              </p>
              {paliers.length > 0 && (
                <ul className="mb-2 flex flex-col gap-1 text-sm"
                    data-testid="plan-paliers">
                  {paliers.map((p, i) => (
                    <li key={`${p.seuil_atteinte_pct}-${p.taux}-${i}`}
                        className="flex items-center gap-2">
                      <span>À partir de {p.seuil_atteinte_pct} % → {p.taux} %</span>
                      <Button type="button" size="sm" variant="outline"
                              onClick={() => retirerPalier(i)}>
                        Retirer
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap items-end gap-2">
                <div className="flex w-40 flex-col gap-1.5">
                  <Label htmlFor="pc-seuil">Seuil d’atteinte (%)</Label>
                  <Input id="pc-seuil" type="number" step="any"
                         value={palier.seuil_atteinte_pct}
                         onChange={(e) => setPalier(
                           (p) => ({ ...p, seuil_atteinte_pct: e.target.value }))} />
                </div>
                <div className="flex w-32 flex-col gap-1.5">
                  <Label htmlFor="pc-palier-taux">Taux du palier (%)</Label>
                  <Input id="pc-palier-taux" type="number" step="any"
                         value={palier.taux}
                         onChange={(e) => setPalier(
                           (p) => ({ ...p, taux: e.target.value }))} />
                </div>
                <Button type="button" size="sm" variant="outline"
                        onClick={ajouterPalier}>
                  Ajouter le palier
                </Button>
              </div>
            </div>

            <div>
              <Button type="submit" size="sm" disabled={busy}>
                Créer le plan
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
