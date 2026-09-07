import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { CalendarClock } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Card, CardContent, Badge, Spinner,
  Tabs, TabsList, TabsTrigger,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import RelanceEtapeRow from '../../features/crm/relances/RelanceEtapeRow'
import ToucheMessageDialog from './ToucheMessageDialog'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { toastError } from '../../lib/toast'

/* ============================================================================
   MRY31 — Écran « Suivi des relances » (`/crm/relances`) : Meryem et sa
   direction voient les touches par jour avec leur statut, sur quatre plages
   (« Aujourd'hui + retard » / « Demain » / « 7 prochains jours » / « 7
   derniers jours »), filtrables par responsable (Moi par défaut ; « toute
   l'équipe » ou un commercial nommé — visible aux rôles responsable et admin
   seulement, comme le reste du CRM : un commercial normal ne voit QUE ses
   propres touches, la portée serveur `scope_queryset` l'impose déjà).

   Lit `GET relance-etapes/suivi/` (contrat committé
   `apps/crm/contract_samples/relance_etapes_suivi.json`, PAYLOAD importé dans
   les tests — jamais un objet retapé à la main). `resume` (à faire / en
   retard / faites / sautées) vient TEL QUEL du serveur, jamais recompté ici.

   Distinct de `RelancesDuJourWidget.jsx` (Cockpit, aujourd'hui + retard
   seulement, format compact) — les deux partagent la même ligne d'action
   (`features/crm/relances/RelanceEtapeRow.jsx`, MRY31).
   ========================================================================== */

// Bornes Casablanca — même trick que `LeadCard.jsx estAujourdhuiCasa` : `en-CA`
// formate nativement en AAAA-MM-JJ, ancré au fuseau EXPLICITE (jamais celui du
// navigateur — un commercial en déplacement verrait sinon le mauvais « demain »).
function todayCasa() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(new Date())
}

// Décale une date AAAA-MM-JJ de `delta` jours, en arithmétique de calendrier
// pure (Date.UTC sur les composantes déjà extraites) — jamais une addition de
// millisecondes, qui glisserait d'un jour autour d'un changement d'heure.
function decalerJours(yyyyMmDd, delta) {
  const [y, m, d] = yyyyMmDd.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + delta)).toISOString().slice(0, 10)
}

// Titre de groupe « lundi 7 septembre » — minuit LOCAL (comme `formatDateFr`
// de `LeadCard.jsx`), jamais UTC, pour ne jamais faire glisser le jour affiché.
function jourTitre(yyyyMmDd) {
  const d = new Date(`${yyyyMmDd}T00:00:00`)
  const semaine = new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(d)
  const jour = new Intl.DateTimeFormat('fr-FR', { day: 'numeric' }).format(d)
  const mois = new Intl.DateTimeFormat('fr-FR', { month: 'long' }).format(d)
  return `${semaine} ${jour} ${mois}`
}

const ONGLETS = [
  { value: 'aujourdhui', label: "Aujourd'hui + retard" },
  { value: 'demain', label: 'Demain' },
  { value: 'semaine', label: '7 prochains jours' },
  { value: 'precedente', label: '7 derniers jours' },
]

/** Bornes [date_debut, date_fin] envoyées au serveur pour chaque onglet (62 j
 *  d'écart max, cf. le contrat) : l'onglet « Aujourd'hui + retard » élargit la
 *  fenêtre serveur à 30 j en arrière (un retard peut dater de plusieurs
 *  semaines) et le filtrage FIN (aujourd'hui ou encore à faire en retard) se
 *  fait CÔTÉ ÉCRAN — voir `visiblesPourOnglet` ci-dessous. */
function bornesOnglet(onglet, today) {
  if (onglet === 'demain') {
    const demain = decalerJours(today, 1)
    return { date_debut: demain, date_fin: demain }
  }
  if (onglet === 'semaine') {
    return { date_debut: decalerJours(today, 1), date_fin: decalerJours(today, 7) }
  }
  if (onglet === 'precedente') {
    return { date_debut: decalerJours(today, -7), date_fin: decalerJours(today, -1) }
  }
  return { date_debut: decalerJours(today, -30), date_fin: today }
}

// Seul l'onglet « Aujourd'hui + retard » filtre CÔTÉ ÉCRAN (fenêtre serveur
// volontairement plus large que la plage affichée) : une ligne compte si elle
// tombe aujourd'hui, OU si elle est encore à faire et déjà en retard. Les
// trois autres onglets affichent TOUT ce que le serveur renvoie pour leur
// fenêtre — aucun filtrage supplémentaire.
function visiblesPourOnglet(onglet, results, today) {
  if (onglet !== 'aujourdhui') return results
  return results.filter((e) => e.due_date === today
    || (e.statut === 'a_faire' && e.due_date < today))
}

