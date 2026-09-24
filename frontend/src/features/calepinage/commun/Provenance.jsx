/* eslint-disable react-refresh/only-export-components --
   Ce fichier porte À LA FOIS le composant réutilisable de provenance (la
   pastille + son infobulle, importée par les autres écrans du module) et
   l'écran qui le rend ATTEIGNABLE. Les deux constantes exportées (`ORIGINES`,
   `estOrigineDeclaree`) sont la table des cinq origines admises : les sortir
   dans un `.js` voisin séparerait la table de son unique lecteur pour
   satisfaire une règle de fast-refresh qui ne s'applique pas à une constante —
   même dérogation que `module.config.jsx` et `equipements/FichesIncompletes.jsx`
   du même module. */
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber } from '../../../lib/format'
import { Card, Spinner } from '../../../ui'

/* ============================================================================
   CAL165 — LA SOURCE DE CHAQUE PARAMÈTRE NORMATIF, AFFICHÉE AVEC LUI.
   ----------------------------------------------------------------------------
   LA RÈGLE QUI COMMANDE CE FICHIER (D5, « checked-facts-only ») : un chiffre
   montré à un client est RÉEL, DÉRIVÉ TRAÇABLE, ou OMIS. Les écrans du module
   affichent aujourd'hui des résultats d'ingénierie (coefficients de norme
   électrique, paramètres de lestage, dégagements) sans dire D'OÙ ILS VIENNENT :
   rien ne distingue une valeur lue sur une fiche technique d'une valeur que
   quelqu'un a tapée un jour dans l'atelier. Un lecteur ne peut donc pas savoir
   ce qu'il a le droit d'opposer à un tiers.

   CE QUE LE COMPOSANT GARANTIT, ET QUI EST TESTÉ :
   un chiffre SANS provenance déclarée n'est PAS RENDU. `ValeurSourcee` refuse :
   elle écrit « — » et la pastille « non sourcée », jamais le nombre. C'est le
   seul moyen mécanique d'empêcher qu'une valeur d'atelier se lise comme une
   norme — une simple convention d'écriture serait oubliée au premier écran
   suivant.

   LES CINQ ORIGINES sont fermées (`ORIGINES`). Toute autre chaîne — y compris
   une chaîne vide, `null`, ou une origine inventée — vaut « non déclarée » et
   déclenche le refus ci-dessus. La référence textuelle, quand le serveur en
   publie une, est citée dans l'infobulle ET sous la valeur : c'est elle qui
   rend la valeur opposable.

   AUCUN CALCUL, AUCUNE DÉDUCTION D'ORIGINE. L'écran ne DEVINE jamais une
   provenance à partir d'un nom de champ : il lit ce que le serveur publie
   (`GET /calepinage/parametres/`, contrat `parametres_calepinage.json`), où
   les paramètres de lestage (CAL163/CAL164) portent `{valeur, source}` et les
   coefficients de norme (CAL130) `{valeur, reference}`. Ces paramètres sont des
   RÉGLAGES SOCIÉTÉ : leur origine est `societe`, ce que le contrat dit en
   toutes lettres (« saisie par la société »). Une section vide reste vide —
   aucune valeur par défaut n'est fabriquée ici.
   ========================================================================== */

/** Les CINQ origines admises. Toute autre valeur = provenance non déclarée. */
export const ORIGINES = {
  fiche: {
    libelle: 'fiche technique',
    explication: 'valeur lue sur la fiche technique du produit retenu',
  },
  pvgis: {
    libelle: 'PVGIS',
    explication: 'donnée renvoyée par PVGIS pour ce site',
  },
  societe: {
    libelle: 'réglage société',
    explication: 'paramètre enregistré dans les réglages de la société',
  },
  saisie: {
    libelle: 'saisie',
    explication: 'valeur saisie pour ce calepinage',
  },
  hypothese: {
    libelle: 'hypothèse',
    explication: 'hypothèse assumée, à confirmer avant de l’opposer à un tiers',
  },
}

/** Vrai si `origine` est l'une des cinq origines fermées ci-dessus. */
export function estOrigineDeclaree(origine) {
  return typeof origine === 'string'
    && Object.prototype.hasOwnProperty.call(ORIGINES, origine)
}

/**
 * La PASTILLE de provenance. Sans origine déclarée, elle dit « non sourcée »
 * — jamais rien, jamais un libellé rassurant.
 */
