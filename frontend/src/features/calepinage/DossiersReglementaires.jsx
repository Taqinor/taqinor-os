import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import { formatDateTime } from '../../lib/format'
import { Button, Card, Spinner } from '../../ui'

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

   LA GÉNÉRATION N'EST PAS SERVIE. Le contrat publie `peut_generer` et
   `motif_non_generable`, mais AUCUNE route de génération n'est enregistrée à
   ce jour (`apps/calepinage/views/reglementaire.py` n'expose que la lecture).
   Le bouton est donc présent et DÉSACTIVÉ, en disant pourquoi — plutôt qu'un
   bouton qui appellerait un chemin inexistant (la faute de la Bibliothèque AO
   du 03/08/2026, neuf chemins appelés sous aucune route).
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

function ChampsACompleter({ champs, dossierId }) {
  if (!champs?.length) return null
  return (
    <div className="flex flex-col gap-2" data-testid="cal196-champs">
      <p className="text-xs font-medium text-muted-foreground">Champs à compléter</p>
      {champs.map((champ) => {
        const idChamp = `cal196-${dossierId}-${champ.code}`
        return (
          <div key={champ.code} className="flex flex-col gap-1">
            <label className="text-sm" htmlFor={idChamp}>
              {champ.libelle}
              {champ.obligatoire ? ' *' : ''}
            </label>
            {/* AUCUN PRÉREMPLISSAGE INVENTÉ : `valeur === null` ⇒ champ VIDE.
                `defaultValue` et non `value` : l'utilisateur saisit, et cet
                écran n'enregistre rien tant qu'aucune route ne le sert. */}
            <input
              id={idChamp}
              data-testid={`cal196-champ-${champ.code}`}
              type={champ.type === 'date' ? 'date' : 'text'}
              defaultValue={champ.valeur == null ? '' : String(champ.valeur)}
              className="rounded border border-border px-2 py-1 text-sm"
            />
            {champ.message
              ? (
                <p className="text-xs text-muted-foreground" data-testid={`cal196-message-${champ.code}`}>
                  {champ.message}
                </p>
              )
              : null}
          </div>
        )
      })}
    </div>
  )
}

function Dossier({ dossier }) {
  const gabarit = dossier.gabarit || {}
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
      <ChampsACompleter champs={dossier.champs_a_completer} dossierId={dossier.id} />

      <div className="flex flex-col gap-1">
        <Button
          type="button"
          disabled
          data-testid={`cal196-generer-${dossier.id}`}
        >
          Générer le dossier
        </Button>
        <p className="text-xs text-muted-foreground" data-testid={`cal196-motif-${dossier.id}`}>
          {dossier.peut_generer
            ? 'La génération n’est pas encore servie par le serveur : aucun dossier n’est fabriqué depuis cet écran.'
            : dossier.motif_non_generable}
        </p>
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

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.dossiersReglementaires(id), id,
    { select: (r) => r.data, errorMessage: 'Dossiers réglementaires indisponibles.' },
  )

  if (loading) return <Spinner />
  if (error) {
    return <p className="text-sm text-destructive" data-testid="cal196-erreur">{error}</p>
  }

  const dossiers = data?.dossiers || []

  return (
    <div className="flex flex-col gap-4" data-testid="cal196-ecran">
      <header className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Dossiers réglementaires</h2>
        <p className="text-sm text-muted-foreground" data-testid="cal196-entete">
          Pays de la société : {data?.pays || '—'} · gabarits déposés :
          {' '}
          {data?.gabarits_deposes == null ? '—' : data.gabarits_deposes}
        </p>
      </header>

      {data?.message_aucun_gabarit
        ? (
          <p className="text-sm text-muted-foreground" data-testid="cal196-aucun-gabarit">
            {data.message_aucun_gabarit}
          </p>
        )
        : null}

      {dossiers.map((dossier) => <Dossier key={dossier.id} dossier={dossier} />)}
    </div>
  )
}
