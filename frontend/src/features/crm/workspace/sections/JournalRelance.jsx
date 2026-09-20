// RLC2 (relevé fondateur du 08/09/2026, lead test1 aa — « on ne voit pas d'un
// coup d'œil ce qui s'est passé dans le plan de relance ») — LE panneau
// chronologique du Suivi commercial.
//
// Une seule liste, fusionnée CÔTÉ SERVEUR (`selectors.journal_relance`) :
// touches faites/sautées/retirées avec leur ISSUE, WhatsApp ouverts, rappels
// reportés, arrêts et redémarrages de cadence avec leur MOTIF, filets posés
// automatiquement, changements d'étape du funnel, devis partis, annulations
// (RLC1). Rien n'est recalculé ici : la nature d'une ligne vient de son `type`
// (constante serveur `JOURNAL_TYPES`), sa cause de `cause`, son auteur de
// `par` — l'écran ne devine JAMAIS depuis un texte libre.
//
// Distinct de `ArbreHistorique` juste à côté (le chatter CONDENSÉ du client,
// données déjà chargées par le shell) : ici c'est le PLAN DE RELANCE qui parle,
// avec ses causes, et c'est une lecture serveur dédiée.
import { useEffect, useState } from 'react'
import {
  Check, SkipForward, Ban, Clock3, MessageCircle, TrendingUp, Send,
  StickyNote, Sparkles, XCircle, Activity,
} from 'lucide-react'
import crmApi from '../../../../api/crmApi'
import { Spinner } from '../../../../ui'

// Icône + libellé par NATURE de ligne (les clés sont celles du serveur —
// `selectors.JOURNAL_TYPES` — jamais un vocabulaire inventé ici).
const TYPE_RENDER = {
  touche_faite: { Icon: Check, label: 'Touche faite' },
  touche_sautee: { Icon: SkipForward, label: 'Touche sautée' },
  touche_annulee: { Icon: Ban, label: 'Touche retirée du plan' },
  annulation: { Icon: Activity, label: 'Annulation' },
  message_ouvert: { Icon: MessageCircle, label: 'Message ouvert' },
  rappel_reporte: { Icon: Clock3, label: 'Rappel reporté' },
  cadence_demarree: { Icon: Sparkles, label: 'Cadence démarrée' },
  cadence_arretee: { Icon: XCircle, label: 'Cadence arrêtée' },
  filet_pose: { Icon: StickyNote, label: 'Étape posée' },
  devis_suivi: { Icon: Send, label: 'Devis envoyé' },
  etape_funnel: { Icon: TrendingUp, label: 'Étape du lead' },
}

/** « JJ/MM à HH:MM », heure de Casablanca — fuseau EXPLICITE (jamais celui du
 *  navigateur : un commercial en déplacement lirait sinon une fausse heure).
 *  Chaîne vide si l'horodatage est absent ou illisible — jamais un « — » qui
 *  ressemblerait à une information. */
function quandCourt(iso) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    timeZone: 'Africa/Casablanca',
  }).format(t).replace(', ', ' à ')
}

/**
 * @param {number|string|null} leadId
 * @param {number} [reloadToken]  Incrémenté par le parent après un geste de
 *   relance (Fait/Sauter/Reporter/Annuler, Relancer/Arrêter la cadence) — le
 *   journal se relit alors, jamais un polling.
 */
export default function JournalRelance({ leadId, reloadToken = 0 }) {
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [journal, setJournal] = useState(null)

  useEffect(() => {
    if (!leadId) return undefined
    let actif = true
    // Garde défensive (même motif que `CadenceFrise` pour `getLeadVisites`) :
    // les suites existantes mockent `crmApi` avec un sous-ensemble de méthodes
    // qui ne connaît pas encore `getJournalRelance` — le panneau doit alors se
    // taire exactement comme sur une panne réseau, jamais lever une TypeError
    // qui casserait la fiche entière.
    const requete = typeof crmApi.getJournalRelance === 'function'
      ? crmApi.getJournalRelance(leadId)
      : Promise.reject(new Error('getJournalRelance indisponible'))
    queueMicrotask(() => { if (actif) { setLoading(true); setErreur(false) } })
    requete
      .then((r) => { if (actif) setJournal(r.data ?? null) })
      .catch(() => { if (actif) { setErreur(true); setJournal(null) } })
      .finally(() => { if (actif) setLoading(false) })
    return () => { actif = false }
  }, [leadId, reloadToken])

  if (!leadId) return null
  if (loading) return <Spinner className="size-3.5" />
  if (erreur || journal === null) {
    return (
      <p className="text-xs text-muted-foreground">
        Journal du plan de relance indisponible pour le moment.
      </p>
    )
  }

  const lignes = journal.lignes ?? []
  return (
    <section className="mt-2 flex flex-col gap-1" data-testid="journal-relance">
      <h4 className="text-xs font-semibold text-foreground">
        Ce qui s’est passé
      </h4>
      {/* L'état courant EN UNE PHRASE, servie par le serveur (jamais
          recomposée ici — deux phrases auraient divergé). */}
      {journal.etat?.phrase && (
        <p className="text-xs text-foreground" data-testid="journal-etat">
          {journal.etat.phrase}
        </p>
      )}
      {lignes.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Rien ne s’est encore passé sur le plan de relance de ce lead.
        </p>
      ) : (
        <ol className="flex flex-col gap-1" aria-label="Journal du plan de relance">
          {lignes.map((ligne, index) => {
            const rendu = TYPE_RENDER[ligne.type]
            const Icon = rendu?.Icon ?? StickyNote
            const quand = quandCourt(ligne.quand)
            return (
              <li
                // Le serveur ne numérote pas les lignes (elles viennent de deux
                // tables) : la clé est donc la position dans une liste RENDUE
                // telle quelle, jamais réordonnée à l'écran.
                key={`${ligne.type}-${ligne.quand}-${index}`}
                data-testid="journal-ligne"
                data-type={ligne.type}
                className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground"
              >
                <Icon className="size-3.5 shrink-0" aria-hidden="true" />
                {quand && <span>{quand}</span>}
                <span className="text-foreground">
                  {rendu?.label ?? ligne.type}
                </span>
                <span aria-hidden="true">·</span>
                <span>{ligne.titre}</span>
                {/* La CAUSE : pourquoi cette ligne existe. Omise — jamais
                    remplacée par un tiret — quand le serveur ne la connaît
                    pas. */}
                {ligne.cause && <span>— {ligne.cause}</span>}
                {/* `par` vide = geste du MOTEUR (CKP1) : aucun nom d'humain
                    n'est alors affiché, et surtout pas inventé. */}
                {ligne.par && <span>· {ligne.par}</span>}
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
