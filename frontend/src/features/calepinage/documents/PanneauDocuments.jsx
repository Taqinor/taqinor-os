import { useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { downloadBlob, filenameFromResponse } from '../../../utils/downloadBlob'
import { formatDateTime } from '../../../lib/format'
import { Button, Card, Spinner } from '../../../ui'
import { PARAM_ONGLET, ONGLETS } from '../atelier/onglets'
import { deposerCarteDeChaleur, deposerDiagrammeDePertes } from './deposerImage'

/* ============================================================================
   CALX320 — LE PANNEAU « DOCUMENTS » BASCULE SUR L'INVENTAIRE `documents/`.
   ----------------------------------------------------------------------------
   CALX19 posait ce panneau sur l'inventaire `sorties/` (planche, plans, note
   de calcul, DXF, tableurs, pack technique — des SORTIES TECHNIQUES, CAL175).
   `sorties/` ne publie qu'une phrase libre par pièce indisponible et ne garde
   AUCUNE version : impossible d'y montrer « ce qui manque » champ par champ
   ou « la dernière version produite ». `documents/` (CALX291, contrat
   `contract_samples/calepinage_documents.json`) est l'inventaire DISTINCT des
   NEUF LIVRABLES du lot 6 (rapport d'étude, rapport d'ombrage, export projet,
   plan de câblage, manuel propriétaire, as-built, dossier de fin de chantier,
   diagramme de pertes, présentation compacte) — chaque pièce y porte
   `manque: [{champ, libelle, ou_saisir}]` (CALX321) et `versions: [...]`
   (CALX322, la plus récente d'abord). C'est CETTE inventaire que ce panneau
   consomme désormais — MÊME FICHIER, MÊME clé d'onglet `documents` (unique
   dans `atelier/onglets.js` — aucun second panneau n'est inscrit ici).

   CE PANNEAU N'INVENTE RIEN. Chaque entrée affichée est EXACTEMENT une pièce
   de l'inventaire servi (`documents()`) : le libellé, le format, si le
   bouton est actif (`disponible`), le motif du serveur ET la liste NOMMÉE de
   ce qui manque — jamais recalculés ni reformulés ici (règle fondateur
   « erreurs = le champ fautif, message exact »). AUCUNE pièce indisponible
   n'est masquée : elle reste affichée, grisée, bouton désactivé, motif et
   manque lisibles.

   LE LIEN VERS L'ONGLET. `manque[].ou_saisir` est une phrase FRANÇAISE déjà
   écrite par le serveur (ex. « Vérifiez les températures sur l'onglet
   Équipements électriques. ») — jamais une clé de registre. `ongletCiteDans`
   cherche, DANS ce texte, le libellé d'un onglet qui existe RÉELLEMENT dans
   `atelier/onglets.js` (« l'onglet <libellé> » / « le panneau <libellé> ») :
   seul un texte qui NOMME un onglet inscrit devient un lien cliquable —
   jamais une devinette (un champ comme `roof_layout`, dont le texte cite
   « l'onglet Toiture », qui n'existe pas dans le registre sous ce nom,
   n'obtient donc AUCUN lien : le texte reste lisible, sans destination
   fausse).

   L'EMPREINTE. Le contrat ne publie AUCUNE empreinte par version (seulement
   `numero`/`produit_le`/`produit_par_utilisateur`/`attachment`) — en publier
   une par ligne serait un chiffre inventé (règle fondateur). L'EMPREINTE DE
   LA CONCEPTION (`layout_hash`, publiée UNE fois par l'inventaire) s'affiche
   en tête de panneau, même lecture que `FicheCalepinage.jsx` (`layout_hash
   .slice(0, 12)`, libellé « Empreinte de la conception »).

   LE TÉLÉCHARGEMENT D'UNE VERSION ANTÉRIEURE. `versions[].attachment` n'est
   qu'un IDENTIFIANT numérique (`records.Attachment`), jamais une URL — le
   contrat ne publie pas mieux. Le proxy Django générique des pièces jointes
   (`apps.records`, route DRF déclarée `attachments/<pk>/download/`) est LA
   MÊME convention que sert `AttachmentSerializer.get_url` et que consomme
   déjà `AttachmentsPanel.jsx` (`a.url`) : construire ce chemin à partir de
   l'identifiant n'est pas une devinette, c'est une route STABLE du dépôt.

   IMAGES JOINTES. `images[]` (CALX302) liste les dépôts RÉELLEMENT
   persistés (`{genre, attachment, depose_le}`) — affichées ICI, en plus de
   la confirmation éphémère de LA session courante que CALX302 posait déjà.

   SectionConception (CALX28) et SectionImages (CALX302, étendue ici du
   bouton « Joindre le diagramme de pertes ») restent HORS inventaire —
   aucune des deux n'était gouvernée par `sorties()`, ni par `documents()`.
   ========================================================================== */

/** Une erreur serveur -> `[{champ, message}]`, triée pour un affichage
    STABLE. Couvre les DEUX formes vues sur ce module : un objet
    `{champ: message}` et une LISTE de chaînes. Jamais un message générique
    tant qu'un détail existe. */
function detailsErreur(donnee) {
  if (Array.isArray(donnee)) {
    return donnee.map((message, index) => ({ champ: String(index + 1), message: String(message) }))
  }
  if (donnee && typeof donnee === 'object') {
    return Object.entries(donnee)
      .map(([champ, message]) => ({ champ, message: String(message) }))
      .sort((a, b) => a.champ.localeCompare(b.champ))
  }
  return [{ champ: '', message: 'Le serveur a refusé la demande, sans détail lisible.' }]
}

/** Le corps JSON d'une erreur axios dont la réponse est un BLOB
    (`responseType: 'blob'` — c'est le cas de tout téléchargement de ce
    panneau) : le corps d'erreur voyage lui aussi en blob, il faut le relire
    en texte avant de le parser. Sans réponse du tout (réseau coupé), un motif
    générique — jamais un plantage muet. */
async function erreurDeTelechargement(erreur) {
  const donnees = erreur?.response?.data
  if (typeof Blob !== 'undefined' && donnees instanceof Blob) {
    try {
      return detailsErreur(JSON.parse(await donnees.text()))
    } catch {
      return [{ champ: '', message: 'Réponse du serveur illisible.' }]
    }
  }
  if (donnees) return detailsErreur(donnees)
  return [{ champ: '', message: 'Le serveur est resté injoignable.' }]
}

/** La liste des motifs/signalements d'une carte — jamais en tête de panneau. */
function ErreursSortie({ erreurs }) {
  if (!erreurs?.length) return null
  return (
    <ul
      role="alert"
      className="mt-2 space-y-0.5 text-xs text-destructive"
      data-testid="cal-doc-erreurs"
    >
      {erreurs.map((e) => (
        <li key={`${e.champ}-${e.message}`}>
          {e.champ ? <strong>{e.champ}</strong> : null}
          {e.champ ? ' — ' : ''}
          {e.message}
        </li>
      ))}
    </ul>
  )
}

/** Le proxy Django GÉNÉRIQUE d'une pièce jointe (`apps.records`), MÊME
    convention que `AttachmentSerializer.get_url` / `AttachmentsPanel.jsx`
    (`a.url`) : `documents()` ne publie qu'un IDENTIFIANT numérique par
    version/image (`attachment`), jamais une URL — ce chemin est la SEULE
    façon de le résoudre, une route DRF déclarée et stable, jamais une
    devinette. */
function hrefAttachment(attachmentId) {
  return `/api/django/records/attachments/${attachmentId}/download/`
}

/** L'onglet du REGISTRE (`atelier/onglets.js`) dont le libellé est cité,
    EN TOUTES LETTRES, par un texte `ou_saisir` (« … sur l'onglet Toiture. »,
    « … le panneau Pertes. ») — `null` si aucun onglet du registre n'y est
    nommé : JAMAIS un lien vers une devinette. Recherche DEPUIS le registre
    (pas l'inverse) : ça évite toute ambiguïté de découpage de phrase. */
function ongletCiteDans(texte) {
  if (!texte) return null
  const bas = texte.toLowerCase()
  return ONGLETS.find((o) => {
    const nom = o.libelle.toLowerCase()
    return bas.includes(`l'onglet ${nom}`) || bas.includes(`l’onglet ${nom}`)
      || bas.includes(`le panneau ${nom}`)
  }) ?? null
}

/** La liste `manque[]` d'un document indisponible — chaque entrée NOMME son
    champ et son libellé ; `ou_saisir` devient un LIEN vers l'onglet du
    registre quand le texte en cite un qui existe réellement (voir
    `ongletCiteDans`), sinon reste un texte simple. */
function ListeManque({ manque, calepinageId, code }) {
  if (!manque?.length) return null
  return (
    <ul className="mt-2 space-y-1 text-xs text-muted-foreground" data-testid={`cal-doc-manque-${code}`}>
      {manque.map((m) => {
        const onglet = ongletCiteDans(m.ou_saisir)
        return (
          <li key={`${code}-${m.champ}`} data-testid={`cal-doc-manque-item-${code}-${m.champ}`}>
            <strong className="text-foreground">{m.libelle}</strong>
            {' — '}
            {onglet ? (
              <Link
                to={`/calepinage/${calepinageId}?${PARAM_ONGLET}=${onglet.cle}`}
                className="underline"
                data-testid={`cal-doc-manque-lien-${code}-${m.champ}`}
              >
                {m.ou_saisir}
              </Link>
            ) : m.ou_saisir}
          </li>
        )
      })}
    </ul>
  )
}

/** Une ligne de version : numéro, date, auteur (quand le serveur le publie),
    et son téléchargement propre (`attachment`, proxy générique). */
function LigneVersion({ code, version, etiquette }) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground"
      data-testid={`cal-doc-version-${code}-${version.numero}`}
    >
      <span>
        {etiquette} v{version.numero} — {formatDateTime(version.produit_le)}
        {version.produit_par_utilisateur?.nom_complet
          ? ` · ${version.produit_par_utilisateur.nom_complet}` : ''}
      </span>
      <a
        href={hrefAttachment(version.attachment)}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-primary-text underline"
        data-testid={`cal-doc-version-telecharger-${code}-${version.numero}`}
      >
        Télécharger
      </a>
    </div>
  )
}

