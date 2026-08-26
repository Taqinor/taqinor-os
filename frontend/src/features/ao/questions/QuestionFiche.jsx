import { useState } from 'react'
import { Badge, Button, Input, Label, Textarea } from '../../../ui'
import { formatDate } from '../../../lib/format'
import { deltaReel } from './QuestionFiche.utils'

/* ============================================================================
   AOF107 (1/3) — Fiche question : impact PRÉVU → delta RÉEL.
   ----------------------------------------------------------------------------
   Chaque repère posé par l'annotateur (AOF106) ouvre CETTE fiche. Le contrat
   produit gravé, deux fois répété dans l'en-tête du Groupe AOF : « on ne pose
   une question que si sa réponse change le compte ». D'où le refus À
   L'ENREGISTREMENT d'une question sans impact chiffré — pas une validation
   HTML5 discrète, un message qui NOMME la règle.

   **Le delta réel est une SOUSTRACTION D'AFFICHAGE entre deux comptes
   SERVEUR** (`compte_avant_modules` / `compte_apres_modules`, fournis par le
   propriétaire de l'atelier après un vrai recalcul serveur) — jamais un
   calepinage rejoué côté front. Même discipline que `DiffPlan.jsx`
   (`deltaCompte`, AOF105) : ce composant ne fait QUE l'affichage, la
   soustraction d'un chiffre déjà produit par le moteur n'est pas une
   dérivation métier.

   `onRecalculer` appartient au propriétaire de l'atelier : il rejoue le
   calepinage serveur (`useCalepinage.recalculer`, AOF94) et fournit le
   nouveau `compte_apres_modules` en retour — ce composant ne l'appelle
   jamais lui-même, il ne fait que déclencher l'action.

   ── Contrat de charge utile ───────────────────────────────────────────────
   question = {
     id, repere, texte, impact_min_modules, impact_max_modules,
     reponse, decision, date_decision, statut,
     compte_avant_modules?, compte_apres_modules?,
   }
   historique = [{ date, compte_avant_modules, compte_apres_modules }]
   ========================================================================== */

const STATUTS = {
  posee: { label: 'Posée', tone: 'neutral' },
  repondue: { label: 'Répondue', tone: 'info' },
  tranchee: { label: 'Tranchée', tone: 'success' },
  sans_suite: { label: 'Sans suite', tone: 'neutral' },
}

const MESSAGE_IMPACT_REQUIS = 'on ne pose une question que si sa réponse change le compte'

/* WIR207 — les QUATRE actions que `services.trancher_question` accepte
   (`ACTIONS_QUESTION`). L'écran ne propose rien d'autre : une action inconnue
   part en 400, et une action inventée ici serait un bouton qui ne marche
   jamais. Le libellé dit ce que l'action FAIT à la donnée, pas son nom de
   code. */
const ACTIONS_TRANCHER = [
  { valeur: 'aucune', libelle: 'Aucune — enregistrer la décision seule' },
  { valeur: 'ecarter_obstacle', libelle: 'Écarter l’obstacle lié (il sort du compte)' },
  { valeur: 'confirmer_obstacle', libelle: 'Confirmer l’obstacle lié (requalifier sa provenance)' },
  { valeur: 'requalifier_cote', libelle: 'Requalifier les cotes de la chaîne liée' },
]

/* Les provenances que `confirmer_obstacle` peut poser — celles d'`ObstacleAO.
   Provenance` côté serveur. `ECARTE` n'y figure PAS : écarter est une action à
   part entière (ci-dessus), pas une provenance à choisir. */
const PROVENANCES_CONFIRMATION = [
  { valeur: 'MESURE', libelle: 'Mesuré' },
  { valeur: 'MESURE_DOUTEUX', libelle: 'Mesuré, à confirmer' },
  { valeur: 'PLAN', libelle: 'Relevé sur plan' },
  { valeur: 'DEVINE', libelle: 'Deviné' },
  { valeur: 'DECLARE_CLIENT', libelle: 'Déclaré par le client' },
]

/* Les statuts de cote que `requalifier_cote` peut poser (`StatutCote`). */
const STATUTS_COTE = [
  { valeur: 'MESURE', libelle: 'Mesurée' },
  { valeur: 'A_CONFIRMER', libelle: 'À confirmer' },
  { valeur: 'PLAN_OU_DEDUIT', libelle: 'Relevée sur plan ou déduite' },
]

function versEntier(brut) {
  if (brut === '' || brut == null) return null
  const n = Number.parseInt(brut, 10)
  return Number.isFinite(n) ? n : null
}

function signe(v) {
  if (!Number.isFinite(v)) return null
  return v > 0 ? `+${v}` : String(v)
}

function texteImpactPrevu(question) {
  const mini = question?.impact_min_modules
  const maxi = question?.impact_max_modules
  if (!Number.isFinite(mini) && !Number.isFinite(maxi)) return null
  if (Number.isFinite(mini) && Number.isFinite(maxi) && mini !== maxi) {
    return `${signe(mini)} à ${signe(maxi)} modules`
  }
  const v = Number.isFinite(mini) ? mini : maxi
  return `${signe(v)} module${Math.abs(v) > 1 ? 's' : ''}`
}

