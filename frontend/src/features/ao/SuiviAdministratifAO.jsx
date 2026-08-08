import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Banknote, CalendarClock, Trophy } from 'lucide-react'
import aoApi from '../../api/aoApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import {
  Badge, Button, Card, CardHeader, CardTitle, CardContent, Input, Label, Select,
  SelectTrigger, SelectValue, SelectContent, SelectItem, Checkbox, Textarea,
  EmptyState, Skeleton, toast,
} from '../../ui'
import { formatDate, formatMAD } from '../../lib/format'
import { getApiError } from '../../lib/apiError'

/* ============================================================================
   PACT70 — Suivi administratif de l'AO : cautions, échéances, résultat.
   ----------------------------------------------------------------------------
   Trou constaté : le tableau de bord (`/ao/tableau-marches/`, PACT15) AGRÈGE
   `CautionSoumission`/`EcheanceAO`/`ResultatAO` (taux de réussite, cautions
   immobilisées, échéances dues) mais aucun écran ne permettait d'en créer une
   seule — ses indicateurs restaient à zéro. Les trois ressources sont
   enregistrées de longue date côté serveur (`apps/ao/urls.py`) : ce fichier
   est le premier écran à les consommer en écriture, via `aoApi.cautionsSoumission`
   / `aoApi.echeancesAo` / `aoApi.resultatsAo` (PACT70, publiés dans le même
   commit).

   Trois sections indépendantes, chacune scopée à `?appel_offre=<id>` (le
   champ RÉEL des trois modèles) : jamais un mélange d'affaires sous le titre
   d'une seule.

   Un `ResultatAO` est une relation UN-À-UN avec l'affaire
   (`OneToOneField`) : la section « Résultat » écrit via l'action serveur
   `resultats-ao/enregistrer/` (AOF32), qui CRÉE ou MET À JOUR l'unique
   résultat de l'affaire — jamais un POST brut qui violerait la contrainte.

   AUCUN chiffre n'est dérivé ici : `expire_avant_ouverture`, `ecart_prix`,
   `ecart_prix_pct` viennent tels quels du serveur (AOF94).
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

const TYPES_CAUTION = [
  ['provisoire', 'Provisoire'],
  ['definitive', 'Définitive'],
  ['retenue_garantie', 'Retenue de garantie'],
]
const STATUTS_CAUTION = [
  ['constituee', 'Constituée'],
  ['restituee', 'Restituée'],
  ['appelee', 'Appelée'],
]
const TYPES_ECHEANCE = [
  ['remise_plis', 'Remise des plis'],
  ['ouverture', 'Ouverture des plis'],
  ['validite', "Fin de validité de l'offre"],
  ['autre', 'Autre date clé'],
]
const ISSUES_RESULTAT = [
  ['gagne', 'Gagné'],
  ['perdu', 'Perdu'],
  ['infructueux', 'Infructueux'],
  ['annule', 'Annulé'],
]

function Champ({ id, label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

/* ── Section « Cautions » ─────────────────────────────────────────────── */

