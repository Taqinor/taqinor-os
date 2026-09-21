import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import { formatDateTime } from '../../lib/format'
import { Button, Card, Spinner } from '../../ui'
import RetourAtelier from './atelier/RetourAtelier'

/* ============================================================================
   CAL196 — L'ÉCRAN « DOSSIERS RÉGLEMENTAIRES » DU CALEPINAGE.
   ----------------------------------------------------------------------------
   LE TROU QU'IL BOUCHE. Le module ne montrait AUCUN dossier administratif :
   les gabarits déposés par la société (CAL190-CAL193) vivaient côté serveur
   sans écran pour les lire. Celui-ci liste, pour le PAYS de la société, les
   dossiers disponibles, leur état PIÈCE PAR PIÈCE, les champs « à compléter »
   et l'état de la génération.

   LA RÈGLE QUI COMMANDE CE FICHIER — AUCUNE PIÈCE RÉGLEMENTAIRE INVENTÉE.
   L'ERP ne fabrique aucun formulaire officiel qu'il n'a pas reçu (CAL190) :
   une société sans gabarit déposé ne voit AUCUN dossier, et l'écran le DIT
   (`message_aucun_gabarit`) au lieu d'afficher une liste vide muette. Un
   dossier dont le fichier de gabarit manque reste VISIBLE, marqué comme tel :
   le masquer donnerait l'illusion que le dossier n'existe pas alors que c'est
   le FICHIER qui manque.

   LES CHAMPS « À COMPLÉTER » VIENNENT DU SERVEUR, ET DE LUI SEUL. `valeur`
   vaut `null` quand le serveur n'a rien à préremplir : le champ est alors
   RENDU VIDE, avec le message du serveur. Aucun préremplissage n'est deviné
   ici — c'est le Done de la tâche, et le test jumeau le prouve en parcourant
   l'échantillon committé.

   LA SOURCE EST LE CONTRAT.
   `GET /calepinage/calepinages/<pk>/dossiers-reglementaires/`, échantillon
   `apps/calepinage/contract_samples/dossiers_reglementaires.json` (CAL247,
   parti SEUL sur `main` — PACT10). Rien n'est recalculé côté écran : les
   états, les motifs et les messages sont RECOPIÉS tels que servis.

   CALX40 — LA GÉNÉRATION EST SERVIE, ET C'EST LE SERVEUR QUI L'AUTORISE.
   `POST calepinages/<pk>/generer-dossier/` existe désormais : le bouton
   n'est actif QUE si le serveur déclare `peut_generer` pour CE dossier, et il
   rend le `motif_non_generable` du serveur sinon — l'écran ne recalcule
   jamais l'autorisation, il la RECOPIE (c'est le serveur qui refuse à
   nouveau, un bouton actif ne suffit jamais à faire sortir un dossier).
   Un refus 400 est rendu SOUS le champ que le serveur nomme (`gabarit`,
   `dossier`, ou le code de la pièce qui n'a pas pu être rendue) : jamais un
   « non enregistré » générique (règle fondateur du 08/09/2026).
   ========================================================================== */

/** Les états de pièce servis par le contrat, et leur libellé français. */
const ETAT_PIECE = {
  fournie: 'fournie',
  a_completer: 'à compléter',
  manquante: 'manquante',
}

/** Les statuts de dossier servis par le contrat. */
const STATUT_DOSSIER = {
  complet: 'complet',
  incomplet: 'incomplet',
  gabarit_manquant: 'gabarit non déposé',
}

/** Le message du serveur, qu'il arrive en liste (DRF) ou en texte. */
function messageErreur(message) {
  return Array.isArray(message) ? message.join(' ') : String(message)
}

