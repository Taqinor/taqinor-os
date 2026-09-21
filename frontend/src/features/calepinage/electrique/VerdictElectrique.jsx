/* eslint-disable react-refresh/only-export-components --
   `STATUTS`, `DOMAINES`, `libelleStatut`, `tonStatut`, `domaineDuMotif`,
   `grouperMotifs` et `motifsRefusants` sont des constantes et des fonctions
   PURES que le test unitaire confronte directement à la forme publiée par
   `services/electrique.py::verdict_publiable`. Les sortir dans un `.js`
   voisin séparerait la table de son unique lecteur pour satisfaire une règle
   de fast-refresh qui ne s'applique pas à une constante — même dérogation que
   `Raccordement.jsx`/`CheminementCables.jsx`/`EquipementsElectriques.jsx` du
   même dossier. */
import { Link, useParams } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Badge, Card, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { PARAM_ONGLET, ongletParCle } from '../atelier/onglets'

/* ============================================================================
   CALX249 — L'ONGLET « VERDICT ÉLECTRIQUE » DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT QUI JUSTIFIE CE FICHIER. `AffectationChaines.jsx:44-48` affiche déjà
   les bloquants servis par le serveur, mais uniquement ceux de l'affectation ;
   `SchemaUnifilairePanel.jsx:33-57` ne montre ses motifs que lorsqu'il n'a PAS
   de schéma à dessiner. Aucune surface ne rassemblait norme, chaînes, câbles,
   protections, terre et raccordement : un installateur ne pouvait donc jamais
   lire, en un seul endroit, ce qui empêche de publier son dossier. Parité
   OpenSolar : un retour de compatibilité en direct, par pastilles, au niveau
   onduleur ET au niveau MPPT.

   LA SOURCE EST LE VERDICT PUBLIABLE DU SERVEUR (CALX248),
   `services/electrique.py::verdict_publiable` → `{publiable, motifs}`, chaque
   motif valant `{code, statut, libelle, source}`. Il voyage sous la clé
   `publication` de la réponse de `POST calepinages/<pk>/evaluer-electrique/`
   (`views/electrique.py`). AUCUNE MÉTHODE D'API N'EST AJOUTÉE : la méthode
   `calepinages.evaluerElectrique` existe déjà (`api/calepinageApi.js`) et sert
   exactement cette donnée — en ajouter une seconde ouvrirait une deuxième
   porte vers la même route.

   L'APPEL PORTE UN CORPS VIDE, ET C'EST LE FOND DE L'AFFAIRE. Le serveur met
   `publication` à `null` dès que l'appel joint un dessin (`layout`) ou une
   entrée « à chaud » : on publie ce qui est ENREGISTRÉ, pas ce qui est en
   cours de dessin. Cet écran n'envoie donc ni l'un ni l'autre. Reçu `null`, il
   RECOPIE ce que le serveur dit de l'évaluation (`manquantes[]`) ou affiche sa
   seule phrase fixe, « Aucune évaluation enregistrée. » — jamais un chiffre,
   jamais un « OK » supposé.

   AUCUN RECALCUL CÔTÉ PAGE (D-CALX 7). Le statut, le libellé et la source sont
   recopiés tels quels ; rien n'est reformulé, rien n'est agrégé d'un côté et
   de l'autre. Le seul verdict global affiché est le booléen `publiable` DU
   SERVEUR, et le « pourquoi » n'est que la sélection des motifs qui portent un
   statut refusant — pas un second jugement.

   UN STATUT D'ABSTENTION NE PEUT PAS S'AFFICHER EN VERT. `non_verifiable` et
   `omis` ont leur propre apparence, distincte de `ok` : un contrôle qui n'a pas
   eu lieu n'est pas un contrôle réussi (c'est déjà la règle du noyau,
   `core/electrique/types.py::VerdictElectrique.est_ok`). `sans_source` est
   traité comme ce qu'il est : une valeur qui a jugé sans qu'on sache d'où elle
   vient — elle EMPÊCHE l'édition d'un document, et l'écran le dit.

   LE BOUTON MÈNE À L'ONGLET RESPONSABLE, DONT LE NOM VIENT DU REGISTRE. Le
   libellé affiché est celui de `atelier/onglets.js` (seule source des noms
   d'onglets) : aucun nom d'écran n'est écrit en dur ici. Un domaine dont
   l'atelier n'a pas d'onglet (la norme électrique, qui est un réglage société)
   n'affiche AUCUN bouton plutôt qu'un bouton qui mènerait ailleurs.
   ========================================================================== */

