import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { PlugZap } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Badge, Button, Card, Input, Label, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { CHAMPS, TONS_STATUT, corpsDeSaisie, erreursParChamp, libelleStatut, saisieVide } from './Raccordement.helpers'

/* ACAL44 — le motif d'un bouton d'écriture en lecture seule (devis lié figé). */
const MOTIF_LECTURE_SEULE = 'Conception figée : révisez le devis (nouvelle version) pour la modifier.'

/** L'identifiant DOM d'un champ — le bandeau s'en sert pour y renvoyer. */
function idChamp(cle) {
  return `calx244-champ-${cle}`
}

function valeurAffichee(saisie, cle) {
  const valeur = saisie?.[cle]
  return valeur === null || valeur === undefined ? '' : String(valeur)
}

/**
 * ACAL158 — « valeurs du lead » : la proposition du serveur (`proposition_lead`), avec sa source
 * visible. Le bouton REMPLIT le formulaire sans rien enregistrer ; absent dès qu'une saisie
 * existe (la proposition reste alors lisible, jamais appliquée).
 */
function PropositionLead({ proposition, peutReprendre, onReprendre, lectureSeule = false }) {
  if (!proposition) return null
  return (
    <div
      className="flex flex-col gap-2 border border-border/60 px-3 py-2 text-sm"
      data-testid="acal158-proposition"
    >
      <p>
        {'Valeurs du lead : '}
        <strong data-testid="acal158-valeurs">
          {[
            proposition.puissance_souscrite_kva != null
              ? `${formatNumber(proposition.puissance_souscrite_kva, { decimals: 1 })} kVA` : null,
            proposition.phases != null ? `${proposition.phases} phase${proposition.phases > 1 ? 's' : ''}` : null,
          ].filter(Boolean).join(' · ') || '—'}
        </strong>
        {proposition.source
          ? <span className="text-xs text-lune-faint" data-testid="acal158-source">{` — source : ${proposition.source}`}</span>
          : null}
      </p>
      {peutReprendre
        ? (
          <div>
            <Button
              type="button"
              onClick={onReprendre}
              disabled={lectureSeule}
              title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined}
              data-testid="acal158-reprendre"
            >
              Reprendre les valeurs du lead
            </Button>
            <span className="ml-2 text-xs text-lune-faint">Rien n’est enregistré avant « Enregistrer ».</span>
          </div>
        )
        : <p className="text-xs text-lune-faint">Une saisie existe déjà : la proposition n’est pas appliquée.</p>}
    </div>
  )
}

/** Le bandeau qui NOMME les champs fautifs et y renvoie d'un clic. */
function BandeauRefus({ erreurs }) {
  const cles = Object.keys(erreurs)
  if (cles.length === 0) return null
  const nommes = cles.map((cle) => ({
    cle,
    libelle: CHAMPS.find((champ) => champ.cle === cle)?.libelle ?? cle,
  }))
  return (
    <p
      role="alert"
      data-testid="calx244-bandeau"
      className="border border-destructive/50 bg-destructive/5 px-3 py-2 text-sm text-destructive"
    >
      {'Raccordement non enregistré — à corriger : '}
      {nommes.map(({ cle, libelle }, index) => (
        <span key={cle}>
          {index > 0 ? ', ' : ''}
          <button
            type="button"
            className="underline"
            data-testid={`calx244-aller-${cle}`}
            onClick={() => document.getElementById(idChamp(cle))?.focus()}
          >
            {libelle}
          </button>
        </span>
      ))}
    </p>
  )
}

