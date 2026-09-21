import { useMemo, useState } from 'react'
import { CalendarClock, Check, Flag } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import { Badge, Button, Card, EmptyState, Input, Label, toast } from '../../../ui'
import { EcheanceCenter, daysUntil, urgencyLevel, urgencyTone, urgencyLabel } from '../../../ui/module'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   AOF178 — Échéances et jalons du dossier.
   ----------------------------------------------------------------------------
   AOF15 génère l'échéancier et les rappels côté serveur ; il manquait l'écran.

   **UNE SEULE SOURCE d'urgence.** Le compte à rebours, la liste d'échéances et
   la colonne « Date limite » de la liste des affaires affichent EXACTEMENT la
   même chose parce qu'elles appellent les MÊMES fonctions pures :
   `daysUntil` / `urgencyLevel` / `urgencyTone` / `urgencyLabel` de
   `ui/module/urgency.js` (UX1) — et la liste passe par `EcheanceCenter`, le
   même composant que le centre d'échéances du tableau de bord AO (AOF172).
   **Aucun seuil d'urgence n'est redéfini ici** : ni 7 jours, ni 30, ni « en
   retard » — les inventer localement, c'est garantir deux vérités.

   **La prorogation DÉCALE les rappels, elle n'en crée pas.** L'écran se
   contente de SAISIR la prorogation écrite (date + référence du courrier, les
   deux obligatoires : une prorogation non écrite n'existe pas) et de laisser le
   serveur recalculer l'échéancier (AOF15) ; il ne déplace aucune date lui-même.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

// Jalons du cycle réel d'un AO — libellés de repli quand le serveur n'en
// fournit pas ; jamais une liste FERMÉE (un type inconnu s'affiche tel quel).
const JALONS_LABELS = {
  visite_site: 'Visite de site',
  questions_mo: "Questions au maître d'ouvrage",
  reponse_mo: "Réponse du maître d'ouvrage",
  prorogation: 'Prorogation obtenue',
  ouverture_plis: 'Ouverture des plis',
}

function CompteARebours({ date }) {
  const jours = daysUntil(date)
  const niveau = urgencyLevel(jours)
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <p className="text-xs text-muted-foreground">Date limite de remise des plis</p>
        <p className="font-display text-lg font-semibold">
          {date ? formatDate(date) : '—'}
        </p>
      </div>
      <Badge tone={urgencyTone(niveau)} className="text-sm">
        <CalendarClock className="size-3.5" aria-hidden="true" />
        {urgencyLabel(jours)}
      </Badge>
    </Card>
  )
}

function Jalons({ jalons }) {
  if (!jalons.length) {
    return (
      <EmptyState
        icon={Flag}
        title="Aucun jalon"
        description="Visite de site, questions au maître d’ouvrage, prorogation… rien n’est encore posé."
      />
    )
  }
  return (
    <ul className="flex flex-col gap-2">
      {jalons.map((j) => {
        const jours = daysUntil(j.date)
        return (
          <li key={j.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5">
            {j.fait
              ? <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
              : <Flag className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
            <span className="text-sm font-medium">
              {j.libelle || JALONS_LABELS[j.type] || j.type}
            </span>
            <span className="text-xs text-muted-foreground">{j.date ? formatDate(j.date) : '—'}</span>
            {!j.fait && j.date && (
              <Badge tone={urgencyTone(urgencyLevel(jours))}>{urgencyLabel(jours)}</Badge>
            )}
            {j.fait && <Badge tone="success">Fait</Badge>}
          </li>
        )
      })}
    </ul>
  )
}

function ProrogationForm({ onProroger, onProrogee }) {
  const [date, setDate] = useState('')
  const [reference, setReference] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const complet = Boolean(date && reference.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!complet) return
    setEnvoi(true)
    try {
      await onProroger({ date, reference: reference.trim() })
      toast.success('Prorogation enregistrée — les rappels sont décalés par le serveur.')
      setDate('')
      setReference('')
      onProrogee?.()
    } catch (e2) {
      toast.error(errMsg(e2, 'Prorogation non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
      <p className="text-xs text-muted-foreground">
        Une prorogation ne se retient que si elle est ÉCRITE : la référence du courrier est obligatoire.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <Label htmlFor="ao-prorogation-date" required>Nouvelle date limite</Label>
          <Input
            id="ao-prorogation-date" type="date" value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="ao-prorogation-ref" required>Référence du courrier</Label>
          <Input
            id="ao-prorogation-ref" value={reference}
            placeholder="Ex. avis de prorogation n° 12/2026"
            onChange={(e) => setReference(e.target.value)}
          />
        </div>
      </div>
      <Button type="submit" size="sm" className="self-start" disabled={!complet || envoi}>
        {envoi ? 'Enregistrement…' : 'Enregistrer la prorogation'}
      </Button>
    </form>
  )
}

export default function EcheancesDossier({
  affaireId,
  dateLimite,
  echeances = [],
  jalons = [],
  onProroger,
  onProrogee,
  peutProroger = true,
}) {
  // Défaut branché sur la ressource RÉELLEMENT exposée par `api/aoApi.js`
  // (AOF11) — aucun endpoint inventé, aucun `axios` direct.
  const proroger = onProroger
    ?? (({ date, reference }) => aoApi.affaires.update(affaireId, {
      prorogation_date: date,
      prorogation_reference: reference,
    }))

  const items = useMemo(() => echeances.map((e) => ({
    id: e.id,
    label: e.libelle || e.type_label || e.type,
    date: e.date_echeance,
    meta: e.rappel_date ? `Rappel le ${formatDate(e.rappel_date)}` : null,
  })), [echeances])

  return (
    <div className="flex flex-col gap-4">
      <CompteARebours date={dateLimite} />

      {/* Le MÊME composant que le centre d'échéances du tableau de bord AO. */}
      <EcheanceCenter title="Échéances et rappels" items={items} />

      <Card className="p-4">
        <h3 className="mb-2 font-display text-base font-semibold">Jalons</h3>
        <Jalons jalons={jalons} />
      </Card>

      {peutProroger && (
        <Card className="p-4">
          <h3 className="mb-2 font-display text-base font-semibold">Prorogation écrite</h3>
          <ProrogationForm onProroger={proroger} onProrogee={onProrogee} />
        </Card>
      )}
    </div>
  )
}