/** La clé de l'onglet — celle du registre, et celle du fil d'Ariane. */
export const CLE_ONGLET = 'verdict-electrique'

/**
 * Les statuts publiés par `verdict_publiable`, chacun avec SON apparence.
 *
 * `refuse` dit si le statut empêche de publier — c'est la règle du serveur
 * (`verdict_publiable` : zéro bloquant ET zéro `sans_source`), recopiée ici
 * pour EXPLIQUER le booléen, jamais pour le recalculer.
 */
export const STATUTS = {
  bloquant: { libelle: 'Bloquant', ton: 'danger', refuse: true },
  sans_source: { libelle: 'Sans provenance', ton: 'outline', refuse: true },
  alerte: { libelle: 'À surveiller', ton: 'warning', refuse: false },
  non_verifiable: { libelle: 'Non vérifiable', ton: 'info', refuse: false },
  omis: { libelle: 'Non calculé, motivé', ton: 'neutral', refuse: false },
  ok: { libelle: 'Conforme', ton: 'success', refuse: false },
}

/** Le libellé d'un statut — un statut inconnu est NOMMÉ, jamais tu. */
export function libelleStatut(statut) {
  return STATUTS[statut]?.libelle ?? `statut « ${statut} »`
}

/**
 * Le ton du badge. Un statut INCONNU ne prend jamais le ton de `ok` : une
 * valeur que cet écran ne comprend pas ne peut pas se lire comme un succès.
 */
export function tonStatut(statut) {
  return STATUTS[statut]?.ton ?? 'primary'
}

/** Vrai quand CE statut est l'un des deux que le serveur juge refusants. */
export function statutRefuse(statut) {
  return STATUTS[statut]?.refuse === true
}

/**
 * Les domaines, dans l'ordre de lecture, et l'onglet qui en RÉPOND.
 *
 * Les codes sont ceux que produisent les producteurs du verdict :
 * `core/electrique/chaines.py` (`CH_*`), `services/norme.py`,
 * `services/raccordement.py` (`CODE_*`, en minuscules),
 * `services/troncons.py` (`CODE_VERDICT`), `services/terre.py` et la garde de
 * fiche de `services/electrique.py`. Un code inconnu tombe dans `autre` avec
 * son libellé intact : il est AFFICHÉ, jamais avalé.
 */
export const DOMAINES = [
  {
    cle: 'fiches',
    libelle: 'Fiches équipements',
    onglet: 'fiches',
    codes: ['FICHE_INCOMPLETE'],
    prefixes: [],
  },
  {
    cle: 'chaines',
    libelle: 'Chaînes et entrées MPPT',
    onglet: 'affectation',
    codes: [],
    prefixes: ['CH_'],
  },
  {
    cle: 'norme',
    // Réglage SOCIÉTÉ : l'atelier d'un calepinage n'en répond pas, donc
    // aucun bouton — mieux vaut pas de bouton qu'un bouton qui ment.
    libelle: 'Norme électrique',
    onglet: null,
    codes: ['NORME_NON_APPLICABLE'],
    prefixes: [],
  },
  {
    cle: 'raccordement',
    libelle: 'Raccordement réseau',
    onglet: 'raccordement',
    codes: ['RACCORDEMENT_REFUSE', 'puissance_souscrite', 'regime_phases',
      'tension_nominale', 'elevation_tension', 'desequilibre_phases'],
    prefixes: [],
  },
  {
    cle: 'troncons',
    libelle: 'Cheminement et câbles',
    onglet: 'cheminement-cables',
    codes: ['TRONCON_NON_CALCULABLE', 'chute_cumulee_dc', 'chute_cumulee_ac'],
    prefixes: [],
  },
  {
    cle: 'terre',
    // La terre est le troisième côté des tronçons (`LIBELLES_COTE` de
    // `CheminementCables.jsx`) : c'est là qu'elle se lit.
    libelle: 'Mise à la terre',
    onglet: 'cheminement-cables',
    codes: [],
    prefixes: ['TERRE_'],
  },
]

