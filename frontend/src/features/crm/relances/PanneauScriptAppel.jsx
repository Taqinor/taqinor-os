// CAD152 — T5 : LE SCRIPT SOUS LES YEUX PENDANT L'APPEL.
//
// Avant : « Appeler » était un `tel:` nu sur les trois écrans qui l'exposent
// (ligne de touche, rail de la fiche), et le seul chemin vers un script
// passait par la modale WhatsApp, dont le CTA journalise un « WhatsApp
// ouvert ». Ce panneau est le FRÈRE de `PanneauProposerVisite` (même ligne,
// même patron dépliable) : il charge le lead (la ligne n'a que l'étape),
// affiche le script et les questions encore à poser, écrit les réponses par
// le CHEMIN DE LA FICHE (`PATCH /crm/leads/<id>/` — le serveur y recalcule le
// score), et mène à l'issue avec le vocabulaire EXISTANT de la touche (CKP4).
//
// Trois règles tenues ici, et testées :
//   · aucun envoi, aucun POST « WhatsApp ouvert » — le panneau ne fait que
//     LIRE (`getPanneauAppel`, `getRelanceEtapeMessage`) et écrire la fiche ;
//   · aucune question formulée ici : le texte est le `help_text` servi par le
//     contrat (`panneau_appel.json`), l'ORDRE et les consignes viennent de
//     `appelGuidance.js` ;
//   · une erreur NOMME le champ, sous le champ (règle fondateur du 08/09).
import { useEffect, useState } from 'react'
import {
  ChevronDown, ChevronRight, Copy, PhoneCall, TriangleAlert,
} from 'lucide-react'
import { Badge, Button, Input } from '../../../ui'
import { toastInfo } from '../../../lib/toast'
import crmApi from '../../../api/crmApi'
import {
  guidanceAppel, texteQuestion, scriptTouche, normaliserSaisie,
  messageErreurServeur, FLUX_LOCATAIRE, MENTION_D7, BANDEAU_PROFIL_SUPPOSE,
  EXPLICATION_PROFIL_SUPPOSE, CONSIGNE_ISSUE, ISSUE_VERROUILLEE,
  AUCUNE_QUESTION,
} from './appelGuidance'

const PANNEAU_INDISPONIBLE = 'Questions indisponibles pour le moment — le '
  + 'script de la touche reste lisible.'

// Écritures de droite à gauche — seulement quand le texte EST dans cette
// langue (jamais pour une version française partie en repli, CAD64).
const LANGUES_RTL = ['darija', 'ar']

