// MRY15 — Frise de la cadence de relance du lead : TOUTES les touches (tous
// statuts, toutes cadences confondues, MRY5 `?lead=<id>`), triées serveur
// cadence puis ordre. Auto-suffisant (comme InitRelanceButton juste
// au-dessus) : charge lui-même via `crmApi`, jamais un second appel réseau
// pour les champs déjà posés sur le lead (`prochaine_touche_at` etc., MRY16).
import { Fragment, useEffect, useState } from 'react'
import {
  Check, SkipForward, Clock3, Ban, MapPin,
} from 'lucide-react'
import crmApi from '../../../../api/crmApi'
import { Spinner, Badge } from '../../../../ui'
import { formatDate } from '../../../../lib/format'
import { toastError } from '../../../../lib/toast'
import RelanceEtapeRow from '../../relances/RelanceEtapeRow'
import ToucheMessageDialog from '../../relances/ToucheMessageDialog'
import { STATUT_VISITE_TONE, visitePassee } from '../../relances/visiteGuidance'

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

// CKP1/CKP4 — `annulee` (arrêt MOTEUR, `Ban`) reste une icône DISTINCTE de
// `sautee` (action humaine, `SkipForward`) : la vérité des sautées ne se
// limite pas au badge de `RelanceEtapeRow`, la frise a sa propre icône.
const STATUT_ICON = {
  fait: Check,
  sautee: SkipForward,
  annulee: Ban,
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
 * @param {() => void} [onChanged]  MRY32 — appelé après Fait/Sauter/Reporter/
 *   WhatsApp sur une touche rendue ICI en mode compact (la prochaine à faire,
 *   ou toute touche en retard). Le parent (`SectionPipeline.jsx`) l'utilise
 *   pour à la fois bumper `friseReload` (qui repasse un nouveau `reloadToken`
 *   à cette frise — le rechargement de LA FRISE elle-même passe déjà par là,
 *   jamais un second appel réseau ici) ET rafraîchir la fiche entière
 *   (`refData.onRelanceChanged`, `LeadWorkspace.jsx`) — une touche « Fait »
 *   peut avancer l'étape/les tags du lead (règles d'arrêt MRY9).
 */