/** La « dernière version » PUIS les versions antérieures (`versions[]` sert
    déjà la plus récente d'abord, CALX322) — rien tant que la liste est
    vide. */
function VersionsDocument({ versions, code }) {
  if (!versions?.length) return null
  const [derniere, ...anterieures] = versions
  return (
    <div className="mt-2 space-y-1" data-testid={`cal-doc-versions-${code}`}>
      <LigneVersion code={code} version={derniere} etiquette="Dernière version" />
      {anterieures.map((v) => (
        <LigneVersion key={v.numero} code={code} version={v} etiquette="Version antérieure" />
      ))}
    </div>
  )
}

/** Une carte de document (contrat `calepinage_documents.json`) : libellé,
    format, bouton de téléchargement (actif seulement si `disponible`), le
    motif SOUS le bouton quand il ne l'est pas — suivi de la liste `manque[]`
    NOMMÉE (CALX321) — puis les versions déjà produites (CALX322), qu'il
    soit disponible ou non (une pièce redevenue indisponible garde son
    historique). */
function CarteDocument({
  entree, calepinageId, enCours, onTelecharger, erreurs,
}) {
  return (
    <div
      className="rounded-md border border-border/60 p-3"
      data-testid={`cal-doc-sortie-${entree.code}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-foreground">{entree.libelle}</p>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{entree.format}</p>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={!entree.disponible}
          loading={enCours}
          onClick={onTelecharger}
          data-testid={`cal-doc-bouton-${entree.code}`}
        >
          Télécharger
        </Button>
      </div>
      {!entree.disponible && (
        <>
          <p
            className="mt-2 text-xs text-muted-foreground"
            data-testid={`cal-doc-motif-${entree.code}`}
          >
            {entree.motif_indisponible}
          </p>
          <ListeManque manque={entree.manque} calepinageId={calepinageId} code={entree.code} />
        </>
      )}
      <VersionsDocument versions={entree.versions} code={entree.code} />
      <ErreursSortie erreurs={erreurs} />
    </div>
  )
}

/** CALX28 — l'export/import du document de conception. INDÉPENDANT de
    l'inventaire des documents : deux boutons toujours visibles, jamais
    gouvernés par `disponible`. Un déclencheur `<input type="file">` masqué +
    `ref.click()` — le patron déjà en usage ailleurs dans le dépôt
    (`EntitesPage.jsx`), jamais un second widget d'upload inventé ici. */
function SectionConception({
  enCours, erreurs, confirmation, onExporter, onImporter,
}) {
  const entreeFichier = useRef(null)
  return (
    <div className="rounded-md border border-border/60 p-3" data-testid="cal-doc-conception">
      <p className="text-sm font-medium text-foreground">Document de conception</p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          variant="outline"
          loading={enCours === 'export'}
          onClick={onExporter}
          data-testid="cal-doc-bouton-export-layout"
        >
          Exporter la conception (JSON)
        </Button>
        <Button
          size="sm"
          variant="outline"
          loading={enCours === 'import'}
          onClick={() => entreeFichier.current?.click()}
          data-testid="cal-doc-bouton-import-layout"
        >
          Importer une conception
        </Button>
        <input
          ref={entreeFichier}
          type="file"
          accept="application/json"
          className="hidden"
          aria-label="Importer un document de conception (JSON)"
          data-testid="cal-doc-fichier-import-layout"
          onChange={(evenement) => {
            const fichier = evenement.target.files?.[0]
            evenement.target.value = '' // même fichier ré-importable deux fois de suite
            if (fichier) onImporter(fichier)
          }}
        />
      </div>
      {confirmation && (
        <p
          role="status"
          className="mt-2 text-xs text-foreground"
          data-testid="cal-doc-conception-confirmation"
        >
          {confirmation}
        </p>
      )}
      <ErreursSortie erreurs={erreurs} />
    </div>
  )
}

/** Libellés FRANÇAIS des genres d'image déposables (`GENRES_IMAGE`,
    `services/images_document.py`) — un genre HORS de cette table (ne
    devrait jamais arriver, l'énumération serveur est FERMÉE) s'affiche tel
    quel plutôt que de faire planter la liste. */
const LIBELLE_GENRE_IMAGE = {
  ombrage: 'Carte de chaleur (ombrage)',
  sankey: 'Diagramme de pertes',
  plan3d: 'Rendu 3D',
}

/** CALX302/CALX320 — les images PRODUITES PAR LE NAVIGATEUR jointes au
    calepinage. Aucun rasteriseur SVG côté serveur (même limite que
    `sorties/planche_png`, CAL175) : la carte de chaleur d'ombrage est rendue
    par l'atelier 3D (`builderApi.renderImageHd(2)`) — sans `builderApi`
    (panneau ouvert hors de la scène 3D), SEUL ce bouton le dit et se
    désactive ; le diagramme de pertes, lui, vient du SVG autonome SERVEUR
    (`diagrammePertesSvg`, CALX308) rastérisé ICI — il ne dépend d'AUCUN
    outil 3D et reste donc toujours actif. Le genre et l'horodatage du
    DERNIER dépôt réussi de CETTE session s'affichent sous les boutons ; la
    liste `images[]` (persistée, CALX291) s'affiche EN PLUS, en dessous —
    « images jointes visibles » (CALX320). */
function SectionImages({
  builderApi, enCours, erreurs, deposeLe, images,
  onDeposerCarteDeChaleur, onDeposerDiagrammePertes,
}) {
  return (
    <div className="rounded-md border border-border/60 p-3" data-testid="cal-doc-images">
      <p className="text-sm font-medium text-foreground">Images de l’atelier</p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          variant="outline"
          loading={enCours === 'ombrage'}
          disabled={!builderApi}
          onClick={onDeposerCarteDeChaleur}
          data-testid="cal-doc-bouton-joindre-ombrage"
        >
          Joindre la carte de chaleur
        </Button>
        <Button
          size="sm"
          variant="outline"
          loading={enCours === 'sankey'}
          onClick={onDeposerDiagrammePertes}
          data-testid="cal-doc-bouton-joindre-pertes"
        >
          Joindre le diagramme de pertes
        </Button>
      </div>
      {!builderApi && (
        <p className="mt-2 text-xs text-muted-foreground" data-testid="cal-doc-images-outil-absent">
          Outil 3D non ouvert — ouvrez la conception pour joindre une carte de chaleur.
        </p>
      )}
      {deposeLe?.genre === 'ombrage' && (
        <p role="status" className="mt-2 text-xs text-foreground" data-testid="cal-doc-images-confirmation">
          Carte de chaleur jointe ({deposeLe.deposeLe}).
        </p>
      )}
      {deposeLe?.genre === 'sankey' && (
        <p role="status" className="mt-2 text-xs text-foreground" data-testid="cal-doc-images-confirmation-pertes">
          Diagramme de pertes joint ({deposeLe.deposeLe}).
        </p>
      )}
      <ErreursSortie erreurs={erreurs} />
      {images?.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-muted-foreground" data-testid="cal-doc-images-jointes">
          {images.map((img) => (
            <li key={`${img.genre}-${img.attachment}`} data-testid={`cal-doc-image-${img.genre}-${img.attachment}`}>
              {LIBELLE_GENRE_IMAGE[img.genre] || img.genre} — {formatDateTime(img.depose_le)}
              {' — '}
              <a
                href={hrefAttachment(img.attachment)}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-primary-text underline"
              >
                Voir
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function PanneauDocuments({ calepinageId, builderApi = null }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.documents(id), id,
    { select: (r) => r.data, errorMessage: 'Inventaire des documents indisponible.' },
  )

  // `code` en téléchargement -> vrai. `code` -> `[{champ,message}]` en refus.
  const [enCours, setEnCours] = useState(null)
  const [erreurs, setErreurs] = useState({})
  // CALX28 — export/import du document de conception : 'export' | 'import' |
  // null, sa liste d'erreurs (`{champ,message}`, `champ` = chemin JSON du
  // premier défaut) et une confirmation de succès.
  const [enCoursConception, setEnCoursConception] = useState(null)
  const [erreurConception, setErreurConception] = useState(null)
  const [confirmationConception, setConfirmationConception] = useState(null)
  // CALX302/CALX320 — dépôt d'image : 'ombrage' | 'sankey' | null pendant
  // l'appel, ses erreurs (`{champ,message}`) et le dernier dépôt RÉUSSI de
  // cette session (`{genre, deposeLe}`).
  const [enCoursImage, setEnCoursImage] = useState(null)
  const [erreursImage, setErreursImage] = useState(null)
  const [derniereImageDeposee, setDerniereImageDeposee] = useState(null)

  const parCode = useMemo(() => {
    const carte = new Map()
    for (const entree of data?.documents || []) carte.set(entree.code, entree)
    return carte
  }, [data])

  async function telecharger(code) {
    const entree = parCode.get(code)
    if (!entree) return
    setErreurs((precedent) => ({ ...precedent, [code]: null }))
    setEnCours(code)
    try {
      const reponse = await calepinageApi.calepinages.telechargerDocument(entree.endpoint)
      downloadBlob(reponse.data, filenameFromResponse(reponse, code))
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreurs((precedent) => ({ ...precedent, [code]: details }))
    } finally {
      setEnCours(null)
    }
  }

  // CALX28 — exporte `roof_layout` TEL QUEL, en fichier JSON téléchargé (le
  // MÊME helper `downloadBlob` que tous les autres boutons de ce panneau :
  // jamais un second `URL.createObjectURL`).
  async function exporterConception() {
    setErreurConception(null)
    setConfirmationConception(null)
    setEnCoursConception('export')
    try {
      const reponse = await calepinageApi.calepinages.exporterConception(id)
      const contenu = JSON.stringify(reponse.data, null, 2)
      downloadBlob(
        new Blob([contenu], { type: 'application/json' }),
        `conception-calepinage-${id}.json`,
      )
    } catch (erreur) {
      setErreurConception(await erreurDeTelechargement(erreur))
    } finally {
      setEnCoursConception(null)
    }
  }

  // CALX28 — importe un document choisi par l'utilisateur. VALIDATION
  // STRICTE côté SERVEUR (jamais rejouée ici) : un document hors schéma
  // refuse en NOMMANT le CHEMIN JSON du premier défaut (`champ` —
  // `services/io_layout.py::valider_document`, `erreur.absolute_path`),
  // affiché ligne par ligne par `ErreursSortie`. Un JSON illisible (avant
  // même d'atteindre le serveur) l'est tout autant, sous le même régime.
  // AUCUN ÉTAT DE CE PANNEAU N'EST ÉCRASÉ tant que le serveur n'a pas
  // confirmé : sur refus, ni `confirmationConception` ni la sélection de
  // sortie précédente ne bougent.
  async function importerConception(fichier) {
    setErreurConception(null)
    setConfirmationConception(null)
    setEnCoursConception('import')
    try {
      let document
      try {
        document = JSON.parse(await fichier.text())
      } catch {
        setErreurConception([{ champ: '<racine>', message: 'Le fichier n’est pas un JSON valide.' }])
        return
      }
      const reponse = await calepinageApi.calepinages.importerConception(id, document)
      setConfirmationConception(reponse.data.inchange
        ? 'Conception importée — identique à celle déjà enregistrée (empreinte inchangée).'
        : 'Conception importée et enregistrée.')
    } catch (erreur) {
      setErreurConception(await erreurDeTelechargement(erreur))
    } finally {
      setEnCoursConception(null)
    }
  }

  // CALX302 — joint la carte de chaleur ACTIVE de l'atelier 3D. Jamais
  // d'exception non attrapée : `deposerCarteDeChaleur` rend toujours
  // `{ok, motif, erreurs?}`, régime IDENTIQUE aux autres boutons du panneau.
  async function joindreCarteDeChaleur() {
    setErreursImage(null)
    setEnCoursImage('ombrage')
    try {
      const resultat = await deposerCarteDeChaleur(id, builderApi)
      if (resultat.ok) {
        setDerniereImageDeposee({ genre: resultat.genre, deposeLe: resultat.deposeLe })
      } else {
        setErreursImage(resultat.erreurs || [{ champ: '', message: resultat.motif }])
      }
    } finally {
      setEnCoursImage(null)
    }
  }

  // CALX320 — joint le diagramme de pertes (SVG serveur rastérisé ICI). MÊME
  // régime que `joindreCarteDeChaleur` ci-dessus — `deposerDiagrammeDePertes`
  // rend toujours `{ok, motif, erreurs?}`, jamais une exception non attrapée.
  async function joindreDiagrammeDePertes() {
    setErreursImage(null)
    setEnCoursImage('sankey')
    try {
      const resultat = await deposerDiagrammeDePertes(id)
      if (resultat.ok) {
        setDerniereImageDeposee({ genre: resultat.genre, deposeLe: resultat.deposeLe })
      } else {
        setErreursImage(resultat.erreurs || [{ champ: '', message: resultat.motif }])
      }
    } finally {
      setEnCoursImage(null)
    }
  }

  if (loading) return <Spinner />
  if (error) {
    return <p className="text-sm text-destructive" data-testid="cal-doc-erreur">{error}</p>
  }

  const documents = data?.documents || []

  return (
    <Card className="flex flex-col gap-3 p-4" data-testid="cal-doc-panneau">
      <h2 className="text-base font-semibold">Documents</h2>
      {data?.layout_hash && (
        <p className="text-xs text-muted-foreground" data-testid="cal-doc-empreinte">
          Empreinte de la conception : <code>{data.layout_hash.slice(0, 12)}</code>
          {data.version_moteur ? ` · moteur ${data.version_moteur}` : ''}
        </p>
      )}
      {documents.length === 0 && (
        <p className="text-sm text-muted-foreground" data-testid="cal-doc-vide">
          Aucun document disponible pour l’instant.
        </p>
      )}
      {documents.map((entree) => (
        <CarteDocument
          key={entree.code}
          entree={entree}
          calepinageId={id}
          enCours={enCours === entree.code}
          onTelecharger={() => telecharger(entree.code)}
          erreurs={erreurs[entree.code]}
        />
      ))}
      {/* CALX28 — HORS inventaire (aucun document ne le déclare) : toujours
          visible, jamais gouverné par `disponible`. */}
      <SectionConception
        enCours={enCoursConception}
        erreurs={erreurConception}
        confirmation={confirmationConception}
        onExporter={exporterConception}
        onImporter={importerConception}
      />
      {/* CALX302/CALX320 — HORS inventaire, comme `SectionConception`
          ci-dessus. */}
      <SectionImages
        builderApi={builderApi}
        enCours={enCoursImage}
        erreurs={erreursImage}
        deposeLe={derniereImageDeposee}
        images={data?.images}
        onDeposerCarteDeChaleur={joindreCarteDeChaleur}
        onDeposerDiagrammePertes={joindreDiagrammeDePertes}
      />
    </Card>
  )
}