function Question({ entree, saisie, erreur, occupe, onChoix, onSaisie, onEnregistrer }) {
  const id = `panneau-appel-${entree.champ}`
  return (
    <div className="flex flex-col gap-1" data-testid={`question-appel-${entree.champ}`}>
      {Array.isArray(entree.choix) ? (
        <p className="text-sm text-foreground">{texteQuestion(entree)}</p>
      ) : (
        <label className="text-sm text-foreground" htmlFor={id}>{texteQuestion(entree)}</label>
      )}
      {Array.isArray(entree.choix) ? (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label={entree.libelle}>
          {entree.choix.map((c) => (
            <Button
              key={String(c.valeur)} type="button" size="sm" variant="outline"
              disabled={occupe} onClick={() => onChoix(c.valeur)}
            >
              {c.libelle}
            </Button>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5">
          <Input
            id={id} className="w-44" value={saisie} invalid={Boolean(erreur)}
            inputMode={entree.nature === 'nombre' ? 'decimal' : undefined}
            onChange={(e) => onSaisie(e.target.value)}
          />
          <Button type="button" size="sm" disabled={occupe} onClick={onEnregistrer}>
            Enregistrer
          </Button>
        </div>
      )}
      {entree.complements?.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Ensuite, selon la réponse : {entree.complements.map((c) => c.libelle).join(', ')}.
        </p>
      )}
      {erreur && (
        <p className="text-xs text-danger" role="alert" data-testid={`erreur-question-${entree.champ}`}>
          {erreur}
        </p>
      )}
    </div>
  )
}

export default function PanneauScriptAppel({
  leadId,
  // La touche de la LIGNE d'où le panneau s'ouvre (`relance_etape_v2`) :
  // son script est lu tel quel, et sa phase prime (la frise peut ouvrir une
  // touche à venir). Absente sur la fiche : la prochaine touche du lead.
  etape = null,
  // 'ligne' : bulle dépliable sur la touche ; 'fiche' : toujours déplié
  // (dans la modale d'appel du rail de la fiche).
  mode = 'ligne',
  ouvert = false,
  onBasculer,
  telephone = '',
  onComposer,
  onSaisirIssue,
  issueVerrouillee = false,
  onLeadEcrit,
}) {
  const actif = mode === 'fiche' || ouvert
  const [etat, setEtat] = useState({ chargement: false, panneau: null, erreur: '' })
  const [version, setVersion] = useState(0)
  const [script, setScript] = useState({ chargement: false, rendu: null, erreur: false })
  const [saisies, setSaisies] = useState({})
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState('')
  const [score, setScore] = useState(null)

  const etapeId = etape?.id ?? null
  // Le script de la LIGNE : une touche d'APPEL qui porte un gabarit (CAD78).
  const scriptLigne = Boolean(etape) && etape.canal === 'appel' && Boolean(etape.template_cle)

  // Le panneau du lead, lu à chaque ouverture et après chaque réponse
  // enregistrée (la question répondue disparaît : c'est le SERVEUR qui le
  // dit). Patron `queueMicrotask` : aucun setState synchrone dans l'effet.
  useEffect(() => {
    let active = true
    if (!actif || !leadId) return () => { active = false }
    if (typeof crmApi.getPanneauAppel !== 'function') {
      queueMicrotask(() => {
        if (active) setEtat({ chargement: false, panneau: null, erreur: PANNEAU_INDISPONIBLE })
      })
      return () => { active = false }
    }
    queueMicrotask(() => { if (active) setEtat((e) => ({ ...e, chargement: true, erreur: '' })) })
    crmApi.getPanneauAppel(leadId)
      .then((r) => { if (active) setEtat({ chargement: false, panneau: r?.data ?? null, erreur: '' }) })
      .catch(() => {
        if (active) setEtat((e) => ({ ...e, chargement: false, erreur: PANNEAU_INDISPONIBLE }))
      })
    return () => { active = false }
  }, [actif, leadId, version])

  // Le script de la touche : le MÊME rendu que le message (lecture pure,
  // jamais le POST qui journaliserait un « WhatsApp ouvert »).
  useEffect(() => {
    let active = true
    if (!actif || !scriptLigne) return () => { active = false }
    if (typeof crmApi.getRelanceEtapeMessage !== 'function') {
      queueMicrotask(() => { if (active) setScript({ chargement: false, rendu: null, erreur: true }) })
      return () => { active = false }
    }
    queueMicrotask(() => { if (active) setScript((s) => ({ ...s, chargement: true, erreur: false })) })
    crmApi.getRelanceEtapeMessage(etapeId)
      .then((r) => { if (active) setScript({ chargement: false, rendu: r?.data ?? null, erreur: false }) })
      .catch(() => { if (active) setScript({ chargement: false, rendu: null, erreur: true }) })
    return () => { active = false }
  }, [actif, scriptLigne, etapeId])

  const panneau = etat.panneau
  const toucheLigne = etape
    ? { id: etape.id, template_cle: etape.template_cle || '', canal: etape.canal }
    : undefined
  const g = panneau ? guidanceAppel(panneau, etape ? { touche: toucheLigne } : {}) : null
  const cleTouche = etape ? etape.template_cle : panneau?.touche?.template_cle
  const titreTouche = scriptTouche(cleTouche)?.titre ?? null

  // Le texte à lire : celui de la LIGNE (touche d'appel scriptée), sinon
  // l'accroche servie par le contrat pour la prochaine touche (fiche).
  const rendu = scriptLigne ? script.rendu : null
  const accroche = scriptLigne ? (rendu?.message ?? null) : (etape ? null : g?.accroche ?? null)
  const langueScript = scriptLigne ? rendu?.langue : panneau?.script?.langue
  const rtl = Boolean(accroche) && !(scriptLigne && rendu?.repli_langue)
    && LANGUES_RTL.includes(langueScript)
  const manquants = (scriptLigne ? rendu?.placeholders_manquants : panneau?.script?.placeholders_manquants) || []

  const copier = async () => {
    if (!accroche) return
    try {
      await navigator.clipboard.writeText(accroche)
      toastInfo('Texte copié.')
    } catch {
      // best-effort — presse-papier indisponible : le texte reste lisible.
    }
  }

  const ecrire = (entree, valeur) => {
    if (enCours || typeof crmApi.updateLead !== 'function') return
    setEnCours(entree.champ)
    setErreurs((e) => ({ ...e, [entree.champ]: '' }))
    Promise.resolve()
      .then(() => crmApi.updateLead(leadId, { [entree.champ]: valeur }))
      .then((r) => {
        const data = r?.data
        // Le score est recalculé par le serveur à chaque écriture de fiche
        // (`LeadViewSet.perform_update`) : on AFFICHE le sien, jamais un
        // calcul d'écran.
        if (data && data.score !== undefined && data.score !== null) setScore(data.score)
        setSaisies((s) => {
          const suite = { ...s }
          delete suite[entree.champ]
          return suite
        })
        toastInfo(`« ${entree.libelle} » enregistré sur la fiche.`)
        setVersion((v) => v + 1)
        onLeadEcrit?.(data)
      })
      .catch((err) => {
        const donnees = err?.response?.status === 400 ? err?.response?.data : null
        setErreurs((e) => ({
          ...e,
          [entree.champ]: messageErreurServeur(entree, donnees)
            || `« ${entree.libelle} » : la réponse n’a pas pu être enregistrée — réessayez.`,
        }))
      })
      .finally(() => setEnCours(''))
  }

  const enregistrerLibre = (entree) => {
    const { valeur, erreur } = normaliserSaisie(entree, saisies[entree.champ] ?? '')
    if (erreur) {
      setErreurs((e) => ({ ...e, [entree.champ]: erreur }))
      return
    }
    ecrire(entree, valeur)
  }

  const rendreQuestion = (entree) => (
    <Question
      key={entree.champ}
      entree={entree}
      saisie={saisies[entree.champ] ?? ''}
      erreur={erreurs[entree.champ] || ''}
      occupe={Boolean(enCours)}
      onChoix={(valeur) => ecrire(entree, valeur)}
      onSaisie={(valeur) => {
        setSaisies((s) => ({ ...s, [entree.champ]: valeur }))
        setErreurs((e) => ({ ...e, [entree.champ]: '' }))
      }}
      onEnregistrer={() => enregistrerLibre(entree)}
    />
  )

  // Q5 — la présence en journée remonte EN TÊTE : la liste ordonnée ne la
  // répète pas (l'ordre des autres étapes reste celui de CAD162).
  const questions = g?.livre
    ? g.questions.filter((q) => !g.enTete || q.champ !== g.enTete.champ)
    : []
  const locataire = g?.livre && (
    questions.some((q) => q.champ === 'ownership')
    || panneau?.prefill?.ownership === 'locataire')

  const contenu = (
    <div className="mt-2 flex flex-col gap-2 text-xs text-muted-foreground">
      {g?.livre && g.profilSuppose && g.enTete && (
        <div
          className="flex flex-col gap-1.5 rounded-md border border-warning/40 bg-warning/10 p-2"
          role="status" data-testid="bandeau-profil-suppose"
        >
          <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <TriangleAlert className="size-3.5 shrink-0 text-warning" aria-hidden="true" />
            {BANDEAU_PROFIL_SUPPOSE}
          </p>
          <p>{EXPLICATION_PROFIL_SUPPOSE}</p>
          {rendreQuestion(g.enTete)}
        </div>
      )}
      {g?.avertissement && (
        <p className="text-xs text-warning" data-testid="segment-a-confirmer">{g.avertissement}</p>
      )}
      {titreTouche && <Badge tone="neutral" className="self-start">{titreTouche}</Badge>}
      {scriptLigne && (
        <div className="flex flex-col gap-1.5" data-testid="texte-touche">
          {script.chargement && <p>Chargement du script…</p>}
          {script.erreur && <p>Script indisponible pour le moment.</p>}
          {rendu && (
            <p
              className={`whitespace-pre-wrap rounded-md bg-muted/40 p-2 text-sm text-foreground${rtl ? ' text-right' : ''}`}
              dir={rtl ? 'rtl' : 'auto'} lang={rtl ? 'ar' : 'fr'}
              data-testid="texte-touche-contenu"
            >
              {rendu.message || '—'}
            </p>
          )}
        </div>
      )}
      {!scriptLigne && accroche && (
        <p
          className={`whitespace-pre-wrap rounded-md bg-muted/40 p-2 text-sm text-foreground${rtl ? ' text-right' : ''}`}
          dir={rtl ? 'rtl' : 'auto'} lang={rtl ? 'ar' : 'fr'}
          data-testid="script-accroche"
        >
          {accroche}
        </p>
      )}
      {accroche && (
        <div className="flex justify-end">
          <Button type="button" size="sm" variant="outline" onClick={copier}>
            <Copy className="size-3.5" /> Copier
          </Button>
        </div>
      )}
      {manquants.length > 0 && (
        <p className="text-xs text-warning">
          Informations manquantes ({manquants.join(', ')}) — la phrase correspondante a été omise du script.
        </p>
      )}
      {etat.chargement && !panneau && <p>Chargement des questions…</p>}
      {etat.erreur && <p data-testid="panneau-indisponible">{etat.erreur}</p>}
      {g && !g.livre && (
        <p className="text-sm text-foreground" role="status" data-testid="segment-non-livre">{g.message}</p>
      )}
      {g?.livre && (
        <div className="flex flex-col gap-2" data-testid="questions-appel">
          <p className="font-medium text-foreground">
            {g.phase === 'rappel' ? 'Questions du rappel' : 'Questions de l’appel'}
          </p>
          {questions.length > 0
            ? questions.map(rendreQuestion)
            : !g.enTete && <p data-testid="aucune-question">{AUCUNE_QUESTION}</p>}
        </div>
      )}
      {locataire && (
        <div className="rounded-md border border-border p-2" data-testid="flux-locataire">
          <p className="font-medium text-foreground">Si le client est locataire</p>
          <p>{FLUX_LOCATAIRE.consigne}</p>
          <p>{FLUX_LOCATAIRE.sinon}</p>
        </div>
      )}
      {g?.livre && (
        <p data-testid="mention-d7">{MENTION_D7}</p>
      )}
      {score !== null && (
        <p className="font-medium text-foreground" data-testid="score-recalcule">
          Score recalculé : {score}/100
        </p>
      )}
      {g?.livre && (
        <details data-testid="objections-appel">
          <summary className="cursor-pointer font-medium text-foreground">
            Si le client objecte
          </summary>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {g.objections.map((o) => (
              <div key={o.cle} data-testid={`objection-${o.cle}`}>
                <p className="font-medium text-foreground">{o.titre}</p>
                <p>{o.quand}</p>
                <p className="italic text-foreground">« {o.reponse} »</p>
                <p>{o.jamais}</p>
                {o.ensuite && <p>{o.ensuite}</p>}
              </div>
            ))}
          </div>
        </details>
      )}
      {g?.livre && (
        <details data-testid="interdits-appel">
          <summary className="cursor-pointer font-medium text-foreground">
            Ce qui ne se dit jamais au téléphone
          </summary>
          <ul className="ml-4 mt-1.5 list-disc">
            {g.interdits.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </details>
      )}
      {(onComposer || onSaisirIssue) && (
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap justify-end gap-1.5">
            {onSaisirIssue && (
              <Button
                type="button" size="sm" variant="outline"
                disabled={issueVerrouillee} onClick={onSaisirIssue}
              >
                Saisir l’issue de l’appel
              </Button>
            )}
            {onComposer && telephone && (
              <Button type="button" size="sm" onClick={onComposer}>
                <PhoneCall className="size-3.5" /> Composer le numéro
              </Button>
            )}
          </div>
          {onSaisirIssue && (
            <p className="text-right" data-testid="consigne-issue">
              {issueVerrouillee ? ISSUE_VERROUILLEE : CONSIGNE_ISSUE}
            </p>
          )}
        </div>
      )}
    </div>
  )

  if (mode === 'fiche') {
    return <div data-testid="panneau-script-appel">{contenu}</div>
  }
  return (
    <div className="mt-1.5 rounded-md border border-dashed border-border p-2" data-testid="panneau-script-appel">
      <button
        type="button"
        className="flex w-full items-center gap-1.5 text-left text-xs font-medium text-foreground"
        aria-expanded={ouvert}
        onClick={onBasculer}
      >
        {ouvert ? <ChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
          : <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" />}
        <PhoneCall className="size-3.5 shrink-0" aria-hidden="true" />
        <span>Script d’appel</span>
      </button>
      {ouvert && contenu}
    </div>
  )
}