export function Provenance({ origine, reference }) {
  const declaree = estOrigineDeclaree(origine)
  const meta = declaree ? ORIGINES[origine] : null
  const infobulle = declaree
    ? [meta.explication, reference || null].filter(Boolean).join(' — ')
    : 'Aucune provenance déclarée : cette valeur n’est pas une norme et n’est pas affichée.'
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] ${
        declaree ? 'bg-muted text-muted-foreground' : 'bg-destructive/10 text-destructive'
      }`}
      data-testid="cal165-pastille"
      data-origine={declaree ? origine : 'non-declaree'}
      title={infobulle}
    >
      {declaree ? meta.libelle : 'non sourcée'}
    </span>
  )
}

/**
 * Un chiffre d'ingénierie ET sa provenance, indissociables.
 *
 * Provenance non déclarée ⇒ le chiffre N'EST PAS RENDU (« — »). C'est le
 * refus exigé par CAL165, et il est vérifié par le test jumeau.
 */
export function ValeurSourcee({
  valeur, unite, origine, reference, decimals, testId,
}) {
  const declaree = estOrigineDeclaree(origine)
  const nombre = typeof valeur === 'number' && Number.isFinite(valeur)
  const rendable = declaree && nombre
  return (
    <span className="inline-flex items-center gap-2" data-testid={testId}>
      <span className="tabular-nums" data-testid="cal165-valeur">
        {rendable
          ? `${formatNumber(valeur, decimals === undefined ? {} : { decimals })}${unite ? ` ${unite}` : ''}`
          : '—'}
      </span>
      <Provenance origine={origine} reference={reference} />
      {declaree && reference
        ? (
          <span className="text-[11px] text-muted-foreground" data-testid="cal165-reference">
            {reference}
          </span>
        )
        : null}
    </span>
  )
}

/* ── L'ÉCRAN ───────────────────────────────────────────────────────────────
   Il liste les paramètres normatifs de la société, chacun avec sa provenance.
   Il n'en calcule aucun et n'en invente aucun : ce qui n'est pas servi n'est
   pas affiché. */

function Section({ titre, vide, children, testId }) {
  return (
    <section className="flex flex-col gap-2" data-testid={testId}>
      <h3 className="text-sm font-semibold">{titre}</h3>
      {vide
        ? <p className="text-sm text-muted-foreground">{vide}</p>
        : <dl className="flex flex-col gap-1 text-sm">{children}</dl>}
    </section>
  )
}

function Ligne({ libelle, children }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 py-1">
      <dt className="text-muted-foreground">{libelle}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** Intitulé lisible d'un code de paramètre servi par le serveur. */
function libelleDeCode(code) {
  return String(code).replace(/_/g, ' ')
}

// CALX340 — `zones` et `zone_par_defaut` sont la STRUCTURE de la section
// `lestage` (zones de vent et de neige par site), pas des paramètres : les
// rendre comme un paramètre afficherait une pastille « non sourcée » sur une
// clé qui n'est pas un chiffre. Chaque paramètre DE ZONE est rendu sous le
// nom de sa zone, avec SA propre source.
const CLES_STRUCTURE_LESTAGE = ['zones', 'zone_par_defaut']

export default function SourcesNormatives() {
  const { data, loading, error } = useResource(
    () => calepinageApi.parametres.get(), null,
    { select: (r) => r.data, errorMessage: 'Paramètres normatifs indisponibles.' },
  )

  if (loading) return <Spinner />
  if (error) {
    return <p className="text-sm text-destructive" data-testid="cal165-erreur">{error}</p>
  }

  const norme = data?.norme_electrique || {}
  const coefficients = norme.coefficients || {}
  const lestage = data?.lestage || {}
  const codesLestage = Object.keys(lestage)
    .filter((c) => !CLES_STRUCTURE_LESTAGE.includes(c))
  const zonesLestage = Array.isArray(lestage.zones) ? lestage.zones : []
  const degagements = data?.degagements || {}
  // Le dégagement porte UNE source pour toute la section : c'est la forme du
  // contrat, elle n'est pas réinterprétée ici.
  const sourceDegagements = degagements.source
  const codesDegagements = Object.keys(degagements).filter((c) => c !== 'source')

  return (
    <Card className="flex flex-col gap-5 p-4" data-testid="cal165-ecran">
      <header className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Sources des paramètres normatifs</h2>
        <p className="text-sm text-muted-foreground">
          Un paramètre sans provenance déclarée est marqué « non sourcée » et sa
          valeur n’est pas affichée : ce n’est pas une norme.
        </p>
      </header>

      <Section
        titre="Norme électrique"
        testId="cal165-norme"
        vide={Object.keys(coefficients).length === 0
          ? 'Aucune norme électrique choisie : les coefficients sont omis.'
          : null}
      >
        {norme.reference
          ? <Ligne libelle="Référence de la norme">{norme.reference}</Ligne>
          : null}
        {Object.entries(coefficients).map(([code, coefficient]) => (
          <Ligne key={code} libelle={libelleDeCode(code)}>
            <ValeurSourcee
              valeur={coefficient?.valeur}
              // La référence du coefficient EST la provenance publiée par
              // CAL130 ; sans elle, le coefficient reste non sourcé.
              origine={coefficient?.reference ? 'societe' : undefined}
              reference={coefficient?.reference}
              decimals={2}
            />
          </Ligne>
        ))}
      </Section>

      <Section
        titre="Lestage"
        testId="cal165-lestage"
        vide={codesLestage.length === 0 && zonesLestage.length === 0
          ? 'Aucun paramètre de lestage enregistré : la feuille de lestage est omise.'
          : null}
      >
        {codesLestage.map((code) => {
          const parametre = lestage[code]
          return (
            <Ligne key={code} libelle={libelleDeCode(code)}>
              <ValeurSourcee
                valeur={parametre?.valeur}
                origine={parametre?.source ? 'societe' : undefined}
                reference={parametre?.source}
                decimals={2}
              />
            </Ligne>
          )
        })}
        {zonesLestage.flatMap((zone) => Object.entries(zone?.parametres || {})
          .map(([code, parametre]) => (
            <Ligne
              key={`${zone?.code}:${code}`}
              libelle={`zone « ${zone?.libelle || zone?.code} » — ${libelleDeCode(code)}`}
            >
              <ValeurSourcee
                valeur={parametre?.valeur}
                origine={parametre?.source ? 'societe' : undefined}
                reference={parametre?.source}
                decimals={2}
              />
            </Ligne>
          )))}
      </Section>

      <Section
        titre="Dégagements"
        testId="cal165-degagements"
        vide={codesDegagements.length === 0
          ? 'Aucun dégagement enregistré : les valeurs de l’atelier s’appliquent.'
          : null}
      >
        {codesDegagements.map((code) => (
          <Ligne key={code} libelle={libelleDeCode(code)}>
            <ValeurSourcee
              valeur={degagements[code]}
              origine={sourceDegagements ? 'societe' : undefined}
              reference={sourceDegagements}
              decimals={2}
            />
          </Ligne>
        ))}
      </Section>
    </Card>
  )
}
