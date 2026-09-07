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
      if (action === 'fait') await crmApi.marquerRelanceEtapeFait(id, payload)
      else if (action === 'sauter') await crmApi.marquerRelanceEtapeSautee(id, payload)
      else if (action === 'reporter') await crmApi.reporterRelanceEtape(id, payload)
      retirer(id)
      // MRY9/MRY11 — une action peut faire naître une NOUVELLE touche due
      // (report, clôture de cadence…) : refetch silencieux, jamais bloquant.
      setTimeout(() => { charger() }, 1000)
    } catch {
      // F2 — l'échec n'est plus MUET : la ligne reste (retirer() jamais
      // appelé ici) et redevient cliquable (busyId remis à null ci-dessous),
      // mais l'agent doit être PRÉVENU que son geste n'a rien fait.
      toastError('Action impossible pour le moment.')
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
        onSent={(id) => { retirer(id); setTimeout(() => { charger() }, 1000) }}
      />
    </Card>
  )
}