/** Le fourre-tout NOMMÉ des codes que cet écran ne connaît pas encore. */
export const DOMAINE_AUTRE = {
  cle: 'autre',
  libelle: 'Autres contrôles',
  onglet: null,
  codes: [],
  prefixes: [],
}

/** Le domaine d'un code — `DOMAINE_AUTRE` quand aucun ne le revendique. */
export function domaineDuMotif(code) {
  const nom = String(code ?? '')
  for (const domaine of DOMAINES) {
    if (domaine.codes.includes(nom)) return domaine
    if (domaine.prefixes.some((prefixe) => nom.startsWith(prefixe))) {
      return domaine
    }
  }
  return DOMAINE_AUTRE
}

/**
 * Les motifs rangés par domaine : `[{domaine, motifs}]`, dans l'ordre de
 * `DOMAINES` puis `autre`. Un domaine sans motif n'est pas rendu — une section
 * vide se lirait comme « tout va bien ici », ce que personne n'a dit.
 */
export function grouperMotifs(motifs) {
  const liste = Array.isArray(motifs) ? motifs : []
  const groupes = []
  for (const domaine of [...DOMAINES, DOMAINE_AUTRE]) {
    const siens = liste.filter(
      (motif) => domaineDuMotif(motif?.code).cle === domaine.cle)
    if (siens.length > 0) groupes.push({ domaine, motifs: siens })
  }
  return groupes
}

/** Les motifs qui EMPÊCHENT de publier — bloquants et valeurs sans source. */
export function motifsRefusants(motifs) {
  const liste = Array.isArray(motifs) ? motifs : []
  return liste.filter((motif) => statutRefuse(motif?.statut))
}

/** Le lien vers l'onglet responsable — son NOM vient du registre. */
function AllerAOnglet({ calepinageId, cleOnglet, cleDomaine }) {
  const onglet = ongletParCle(cleOnglet)
  if (!calepinageId || !onglet) return null
  const parametres = new URLSearchParams()
  parametres.set(PARAM_ONGLET, onglet.cle)
  return (
    <Link
      to={`/calepinage/${calepinageId}?${parametres.toString()}`}
      className="text-sm font-medium text-brass-300 underline"
      data-testid={`calx249-aller-${cleDomaine}`}
    >
      {onglet.libelle}
    </Link>
  )
}

