/* eslint-disable react-refresh/only-export-components --
   `CHAMPS`, `LIBELLES_STATUT`, `TONS_STATUT`, `erreursParChamp` et
   `corpsDeSaisie` sont des constantes et des fonctions PURES que le test
   unitaire confronte directement à l'échantillon committé du contrat
   (`calepinage_raccordement.json`, CALX205). Les sortir dans un `.js` voisin
   séparerait la table de son unique lecteur pour satisfaire une règle de
   fast-refresh qui ne s'applique pas à une constante — même dérogation que
   `EquipementsElectriques.jsx`/`CheminementCables.jsx` du même dossier. */
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { PlugZap } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Badge, Button, Card, Input, Label, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'

/* ============================================================================
   CALX244 — L'ONGLET « RACCORDEMENT RÉSEAU » DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT QUI JUSTIFIE CE FICHIER. Aucun écran du module ne demandait la
   puissance souscrite, le régime du branchement, la limite d'élévation de
   tension ni le cos φ imposé par le contrat de raccordement : les trois
   calculs existaient côté serveur (CALX241-243) et personne ne pouvait ni
   les nourrir ni les lire. Parité OpenSolar : les réglages de site se
   saisissent dans les détails du site et redescendent dans tous les
   contrôles.

   LA SOURCE EST `GET`/`POST calepinages/<pk>/raccordement/` (CALX205,
   contrat `calepinage_raccordement.json`), ajoutée EN FIN de
   `calepinageApi.js` (`// CALX244`). Le `POST` REND le raccordement
   recalculé : cet écran n'enchaîne donc aucun second appel.

   ZÉRO CHIFFRE INVENTÉ (D-CALX 7), DANS LES DEUX SENS. Les quatre grandeurs
   du bloc `calcul` sont recopiées telles quelles ; `null` n'est jamais rendu
   `0` (`formatNumber`/`formatPercent` rendent « — »). Les cinq verdicts sont
   lus PAR LEUR CODE, jamais par leur position — et un verdict `omis` affiche
   le MOTIF du serveur, jamais une pastille verte et jamais un chiffre qui
   ferait croire à un contrôle réussi.

   UNE LIMITE EST UNE SAISIE QUI PORTE SA SOURCE. `limite_elevation_pct` et
   `cos_phi_impose` exigent leur provenance : c'est le SERVEUR qui refuse (il
   est la seule autorité), et l'écran pose son message SOUS le champ qu'il
   NOMME, avec un bandeau qui y renvoie d'un clic (règle fondateur du
   08/09/2026 — jamais un « non enregistré » générique).
   ========================================================================== */

/** Le préfixe que le serveur met devant le champ fautif d'un refus. */
export const PREFIXE_CHAMP = 'raccordement.'

/** Les sept champs de la saisie, dans l'ordre où l'écran les demande. */
export const CHAMPS = [
  {
    cle: 'puissance_souscrite_kva',
    libelle: 'Puissance souscrite',
    unite: 'kVA',
    aide: 'Celle du contrat de raccordement. Laissez vide tant qu’elle n’est pas connue — rien n’est supposé.',
  },
  {
    cle: 'phases',
    libelle: 'Phases du branchement',
    unite: '1 ou 3',
    aide: 'Monophasé (1) ou triphasé (3). Aucun régime n’est deviné.',
  },
  {
    cle: 'tension_nominale_v',
    libelle: 'Tension nominale',
    unite: 'V',
    aide: 'Celle du compteur. Ni 230 V ni 400 V ne sont supposés.',
  },
  {
    cle: 'limite_elevation_pct',
    libelle: 'Limite d’élévation de tension',
    unite: '%',
    aide: 'Aucun barème marocain n’est présent dans ce dépôt : sans limite saisie, l’élévation est publiée mais aucun verdict n’est prononcé.',
  },
  {
    cle: 'source_limite',
    libelle: 'Source de la limite',
    unite: '',
    texte: true,
    aide: 'Le texte réglementaire ou le contrat qui fixe la limite. Obligatoire dès qu’une limite est saisie.',
  },
  {
    cle: 'cos_phi_impose',
    libelle: 'Cos φ imposé',
    unite: '',
    aide: 'Celui que le contrat de raccordement de CE site impose — à ne pas confondre avec le réglage société « cos φ retenu à défaut de mesure ».',
  },
  {
    cle: 'source_cos_phi',
    libelle: 'Source du cos φ',
    unite: '',
    texte: true,
    aide: 'Le contrat de raccordement ou la prescription du gestionnaire de réseau. Obligatoire dès qu’un cos φ est saisi.',
  },
]

/** Le libellé FRANÇAIS de chaque statut publié par le contrat. */
export const LIBELLES_STATUT = {
  ok: 'Conforme',
  alerte: 'À surveiller',
  bloquant: 'Bloquant',
  omis: 'Non vérifié',
}

/** Le ton du badge — `omis` est NEUTRE : ce n'est pas un contrôle réussi. */
export const TONS_STATUT = {
  ok: 'success',
  alerte: 'warning',
  bloquant: 'danger',
  omis: 'neutral',
}

/** Le libellé d'un statut — un statut inconnu est NOMMÉ, jamais tu. */
export function libelleStatut(statut) {
  return LIBELLES_STATUT[statut] ?? `statut « ${statut} »`
}

/**
 * Les erreurs du serveur, rangées PAR CHAMP : `{ 'raccordement.source_limite':
 * '…' }` devient `{ source_limite: '…' }`. Une clé sans préfixe (refus
 * générique) est conservée telle quelle — elle s'affiche alors en bandeau
 * seul, jamais avalée.
 */
export function erreursParChamp(donnees) {
  const par = {}
  if (!donnees || typeof donnees !== 'object') return par
  for (const [cle, message] of Object.entries(donnees)) {
    const champ = cle.startsWith(PREFIXE_CHAMP)
      ? cle.slice(PREFIXE_CHAMP.length)
      : cle
    par[champ] = Array.isArray(message) ? message.join(' ') : String(message)
  }
  return par
}

/**
 * Le corps POSTÉ : les SEPT champs, un champ vidé valant `null` (« pas
 * saisi »), jamais `0` ni une chaîne vide qui se lirait comme une valeur.
 */
export function corpsDeSaisie(saisie) {
  const corps = {}
  for (const { cle } of CHAMPS) {
    const valeur = saisie?.[cle]
    corps[cle] = valeur === '' || valeur === undefined ? null : valeur
  }
  return corps
}

/** L'identifiant DOM d'un champ — le bandeau s'en sert pour y renvoyer. */
function idChamp(cle) {
  return `calx244-champ-${cle}`
}

function valeurAffichee(saisie, cle) {
  const valeur = saisie?.[cle]
  return valeur === null || valeur === undefined ? '' : String(valeur)
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

export default function Raccordement({ calepinageId } = {}) {
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

        <form className="flex flex-col gap-3" onSubmit={enregistrer} data-testid="calx244-formulaire">
          <div className="grid gap-3 sm:grid-cols-2">
            {CHAMPS.map(({ cle, libelle, unite, texte, aide }) => (
              <div key={cle} className="flex flex-col gap-1">
                <Label htmlFor={idChamp(cle)}>
                  {unite ? `${libelle} (${unite})` : libelle}
                </Label>
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
            <Button type="submit" disabled={enregistrement} data-testid="calx244-enregistrer">
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
              {formatPercent(calcul.marge_pct, { decimals: 2 })}
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
