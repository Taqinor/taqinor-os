import { useEffect, useState } from 'react'
import { Badge, Button, Input, Label, Textarea } from '../../../ui'
import { formatDate } from '../../../lib/format'

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

function versEntier(brut) {
  if (brut === '' || brut == null) return null
  const n = Number.parseInt(brut, 10)
  return Number.isFinite(n) ? n : null
}

function signe(v) {
  if (!Number.isFinite(v)) return null
  return v > 0 ? `+${v}` : String(v)
}

/** Delta RÉEL = soustraction d'affichage entre deux comptes serveur. */
export function deltaReel(question) {
  const { compte_avant_modules: avant, compte_apres_modules: apres } = question || {}
  if (!Number.isFinite(avant) || !Number.isFinite(apres)) return null
  return apres - avant
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
  onRecalculer,
  recalculEnCours = false,
}) {
  const [texte, setTexte] = useState(question?.texte ?? '')
  const [impactMin, setImpactMin] = useState(question?.impact_min_modules ?? '')
  const [impactMax, setImpactMax] = useState(question?.impact_max_modules ?? '')
  const [reponse, setReponse] = useState(question?.reponse ?? '')
  const [decision, setDecision] = useState(question?.decision ?? '')
  const [dateDecision, setDateDecision] = useState(question?.date_decision ?? '')

  useEffect(() => {
    setTexte(question?.texte ?? '')
    setImpactMin(question?.impact_min_modules ?? '')
    setImpactMax(question?.impact_max_modules ?? '')
    setReponse(question?.reponse ?? '')
    setDecision(question?.decision ?? '')
    setDateDecision(question?.date_decision ?? '')
  }, [question])

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

  const enregistrerReponse = () => {
    onChange?.({ reponse, decision, date_decision: dateDecision || null })
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
        <Label htmlFor={`ao-question-decision-${question.id}`}>Décision retenue</Label>
        <Textarea
          id={`ao-question-decision-${question.id}`}
          rows={2}
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
        />
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor={`ao-question-date-${question.id}`}>Date de la décision</Label>
            <Input
              id={`ao-question-date-${question.id}`}
              type="date"
              value={dateDecision ?? ''}
              onChange={(e) => setDateDecision(e.target.value)}
            />
          </div>
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
                // eslint-disable-next-line react/no-array-index-key -- historique en lecture seule, append-only
                <li key={i}>
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