function Etiquette({ texte, alerte }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] ${
      alerte ? 'bg-destructive/10 text-destructive' : 'bg-muted text-muted-foreground'
    }`}
    >
      {texte}
    </span>
  )
}

function SourcePiece({ source }) {
  if (!source?.type) {
    // Une pièce sans source déclarée n'est pas présentée comme officielle.
    return <span className="text-[11px] text-destructive">source non déclarée</span>
  }
  const libelle = source.type === 'gabarit_societe'
    ? `gabarit déposé par la société${source.fichier ? ` — ${source.fichier}` : ''}`
    : 'pièce déclarée par la société'
  return (
    <span className="text-[11px] text-muted-foreground" data-testid="cal196-source">
      {libelle}
      {source.depose_le ? ` · ${formatDateTime(source.depose_le)}` : ''}
    </span>
  )
}

function Pieces({ pieces }) {
  if (!pieces?.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal196-pieces-vide">
        Aucune pièce : le gabarit de la société n’a pas été déposé.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-2" data-testid="cal196-pieces">
      {pieces.map((piece) => (
        <li key={piece.code} className="border-t border-border/60 pt-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm">{piece.intitule}</span>
            <Etiquette
              texte={ETAT_PIECE[piece.etat] || piece.etat}
              alerte={piece.etat !== 'fournie'}
            />
            {piece.obligatoire ? <Etiquette texte="obligatoire" /> : null}
          </div>
          {/* Le fichier n'est proposé que si le serveur a publié son URL. */}
          {piece.fichier_url
            ? (
              <a
                className="text-xs underline"
                href={piece.fichier_url}
                target="_blank"
                rel="noreferrer"
              >
                {piece.fichier || 'ouvrir la pièce'}
              </a>
            )
            : null}
          {piece.message
            ? <p className="text-xs text-muted-foreground">{piece.message}</p>
            : null}
          <SourcePiece source={piece.source} />
        </li>
      ))}
    </ul>
  )
}

/* CALX41 — LES CHAMPS DU DOSSIER, CONTRÔLÉS ET ENREGISTRÉS.
   Avant : `defaultValue` sans `onChange` ni envoi — ce que l'utilisateur
   tapait était perdu à la fermeture, alors que le dossier est un modèle
   PERSISTANT. Maintenant : la saisie est contrôlée, l'enregistrement est
   EXPLICITE (`POST champs-dossier/`), et le serveur renvoie l'agrégat
   recomposé — un champ enregistré quitte « à compléter » et réapparaît dans
   « déjà saisis », donc il reste relisible et corrigeable. */
function ChampsDossier({ dossier, calepinageId, onEnregistre }) {
  const [saisies, setSaisies] = useState(() => new Map())
  const [erreurs, setErreurs] = useState({})
  const [enVol, setEnVol] = useState(false)
  const [enregistre, setEnregistre] = useState(null)

  const aCompleter = dossier.champs_a_completer || []
  const dejaSaisis = dossier.champs_saisis || []
  const champs = [...aCompleter, ...dejaSaisis]
  const codes = champs.map((champ) => champ.code)

  const valeurDe = (champ) => (saisies.has(champ.code)
    ? saisies.get(champ.code)
    : (champ.valeur == null ? '' : String(champ.valeur)))

  const poser = (code, valeur) => {
    setEnregistre(null)
    setSaisies((precedente) => {
      const suivante = new Map(precedente)
      suivante.set(code, valeur)
      return suivante
    })
  }

  const enregistrer = () => {
    setErreurs({})
    setEnregistre(null)
    setEnVol(true)
    const corps = {}
    saisies.forEach((valeur, code) => { corps[code] = valeur })
    calepinageApi.calepinages.enregistrerChampsDossier(calepinageId, {
      ...corpsDeGeneration(dossier), champs: corps,
    })
      .then((r) => {
        // La réponse EST l'agrégat recomposé : la saisie locale n'a plus de
        // raison d'exister, c'est le serveur qui la sert désormais.
        setSaisies(new Map())
        setEnregistre('Champs enregistrés.')
        if (onEnregistre) onEnregistre(r.data)
      })
      .catch((err) => {
        // Un 400 NOMME le champ fautif : on le rend SOUS ce champ-là.
        const corpsErreur = err?.response?.data
        setErreurs(corpsErreur && typeof corpsErreur === 'object'
          ? corpsErreur
          : { champs: 'Enregistrement refusé par le serveur.' })
      })
      .finally(() => setEnVol(false))
  }

  if (!champs.length) return null
  return (
    <div className="flex flex-col gap-2" data-testid="cal196-champs">
      <p className="text-xs font-medium text-muted-foreground">Champs du dossier</p>
      {champs.map((champ) => {
        const idChamp = `cal196-${dossier.id}-${champ.code}`
        return (
          <div key={champ.code} className="flex flex-col gap-1">
            <label className="text-sm" htmlFor={idChamp}>
              {champ.libelle}
              {champ.obligatoire ? ' *' : ''}
            </label>
            {/* AUCUN PRÉREMPLISSAGE INVENTÉ : `valeur === null` ⇒ champ VIDE.
                La valeur affichée est la saisie en cours, sinon celle que le
                serveur sert — l'écran n'en devine aucune. */}
            <input
              id={idChamp}
              data-testid={`cal196-champ-${champ.code}`}
              type={champ.type === 'date' ? 'date' : 'text'}
              value={valeurDe(champ)}
              onChange={(e) => poser(champ.code, e.target.value)}
              className="rounded border border-border px-2 py-1 text-sm"
            />
            {champ.message
              ? (
                <p className="text-xs text-muted-foreground" data-testid={`cal196-message-${champ.code}`}>
                  {champ.message}
                </p>
              )
              : null}
            {/* L'ERREUR SOUS LE CHAMP QU'ELLE CONCERNE. */}
            {erreurs[champ.code]
              ? (
                <p className="text-xs text-destructive" data-testid={`calx41-erreur-${champ.code}`}>
                  {messageErreur(erreurs[champ.code])}
                </p>
              )
              : null}
          </div>
        )
      })}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          onClick={enregistrer}
          disabled={enVol || saisies.size === 0}
          data-testid={`calx41-enregistrer-${dossier.id}`}
        >
          {enVol ? 'Enregistrement…' : 'Enregistrer les champs'}
        </Button>
        {enregistre
          ? (
            <p className="text-xs text-muted-foreground" data-testid={`calx41-enregistre-${dossier.id}`}>
              {enregistre}
            </p>
          )
          : null}
      </div>
      {/* Un refus sous une clé que cet écran ne rend pas champ par champ
          (`dossier`, `gabarit`, `champs`…) reste AFFICHÉ, et il NOMME sa clé :
          un 400 silencieux serait le « non enregistré » générique interdit. */}
      {Object.entries(erreurs)
        .filter(([code]) => !codes.includes(code))
        .map(([code, message]) => (
          <p key={code} className="text-xs text-destructive" data-testid={`calx41-erreur-${code}`}>
            {messageErreur(message)}
          </p>
        ))}
    </div>
  )
}

/* CALX40 — le corps de la demande : un dossier déjà commencé se désigne par
   son `id` ; un dossier jamais commencé (`id: null`) par son gabarit. */
function corpsDeGeneration(dossier) {
  return dossier.id == null
    ? { gabarit: dossier.gabarit_id }
    : { dossier: dossier.id }
}

function Dossier({ dossier, calepinageId, onGenere, onEnregistre }) {
  const gabarit = dossier.gabarit || {}
  const [enVol, setEnVol] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [genere, setGenere] = useState(null)

  const generer = () => {
    setErreurs({})
    setGenere(null)
    setEnVol(true)
    calepinageApi.calepinages.genererDossier(
      calepinageId, corpsDeGeneration(dossier),
    )
      .then((r) => {
        setGenere(r.data)
        if (onGenere) onGenere()
      })
      .catch((err) => {
        // Un 400 NOMME son champ : on le rend sous ce champ-là, jamais sous
        // un « non enregistré » générique.
        const corps = err?.response?.data
        setErreurs(corps && typeof corps === 'object'
          ? corps
          : { dossier: 'Génération refusée par le serveur.' })
      })
      .finally(() => setEnVol(false))
  }

  return (
    <Card className="flex flex-col gap-3 p-3" data-testid={`cal196-dossier-${dossier.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{dossier.intitule}</h3>
        <Etiquette
          texte={STATUT_DOSSIER[dossier.statut] || dossier.statut}
          alerte={dossier.statut !== 'complet'}
        />
      </div>

      <p className="text-xs text-muted-foreground" data-testid={`cal196-gabarit-${dossier.id}`}>
        {gabarit.present
          ? `Gabarit ${gabarit.fichier}${gabarit.version ? ` (version ${gabarit.version})` : ''}`
            + `${gabarit.depose_le ? ` · déposé le ${formatDateTime(gabarit.depose_le)}` : ''}`
            + `${gabarit.depose_par?.nom_complet ? ` par ${gabarit.depose_par.nom_complet}` : ''}`
          : 'Gabarit non déposé : aucun formulaire officiel n’est fabriqué sans le fichier de la société.'}
      </p>

      <Pieces pieces={dossier.pieces} />
      <ChampsDossier
        dossier={dossier}
        calepinageId={calepinageId}
        onEnregistre={onEnregistre}
      />

      <div className="flex flex-col gap-1">
        <Button
          type="button"
          onClick={generer}
          disabled={!dossier.peut_generer || enVol}
          data-testid={`cal196-generer-${dossier.id}`}
        >
          {enVol ? 'Génération en cours…' : 'Générer le dossier'}
        </Button>
        <p className="text-xs text-muted-foreground" data-testid={`cal196-motif-${dossier.id}`}>
          {dossier.peut_generer
            ? 'Toutes les pièces et tous les champs obligatoires sont là : le dossier peut être généré.'
            : dossier.motif_non_generable}
        </p>
        {/* TOUT refus serveur est rendu SOUS le champ qu'il nomme. */}
        {Object.entries(erreurs).map(([code, message]) => (
          <p
            key={code}
            className="text-xs text-destructive"
            data-testid={`calx40-erreur-${code}`}
          >
            {messageErreur(message)}
          </p>
        ))}
        {genere
          ? (
            <p className="text-xs text-muted-foreground" data-testid={`calx40-genere-${dossier.id}`}>
              Dossier généré —
              {' '}
              {(genere.pieces || []).map((piece) => piece.libelle).join(', ')
                || 'aucune pièce listée par le serveur'}
            </p>
          )
          : null}
        {/* Les signalements du serveur (pièce facultative non rendue) sont
            RECOPIÉS : une pièce absente ne se découvre pas au dépôt. */}
        {(genere?.signalements || []).map((signalement) => (
          <p key={signalement} className="text-xs text-muted-foreground" data-testid="calx40-signalement">
            {signalement}
          </p>
        ))}
        <p className="text-xs text-muted-foreground">
          {dossier.genere_le
            ? `Dernière génération : ${formatDateTime(dossier.genere_le)}`
            : 'Jamais généré : —'}
        </p>
      </div>
    </Card>
  )
}