function CautionForm({ affaireId, onCree }) {
  const [form, setForm] = useState({
    type_caution: 'provisoire', montant: '', banque: '', reference_acte: '',
    date_emission: '', date_echeance: '', date_restitution: '', statut: 'constituee',
  })
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    setEnvoi(true)
    try {
      const payload = { appel_offre: affaireId, type_caution: form.type_caution, statut: form.statut }
      if (form.montant !== '') payload.montant = form.montant
      if (form.banque.trim()) payload.banque = form.banque.trim()
      if (form.reference_acte.trim()) payload.reference_acte = form.reference_acte.trim()
      if (form.date_emission) payload.date_emission = form.date_emission
      if (form.date_echeance) payload.date_echeance = form.date_echeance
      if (form.date_restitution) payload.date_restitution = form.date_restitution
      await aoApi.cautionsSoumission.create(payload)
      toast.success('Caution enregistrée.')
      setForm({
        type_caution: 'provisoire', montant: '', banque: '', reference_acte: '',
        date_emission: '', date_echeance: '', date_restitution: '', statut: 'constituee',
      })
      onCree()
    } catch (e2) {
      toast.error(errMsg(e2, 'Caution non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-3">
      <Champ id="ao-caution-type" label="Type">
        <Select value={form.type_caution} onValueChange={(v) => setForm((p) => ({ ...p, type_caution: v }))}>
          <SelectTrigger id="ao-caution-type"><SelectValue /></SelectTrigger>
          <SelectContent>
            {TYPES_CAUTION.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-caution-montant" label="Montant (MAD)">
        <Input id="ao-caution-montant" type="number" step="any" value={form.montant} onChange={set('montant')} />
      </Champ>
      <Champ id="ao-caution-banque" label="Banque">
        <Input id="ao-caution-banque" value={form.banque} onChange={set('banque')} />
      </Champ>
      <Champ id="ao-caution-reference" label="Référence de l'acte">
        <Input id="ao-caution-reference" value={form.reference_acte} onChange={set('reference_acte')} />
      </Champ>
      <Champ id="ao-caution-emission" label="Date d'émission">
        <Input id="ao-caution-emission" type="date" value={form.date_emission} onChange={set('date_emission')} />
      </Champ>
      <Champ id="ao-caution-echeance" label="Date d'échéance">
        <Input id="ao-caution-echeance" type="date" value={form.date_echeance} onChange={set('date_echeance')} />
      </Champ>
      <Champ id="ao-caution-restitution" label="Date de restitution">
        <Input id="ao-caution-restitution" type="date" value={form.date_restitution} onChange={set('date_restitution')} />
      </Champ>
      <Champ id="ao-caution-statut" label="Statut">
        <Select value={form.statut} onValueChange={(v) => setForm((p) => ({ ...p, statut: v }))}>
          <SelectTrigger id="ao-caution-statut"><SelectValue /></SelectTrigger>
          <SelectContent>
            {STATUTS_CAUTION.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
      </Champ>
      <div className="flex items-end">
        <Button type="submit" disabled={envoi}>{envoi ? 'Enregistrement…' : 'Enregistrer la caution'}</Button>
      </div>
    </form>
  )
}

function SectionCautions({ affaireId }) {
  const params = { appel_offre: affaireId }
  const { data: cautions, loading, error, refetch } = useResource(
    () => aoApi.cautionsSoumission.list(params), JSON.stringify(params),
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les cautions.' },
  )

  const deriverDefinitive = async () => {
    try {
      await aoApi.cautionsSoumission.deriverDefinitive({ appel_offre: affaireId })
      toast.success('Caution définitive dérivée du taux du CPS.')
      refetch()
    } catch (e) {
      toast.error(errMsg(e, "Dérivation impossible — vérifiez la clause CAUTION_DEFINITIVE_TAUX du CPS."))
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2">
          <Banknote className="size-4" aria-hidden="true" />
          Cautions
        </CardTitle>
        <Button size="sm" variant="outline" onClick={deriverDefinitive}>
          Dériver la caution définitive (taux CPS)
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <CautionForm affaireId={affaireId} onCree={refetch} />
        {loading && <Skeleton className="h-24 w-full" />}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && (
          cautions.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune caution enregistrée pour cette affaire.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {cautions.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5 text-sm">
                  <Badge tone="neutral">{c.type_caution_display}</Badge>
                  <span className="tabular-nums">{c.montant != null ? formatMAD(c.montant) : '—'}</span>
                  {c.banque && <span className="text-muted-foreground">— {c.banque}</span>}
                  <span className="text-xs text-muted-foreground">
                    {c.date_echeance ? `échéance ${formatDate(c.date_echeance)}` : ''}
                  </span>
                  <Badge tone="neutral" className="ml-auto">{c.statut_display}</Badge>
                  {c.expire_avant_ouverture && (
                    <Badge tone="danger">expire AVANT l’ouverture des plis</Badge>
                  )}
                </li>
              ))}
            </ul>
          )
        )}
      </CardContent>
    </Card>
  )
}

/* ── Section « Échéances » ────────────────────────────────────────────── */

function EcheanceForm({ affaireId, onCree }) {
  const [form, setForm] = useState({
    type_echeance: 'autre', libelle: '', date_echeance: '', rappel_jours: '3',
  })
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    if (!form.date_echeance) return
    setEnvoi(true)
    try {
      await aoApi.echeancesAo.create({
        appel_offre: affaireId,
        type_echeance: form.type_echeance,
        libelle: form.libelle.trim(),
        date_echeance: form.date_echeance,
        rappel_jours: form.rappel_jours === '' ? 3 : Number(form.rappel_jours),
      })
      toast.success('Échéance enregistrée.')
      setForm({ type_echeance: 'autre', libelle: '', date_echeance: '', rappel_jours: '3' })
      onCree()
    } catch (e2) {
      toast.error(errMsg(e2, 'Échéance non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-4">
      <Champ id="ao-echeance-type" label="Type">
        <Select value={form.type_echeance} onValueChange={(v) => setForm((p) => ({ ...p, type_echeance: v }))}>
          <SelectTrigger id="ao-echeance-type"><SelectValue /></SelectTrigger>
          <SelectContent>
            {TYPES_ECHEANCE.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-echeance-libelle" label="Libellé">
        <Input id="ao-echeance-libelle" value={form.libelle} onChange={set('libelle')} />
      </Champ>
      <Champ id="ao-echeance-date" label="Date d'échéance">
        <Input id="ao-echeance-date" type="date" value={form.date_echeance} onChange={set('date_echeance')} required />
      </Champ>
      <Champ id="ao-echeance-rappel" label="Rappel (jours avant)">
        <Input id="ao-echeance-rappel" type="number" step="1" value={form.rappel_jours} onChange={set('rappel_jours')} />
      </Champ>
      <div className="flex items-end sm:col-span-4">
        <Button type="submit" disabled={envoi || !form.date_echeance}>
          {envoi ? 'Enregistrement…' : "Enregistrer l'échéance"}
        </Button>
      </div>
    </form>
  )
}

function SectionEcheances({ affaireId }) {
  const params = { appel_offre: affaireId }
  const { data: echeances, loading, error, refetch } = useResource(
    () => aoApi.echeancesAo.list(params), JSON.stringify(params),
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les échéances.' },
  )

  const basculerTraitee = async (echeance) => {
    try {
      await aoApi.echeancesAo.update(echeance.id, { traitee: !echeance.traitee })
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Échéance non modifiée.'))
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarClock className="size-4" aria-hidden="true" />
          Échéances
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <EcheanceForm affaireId={affaireId} onCree={refetch} />
        {loading && <Skeleton className="h-24 w-full" />}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && (
          echeances.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune échéance enregistrée pour cette affaire.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {echeances.map((ec) => (
                <li key={ec.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5 text-sm">
                  <Checkbox checked={Boolean(ec.traitee)} onCheckedChange={() => basculerTraitee(ec)} aria-label={`Traitée — ${ec.libelle || ec.type_echeance_display}`} />
                  <Badge tone="neutral">{ec.type_echeance_display}</Badge>
                  <span>{ec.libelle || '—'}</span>
                  <span className="ml-auto tabular-nums text-muted-foreground">{formatDate(ec.date_echeance)}</span>
                  {ec.traitee && <Badge tone="success">Traitée</Badge>}
                </li>
              ))}
            </ul>
          )
        )}
      </CardContent>
    </Card>
  )
}

/* ── Section « Résultat » ─────────────────────────────────────────────── */

function ResultatForm({ affaireId, resultat, onEnregistre }) {
  const [form, setForm] = useState({
    issue: resultat?.issue || 'perdu',
    attributaire: resultat?.attributaire || '',
    notre_prix: resultat?.notre_prix ?? '',
    prix_gagnant: resultat?.prix_gagnant ?? '',
    motif: resultat?.motif || '',
    date_resultat: resultat?.date_resultat || '',
    date_ouverture: resultat?.date_ouverture || '',
    nombre_plis: resultat?.nombre_plis ?? '',
    notre_rang: resultat?.notre_rang ?? '',
  })
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    setEnvoi(true)
    try {
      const payload = { appel_offre: affaireId, issue: form.issue }
      if (form.attributaire.trim()) payload.attributaire = form.attributaire.trim()
      if (form.notre_prix !== '') payload.notre_prix = form.notre_prix
      if (form.prix_gagnant !== '') payload.prix_gagnant = form.prix_gagnant
      if (form.motif.trim()) payload.motif = form.motif.trim()
      if (form.date_resultat) payload.date_resultat = form.date_resultat
      if (form.date_ouverture) payload.date_ouverture = form.date_ouverture
      if (form.nombre_plis !== '') payload.nombre_plis = Number(form.nombre_plis)
      if (form.notre_rang !== '') payload.notre_rang = Number(form.notre_rang)
      await aoApi.resultatsAo.enregistrer(payload)
      toast.success('Résultat enregistré.')
      onEnregistre()
    } catch (e2) {
      toast.error(errMsg(e2, 'Résultat non enregistré.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-3">
      <Champ id="ao-resultat-issue" label="Issue">
        <Select value={form.issue} onValueChange={(v) => setForm((p) => ({ ...p, issue: v }))}>
          <SelectTrigger id="ao-resultat-issue"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ISSUES_RESULTAT.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-resultat-attributaire" label="Attributaire">
        <Input id="ao-resultat-attributaire" value={form.attributaire} onChange={set('attributaire')} />
      </Champ>
      <Champ id="ao-resultat-ouverture" label="Date d'ouverture des plis">
        <Input id="ao-resultat-ouverture" type="date" value={form.date_ouverture} onChange={set('date_ouverture')} />
      </Champ>
      <Champ id="ao-resultat-notre-prix" label="Notre prix (MAD)">
        <Input id="ao-resultat-notre-prix" type="number" step="any" value={form.notre_prix} onChange={set('notre_prix')} />
      </Champ>
      <Champ id="ao-resultat-prix-gagnant" label="Prix gagnant (MAD)">
        <Input id="ao-resultat-prix-gagnant" type="number" step="any" value={form.prix_gagnant} onChange={set('prix_gagnant')} />
      </Champ>
      <Champ id="ao-resultat-rang" label="Notre rang">
        <Input id="ao-resultat-rang" type="number" step="1" value={form.notre_rang} onChange={set('notre_rang')} />
      </Champ>
      <Champ id="ao-resultat-nombre-plis" label="Nombre de plis reçus">
        <Input id="ao-resultat-nombre-plis" type="number" step="1" value={form.nombre_plis} onChange={set('nombre_plis')} />
      </Champ>
      <Champ id="ao-resultat-date" label="Date du résultat">
        <Input id="ao-resultat-date" type="date" value={form.date_resultat} onChange={set('date_resultat')} />
      </Champ>
      <div className="flex flex-col gap-1.5 sm:col-span-3">
        <Label htmlFor="ao-resultat-motif">Motif / commentaire</Label>
        <Textarea id="ao-resultat-motif" rows={2} value={form.motif} onChange={set('motif')} />
      </div>
      <div className="flex items-end">
        <Button type="submit" disabled={envoi}>{envoi ? 'Enregistrement…' : 'Enregistrer le résultat'}</Button>
      </div>
    </form>
  )
}

function SectionResultat({ affaireId }) {
  const params = { appel_offre: affaireId }
  const { data: resultats, loading, error, refetch } = useResource(
    () => aoApi.resultatsAo.list(params), JSON.stringify(params),
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger le résultat.' },
  )
  const resultat = resultats[0] || null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trophy className="size-4" aria-hidden="true" />
          Résultat (ouverture des plis)
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loading && <Skeleton className="h-24 w-full" />}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && (
          <>
            {resultat && (
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-2.5 text-sm">
                <Badge tone={resultat.issue === 'gagne' ? 'success' : resultat.issue === 'perdu' ? 'danger' : 'neutral'}>
                  {resultat.issue_display}
                </Badge>
                {resultat.attributaire && <span>Attributaire : {resultat.attributaire}</span>}
                {resultat.ecart_prix_pct != null && (
                  <span className="tabular-nums text-muted-foreground">
                    Écart vs gagnant : {resultat.ecart_prix_pct} %
                  </span>
                )}
              </div>
            )}
            <ResultatForm affaireId={affaireId} resultat={resultat} onEnregistre={refetch} />
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default function SuiviAdministratifAO({ affaireId } = {}) {
  const routeParams = useParams()
  const id = affaireId ?? routeParams.id

  if (!id) {
    return (
      <EmptyState
        icon={Banknote}
        title='Suivi administratif indisponible'
        description="Cette page se rattache à une affaire — ouvrez-la depuis la liste des affaires."
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">Suivi administratif</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Cautions, échéances et résultat d’ouverture des plis — ce qui alimente le tableau de bord.
        </p>
      </div>
      <SectionCautions affaireId={id} />
      <SectionEcheances affaireId={id} />
      <SectionResultat affaireId={id} />
    </div>
  )
}
