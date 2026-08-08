import { useState } from 'react'
import { Map as MapIcon, Ruler } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import {
  Badge, Button, Card, Input, Label, Select,
  SelectTrigger, SelectValue, SelectContent, SelectItem,
  EmptyState, Skeleton, toast,
} from '../../../ui'
import { getApiError } from '../../../lib/apiError'

/* ============================================================================
   PACT76 — Plan source de la toiture : le calibrage ENFIN persisté (AOF20).
   ----------------------------------------------------------------------------
   Trou **(b) déjà corrigé + (a) résiduel**. La réparation du 03/08/2026 a
   corrigé le NOM côté client (`plansSources: crud('plans-source')`), mais
   aucun écran ne l'appelait encore : les outils de calibration/import
   DXF/fond de plan de l'onglet « Calage » de `ToituresPage` (INCHANGÉ ici)
   travaillent sur une image tenue en état RÉACT LOCAL — un rechargement de
   page la perd, calibrage compris.

   Ce panneau est le PREMIER consommateur de `PlanSource` : il liste les
   supports RÉELLEMENT ENREGISTRÉS pour une toiture, avec leur état
   (brut/calibré/vectorisé), et persiste un calibrage via un PATCH réel —
   jamais un recalcul côté front (AOF94). `echelle_m_par_px` et `etat` sont
   dérivés et RENVOYÉS PAR LE SERVEUR à chaque écriture
   (`PlanSourceViewSet._recalibrer`, appelé par `create`/`update`) : ce
   panneau les affiche tels quels, il ne calcule jamais lui-même un facteur
   px→m.

   **Saisie NUMÉRIQUE des deux points de calibration**, pas un clic sur une
   image : l'outil interactif à deux clics (`toiture/Calibration.jsx`) exige
   de rendre le fond de plan (PDF worker, rasterisation) — c'est le périmètre
   DÉJÀ COUVERT et INCHANGÉ de l'onglet « Calage ». Ce panneau ne le duplique
   pas ; il donne le chemin le plus court vers la PERSISTANCE, qui est le
   trou réel constaté (« un rechargement de page perd le calibrage »).
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

const ORIGINES = [
  ['plan_fourni', 'Plan fourni (PDF/DXF/image)'],
  ['trace_manuel', 'Tracé manuel'],
  ['carte', 'Reprise depuis une carte'],
]
const TYPES_FICHIER = [
  ['pdf', 'PDF'],
  ['dxf', 'DXF'],
  ['image', 'Image'],
  ['aucun', 'Aucun fichier'],
]

function Champ({ id, label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

function CreationForm({ toitureId, onCree }) {
  const [form, setForm] = useState({ origine: 'plan_fourni', type_fichier: 'aucun' })
  const [fichier, setFichier] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  const soumettre = async (e) => {
    e.preventDefault()
    setEnvoi(true)
    try {
      const cree = await aoApi.plansSources.create({
        toiture: toitureId, origine: form.origine, type_fichier: form.type_fichier,
      })
      const id = cree?.data?.id
      if (fichier && id) {
        await aoApi.plansSources.upload(id, fichier)
      }
      toast.success('Plan source enregistré.')
      setForm({ origine: 'plan_fourni', type_fichier: 'aucun' })
      setFichier(null)
      onCree()
    } catch (e2) {
      toast.error(errMsg(e2, 'Plan non enregistré.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-3">
      <Champ id="ao-plan-origine" label="Porte d'entrée">
        <Select value={form.origine} onValueChange={(v) => setForm((p) => ({ ...p, origine: v }))}>
          <SelectTrigger id="ao-plan-origine"><SelectValue /></SelectTrigger>
          <SelectContent>{ORIGINES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-plan-type" label="Type de fichier">
        <Select value={form.type_fichier} onValueChange={(v) => setForm((p) => ({ ...p, type_fichier: v }))}>
          <SelectTrigger id="ao-plan-type"><SelectValue /></SelectTrigger>
          <SelectContent>{TYPES_FICHIER.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-plan-fichier" label="Fichier (facultatif)">
        <input
          id="ao-plan-fichier" type="file" className="text-sm"
          onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
        />
      </Champ>
      <div className="flex items-end">
        <Button type="submit" disabled={envoi}>{envoi ? 'Enregistrement…' : 'Enregistrer le plan'}</Button>
      </div>
    </form>
  )
}

function CalibrationForm({ plan, onCalibrer }) {
  const [form, setForm] = useState({
    ax: plan.calib_point_a_px?.[0] ?? '', ay: plan.calib_point_a_px?.[1] ?? '',
    bx: plan.calib_point_b_px?.[0] ?? '', by: plan.calib_point_b_px?.[1] ?? '',
    distance: plan.calib_distance_reelle_m ?? '',
  })
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    if (form.ax === '' || form.ay === '' || form.bx === '' || form.by === '' || form.distance === '') return
    setEnvoi(true)
    try {
      await onCalibrer(plan, {
        calib_point_a_px: [Number(form.ax), Number(form.ay)],
        calib_point_b_px: [Number(form.bx), Number(form.by)],
        calib_distance_reelle_m: form.distance,
      })
    } finally {
      setEnvoi(false)
    }
  }

  const idPrefix = `ao-plan-calib-${plan.id}`
  return (
    <form onSubmit={soumettre} noValidate className="grid gap-2 sm:grid-cols-5">
      <Champ id={`${idPrefix}-ax`} label="Point A — x (px)">
        <Input id={`${idPrefix}-ax`} type="number" step="any" value={form.ax} onChange={set('ax')} />
      </Champ>
      <Champ id={`${idPrefix}-ay`} label="Point A — y (px)">
        <Input id={`${idPrefix}-ay`} type="number" step="any" value={form.ay} onChange={set('ay')} />
      </Champ>
      <Champ id={`${idPrefix}-bx`} label="Point B — x (px)">
        <Input id={`${idPrefix}-bx`} type="number" step="any" value={form.bx} onChange={set('bx')} />
      </Champ>
      <Champ id={`${idPrefix}-by`} label="Point B — y (px)">
        <Input id={`${idPrefix}-by`} type="number" step="any" value={form.by} onChange={set('by')} />
      </Champ>
      <Champ id={`${idPrefix}-d`} label="Distance réelle A→B (m)">
        <Input id={`${idPrefix}-d`} type="number" step="any" value={form.distance} onChange={set('distance')} />
      </Champ>
      <div className="flex items-end sm:col-span-5">
        <Button type="submit" size="sm" variant="outline" disabled={envoi}>
          <Ruler className="size-3.5" aria-hidden="true" />
          {envoi ? 'Calibration…' : 'Calibrer'}
        </Button>
      </div>
    </form>
  )
}

function LignePlan({ plan, onCalibrer }) {
  return (
    <li className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{plan.origine_display}</Badge>
        <Badge tone={plan.etat === 'brut' ? 'warning' : plan.etat === 'calibre' ? 'success' : 'info'}>
          {plan.etat_display}
        </Badge>
        {plan.echelle_m_par_px && (
          <span className="text-xs tabular-nums text-muted-foreground">
            échelle : {Number(plan.echelle_m_par_px).toFixed(6)} m/px
          </span>
        )}
        {plan.fourni_par && <span className="ml-auto text-xs text-muted-foreground">fourni par {plan.fourni_par}</span>}
      </div>
      <CalibrationForm plan={plan} onCalibrer={onCalibrer} />
    </li>
  )
}

export default function PlanSourcePanel({ toitureId }) {
  const { data: plans, loading, error, refetch } = useResource(
    () => aoApi.plansSources.list({ toiture: toitureId }), toitureId,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les plans sources.',
      enabled: Boolean(toitureId),
    },
  )

  const calibrer = async (plan, patch) => {
    try {
      await aoApi.plansSources.update(plan.id, patch)
      toast.success('Calibrage enregistré — survit désormais à un rechargement.')
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Calibrage refusé.'))
    }
  }

  if (!toitureId) {
    return (
      <EmptyState icon={MapIcon} title="Plans sources indisponibles" description="Choisissez d’abord une toiture." />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-base font-semibold">Plans sources</h2>
        <p className="text-xs text-muted-foreground">
          Les plans attachés à cette toiture et leur état — un calibrage enregistré ici survit à un rechargement.
        </p>
      </div>

      <Card className="p-3">
        <CreationForm toitureId={toitureId} onCree={refetch} />
      </Card>

      {loading && <Skeleton className="h-32 w-full" />}
      {error && <EmptyState icon={MapIcon} tone="error" title="Plans sources indisponibles" description={error} />}
      {!loading && !error && (
        plans.length === 0 ? (
          <EmptyState icon={MapIcon} title="Aucun plan source" description="Cette toiture n’a encore aucun plan enregistré." />
        ) : (
          <ul className="flex flex-col gap-2">
            {plans.map((p) => <LignePlan key={p.id} plan={p} onCalibrer={calibrer} />)}
          </ul>
        )
      )}
    </div>
  )
}