/** Un verdict : son intitulé, son statut, et le MOTIF du serveur mot pour mot. */
function Verdict({ verdict }) {
  return (
    <li
      className="flex flex-col gap-1 border-b border-border/60 pb-2 last:border-0"
      data-testid={`calx244-verdict-${verdict.code}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{verdict.libelle}</span>
        <Badge
          tone={TONS_STATUT[verdict.statut] ?? 'neutral'}
          data-testid={`calx244-statut-${verdict.code}`}
        >
          {libelleStatut(verdict.statut)}
        </Badge>
      </div>
      <p
        className="text-sm text-muted-foreground"
        data-testid={`calx244-detail-${verdict.code}`}
      >
        {verdict.detail}
      </p>
      {verdict.source
        ? (
          <p className="text-xs text-lune-faint" data-testid={`calx244-source-${verdict.code}`}>
            {verdict.source}
          </p>
        )
        : null}
    </li>
  )
}

export default function Raccordement({ calepinageId, lectureSeule = false } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.raccordement(id), id,
    { select: (r) => r.data, errorMessage: 'Raccordement indisponible.' },
  )

  /* `brouillon` reste `null` tant que rien n'est tapé : la saisie affichée
     est alors celle du SERVEUR, sans aucun état recopié dans un effet. */
  const [brouillon, setBrouillon] = useState(null)
  const [blocPoste, setBlocPoste] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [enregistrement, setEnregistrement] = useState(false)

  const bloc = blocPoste ?? data
  const saisie = brouillon ?? bloc?.saisie ?? {}
  const calcul = bloc?.calcul ?? {}
  const verdicts = Array.isArray(bloc?.verdicts) ? bloc.verdicts : []

  const modifier = (cle, valeur) => {
    setBrouillon({ ...saisie, [cle]: valeur })
  }

  // ACAL158 — reprendre = remplir le brouillon (puissance, phases), JAMAIS poster.
  const proposition = bloc?.proposition_lead ?? null
  const reprendreLead = () => {
    if (!proposition) return
    setBrouillon({
      ...saisie,
      puissance_souscrite_kva: proposition.puissance_souscrite_kva ?? saisie.puissance_souscrite_kva ?? null,
      phases: proposition.phases ?? saisie.phases ?? null,
    })
  }

  const enregistrer = (evenement) => {
    evenement.preventDefault()
    setEnregistrement(true)
    setErreurs({})
    calepinageApi.calepinages
      .enregistrerRaccordement(id, corpsDeSaisie(saisie))
      .then((reponse) => {
        setBlocPoste(reponse?.data ?? null)
        setBrouillon(null)
      })
      .catch((err) => {
        const donnees = err?.response?.data
        const parChamp = erreursParChamp(donnees)
        setErreurs(Object.keys(parChamp).length > 0
          ? parChamp
          : { raccordement: 'Raccordement non enregistré : le serveur n’a pas accepté la saisie.' })
      })
      .finally(() => setEnregistrement(false))
  }

  if (loading) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="raccordement" />
        <Spinner />
      </>
    )
  }
  if (error) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="raccordement" />
        <p className="text-sm text-destructive" data-testid="calx244-erreur">{error}</p>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={id} cle="raccordement" />
      <Card className="flex flex-col gap-4 p-4" data-testid="calx244-panneau">
        <header className="flex items-center gap-2">
          <PlugZap size={16} aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <h2 className="text-base font-semibold">Raccordement réseau</h2>
            <p className="text-sm text-muted-foreground">
              Ce que le contrat de raccordement impose, et ce que le moteur en
              tire — recopié du serveur, aucun calcul refait côté écran.
            </p>
          </div>
        </header>

        <BandeauRefus erreurs={erreurs} />

        <PropositionLead
          proposition={proposition}
          peutReprendre={saisieVide(bloc?.saisie)}
          onReprendre={reprendreLead}
          lectureSeule={lectureSeule}
        />

        <p className="text-xs text-lune-faint" data-testid="acal156-note-simulation">
          {'Le cos φ imposé et le plafond d’injection enregistrés ici sont lus par la simulation '
            + '(autoconsommation et batterie) : après un changement, relancez-la — le panneau '
            + 'Production signale un résultat périmé.'}
        </p>

        <form className="flex flex-col gap-3" onSubmit={enregistrer} data-testid="calx244-formulaire">
          <div className="grid gap-3 sm:grid-cols-2">
            {CHAMPS.map(({ cle, libelle, unite, texte, aide, simulation }) => (
              <div key={cle} className="flex flex-col gap-1">
                <Label htmlFor={idChamp(cle)}>
                  {unite ? `${libelle} (${unite})` : libelle}
                </Label>
                {/* ACAL156 — une valeur ENREGISTRÉE de ces deux champs alimente la simulation :
                    l'écran le dit, plutôt que de laisser croire à une saisie décorative. */}
                {simulation && valeurAffichee(bloc?.saisie, cle) !== ''
                  ? (
                    <Badge tone="info" data-testid={`acal156-simulation-${cle}`}>
                      utilisé par la simulation
                    </Badge>
                  )
                  : null}
                <Input
                  id={idChamp(cle)}
                  name={cle}
                  type={texte ? 'text' : 'number'}
                  step={texte ? undefined : 'any'}
                  invalid={Boolean(erreurs[cle])}
                  aria-describedby={erreurs[cle] ? `${idChamp(cle)}-erreur` : undefined}
                  value={valeurAffichee(saisie, cle)}
                  onChange={(e) => modifier(cle, e.target.value)}
                />
                {erreurs[cle]
                  ? (
                    <p
                      id={`${idChamp(cle)}-erreur`}
                      className="text-xs text-destructive"
                      data-testid={`calx244-erreur-${cle}`}
                    >
                      {erreurs[cle]}
                    </p>
                  )
                  : <p className="text-xs text-lune-faint">{aide}</p>}
              </div>
            ))}
          </div>
          <div>
            <Button
              type="submit"
              disabled={enregistrement || lectureSeule}
              title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined}
              data-testid="calx244-enregistrer"
            >
              {enregistrement ? 'Enregistrement…' : 'Enregistrer le raccordement'}
            </Button>
          </div>
        </form>

        <section className="flex flex-wrap gap-4 text-sm" data-testid="calx244-calcul">
          <span>
            {'Élévation de tension : '}
            <strong data-testid="calx244-elevation">
              {formatPercent(calcul.elevation_pct, { decimals: 2 })}
            </strong>
          </span>
          <span>
            {'Marge à la limite : '}
            <strong data-testid="calx244-marge">
              {formatPercent(calcul.ecart_limite_pct, { decimals: 2 })}
            </strong>
          </span>
          <span>
            {'Puissance injectée : '}
            <strong data-testid="calx244-injectee">
              {calcul.puissance_injectee_kva === null || calcul.puissance_injectee_kva === undefined
                ? '—'
                : `${formatNumber(calcul.puissance_injectee_kva, { decimals: 1 })} kVA`}
            </strong>
          </span>
          <span>
            {'Déséquilibre entre phases : '}
            <strong data-testid="calx244-desequilibre">
              {formatPercent(calcul.desequilibre_pct, { decimals: 2 })}
            </strong>
          </span>
        </section>

        <ul className="flex flex-col gap-2" data-testid="calx244-verdicts">
          {verdicts.map((verdict) => (
            <Verdict key={verdict.code} verdict={verdict} />
          ))}
        </ul>
      </Card>
    </>
  )
}
