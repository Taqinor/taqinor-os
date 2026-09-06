// MRY15 — Frise de la cadence de relance du lead : TOUTES les touches (tous
// statuts, toutes cadences confondues, MRY5 `?lead=<id>`), triées serveur
// cadence puis ordre. Auto-suffisant (comme InitRelanceButton juste
// au-dessus) : charge lui-même via `crmApi`, jamais un second appel réseau
// pour les champs déjà posés sur le lead (`prochaine_touche_at` etc., MRY16).
import { useEffect, useState } from 'react'
import { Check, SkipForward, Clock3 } from 'lucide-react'
import crmApi from '../../../../api/crmApi'
import { Spinner } from '../../../../ui'
import { formatDate } from '../../../../lib/format'

const CADENCE_LABELS = {
  contact: 'Contact',
  apres_devis: 'Après devis',
  reveil: 'Réveil',
  generique: 'Générique',
}

const CANAL_LABELS = {
  appel: 'Appel',
  whatsapp: 'WhatsApp',
  email: 'E-mail',
  visite: 'Visite',
}

const STATUT_ICON = {
  fait: Check,
  sautee: SkipForward,
  a_faire: Clock3,
}

/** F3/MRY15 — `due_at` (ISO) → « HH:MM » heure Casablanca, fuseau EXPLICITE
 *  (même calcul que `heureDue` dans `pages/crm/RelancesDuJourWidget.jsx`),
 *  copié plutôt qu'importé (page → section, sens d'import inverse) : SANS le
 *  repli « maintenant » de ce dernier, propre à la file DU JOUR — ici la
 *  frise couvre tout l'historique, une touche passée garde son horaire réel,
 *  jamais un mot qui écraserait la date. `null` (absente/invalide) laisse
 *  l'appelant n'afficher que la date. */
function heureDueAt(dueAt) {
  if (!dueAt) return null
  const t = new Date(dueAt).getTime()
  if (Number.isNaN(t)) return null
  return new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(t)
}

/**
 * @param {number|string|null} leadId
 * @param {number} [reloadToken]  Incrémenté par le parent (Relancer/Arrêter
 *   la cadence) pour forcer un rechargement — jamais un polling.
 */
export default function CadenceFrise({ leadId, reloadToken = 0 }) {
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [etapes, setEtapes] = useState([])

  useEffect(() => {
    if (!leadId) return undefined
    let active = true
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    crmApi.getRelanceEtapesLead(leadId)
      .then((r) => { if (active) setEtapes(r.data?.results ?? []) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [leadId, reloadToken])

  if (!leadId) return null
  if (loading) return <Spinner className="size-3.5" />
  if (erreur) {
    return <p className="text-xs text-muted-foreground">Frise de cadence indisponible pour le moment.</p>
  }
  if (etapes.length === 0) {
    return <p className="text-xs text-muted-foreground">Aucune cadence sur ce lead pour l'instant.</p>
  }

  // La PROCHAINE touche à faire — la première À FAIRE dans l'ordre serveur
  // (cadence puis ordre) — est mise en avant (gras) dans la frise.
  const prochaineId = etapes.find((e) => e.statut === 'a_faire')?.id ?? null

  return (
    <ol className="flex flex-col gap-1" data-testid="cadence-frise" aria-label="Frise de cadence">
      {etapes.map((etape) => {
        const Icon = STATUT_ICON[etape.statut] ?? Clock3
        const estProchaine = etape.id === prochaineId
        const heureAt = heureDueAt(etape.due_at)
        return (
          <li
            key={etape.id}
            data-testid="cadence-frise-etape"
            data-statut={etape.statut}
            className={[
              'flex flex-wrap items-center gap-1 text-xs',
              etape.statut === 'sautee' ? 'text-muted-foreground line-through' : '',
              estProchaine ? 'font-semibold text-foreground' : 'text-muted-foreground',
            ].join(' ')}
          >
            <Icon className="size-3.5 shrink-0" aria-hidden="true" />
            <span>{CADENCE_LABELS[etape.cadence] ?? etape.cadence}</span>
            <span aria-hidden="true">·</span>
            <span>{CANAL_LABELS[etape.canal] ?? etape.canal}</span>
            <span aria-hidden="true">·</span>
            <span>{etape.libelle}</span>
            <span aria-hidden="true">·</span>
            <span>{formatDate(etape.due_date)}{heureAt ? ` ${heureAt}` : ''}</span>
            {etape.note && <span className="text-muted-foreground">— {etape.note}</span>}
          </li>
        )
      })}
    </ol>
  )
}
