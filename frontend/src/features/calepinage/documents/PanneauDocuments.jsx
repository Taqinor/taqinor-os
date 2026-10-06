import { useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { downloadBlob, filenameFromResponse } from '../../../utils/downloadBlob'
import { formatDateTime } from '../../../lib/format'
import { Button, Card, Spinner } from '../../../ui'
import { PARAM_ONGLET, ONGLETS } from '../atelier/onglets'
import { deposerCarteDeChaleur, svgTexteEnPng } from './deposerImage'

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

   LE LIEN VERS L'ONGLET (ACAL223). `manque[].ou_saisir` est une phrase
   FRANÇAISE déjà écrite par le serveur ; `manque[].onglet` est la CLÉ de
   registre (`atelier/onglets.js`) que le serveur NOMME, ou null (geste dans
   l'atelier 3D / Réglages). Seule une clé inscrite devient un lien
   `?onglet=<clé>` ; sinon le texte reste simple. Plus aucune recherche du
   libellé d'un onglet dans la phrase.

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

   SectionConception (CALX28) et SectionImages (CALX302 ; ACAL225 : un seul
   bouton, la carte de chaleur — le rapport embarque déjà le diagramme de
   pertes serveur) restent HORS inventaire —
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

/** La liste `manque[]` d'un document indisponible — chaque entrée NOMME son
    champ et son libellé ; `ou_saisir` devient un LIEN vers l'onglet du
    registre quand le texte en cite un qui existe réellement (voir
    `ongletCiteDans`), sinon reste un texte simple. */
function ListeManque({ manque, calepinageId, code }) {
  if (!manque?.length) return null
  return (
    <ul className="mt-2 space-y-1 text-xs text-muted-foreground" data-testid={`cal-doc-manque-${code}`}>
      {manque.map((m) => {
        // ACAL14/ACAL223 — le SERVEUR nomme l'onglet (`manque[].onglet`, clé du
        // registre, ou null : geste hors registre) ; plus aucune devinette dans
        // la phrase `ou_saisir`.
        const onglet = ONGLETS.find((o) => o.cle === m.onglet) ?? null
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
        {version.perimee === true ? ' — périmée' : version.perimee === false ? ' — à jour' : ''}
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

/** Le résultat d'une carte de méthode POST (dossier de fin de chantier) :
    pièces, pages, signalements et lien vers la GED — tels que servis. */
function ResultatPost({ resultat }) {
  if (!resultat) return null
  return (
    <div className="mt-2 text-xs text-foreground" data-testid="cal-doc-post-resultat">
      <p>
        {resultat.nom ? <strong>{resultat.nom}</strong> : 'Dossier composé'}
        {' — '}
        <Link to="/ged" className="underline" data-testid="cal-doc-post-lien-ged">
          Ouvrir dans la GED
        </Link>
      </p>
      {resultat.pieces?.length > 0 && (
        <ul className="mt-1 list-disc pl-4 text-muted-foreground" data-testid="cal-doc-post-pieces">
          {resultat.pieces.map((piece) => (
            <li key={piece.code}>{piece.libelle} — {piece.pages} p.</li>
          ))}
        </ul>
      )}
      {resultat.signalements?.length > 0 && (
        <ul className="mt-1 list-disc pl-4 text-muted-foreground" data-testid="cal-doc-post-signalements">
          {resultat.signalements.map((signalement) => (
            <li key={signalement}>{signalement}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Une carte de document (contrat `calepinage_documents.json`) : libellé,
    format, bouton de téléchargement (actif seulement si `disponible`), le
    motif SOUS le bouton quand il ne l'est pas — suivi de la liste `manque[]`
    NOMMÉE (CALX321) — puis les versions déjà produites (CALX322), qu'il
    soit disponible ou non (une pièce redevenue indisponible garde son
    historique). ACAL223 : sélecteur de langue (cartes `langues` à deux
    entrées), Remettre (versionne), Aperçu HTML, DXF, méthode POST. */
function CarteDocument({
  entree, calepinageId, enCours, onTelecharger, erreurs,
  langue, onLangue, onRemettre, enRemise, onApercu, onAutreFormat, resultatPost,
}) {
  const estPost = entree.methode === 'POST'
  const langues = entree.langues || []
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
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!entree.disponible}
            loading={enCours}
            onClick={onTelecharger}
            data-testid={`cal-doc-bouton-${entree.code}`}
          >
            {estPost ? 'Composer' : 'Télécharger'}
          </Button>
          {entree.apercu && (
            <Button
              size="sm"
              variant="outline"
              disabled={!entree.disponible}
              onClick={onApercu}
              data-testid={`cal-doc-apercu-${entree.code}`}
            >
              Aperçu
            </Button>
          )}
          {entree.disponible && !estPost && (
            <Button
              size="sm"
              variant="outline"
              loading={enRemise}
              onClick={onRemettre}
              data-testid={`cal-doc-remettre-${entree.code}`}
            >
              Remettre
            </Button>
          )}
          {(entree.autres_formats || []).map((f) => (
            <Button
              key={f.format}
              size="sm"
              variant="outline"
              disabled={!entree.disponible}
              onClick={() => onAutreFormat(f)}
              data-testid={`cal-doc-autre-format-${entree.code}-${f.format}`}
            >
              Télécharger le {f.format.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>
      {langues.length > 1 ? (
        <label className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          Langue du document
          <select
            value={langue}
            onChange={(e) => onLangue(e.target.value)}
            className="rounded border border-border bg-background px-1 py-0.5 text-foreground"
            data-testid={`cal-doc-langue-${entree.code}`}
          >
            {langues.map((l) => <option key={l} value={l}>{l.toUpperCase()}</option>)}
          </select>
        </label>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground" data-testid={`cal-doc-langue-fr-seul-${entree.code}`}>
          Ce document n’existe qu’en français.
        </p>
      )}
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
      <ResultatPost resultat={resultatPost} />
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
}

/** CALX302/CALX320 — les images PRODUITES PAR LE NAVIGATEUR jointes au
    calepinage. Aucun rasteriseur SVG côté serveur (même limite que
    `sorties/planche_png`, CAL175) : la carte de chaleur d'ombrage est rendue
    par l'atelier 3D (`builderApi.renderImageHd(2)`) — sans `builderApi`
    (panneau ouvert hors de la scène 3D), SEUL ce bouton le dit et se
    désactive. ACAL225 : plus de bouton « diagramme de pertes » (le rapport
    embarque le SVG serveur ; `sankey` est refusé en 400). Le genre et l'horodatage du
    DERNIER dépôt réussi de CETTE session s'affichent sous les boutons ; la
    liste `images[]` (persistée, CALX291) s'affiche EN PLUS, en dessous —
    « images jointes visibles » (CALX320). */
function SectionImages({
  builderApi, enCours, erreurs, deposeLe, images,
  onDeposerCarteDeChaleur,
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
      <ErreursSortie erreurs={erreurs} />
      {images?.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-muted-foreground" data-testid="cal-doc-images-jointes">
          {images.map((img) => (
            <li key={`${img.genre}-${img.attachment}`} data-testid={`cal-doc-image-${img.genre}-${img.attachment}`}>
              {LIBELLE_GENRE_IMAGE[img.genre] || img.genre} — {formatDateTime(img.depose_le)}
              {img.perimee === true && (
                <>
                  {' — '}
                  <span
                    className="font-medium text-destructive"
                    data-testid={`cal-doc-image-perimee-${img.genre}-${img.attachment}`}
                  >
                    Périmée (conception modifiée)
                  </span>
                  {' — Rejoindre depuis l’atelier'}
                </>
              )}
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

/** ACAL228 — les cinq PDF du registre de remise (`REGISTRE_REMISE`,
    `views/remise_document.py`) proposent « Remettre » ; les autres sorties
    se téléchargent seulement. */
const SORTIES_REMETTABLES = new Set([
  'planche_pdf', 'plan_pose_pdf', 'plan_toiture_pdf', 'plan_masse_pdf', 'note_calcul_pdf',
])

/** ACAL228 — la seconde section « Plans et exports » : l'inventaire
    `sorties/` (CALX19), DISTINCT de `documents/` (D-ACAL-20). Chaque entrée
    servie est affichée telle quelle (libellé, format, motif) ; l'`endpoint`
    vient de l'entrée, jamais reconstruit. */
function SectionSorties({
  sorties, enCours, enRemise, erreurs, resultatPack, onTelecharger, onRemettre,
}) {
  if (!sorties?.length) return null
  return (
    <div className="rounded-md border border-border/60 p-3" data-testid="cal-doc-sorties">
      <p className="text-sm font-medium text-foreground">Plans et exports</p>
      <div className="mt-2 space-y-2">
        {sorties.map((sortie) => {
          const pack = sortie.code === 'pack_technique'
          const rendu3d = sortie.code === 'image_3d'
          return (
            <div
              key={sortie.code}
              className="rounded border border-border/40 p-2"
              data-testid={`cal-doc-sorties-carte-${sortie.code}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm text-foreground">{sortie.libelle}</p>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{sortie.format}</p>
                </div>
                {!rendu3d && (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!sortie.disponible}
                      loading={enCours === sortie.code}
                      onClick={() => onTelecharger(sortie)}
                      data-testid={`cal-doc-bouton-${sortie.code}`}
                    >
                      {pack ? 'Composer le dossier technique' : 'Télécharger'}
                    </Button>
                    {sortie.disponible && SORTIES_REMETTABLES.has(sortie.code) && (
                      <Button
                        size="sm"
                        variant="outline"
                        loading={enRemise === sortie.code}
                        onClick={() => onRemettre(sortie)}
                        data-testid={`cal-doc-remettre-${sortie.code}`}
                      >
                        Remettre
                      </Button>
                    )}
                  </div>
                )}
              </div>
              {!sortie.disponible && sortie.motif_indisponible && (
                <p
                  className="mt-1 text-xs text-muted-foreground"
                  data-testid={`cal-doc-sorties-motif-${sortie.code}`}
                >
                  {sortie.motif_indisponible}
                </p>
              )}
              {pack && <ResultatPost resultat={resultatPack} />}
              <ErreursSortie erreurs={erreurs[sortie.code]} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function PanneauDocuments({ calepinageId, builderApi = null, onRecharger = null }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.documents(id), id,
    { select: (r) => r.data, errorMessage: 'Inventaire des documents indisponible.' },
  )

  // ACAL228 — l'inventaire `sorties/` (distinct de `documents/`). Une erreur
  // de ce second inventaire n'abat jamais le panneau : la section manque.
  const { data: inventaireSorties } = useResource(
    () => calepinageApi.calepinages.sorties(id), id,
    { select: (r) => r?.data ?? null },
  )
  const [enCoursSortie, setEnCoursSortie] = useState(null)
  const [enRemiseSortie, setEnRemiseSortie] = useState(null)
  const [erreursSorties, setErreursSorties] = useState({})
  const [resultatPack, setResultatPack] = useState(null)

  // `code` en téléchargement -> vrai. `code` -> `[{champ,message}]` en refus.
  const [enCours, setEnCours] = useState(null)
  const [erreurs, setErreurs] = useState({})
  // CALX28 — export/import du document de conception : 'export' | 'import' |
  // null, sa liste d'erreurs (`{champ,message}`, `champ` = chemin JSON du
  // premier défaut) et une confirmation de succès.
  const [enCoursConception, setEnCoursConception] = useState(null)
  const [erreurConception, setErreurConception] = useState(null)
  const [confirmationConception, setConfirmationConception] = useState(null)
  // CALX302/CALX320 — dépôt d'image : 'ombrage' | null pendant
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

  // ACAL223 — langue choisie par carte (état d'écran NON persisté : le défaut
  // est `data.langue` servi), résultat d'une carte POST, remise en cours.
  const [langues, setLangues] = useState({})
  const [resultatsPost, setResultatsPost] = useState({})
  const [enRemise, setEnRemise] = useState(null)

  /** La langue d'une carte : une carte à deux langues suit le choix puis
      `data.langue` ; une carte française seule vaut toujours `fr`. */
  function langueDe(entree) {
    const admises = entree.langues || []
    if (admises.length < 2) return admises[0] || 'fr'
    if (langues[entree.code]) return langues[entree.code]
    return admises.includes(data?.langue) ? data.langue : admises[0]
  }

  /** `{langue}` transmis seulement aux cartes qui en proposent plusieurs. */
  function paramsDe(entree) {
    return (entree.langues || []).length > 1 ? { langue: langueDe(entree) } : undefined
  }

  async function telecharger(code) {
    const entree = parCode.get(code)
    if (!entree) return
    setErreurs((precedent) => ({ ...precedent, [code]: null }))
    setEnCours(code)
    try {
      const params = paramsDe(entree)
      if (entree.methode === 'POST') {
        const reponse = await calepinageApi.calepinages.declencherDocument(entree.endpoint, params)
        setResultatsPost((precedent) => ({ ...precedent, [code]: reponse.data }))
      } else {
        const reponse = params
          ? await calepinageApi.calepinages.telechargerDocument(entree.endpoint, params)
          : await calepinageApi.calepinages.telechargerDocument(entree.endpoint)
        downloadBlob(reponse.data, filenameFromResponse(reponse, code))
      }
      await refetch()
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreurs((precedent) => ({ ...precedent, [code]: details }))
    } finally {
      setEnCours(null)
    }
  }

  // ACAL223 — l'autre format publié (`autres_formats[]`, ex. le DXF du plan de
  // câblage) : l'endpoint est celui du serveur, tel quel.
  async function telechargerAutreFormat(code, format) {
    setErreurs((precedent) => ({ ...precedent, [code]: null }))
    try {
      const reponse = await calepinageApi.calepinages.telechargerDocument(format.endpoint)
      downloadBlob(reponse.data, filenameFromResponse(reponse, `${code}.${format.format}`))
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreurs((precedent) => ({ ...precedent, [code]: details }))
    }
  }

  // ACAL223 — l'aperçu HTML exact de la pièce, ouvert dans un nouvel onglet.
  async function apercu(code) {
    const entree = parCode.get(code)
    if (!entree) return
    setErreurs((precedent) => ({ ...precedent, [code]: null }))
    try {
      const reponse = await calepinageApi.calepinages.apercuDocument(
        id, code, { langue: langueDe(entree) })
      const url = URL.createObjectURL(new Blob([reponse.data], { type: 'text/html' }))
      window.open(url, '_blank', 'noopener')
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreurs((precedent) => ({ ...precedent, [code]: details }))
    }
  }

  // ACAL223 — la REMISE explicite (POST remettre-document) : crée la version
  // « Dernière version vN » ; l'inventaire est relu ensuite.
  async function remettre(code) {
    const entree = parCode.get(code)
    if (!entree) return
    setErreurs((precedent) => ({ ...precedent, [code]: null }))
    setEnRemise(code)
    try {
      await calepinageApi.calepinages.remettreDocument(id, { code, langue: langueDe(entree) })
      await refetch()
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreurs((precedent) => ({ ...precedent, [code]: details }))
    } finally {
      setEnRemise(null)
    }
  }

  // ACAL228 — une sortie de `sorties/` : l'endpoint servi tel quel ; la
  // planche PNG rastérise `planche.svg` ICI (aucun rasteriseur serveur,
  // D-CAL10) ; le dossier technique est un POST qui range en GED.
  async function telechargerSortie(sortie) {
    const code = sortie.code
    setErreursSorties((precedent) => ({ ...precedent, [code]: null }))
    setEnCoursSortie(code)
    try {
      if (code === 'pack_technique') {
        const reponse = await calepinageApi.calepinages.composerPackTechnique(id)
        setResultatPack(reponse.data)
      } else if (code === 'planche_png') {
        const reponse = await calepinageApi.calepinages.telechargerSortie(sortie.endpoint)
        const png = await svgTexteEnPng(await reponse.data.text())
        downloadBlob(png, `planche-calepinage-${id}.png`)
      } else {
        const reponse = await calepinageApi.calepinages.telechargerSortie(sortie.endpoint)
        downloadBlob(reponse.data, filenameFromResponse(reponse, code))
      }
    } catch (erreur) {
      const details = erreur?.response ? await erreurDeTelechargement(erreur)
        : [{ champ: '', message: erreur?.message || 'Opération impossible sur ce navigateur.' }]
      setErreursSorties((precedent) => ({ ...precedent, [code]: details }))
    } finally {
      setEnCoursSortie(null)
    }
  }

  async function remettreSortie(sortie) {
    const code = sortie.code
    setErreursSorties((precedent) => ({ ...precedent, [code]: null }))
    setEnRemiseSortie(code)
    try {
      await calepinageApi.calepinages.remettreDocument(id, { code })
      await refetch()
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreursSorties((precedent) => ({ ...precedent, [code]: details }))
    } finally {
      setEnRemiseSortie(null)
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
      // ACAL23 — la conception SERVEUR vient de changer : la scène 3D la relit
      // (sinon « Enregistrer le calepinage » republierait la copie d'avant).
      if (!reponse.data.inchange && typeof onRecharger === 'function') await onRecharger()
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
        await refetch() // ACAL223 — images[] à jour sans recharger la page
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
          langue={langueDe(entree)}
          onLangue={(l) => setLangues((precedent) => ({ ...precedent, [entree.code]: l }))}
          onRemettre={() => remettre(entree.code)}
          enRemise={enRemise === entree.code}
          onApercu={() => apercu(entree.code)}
          onAutreFormat={(format) => telechargerAutreFormat(entree.code, format)}
          resultatPost={resultatsPost[entree.code]}
        />
      ))}
      {/* ACAL228 — la section « Plans et exports » : l'inventaire `sorties/`. */}
      <SectionSorties
        sorties={inventaireSorties?.sorties}
        enCours={enCoursSortie}
        enRemise={enRemiseSortie}
        erreurs={erreursSorties}
        resultatPack={resultatPack}
        onTelecharger={telechargerSortie}
        onRemettre={remettreSortie}
      />
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
      />
    </Card>
  )
}