/** Un motif : son statut, son libellé SERVEUR mot pour mot, sa source. */
function Motif({ motif }) {
  return (
    <li
      className="flex flex-col gap-1 border-b border-border/60 pb-2 last:border-0"
      data-testid={`calx249-motif-${motif.code}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          tone={tonStatut(motif.statut)}
          data-testid={`calx249-statut-${motif.code}`}
        >
          {libelleStatut(motif.statut)}
        </Badge>
        <code className="text-xs text-lune-faint" data-testid={`calx249-code-${motif.code}`}>
          {motif.code}
        </code>
        {statutRefuse(motif.statut)
          ? (
            <span
              className="text-xs font-medium text-destructive"
              data-testid={`calx249-refuse-${motif.code}`}
            >
              Empêche l’édition d’un document
            </span>
          )
          : null}
      </div>
      <p className="text-sm" data-testid={`calx249-libelle-${motif.code}`}>
        {motif.libelle}
      </p>
      {motif.source
        ? (
          <p className="text-xs text-lune-faint" data-testid={`calx249-source-${motif.code}`}>
            {motif.source}
          </p>
        )
        : (
          <p className="text-xs text-lune-faint" data-testid={`calx249-sans-source-${motif.code}`}>
            Aucune provenance déclarée.
          </p>
        )}
    </li>
  )
}

export default function VerdictElectrique({ calepinageId } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  /* Corps VIDE : ni `layout`, ni `entree_electrique`. C'est la seule forme
     d'appel pour laquelle le serveur renseigne `publication` (CALX248). */
  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.evaluerElectrique(id, {}), id,
    { select: (r) => r.data, errorMessage: 'Verdict électrique indisponible.' },
  )

  const publication = data?.publication ?? null
  const motifs = Array.isArray(publication?.motifs) ? publication.motifs : []
  const groupes = grouperMotifs(motifs)
  const refusants = motifsRefusants(motifs)
  /* Les phrases du SERVEUR quand il n'a pas pu se prononcer (fiche non
     résolue : `evaluation_electrique` rend `manquantes[]`). */
  const manquantes = Array.isArray(data?.manquantes) ? data.manquantes : []

  if (loading) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle={CLE_ONGLET} />
        <Spinner />
      </>
    )
  }
  if (error) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle={CLE_ONGLET} />
        <p className="text-sm text-destructive" data-testid="calx249-erreur">{error}</p>
      </>
    )
  }

  return (
    <>
      <RetourAtelier calepinageId={id} cle={CLE_ONGLET} />
      <Card className="flex flex-col gap-4 p-4" data-testid="calx249-panneau">
        <header className="flex items-center gap-2">
          <ShieldCheck size={16} aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <h2 className="text-base font-semibold">Verdict électrique</h2>
            <p className="text-sm text-muted-foreground">
              Ce que le serveur a prononcé sur la conception enregistrée, motif
              par motif. Rien n’est recalculé ici.
            </p>
          </div>
        </header>

        {publication === null || publication === undefined
          ? (
            <section className="flex flex-col gap-2" data-testid="calx249-sans-verdict">
              <p className="text-sm text-muted-foreground">
                Aucune évaluation enregistrée.
              </p>
              {manquantes.length > 0
                ? (
                  <ul className="flex flex-col gap-1" data-testid="calx249-manquantes">
                    {manquantes.map((phrase) => (
                      <li key={phrase} className="text-sm">{phrase}</li>
                    ))}
                  </ul>
                )
                : null}
            </section>
          )
          : (
            <>
              <section
                className="flex flex-col gap-2 border border-border/60 p-3"
                data-testid="calx249-global"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">Dossier électrique :</span>
                  <Badge
                    tone={publication.publiable ? 'success' : 'danger'}
                    data-testid="calx249-publiable"
                  >
                    {publication.publiable ? 'Publiable' : 'Non publiable'}
                  </Badge>
                </div>
                {publication.publiable
                  ? (
                    <p className="text-sm text-muted-foreground" data-testid="calx249-pourquoi-oui">
                      Aucun motif bloquant, aucune valeur sans provenance.
                    </p>
                  )
                  : (
                    <div className="flex flex-col gap-1" data-testid="calx249-pourquoi-non">
                      <p className="text-sm text-muted-foreground">
                        Ce qui l’empêche :
                      </p>
                      <ul className="flex flex-col gap-1">
                        {refusants.map((motif) => (
                          <li
                            key={motif.code}
                            className="text-sm"
                            data-testid={`calx249-empeche-${motif.code}`}
                          >
                            <Badge tone={tonStatut(motif.statut)}>
                              {libelleStatut(motif.statut)}
                            </Badge>
                            {' '}
                            <span data-testid={`calx249-empeche-libelle-${motif.code}`}>
                              {motif.libelle}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
              </section>

              {groupes.length === 0
                ? (
                  <p className="text-sm text-muted-foreground" data-testid="calx249-aucun-motif">
                    Le serveur n’a retenu aucun motif.
                  </p>
                )
                : groupes.map(({ domaine, motifs: siens }) => (
                  <section
                    key={domaine.cle}
                    className="flex flex-col gap-2"
                    data-testid={`calx249-domaine-${domaine.cle}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold">{domaine.libelle}</h3>
                      <AllerAOnglet
                        calepinageId={id}
                        cleOnglet={domaine.onglet}
                        cleDomaine={domaine.cle}
                      />
                    </div>
                    <ul className="flex flex-col gap-2">
                      {siens.map((motif) => (
                        <Motif key={motif.code} motif={motif} />
                      ))}
                    </ul>
                  </section>
                ))}
            </>
          )}
      </Card>
    </>
  )
}
