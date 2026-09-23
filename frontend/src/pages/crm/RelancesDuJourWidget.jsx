import { useEffect, useState } from 'react'
import { CalendarClock } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Spinner, Segmented,
} from '../../ui'
import RelanceEtapeRow from '../../features/crm/relances/RelanceEtapeRow'
import ToucheMessageDialog from './ToucheMessageDialog'
import { toastError } from '../../lib/toast'

/* ============================================================================
   RELANCE FOUNDATION / MRY14 — panneau « Relances du jour » v2 (plan de
   relance structuré multi-touches, crm.RelanceEtape). Liste les étapes dues
   AUJOURD'HUI + EN RETARD (scope=all par défaut, mêmes règles de portée que
   le reste du CRM — voir crm.selectors.relance_etapes_dues). Trois cadences
   nommées (contact/après devis/réveil, MRY4/MRY5) : message prêt + WhatsApp
   (MRY13, aperçu-puis-clic, décision D5 — AUCUN envoi automatique), appel
   (`tel:`), Fait (avec issue/note/rappel — MRY10, déclenche les règles
   d'arrêt de MRY9), Sauter, Reporter (décale cette touche ET les suivantes,
   MRY10).

   MRY31 — `RelanceEtapeRow` (badges + panneaux Fait/Sauter/Reporter) est
   désormais EXTRAIT dans `features/crm/relances/RelanceEtapeRow.jsx`, partagé
   avec l'écran « Suivi des relances » et la frise de la fiche lead (MRY32).
   Ce widget l'importe tel quel — comportement/markup INCHANGÉS.

   MRY32 — sélecteur « Aujourd'hui + retard | Demain | 7 jours » (scopes
   `all`/`tomorrow`/`week` de MRY30) : une ligne dont l'échéance tombe APRÈS
   aujourd'hui se lit seulement (`readOnly`) — on ne « fait » jamais une
   touche qui n'a pas encore eu lieu.

   CAD117 — « X leads sans cadence » : le seul filet existant était le
   panneau Adhérence (`AdherenceRelancesPanel.jsx`, section « Leads sans
   touche due »), invisible tant qu'on n'ouvre pas cet écran-là. Le compteur
   ci-dessous lit le MÊME sélecteur serveur (`kpi_adherence.leads_sans_touche`,
   `GET relance-etapes/kpi-adherence/`) — jamais recompté ici — et ouvre la
   même liste en lecture seule, à côté des relances du jour. Aucun démarrage
   de cadence en masse depuis ce compteur (garde-fou de la tâche).
   ========================================================================== */

const SCOPES = [
  { value: 'all', label: "Aujourd'hui + retard" },
  { value: 'tomorrow', label: 'Demain' },
  { value: 'week', label: '7 jours' },
]

// Casablanca EXPLICITE (jamais le fuseau du navigateur) — même trick que
// `RelancesSuiviPage.jsx`/`LeadCard.jsx` (`en-CA` -> AAAA-MM-JJ, comparable
// par simple ordre de chaîne). Copié plutôt qu'importé (même motif que
// `CadenceFrise.jsx heureDueAt` — deux dérivations de présentation
// indépendantes du même state, pas une logique métier partagée).
function todayCasa() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(new Date())
}

