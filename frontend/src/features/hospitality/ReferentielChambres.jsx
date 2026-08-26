import { useEffect, useState } from 'react'
import { Card, Button, Input, Label, EmptyState, Spinner, toast } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   WIR211 — Référentiel hôtellerie (types de chambre, chambres, plans
   tarifaires).
   ----------------------------------------------------------------------------
   Constat : le module était INERTE. `createTypeChambre`, `createChambre` et
   `createPlanTarifaire` existaient côté client mais aucun écran ne les
   appelait : impossible de créer un type, donc une chambre, donc un plan — le
   plan des chambres restait vide, les folios vides et le RevPAR à 0.

   Cet écran est le point d'entrée de la mise en route : type → chambre → plan.
   La société est TOUJOURS posée côté serveur (TenantMixin) ; rien n'est envoyé
   dans le corps. Les prix saisis partent TELS QUELS (formulaires `noValidate`,
   champs numériques `step="any"`) — aucun arrondi ni rejet côté écran.
   ========================================================================== */

const CANAUX = [
  { value: 'rack', label: 'Rack (tarif public)' },
  { value: 'corporate', label: 'Corporate' },
  { value: 'ota', label: 'OTA' },
]

const TYPE_VIDE = { libelle: '', capacite_max: '2', description: '' }
const CHAMBRE_VIDE = { type_chambre: '', numero: '', nom: '', etage: '', vue: '' }
const PLAN_VIDE = {
  type_chambre: '', canal: 'rack', date_debut: '', date_fin: '',
  prix_nuit_ht: '', min_nuits: '',
}