export default function DossiersReglementaires({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.dossiersReglementaires(id), id,
    { select: (r) => r.data, errorMessage: 'Dossiers réglementaires indisponibles.' },
  )
  /* CALX41 — `champs-dossier/` répond avec l'agrégat RECOMPOSÉ : on l'affiche
     directement, sans enchaîner un second appel pour relire ce que le serveur
     vient déjà de servir. */
  const [surcharge, setSurcharge] = useState(null)
  const donnees = surcharge ?? data

  const regenere = () => { setSurcharge(null); refetch() }

  if (loading) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <Spinner />
      </>
    )
  }
  if (error) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <p className="text-sm text-destructive" data-testid="cal196-erreur">{error}</p>
      </>
    )
  }

  const dossiers = donnees?.dossiers || []

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <div className="flex flex-col gap-4" data-testid="cal196-ecran">
      <header className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Dossiers réglementaires</h2>
        <p className="text-sm text-muted-foreground" data-testid="cal196-entete">
          Pays de la société : {donnees?.pays || '—'} · gabarits déposés :
          {' '}
          {donnees?.gabarits_deposes == null ? '—' : donnees.gabarits_deposes}
        </p>
      </header>

      {donnees?.message_aucun_gabarit
        ? (
          <p className="text-sm text-muted-foreground" data-testid="cal196-aucun-gabarit">
            {donnees.message_aucun_gabarit}
          </p>
        )
        : null}

      {dossiers.map((dossier) => (
        <Dossier
          key={dossier.id ?? `gabarit-${dossier.gabarit_id}`}
          dossier={dossier}
          calepinageId={id}
          onGenere={regenere}
          onEnregistre={setSurcharge}
        />
      ))}
    </div>
    </>
  )
}