export default function CadenceFrise({ leadId, reloadToken = 0, onChanged }) {
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [montrerPassees, setMontrerPassees] = useState(false)
  const [etapes, setEtapes] = useState([])
  // VISCAD1 — les visites techniques du lead, mêlées à la frise (la visite
  // devient une étape VISIBLE du suivi commercial). État INDÉPENDANT de
  // celui des touches ci-dessus : un échec ici ne doit JAMAIS casser la
  // frise existante (voir le `.catch` silencieux plus bas) — la frise
  // continue de se lire comme avant si les visites sont indisponibles.
  const [visites, setVisites] = useState([])
  // MRY32 — état des actions rendues en mode compact ci-dessous (mêmes noms
  // que `RelancesDuJourWidget.jsx`/`RelancesSuiviPage.jsx`).
  const [busyId, setBusyId] = useState(null)
  const [messageEtape, setMessageEtape] = useState(null)

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

  useEffect(() => {
    if (!leadId) return undefined
    let active = true
    // VISCAD1 — appel INDÉPENDANT du fetch des touches ci-dessus : ni
    // bloquant pour le rendu principal, ni fatal pour la frise. Garde
    // défensive `typeof … === 'function'` : de nombreux tests existants
    // (CadenceFrise.mry15, SectionPipeline.relance, LeadWorkspace…) mockent
    // `crmApi` avec un sous-ensemble de méthodes qui ne connaît pas encore
    // `getLeadVisites` — la frise doit continuer de fonctionner À L'IDENTIQUE
    // pour eux (repli silencieux, comme un échec réseau).
    const requete = typeof crmApi.getLeadVisites === 'function'
      ? crmApi.getLeadVisites(leadId)
      : Promise.reject(new Error('getLeadVisites indisponible'))
    requete
      .then((r) => { if (active) setVisites(r.data?.visites ?? []) })
      .catch(() => { if (active) setVisites([]) })
    return () => { active = false }
  }, [leadId, reloadToken])

  const traiter = async (id, action, payload) => {
    setBusyId(id)
    try {
      let res
      if (action === 'fait') res = await crmApi.marquerRelanceEtapeFait(id, payload)
      else if (action === 'sauter') res = await crmApi.marquerRelanceEtapeSautee(id, payload)
      else if (action === 'reporter') res = await crmApi.reporterRelanceEtape(id, payload)
      onChanged?.()
      return res?.data
    } catch (err) {
      // CKP4 — voir `RelancesDuJourWidget.jsx` : un canal APPEL sans issue
      // (400 `{erreurs: {outcome}}`) s'affiche SOUS le contrôle, pas un toast.
      const champOutcome = action === 'fait' && err?.response?.status === 400
        ? err?.response?.data?.erreurs?.outcome : null
      if (!champOutcome) toastError('Action impossible pour le moment.')
      if (action === 'fait') throw err
      return undefined
    } finally {
      setBusyId(null)
    }
  }

  if (!leadId) return null
  if (loading) return <Spinner className="size-3.5" />
  if (erreur) {
    return <p className="text-xs text-muted-foreground">Frise de cadence indisponible pour le moment.</p>
  }
  if (etapes.length === 0) {
    return <p className="text-xs text-muted-foreground">Aucune cadence sur ce lead pour l'instant.</p>
  }

  // La PROCHAINE touche à faire — la première À FAIRE dans l'ordre serveur
  // (cadence puis ordre) — est mise en avant (gras) dans la frise ET rendue
  // actionnable (MRY32), comme toute touche à faire déjà en retard. Calculée
  // UNIQUEMENT sur les touches (jamais une visite — ce n'est pas une relance).
  const prochaineId = etapes.find((e) => e.statut === 'a_faire')?.id ?? null

  // VISCAD1 — « la visite devient une étape du suivi commercial » : mêle les
  // touches et les visites dans UNE frise chronologique. Chaque visite se
  // positionne à sa date prévue (ou réalisée, à défaut) ; le tri est STABLE
  // (ES2019+) — deux entrées à date égale gardent leur ordre d'origine
  // (touches d'abord, cadence/ordre serveur intacts).
  const items = [
    ...etapes.map((e) => ({
      kind: 'etape', id: `e${e.id}`, data: e,
      ts: e.due_at ? new Date(e.due_at).getTime() : (e.due_date ? new Date(e.due_date).getTime() : null),
      passee: e.statut !== 'a_faire',
    })),
    ...visites.map((v) => ({
      kind: 'visite', id: `v${v.id}`, data: v,
      ts: v.date_prevue ? new Date(v.date_prevue).getTime()
        : (v.date_realisee ? new Date(v.date_realisee).getTime() : null),
      // Un RETOUR TERRAIN disponible est l'info la plus actionnable de la
      // frise (c'est lui que le closing lit avant de rappeler) : il reste
      // VISIBLE même une fois la visite terminée/validée — seul le repli
      // d'une visite sans retour suit l'historique.
      passee: visitePassee(v) && !v.retour_disponible,
    })),
  ].sort((a, b) => (a.ts ?? Infinity) - (b.ts ?? Infinity))

  // QJ-LISIBILITÉ (fondateur 07/09/2026, « all the list is still hashed ») —
  // les entrées PASSÉES (touches faites/sautées, visites terminées/validées)
  // sont repliées par défaut : la frise montre ce qui RESTE à faire/venir,
  // l'historique s'ouvre à la demande.
  const passees = items.filter((it) => it.passee)
  const visibles = montrerPassees ? items : items.filter((it) => !it.passee)

  return (
    <>
      {passees.length > 0 && (
        <button
          type="button"
          className="text-xs text-muted-foreground underline underline-offset-2"
          onClick={() => setMontrerPassees((v) => !v)}
        >
          {montrerPassees
            ? 'Masquer les touches passées'
            : `Afficher les ${passees.length} touche(s) passée(s)`}
        </button>
      )}
      <ol className="flex flex-col gap-1" data-testid="cadence-frise" aria-label="Frise de cadence">
        {visibles.map((item) => {
          // VISCAD1 — une visite technique : étape DISTINCTE de la frise
          // (icône différente, jamais d'actions Fait/Sauter/Reporter — ce
          // n'est pas une touche de relance), statut au libellé SERVEUR
          // (`statut_libelle`, jamais réinventé) + « retour terrain
          // disponible » quand le serveur le signale.
          if (item.kind === 'visite') {
            const visite = item.data
            return (
              <li
                key={item.id}
                data-testid="cadence-frise-visite"
                data-statut={visite.statut}
                className="flex flex-wrap items-center gap-1 text-xs text-foreground"
              >
                <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
                <span>
                  Visite technique{visite.date_prevue ? ` — ${formatDate(visite.date_prevue)}` : ''}
                </span>
                <Badge tone={STATUT_VISITE_TONE[visite.statut] ?? 'neutral'}>
                  {visite.statut_libelle ?? visite.statut}
                </Badge>
                {visite.commercial_nom && (
                  <span className="text-muted-foreground">· {visite.commercial_nom}</span>
                )}
                {visite.retour_disponible && (
                  <span className="text-muted-foreground">
                    — Retour terrain disponible{visite.notes ? ` : ${visite.notes}` : ''}
                  </span>
                )}
              </li>
            )
          }
          const etape = item.data
          const Icon = STATUT_ICON[etape.statut] ?? Clock3
          const estProchaine = etape.id === prochaineId
          const heureAt = heureDueAt(etape.due_at)
          // MRY32 — actionnable : la prochaine touche à faire, OU toute
          // touche à faire déjà en retard (les deux peuvent coïncider — le OU
          // logique ne rend alors qu'UNE seule ligne d'action, jamais deux).
          const actionnable = etape.statut === 'a_faire' && (estProchaine || etape.overdue)
          return (
            <Fragment key={item.id}>
              <li
                data-testid="cadence-frise-etape"
                data-statut={etape.statut}
                className={[
                  'flex flex-wrap items-center gap-1 text-xs',
                  etape.statut === 'sautee' ? 'text-muted-foreground line-through' : '',
                  etape.statut === 'annulee' ? 'text-muted-foreground italic' : '',
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
                {/* CKP1/CKP4 — « vérité des sautées » : SAUTEE = action
                    humaine (qui/quand), ANNULEE = arrêt MOTEUR (motif seul,
                    jamais un auteur) — jamais confondues, ici comme dans le
                    badge de `RelanceEtapeRow.jsx`. */}
                {etape.statut === 'sautee' && (
                  <span>
                    Sautée{etape.traite_par_nom ? ` · ${etape.traite_par_nom}` : ''}
                    {heureDueAt(etape.traite_le) ? ` · ${heureDueAt(etape.traite_le)}` : ''}
                  </span>
                )}
                {etape.statut === 'annulee' && <span>Annulée (moteur)</span>}
                {etape.note && <span className="text-muted-foreground">— {etape.note}</span>}
              </li>
              {/* MRY32 — Appeler/WhatsApp/Fait/Sauter/Reporter directement
                  depuis la fiche, sans quitter la frise. Mode compact : pas
                  de nom de lead ni de badges de score/priorité (déjà sous les
                  yeux de qui regarde CETTE fiche). */}
              {actionnable && (
                <RelanceEtapeRow
                  etape={etape} busyId={busyId} compact
                  onFait={(id, payload) => traiter(id, 'fait', payload)}
                  onSauter={(id, note) => traiter(id, 'sauter', note)}
                  onReporter={(id, dueAt) => traiter(id, 'reporter', dueAt)}
                  onOuvrirMessage={setMessageEtape}
                  onVisiteChanged={onChanged}
                />
              )}
            </Fragment>
          )
        })}
      </ol>
      <ToucheMessageDialog
        etape={messageEtape}
        open={!!messageEtape}
        onOpenChange={(o) => { if (!o) setMessageEtape(null) }}
        onSent={() => { setMessageEtape(null); onChanged?.() }}
      />
    </>
  )
}
