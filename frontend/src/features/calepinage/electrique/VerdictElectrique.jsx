import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Badge, Button, Card, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { messageRefus } from '../commun/refusServeur'
import { PARAM_ONGLET, ongletParCle } from '../atelier/onglets'
import { grouperMotifs, libelleStatut, motifsRefusants, statutRefuse, tonStatut } from './VerdictElectrique.helpers'

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

/* ============================================================================
   ACAL284 — LES DÉROGATIONS (CALX215), LUES ET POSÉES ICI.
   ----------------------------------------------------------------------------
   `GET resultat/` sert `derogations` [{code, libelle, auteur, horodatage,
   motif, texte}] et `ecarts_longueur` [{longueur, longueur_dossier, ecart,
   par_pan}] (contrat `calepinage_resultat.json`, listes VIDES jamais absentes).
   Une alerte NON bloquante (`electrique.verdicts[]` : conforme false, bloquant
   false) peut être PASSÉE OUTRE par un porteur de `calepinage_approuver`
   (défaut gravé) : motif obligatoire, POST `entree-electrique/`
   `{derogations: [{code, motif}]}` — l'auteur et l'instant sont posés par le
   SERVEUR. Un refus (400 `derogations.N.motif`, 403, 409) est affiché mot
   pour mot (décodeur commun). Rien n'est gardé localement : le fil est relu.
   ========================================================================== */

/** « 12/10/2026 à 09:30 » — la date du SERVEUR (ISO avec fuseau), lisible. */
function dateLisible(iso) {
  const d = iso ? new Date(iso) : null
  if (!d || Number.isNaN(d.getTime())) return iso || ''
  return d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

const phraseDerogation = (d) => `Passée outre par ${d.auteur || '—'} le ${dateLisible(d.horodatage)}`
  + `${d.motif ? ` — ${d.motif}` : ''}`

function AlertePassable({ alerte, derogation, peutDeroger, onPasserOutre }) {
  const [ouvert, setOuvert] = useState(false)
  const [motif, setMotif] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [refus, setRefus] = useState(null)
  const confirmer = async () => {
    if (!motif.trim() || envoi) return
    setEnvoi(true)
    setRefus(null)
    const erreur = await onPasserOutre(alerte.code, motif.trim())
    setEnvoi(false)
    if (erreur) setRefus(erreur)
    else { setOuvert(false); setMotif('') }
  }
  return (
    <li className="flex flex-col gap-1 text-sm" data-testid={`acal284-alerte-${alerte.code}`}>
      <span>{alerte.libelle}</span>
      {derogation ? (
        <span className="text-xs text-muted-foreground" data-testid={`acal284-derogation-${alerte.code}`}>
          {phraseDerogation(derogation)}
        </span>
      ) : !peutDeroger ? (
        <span className="text-xs text-muted-foreground">Dérogation réservée aux approbateurs</span>
      ) : ouvert ? (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground" htmlFor={`acal284-motif-${alerte.code}`}>
            Motif de la dérogation (obligatoire)
          </label>
          <textarea
            id={`acal284-motif-${alerte.code}`}
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            className="w-full rounded border border-input bg-card px-2 py-1 text-sm"
          />
          <Button type="button" size="sm" variant="outline" disabled={!motif.trim() || envoi}
            data-testid={`acal284-confirmer-${alerte.code}`} onClick={confirmer}>
            Confirmer la dérogation
          </Button>
          {refus && (
            <p role="alert" className="text-xs text-destructive" data-testid={`acal284-refus-${alerte.code}`}>{refus}</p>
          )}
        </div>
      ) : (
        <Button type="button" size="sm" variant="outline" data-testid={`acal284-passer-outre-${alerte.code}`}
          onClick={() => setOuvert(true)}>
          Passer outre
        </Button>
      )}
    </li>
  )
}

function BlocDerogations({ calepinageId }) {
  const peutDeroger = useHasPermission('calepinage_approuver')
  const [resultat, setResultat] = useState(null)
  const relire = useCallback(() => {
    if (!calepinageId) return
    Promise.resolve()
      .then(() => calepinageApi.calepinages.resultat(calepinageId))
      .then((res) => setResultat(res?.data ?? null))
      .catch(() => {})
  }, [calepinageId])
  useEffect(() => { relire() }, [relire])

  const derogations = Array.isArray(resultat?.derogations) ? resultat.derogations : []
  const ecarts = Array.isArray(resultat?.ecarts_longueur) ? resultat.ecarts_longueur : []
  const verdicts = Array.isArray(resultat?.electrique?.verdicts) ? resultat.electrique.verdicts : []
  const alertes = verdicts.filter((v) => v && v.conforme === false && !v.bloquant)
  const codesAlertes = new Set(alertes.map((a) => a.code))
  const orphelines = derogations.filter((d) => !codesAlertes.has(d.code))
  if (alertes.length === 0 && derogations.length === 0 && ecarts.length === 0) return null

  const passerOutre = async (code, motif) => {
    try {
      await calepinageApi.calepinages.enregistrerEntreeElectrique(calepinageId, { derogations: [{ code, motif }] })
      relire()
      return null
    } catch (e) {
      return messageRefus(e, 'La dérogation a été refusée par le serveur.')
    }
  }

  return (
    <section className="flex flex-col gap-2 border-t border-border/60 pt-3" data-testid="acal284-derogations">
      {alertes.length > 0 && (
        <>
          <h3 className="text-sm font-semibold">Alertes non bloquantes</h3>
          <ul className="flex flex-col gap-2">
            {alertes.map((a) => (
              <AlertePassable key={a.code} alerte={a} peutDeroger={peutDeroger}
                derogation={derogations.find((d) => d.code === a.code)} onPasserOutre={passerOutre} />
            ))}
          </ul>
        </>
      )}
      {orphelines.length > 0 && (
        <div data-testid="acal284-derogations-enregistrees">
          <h3 className="text-sm font-semibold">Dérogations enregistrées</h3>
          <ul className="flex flex-col gap-1">
            {orphelines.map((d, i) => (
              <li key={`${d.code}-${i}`} className="text-sm">
                {(d.libelle || d.code)} — {phraseDerogation(d)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {ecarts.length > 0 && (
        <ul className="flex flex-col gap-1" data-testid="acal284-ecarts-longueur">
          {ecarts.map((e, i) => (
            <li key={i} className="text-xs text-muted-foreground">
              {`Longueur de chaîne ${e.longueur} m — dossier ${e.longueur_dossier} m (écart ${e.ecart} m)`}
            </li>
          ))}
        </ul>
      )}
    </section>
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
        <BlocDerogations calepinageId={id} />
      </Card>
    </>
  )
}