// Une erreur DRF devient UNE phrase française — jamais du JSON à l'écran.
function messageErreur(err, repli) {
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

export default function ReferentielChambres() {
  const [types, setTypes] = useState([])
  const [chambres, setChambres] = useState([])
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  const [typeForm, setTypeForm] = useState(TYPE_VIDE)
  const [chambreForm, setChambreForm] = useState(CHAMBRE_VIDE)
  const [planForm, setPlanForm] = useState(PLAN_VIDE)
  const [busy, setBusy] = useState(false)

  const charger = () => {
    setLoading(true)
    setErreur(null)
    Promise.all([
      hospitalityApi.listTypesChambre(),
      hospitalityApi.listChambres(),
      hospitalityApi.listPlansTarifaires(),
    ])
      .then(([t, c, p]) => {
        setTypes(t.data?.results ?? t.data ?? [])
        setChambres(c.data?.results ?? c.data ?? [])
        setPlans(p.data?.results ?? p.data ?? [])
      })
      .catch(() => setErreur('Référentiel indisponible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    charger()
  }, [])

  const creerType = (e) => {
    e.preventDefault()
    if (!typeForm.libelle.trim()) return
    setBusy(true)
    hospitalityApi.createTypeChambre({
      libelle: typeForm.libelle.trim(),
      capacite_max: typeForm.capacite_max === '' ? 2 : typeForm.capacite_max,
      description: typeForm.description,
    })
      .then((r) => {
        setTypes((prev) => [...prev, r.data])
        setTypeForm(TYPE_VIDE)
        toast.success('Type de chambre créé.')
      })
      .catch((err) => toast.error(messageErreur(err, 'Type non créé.')))
      .finally(() => setBusy(false))
  }

  const creerChambre = (e) => {
    e.preventDefault()
    if (!chambreForm.type_chambre || !chambreForm.numero.trim()) return
    setBusy(true)
    hospitalityApi.createChambre({
      type_chambre: Number(chambreForm.type_chambre),
      numero: chambreForm.numero.trim(),
      nom: chambreForm.nom,
      etage: chambreForm.etage,
      vue: chambreForm.vue,
    })
      .then((r) => {
        setChambres((prev) => [...prev, r.data])
        setChambreForm(CHAMBRE_VIDE)
        toast.success('Chambre créée — elle apparaît au plan des chambres.')
      })
      .catch((err) => toast.error(messageErreur(err, 'Chambre non créée.')))
      .finally(() => setBusy(false))
  }

  const creerPlan = (e) => {
    e.preventDefault()
    if (!planForm.type_chambre || !planForm.date_debut || !planForm.date_fin
      || planForm.prix_nuit_ht === '') return
    setBusy(true)
    hospitalityApi.createPlanTarifaire({
      type_chambre: Number(planForm.type_chambre),
      canal: planForm.canal,
      date_debut: planForm.date_debut,
      date_fin: planForm.date_fin,
      prix_nuit_ht: planForm.prix_nuit_ht,
      min_nuits: planForm.min_nuits === '' ? null : planForm.min_nuits,
    })
      .then((r) => {
        setPlans((prev) => [...prev, r.data])
        setPlanForm(PLAN_VIDE)
        toast.success('Plan tarifaire créé.')
      })
      .catch((err) => toast.error(messageErreur(err, 'Plan tarifaire non créé.')))
      .finally(() => setBusy(false))
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement du référentiel…
      </div>
    )
  }
  if (erreur) {
    return <EmptyState title="Référentiel indisponible" description={erreur} />
  }

  const typeOptions = types.map((t) => (
    <option key={t.id} value={t.id}>{t.libelle}</option>
  ))

  return (
    <div className="page flex flex-col gap-4">
      <div>
        <h1 className="page-title">Référentiel hôtellerie</h1>
        <p className="page-subtitle">
          Créez un type de chambre, puis vos chambres, puis leurs plans
          tarifaires — dans cet ordre : une chambre exige un type, un plan
          exige un type.
        </p>
      </div>

      {/* ── Types de chambre ── */}
      <Card className="p-4">
        <h2 className="mb-2 text-base font-semibold">Types de chambre</h2>
        {types.length === 0 ? (
          <p className="mb-3 text-sm text-muted-foreground">
            Aucun type pour l’instant — commencez par ici.
          </p>
        ) : (
          <ul className="mb-3 flex flex-col gap-1 text-sm" data-testid="liste-types">
            {types.map((t) => (
              <li key={t.id}>
                {t.libelle} — {t.capacite_max} personne(s)
              </li>
            ))}
          </ul>
        )}
        <form noValidate className="flex flex-wrap items-end gap-2" onSubmit={creerType}>
          <div className="flex min-w-[12rem] flex-1 flex-col gap-1.5">
            <Label htmlFor="type-libelle">Libellé</Label>
            <Input id="type-libelle" value={typeForm.libelle}
                   onChange={(e) => setTypeForm((p) => ({ ...p, libelle: e.target.value }))} />
          </div>
          <div className="flex w-32 flex-col gap-1.5">
            <Label htmlFor="type-capacite">Capacité max</Label>
            <Input id="type-capacite" type="number" step="any"
                   value={typeForm.capacite_max}
                   onChange={(e) => setTypeForm((p) => ({ ...p, capacite_max: e.target.value }))} />
          </div>
          <Button type="submit" size="sm" disabled={busy || !typeForm.libelle.trim()}>
            Ajouter le type
          </Button>
        </form>
      </Card>

      {/* ── Chambres ── */}
      <Card className="p-4">
        <h2 className="mb-2 text-base font-semibold">Chambres</h2>
        {chambres.length === 0 ? (
          <p className="mb-3 text-sm text-muted-foreground">
            Aucune chambre — le plan des chambres restera vide tant qu’il n’y
            en a pas.
          </p>
        ) : (
          <ul className="mb-3 flex flex-col gap-1 text-sm" data-testid="liste-chambres">
            {chambres.map((c) => (
              <li key={c.id}>
                {c.numero} {c.nom ? `— ${c.nom} ` : ''}
                ({c.type_chambre_libelle ?? '—'})
              </li>
            ))}
          </ul>
        )}
        <form noValidate className="flex flex-wrap items-end gap-2" onSubmit={creerChambre}>
          <div className="flex min-w-[10rem] flex-col gap-1.5">
            <Label htmlFor="chambre-type">Type</Label>
            <select id="chambre-type" className="form-control"
                    value={chambreForm.type_chambre}
                    onChange={(e) => setChambreForm((p) => ({ ...p, type_chambre: e.target.value }))}>
              <option value="">— Choisir un type —</option>
              {typeOptions}
            </select>
          </div>
          <div className="flex w-28 flex-col gap-1.5">
            <Label htmlFor="chambre-numero">Numéro</Label>
            <Input id="chambre-numero" value={chambreForm.numero}
                   onChange={(e) => setChambreForm((p) => ({ ...p, numero: e.target.value }))} />
          </div>
          <div className="flex min-w-[10rem] flex-1 flex-col gap-1.5">
            <Label htmlFor="chambre-nom">Nom (facultatif)</Label>
            <Input id="chambre-nom" value={chambreForm.nom}
                   onChange={(e) => setChambreForm((p) => ({ ...p, nom: e.target.value }))} />
          </div>
          <div className="flex w-24 flex-col gap-1.5">
            <Label htmlFor="chambre-etage">Étage</Label>
            <Input id="chambre-etage" value={chambreForm.etage}
                   onChange={(e) => setChambreForm((p) => ({ ...p, etage: e.target.value }))} />
          </div>
          <Button type="submit" size="sm"
                  disabled={busy || !chambreForm.type_chambre || !chambreForm.numero.trim()}>
            Ajouter la chambre
          </Button>
        </form>
        {types.length === 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            Créez d’abord un type de chambre.
          </p>
        )}
      </Card>

      {/* ── Plans tarifaires ── */}
      <Card className="p-4">
        <h2 className="mb-2 text-base font-semibold">Plans tarifaires</h2>
        {plans.length === 0 ? (
          <p className="mb-3 text-sm text-muted-foreground">
            Aucun plan — sans plan applicable, une réservation ne porte aucun
            prix par nuit.
          </p>
        ) : (
          <ul className="mb-3 flex flex-col gap-1 text-sm" data-testid="liste-plans">
            {plans.map((p) => (
              <li key={p.id}>
                {p.canal_display ?? p.canal} · {p.date_debut} → {p.date_fin} ·
                {' '}{p.prix_nuit_ht} / nuit
              </li>
            ))}
          </ul>
        )}
        <form noValidate className="flex flex-wrap items-end gap-2" onSubmit={creerPlan}>
          <div className="flex min-w-[10rem] flex-col gap-1.5">
            <Label htmlFor="plan-type">Type</Label>
            <select id="plan-type" className="form-control"
                    value={planForm.type_chambre}
                    onChange={(e) => setPlanForm((p) => ({ ...p, type_chambre: e.target.value }))}>
              <option value="">— Choisir un type —</option>
              {typeOptions}
            </select>
          </div>
          <div className="flex min-w-[9rem] flex-col gap-1.5">
            <Label htmlFor="plan-canal">Canal</Label>
            <select id="plan-canal" className="form-control" value={planForm.canal}
                    onChange={(e) => setPlanForm((p) => ({ ...p, canal: e.target.value }))}>
              {CANAUX.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="plan-debut">Du</Label>
            <Input id="plan-debut" type="date" value={planForm.date_debut}
                   onChange={(e) => setPlanForm((p) => ({ ...p, date_debut: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="plan-fin">Au</Label>
            <Input id="plan-fin" type="date" value={planForm.date_fin}
                   onChange={(e) => setPlanForm((p) => ({ ...p, date_fin: e.target.value }))} />
          </div>
          <div className="flex w-32 flex-col gap-1.5">
            <Label htmlFor="plan-prix">Prix/nuit HT</Label>
            <Input id="plan-prix" type="number" step="any" value={planForm.prix_nuit_ht}
                   onChange={(e) => setPlanForm((p) => ({ ...p, prix_nuit_ht: e.target.value }))} />
          </div>
          <div className="flex w-28 flex-col gap-1.5">
            <Label htmlFor="plan-min">Min. nuits</Label>
            <Input id="plan-min" type="number" step="any" value={planForm.min_nuits}
                   onChange={(e) => setPlanForm((p) => ({ ...p, min_nuits: e.target.value }))} />
          </div>
          <Button
            type="submit"
            size="sm"
            disabled={busy || !planForm.type_chambre || !planForm.date_debut
              || !planForm.date_fin || planForm.prix_nuit_ht === ''}
          >
            Ajouter le plan
          </Button>
        </form>
      </Card>
    </div>
  )
}