export default function RelancesDuJourWidget() {
  const navigate = useNavigate()
  const [scope, setScope] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [etapes, setEtapes] = useState([])
  const [busyId, setBusyId] = useState(null)
  const [messageEtape, setMessageEtape] = useState(null)
  // CAD117 — indépendant du scope ci-dessus (« sans cadence » n'a pas de
  // notion d'échéance) : une seule lecture au montage, repliée par défaut.
  const [sansCadence, setSansCadence] = useState([])
  const [sansCadenceOuvert, setSansCadenceOuvert] = useState(false)

  useEffect(() => {
    let active = true
    // Garde défensive (même motif que `JournalRelance.jsx getJournalRelance`) :
    // les suites existantes mockent `crmApi` avec un sous-ensemble de méthodes
    // qui ne connaît pas encore `getKpiAdherence` — le compteur doit alors se
    // taire exactement comme sur une panne réseau, jamais lever une TypeError.
    const requete = typeof crmApi.getKpiAdherence === 'function'
      ? crmApi.getKpiAdherence({ jours: 30 })
      : Promise.reject(new Error('getKpiAdherence indisponible'))
    requete
      .then((r) => { if (active) setSansCadence(r.data?.leads_sans_touche ?? []) })
      .catch(() => { if (active) setSansCadence([]) })
    return () => { active = false }
  }, [])

  const charger = () => {
    let active = true
    crmApi.getRelanceEtapesDues({ scope })
      .then((r) => { if (active) setEtapes(r.data?.results ?? []) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }

  useEffect(() => {
    queueMicrotask(() => setLoading(true))
    return charger()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `charger` referme `scope`, déjà en dépendance ; l'ajouter provoquerait la même relecture à chaque rendu sans rien changer.
  }, [scope])

  const retirer = (id) => setEtapes((prev) => prev.filter((e) => e.id !== id))

  const traiter = async (id, action, payload) => {
    setBusyId(id)
    try {
      let res
      if (action === 'fait') res = await crmApi.marquerRelanceEtapeFait(id, payload)
      else if (action === 'sauter') res = await crmApi.marquerRelanceEtapeSautee(id, payload)
      else if (action === 'reporter') res = await crmApi.reporterRelanceEtape(id, payload)
      retirer(id)
      // MRY9/MRY11 — une action peut faire naître une NOUVELLE touche due
      // (report, clôture de cadence…) : refetch silencieux, jamais bloquant.
      setTimeout(() => { charger() }, 1000)
      return res?.data
    } catch (err) {
      // CKP4 — un canal APPEL clôturé « Fait » sans issue renvoie 400
      // `{erreurs: {outcome}}` : ce champ s'affiche SOUS le contrôle
      // (`RelanceEtapeRow`, promesse rejetée ci-dessous), jamais un toast
      // générique qui masquerait le champ fautif.
      const champOutcome = action === 'fait' && err?.response?.status === 400
        ? err?.response?.data?.erreurs?.outcome : null
      // F2 — l'échec n'est plus MUET : la ligne reste (retirer() jamais
      // appelé ici) et redevient cliquable (busyId remis à null ci-dessous),
      // mais l'agent doit être PRÉVENU que son geste n'a rien fait.
      if (!champOutcome) toastError('Action impossible pour le moment.')
      if (action === 'fait') throw err
      return undefined
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Card data-testid="relances-du-jour-widget">
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4" /> Relances du jour
          </CardTitle>
          <CardDescription>
            Étapes de plan de relance dues aujourd&apos;hui ou en retard.
          </CardDescription>
        </div>
        {/* MRY31 — porte vers l'écran « Suivi des relances » (tous jours,
            tous statuts, filtre Responsable) — ce widget reste volontairement
            limité à aujourd'hui + retard. */}
        <Link to="/crm/relances" className="shrink-0 text-xs font-medium text-primary hover:underline">
          Voir le suivi
        </Link>
      </CardHeader>
      <CardContent>
        <Segmented
          className="mb-3" size="sm" options={SCOPES} value={scope} onChange={setScope}
        />
        {/* CAD117 — lecture seule : ouvre/replie la liste, ne démarre jamais
            rien. Absent quand `sansCadence` est vide (rien à signaler). */}
        {sansCadence.length > 0 && (
          <div className="mb-3" data-testid="cad117-sans-cadence">
            <button
              type="button"
              className="text-xs font-medium text-primary hover:underline"
              onClick={() => setSansCadenceOuvert((o) => !o)}
            >
              {sansCadence.length} lead{sansCadence.length > 1 ? 's' : ''} sans cadence
            </button>
            {sansCadenceOuvert && (
              <ul className="mt-1.5 flex flex-col gap-1">
                {sansCadence.map((lead) => (
                  <li key={lead.lead_id}>
                    <button
                      type="button"
                      className="w-full rounded-md border border-border p-1.5 text-left text-xs hover:bg-muted"
                      onClick={() => navigate(`/crm/leads?lead=${lead.lead_id}`)}
                    >
                      <span className="font-medium">{lead.nom}</span>
                      {lead.ville ? ` · ${lead.ville}` : ''}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {loading ? (
          <Spinner />
        ) : error ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : etapes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune touche due — les cadences démarrent seules à l&apos;arrivée d&apos;un lead.
          </p>
        ) : (
          <ul className="space-y-2">
            {etapes.map((etape) => (
              <RelanceEtapeRow
                key={etape.id} etape={etape} busyId={busyId} navigate={navigate}
                readOnly={etape.due_date > todayCasa()}
                onFait={(id, payload) => traiter(id, 'fait', payload)}
                onSauter={(id, note) => traiter(id, 'sauter', note)}
                onReporter={(id, dueAt) => traiter(id, 'reporter', dueAt)}
                onOuvrirMessage={setMessageEtape}
              />
            ))}
          </ul>
        )}
      </CardContent>
      <ToucheMessageDialog
        etape={messageEtape}
        open={!!messageEtape}
        onOpenChange={(o) => { if (!o) setMessageEtape(null) }}
        onSent={() => { charger() }}
      />
    </Card>
  )
}