export function QuestionFiche({
  question,
  historique = [],
  onChange,
  onTrancher,
  onRecalculer,
  recalculEnCours = false,
  tranchageEnCours = false,
}) {
  const [texte, setTexte] = useState(question?.texte ?? '')
  const [impactMin, setImpactMin] = useState(question?.impact_min_modules ?? '')
  const [impactMax, setImpactMax] = useState(question?.impact_max_modules ?? '')
  const [reponse, setReponse] = useState(question?.reponse ?? '')
  const [decision, setDecision] = useState(question?.decision ?? '')
  const [actionTrancher, setActionTrancher] = useState('aucune')
  const [provenance, setProvenance] = useState('MESURE')
  const [statutCote, setStatutCote] = useState('MESURE')

  // La fiche re-synchronise ses champs locaux quand `question` change
  // (nouvelle référence — on ouvre une AUTRE question) : ajustement pendant
  // le rendu (pattern React recommandé pour dériver un état depuis des props
  // qui changent) plutôt qu'un `useEffect`, qui provoquerait un rendu en
  // cascade évitable.
  const [derniereQuestion, setDerniereQuestion] = useState(question)
  if (question !== derniereQuestion) {
    setDerniereQuestion(question)
    setTexte(question?.texte ?? '')
    setImpactMin(question?.impact_min_modules ?? '')
    setImpactMax(question?.impact_max_modules ?? '')
    setReponse(question?.reponse ?? '')
    setDecision(question?.decision ?? '')
    setActionTrancher('aucune')
    setProvenance('MESURE')
    setStatutCote('MESURE')
  }

  if (!question) return null

  const impactMinN = versEntier(impactMin)
  const impactMaxN = versEntier(impactMax)
  const impactAbsent = impactMinN == null && impactMaxN == null
  const statut = STATUTS[question.statut] ?? STATUTS.posee

  const enregistrerQuestion = () => {
    if (impactAbsent) return
    onChange?.({
      texte,
      impact_min_modules: impactMinN,
      impact_max_modules: impactMaxN,
    })
  }

  /* WIR207 — la RÉPONSE reçue est une donnée de saisie : elle s'enregistre par
     le CRUD, comme le texte de la question. La DÉCISION, elle, ne s'écrit plus
     par ici : la poser en PATCH laissait le texte en base sans rien appliquer
     (obstacle toujours au compte, cotes inchangées, variantes toujours « à
     jour »). Elle passe par « Trancher » ci-dessous. */
  const enregistrerReponse = () => {
    onChange?.({ reponse })
  }

  const trancherQuestion = () => {
    const texteDecision = decision.trim()
    if (!texteDecision) return
    onTrancher?.({
      decision: texteDecision,
      action: actionTrancher,
      // Envoyés SEULEMENT quand l'action les consomme : une clé de trop est
      // ignorée par le serveur, mais elle laisserait croire ici qu'elle agit.
      ...(actionTrancher === 'confirmer_obstacle' ? { provenance } : {}),
      ...(actionTrancher === 'requalifier_cote' ? { statut_cote: statutCote } : {}),
    })
  }

  const delta = deltaReel(question)
  const impactPrevuTexte = texteImpactPrevu(question)
  const peutRecalculer = Boolean(question.reponse)

  return (
    <div className="flex flex-col gap-4" data-question-fiche={question.repere}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold">{`Fiche — Repère ${question.repere}`}</h3>
        <Badge tone={statut.tone} data-ao-etat={question.statut}>{statut.label}</Badge>
      </div>

      {/* ── Question + impact PRÉVISIONNEL (des deux côtés) ─────────────── */}
      <div className="flex flex-col gap-2">
        <Label htmlFor={`ao-question-texte-${question.id}`}>Question</Label>
        <Textarea
          id={`ao-question-texte-${question.id}`}
          rows={2}
          value={texte}
          onChange={(e) => setTexte(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor={`ao-question-impact-min-${question.id}`}>Impact minimal (modules)</Label>
            <Input
              id={`ao-question-impact-min-${question.id}`}
              type="number"
              step="1"
              inputMode="numeric"
              value={impactMin}
              onChange={(e) => setImpactMin(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor={`ao-question-impact-max-${question.id}`}>Impact maximal (modules)</Label>
            <Input
              id={`ao-question-impact-max-${question.id}`}
              type="number"
              step="1"
              inputMode="numeric"
              value={impactMax}
              onChange={(e) => setImpactMax(e.target.value)}
            />
          </div>
        </div>
        {impactAbsent && (
          <p role="alert" className="text-xs text-destructive">
            Question refusée : {MESSAGE_IMPACT_REQUIS}.
          </p>
        )}
        <Button size="sm" disabled={impactAbsent} onClick={enregistrerQuestion} className="self-start">
          Enregistrer la question
        </Button>
      </div>

      {/* ── Réponse reçue + décision retenue + date ─────────────────────── */}
      <div className="flex flex-col gap-2 border-t border-border pt-3">
        <Label htmlFor={`ao-question-reponse-${question.id}`}>Réponse reçue</Label>
        <Textarea
          id={`ao-question-reponse-${question.id}`}
          rows={2}
          value={reponse}
          onChange={(e) => setReponse(e.target.value)}
        />
        <div className="flex flex-wrap items-end gap-3">
          <Button size="sm" variant="outline" onClick={enregistrerReponse}>
            Enregistrer la réponse
          </Button>
          {peutRecalculer && (
            <Button size="sm" loading={recalculEnCours} disabled={recalculEnCours} onClick={() => onRecalculer?.()}>
              Recalculer
            </Button>
          )}
        </div>
      </div>

      {/* ── WIR207 — TRANCHER : la décision est APPLIQUÉE, pas seulement écrite */}
      <div className="flex flex-col gap-2 border-t border-border pt-3" data-ao-trancher={question.id}>
        <Label htmlFor={`ao-question-decision-${question.id}`}>Décision retenue</Label>
        <Textarea
          id={`ao-question-decision-${question.id}`}
          rows={2}
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
        />

        <Label htmlFor={`ao-question-action-${question.id}`}>Ce que la décision applique</Label>
        <select
          id={`ao-question-action-${question.id}`}
          className="form-select h-9 rounded-md border border-input bg-card px-2 text-sm text-foreground"
          value={actionTrancher}
          onChange={(e) => setActionTrancher(e.target.value)}
        >
          {ACTIONS_TRANCHER.map((a) => (
            <option key={a.valeur} value={a.valeur}>{a.libelle}</option>
          ))}
        </select>

        {actionTrancher === 'confirmer_obstacle' && (
          <>
            <Label htmlFor={`ao-question-provenance-${question.id}`}>Provenance à poser</Label>
            <select
              id={`ao-question-provenance-${question.id}`}
              className="form-select h-9 rounded-md border border-input bg-card px-2 text-sm text-foreground"
              value={provenance}
              onChange={(e) => setProvenance(e.target.value)}
            >
              {PROVENANCES_CONFIRMATION.map((p) => (
                <option key={p.valeur} value={p.valeur}>{p.libelle}</option>
              ))}
            </select>
          </>
        )}

        {actionTrancher === 'requalifier_cote' && (
          <>
            <Label htmlFor={`ao-question-statut-cote-${question.id}`}>Statut à poser sur les cotes</Label>
            <select
              id={`ao-question-statut-cote-${question.id}`}
              className="form-select h-9 rounded-md border border-input bg-card px-2 text-sm text-foreground"
              value={statutCote}
              onChange={(e) => setStatutCote(e.target.value)}
            >
              {STATUTS_COTE.map((s) => (
                <option key={s.valeur} value={s.valeur}>{s.libelle}</option>
              ))}
            </select>
          </>
        )}

        <p className="text-xs text-muted-foreground">
          La date de décision est posée par le serveur au moment où la question
          est tranchée — elle ne se saisit pas ici.
          {question.date_decision
            ? ` Tranchée le ${formatDate(question.date_decision)}.`
            : ''}
        </p>

        <Button
          size="sm"
          className="self-start"
          loading={tranchageEnCours}
          disabled={tranchageEnCours || !decision.trim()}
          onClick={trancherQuestion}
          data-ao-trancher-valider={question.id}
        >
          Trancher la question
        </Button>
      </div>

      {/* ── Impact prévu → delta RÉEL ────────────────────────────────────── */}
      {(impactPrevuTexte || delta != null) && (
        <div className="flex flex-col gap-1 border-t border-border pt-3 text-sm" data-question-delta={question.repere}>
          {impactPrevuTexte && (
            <p className="text-muted-foreground">
              Impact prévu&nbsp;: <span className="font-medium text-foreground">{impactPrevuTexte}</span>
            </p>
          )}
          {delta != null ? (
            <p className="font-medium tabular-nums" data-ao-compte={delta}>
              {`Delta réel : ${signe(delta)} module${Math.abs(delta) > 1 ? 's' : ''}`}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">Delta réel non disponible — recalculez après la décision.</p>
          )}
        </div>
      )}

      {/* ── Historique des recalculs ─────────────────────────────────────── */}
      {historique.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-border pt-3">
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Historique des recalculs
          </h4>
          <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
            {historique.map((h, i) => {
              const d = Number.isFinite(h.compte_apres_modules) && Number.isFinite(h.compte_avant_modules)
                ? h.compte_apres_modules - h.compte_avant_modules
                : null
              return (
                // Clé stable issue de la donnée (`date`) + index en garde
                // anti-collision (plusieurs recalculs pourraient partager une
                // même date) — jamais l'index seul.
                <li key={`${h.date}-${i}`}>
                  {`${formatDate(h.date)} — delta ${d != null ? signe(d) : '—'} module(s)`}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}

export default QuestionFiche