export default function RelancesSuiviPage() {
  const navigate = useNavigate()
  const isResponsableOuAdmin = useIsAdminOrResponsable()
  const currentUserId = useSelector((s) => s.auth.user?.id)
  const [onglet, setOnglet] = useState('aujourdhui')
  const [ownerFiltre, setOwnerFiltre] = useState('moi')
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [donnees, setDonnees] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [messageEtape, setMessageEtape] = useState(null)

  // Employés assignables pour le sélecteur Responsable — inutile (et non
  // requêté) pour un rôle normal, qui ne voit jamais ce contrôle.
  useEffect(() => {
    if (!isResponsableOuAdmin) return
    crmApi.getAssignableUsers()
      .then((r) => setUsers(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [isResponsableOuAdmin])

  const today = useMemo(() => todayCasa(), [])
  const owner = ownerFiltre === 'moi'
    ? currentUserId
    : (ownerFiltre === 'tous' ? '' : ownerFiltre)

  const charger = () => {
    let active = true
    const { date_debut, date_fin } = bornesOnglet(onglet, today)
    // setState différé au prochain microtask (jamais synchrone dans l'effet) —
    // évite react-hooks/set-state-in-effect, même patron que
    // `RelancesDuJourWidget.jsx`/`KpiRelancesPanel.jsx`.
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    const params = { date_debut, date_fin }
    if (owner) params.owner = owner
    crmApi.getRelanceEtapesSuivi(params)
      .then((r) => { if (active) setDonnees(r.data) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }

  useEffect(() => charger(),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `charger` recrée une fermeture à chaque rendu (owner/today/onglet la referment déjà) ; l'ajouter provoquerait un rechargement à chaque frappe sans rien changer aux dépendances réelles.
    [onglet, owner, today])

  const traiter = async (id, action, payload) => {
    setBusyId(id)
    try {
      if (action === 'fait') await crmApi.marquerRelanceEtapeFait(id, payload)
      else if (action === 'sauter') await crmApi.marquerRelanceEtapeSautee(id, payload)
      else if (action === 'reporter') await crmApi.reporterRelanceEtape(id, payload)
      charger()
    } catch {
      toastError('Action impossible pour le moment.')
    } finally {
      setBusyId(null)
    }
  }

  // Seul l'onglet « Aujourd'hui + retard » est actionnable — même règle que
  // le widget Cockpit (MRY32 : « Demain »/« 7 jours » se lisent seulement) ;
  // une touche déjà résolue (fait/sautée) ne porte jamais d'action non plus.
  const actionnable = onglet === 'aujourdhui'

  const groupes = useMemo(() => {
    const lignes = donnees ? visiblesPourOnglet(onglet, donnees.results, today) : []
    const map = new Map()
    for (const etape of lignes) {
      if (!map.has(etape.due_date)) map.set(etape.due_date, [])
      map.get(etape.due_date).push(etape)
    }
    return [...map.entries()]
  }, [donnees, onglet, today])

  const resume = donnees?.resume ?? {
    a_faire: 0, en_retard: 0, fait: 0, sautee: 0,
  }

  return (
    <div className="page">
      <div className="lp-controlbar crm-controlbar mb-3">
        <h1 className="lp-cb-title flex items-center gap-2">
          <CalendarClock className="h-5 w-5" aria-hidden="true" />
          Suivi des relances
        </h1>
      </div>

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList>
          {ONGLETS.map((o) => (
            <TabsTrigger key={o.value} value={o.value}>{o.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2" data-testid="relances-suivi-resume">
          <Badge tone="outline">À faire : {resume.a_faire}</Badge>
          <Badge tone="danger">En retard : {resume.en_retard}</Badge>
          <Badge tone="success">Faites : {resume.fait}</Badge>
          <Badge tone="neutral">Sautées : {resume.sautee}</Badge>
        </div>
        {isResponsableOuAdmin && (
          <Select value={ownerFiltre} onValueChange={setOwnerFiltre}>
            <SelectTrigger className="w-48" aria-label="Responsable"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="moi">Moi</SelectItem>
              <SelectItem value="tous">Toute l&apos;équipe</SelectItem>
              {users.map((u) => (
                <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      <Card className="mt-3">
        <CardContent className="pt-4">
          {loading ? (
            <Spinner />
          ) : erreur ? (
            <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
          ) : groupes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune touche sur cette période.</p>
          ) : (
            <div className="flex flex-col gap-4">
              {groupes.map(([jour, etapesJour]) => (
                <div key={jour}>
                  <h3 className="mb-1.5 text-sm font-semibold capitalize">{jourTitre(jour)}</h3>
                  <ul className="space-y-2">
                    {etapesJour.map((etape) => (
                      <RelanceEtapeRow
                        key={etape.id} etape={etape} busyId={busyId} navigate={navigate}
                        showStatut
                        readOnly={!actionnable || etape.statut !== 'a_faire'}
                        onFait={(id, payload) => traiter(id, 'fait', payload)}
                        onSauter={(id, note) => traiter(id, 'sauter', note)}
                        onReporter={(id, dueAt) => traiter(id, 'reporter', dueAt)}
                        onOuvrirMessage={setMessageEtape}
                      />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <ToucheMessageDialog
        etape={messageEtape}
        open={!!messageEtape}
        onOpenChange={(o) => { if (!o) setMessageEtape(null) }}
        onSent={() => { setMessageEtape(null); charger() }}
      />
    </div>
  )
}
