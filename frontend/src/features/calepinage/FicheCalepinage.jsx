import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   CAL17 (moitié écran) — LA FICHE D'UN CALEPINAGE, en un seul appel.
   ----------------------------------------------------------------------------
   La moitié SERVEUR existe (`views/calepinages.py::detail_calepinage`, forme
   figée par `contract_samples/calepinage_detail.json`, `forme_serveur:
   complete`). Sans cette moitié-ci, l'agrégat serait servi et lu par PERSONNE :
   l'écran afficherait le statut et ignorerait les dix-neuf autres clés — le
   commercial ne saurait ni quelle version il regarde, ni combien de variantes
   attendent d'être simulées, ni qui en est responsable.

   CE COMPOSANT NE CALCULE RIEN. Chaque valeur vient de l'agrégat, telle quelle.
   Le test jumeau PARCOURT les clés du contrat et exige un rendu pour CHACUNE :
   le jour où le serveur en ajoute une, l'écran rougit au lieu de l'ignorer en
   silence pendant des mois.

   DISCIPLINE DU NULL, celle du contrat lui-même : une grandeur NON MESURÉE vaut
   `null`, jamais `0` — publier un zéro ferait lire « aucune version » là où
   rien n'a encore été enregistré. L'écran rend donc « — », et n'écrit JAMAIS un
   chiffre à la place de l'inconnu.
   ========================================================================== */

/** Une valeur du serveur, ou le tiret de l'inconnu. Jamais un zéro de repli. */
function texte(brut) {
  if (brut === null || brut === undefined || brut === '') return '—'
  return String(brut)
}

/** Un horodatage ISO tel que le serveur le sert, en date lisible. */
function moment(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? String(iso) : formatDateTime(d)
}

function Champ({ cle, label, children }) {
  return (
    <div data-testid={`cal-fiche-${cle}`}>
      <dt className="tech-label text-lune-faint">{label}</dt>
      <dd className="mt-0.5 text-sm text-white">{children}</dd>
    </div>
  )
}

/** Une personne de l'agrégat (`{id, nom_complet}`) — ou l'inconnu. */
function personne(p) {
  return texte(p?.nom_complet)
}

/* ============================================================================
   CALX26 — ARCHIVER / RESTAURER, branchés sur les portes QUI EXISTENT.
   ----------------------------------------------------------------------------
   `views/archivage.py` sert `POST archiver/` et `POST restaurer-corbeille/`
   (CAL208, corbeille plateforme `apps.trash`) depuis leur livraison, et AUCUN
   écran ne les appelait : une porte sans consommateur se périme en silence.

   POURQUOI L'ÉTAT ARCHIVÉ EST LOCAL ICI, ET PAS LU DE L'AGRÉGAT.
   `selectors.appliquer_filtres_liste` EXCLUT les archivés par défaut (CAL208)
   et `retrieve` passe par `get_queryset()` : un calepinage archivé répond 404
   au détail. L'agrégat CAL17 (23 clés) ne publie donc aucun drapeau d'archive
   — en inventer un ici serait un chiffre inventé. L'écran retient ce QU'IL A
   FAIT : la réponse des deux actions porte `archive: true|false`, et c'est
   elle, et elle seule, qui bascule le bandeau.
   ========================================================================== */

/** Le refus du SERVEUR, tel quel, et le champ qu'il NOMME.
 *
 * Les deux actions rendent `{<champ>: "<motif>"}` (400) ou
 * `{detail: "…"}` (404) : on garde le motif mot pour mot et on retombe sur le
 * geste concerné quand le serveur n'a nommé aucun champ. Jamais un
 * « non enregistré » générique (règle fondateur du 08/09/2026).
 */
function refusServeur(erreur, geste) {
  const corps = erreur?.response?.data
  if (typeof corps === 'string' && corps.trim()) {
    return { geste, message: corps.trim() }
  }
  if (corps && typeof corps === 'object') {
    const entree = Object.entries(corps)[0]
    if (entree) {
      const brut = Array.isArray(entree[1]) ? entree[1].join(' ') : entree[1]
      if (brut) return { geste, message: String(brut) }
    }
  }
  return {
    geste,
    message: "Le serveur n’a rendu aucun motif : rien n’a été modifié.",
  }
}

const LIBELLE_GESTE = { archiver: 'Archiver', restaurer: 'Restaurer' }

/* ============================================================================
   CALX33 — RENOMMER UN CALEPINAGE APRÈS SA CRÉATION.
   ----------------------------------------------------------------------------
   `CalepinageNouveau.jsx` posait le nom UNE fois, à la création, et
   `calepinages.update` (fabrique CRUD, CAL33) n'avait AUCUN appelant : un nom
   mal tapé restait mal tapé pour la vie du calepinage.

   LE CHAMP SERVEUR S'APPELLE `titre`, LA CLÉ DE L'AGRÉGAT `nom`. Le détail
   CAL17 publie `nom` (`views/calepinages.py:823` le dérive de `titre`) mais
   le sérialiseur d'écriture (`CalepinageSerializer.Meta.fields`) ne connaît
   que `titre` : le PATCH part donc sur `titre`, et le refus qui revient le
   nomme sous CE nom — on le rend sous le champ « Nom », jamais ailleurs.
   ========================================================================== */

//: Le nom du champ d'ÉCRITURE côté serveur (jamais `nom`, qui est la clé de
//: lecture de l'agrégat).
const CHAMP_NOM = 'titre'

/** Le refus d'un PATCH DRF, ramené au message du champ demandé. */
function refusChamp(erreur, champ) {
  const corps = erreur?.response?.data
  if (typeof corps === 'string' && corps.trim()) return corps.trim()
  if (corps && typeof corps === 'object') {
    const brut = corps[champ] ?? corps.detail ?? Object.values(corps)[0]
    const message = Array.isArray(brut) ? brut.join(' ') : brut
    if (message) return String(message)
  }
  return "Le serveur n’a rendu aucun motif : rien n’a été enregistré."
}

export default function FicheCalepinage({ detail }) {
  // CALX26 — la confirmation en DEUX TEMPS : un premier clic explique ce que
  // l'archivage fait, le second l'exécute. Jamais un archivage au clic seul.
  const [confirmation, setConfirmation] = useState(false)
  const [archive, setArchive] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)
  // CALX33 — le nom éditable sur place. `nomLocal` reste `null` tant que rien
  // n'a été enregistré : l'écran affiche alors le nom SERVI, jamais une copie.
  const [edition, setEdition] = useState(false)
  const [saisie, setSaisie] = useState('')
  const [nomLocal, setNomLocal] = useState(null)
  const [refusNom, setRefusNom] = useState(null)
  /* CALX42 — le drapeau « modèle ». `null` = INCONNU, et tant qu'il l'est
     aucune bascule n'est proposée : l'agrégat CAL17 ne publie pas ce drapeau
     (il vit sur un `records.Tag`, CAL199), donc l'écran le LIT à la seule
     source qui existe — `GET calepinages/modeles/` — au lieu d'en supposer
     un état. */
  const [estModele, setEstModele] = useState(null)
  const [refusModele, setRefusModele] = useState(null)
  /* CALX35 — la duplication. La boîte de confirmation ÉNUMÈRE ce que la copie
     laisse derrière elle AVANT de dupliquer : OpenSolar publie la même liste
     pour sa duplication de projet, et c'est la seule façon qu'un commercial
     ne découvre pas après coup que l'historique n'a pas suivi. */
  const [confirmationCopie, setConfirmationCopie] = useState(false)
  const [avecVariantes, setAvecVariantes] = useState(true)
  const [refusCopie, setRefusCopie] = useState(null)
  const identifiant = detail?.id ?? null
  const naviguer = useNavigate()

  useEffect(() => {
    if (!identifiant) return undefined
    const lire = calepinageApi?.calepinages?.modeles
    if (typeof lire !== 'function') return undefined
    let annule = false
    Promise.resolve(lire())
      .then((res) => {
        if (annule) return
        const brut = res?.data
        const liste = Array.isArray(brut) ? brut : (brut?.results ?? [])
        setEstModele(liste.some((ligne) => ligne?.id === identifiant))
      })
      // Drapeau NON LU : il reste inconnu, et aucune bascule n'est offerte.
      .catch(() => { if (!annule) setEstModele(null) })
    return () => { annule = true }
  }, [identifiant])

  if (!detail) return null

  const versions = detail.versions ?? {}
  const variantes = detail.variantes ?? {}
  const image = detail.image ?? {}
  const geo = detail.contexte_geographique ?? {}
  const permissions = detail.permissions ?? {}

  // Les gestes AUTORISÉS, nommés par le serveur. On liste ce qui est permis :
  // une permission refusée n'a pas à être annoncée comme une interdiction.
  const gestes = [
    permissions.peut_modifier ? 'modifier' : null,
    permissions.peut_retenir_variante ? 'retenir une variante' : null,
    permissions.peut_supprimer ? 'supprimer' : null,
  ].filter(Boolean)

  // `peut_modifier` EST `calepinage_gerer` côté serveur
  // (`views/calepinages.py::_permissions`) — la permission que les deux
  // actions exigent (`PeutGererCalepinage`). Sans elle, aucun geste d'écriture
  // n'est proposé : une permission refusée ne s'annonce pas en bouton grisé.
  const peutGerer = permissions.peut_modifier === true

  const lancerArchivage = async () => {
    if (!confirmation) {
      setRefus(null)
      setConfirmation(true)
      return
    }
    setEnCours(true)
    setRefus(null)
    try {
      await calepinageApi.calepinages.archiver(detail.id)
      setConfirmation(false)
      setArchive(true)
    } catch (erreur) {
      setRefus(refusServeur(erreur, 'archiver'))
    } finally {
      setEnCours(false)
    }
  }

  const lancerRestauration = async () => {
    setEnCours(true)
    setRefus(null)
    try {
      await calepinageApi.calepinages.restaurerCorbeille(detail.id)
      setArchive(false)
    } catch (erreur) {
      setRefus(refusServeur(erreur, 'restaurer'))
    } finally {
      setEnCours(false)
    }
  }

  const nomAffiche = nomLocal === null ? detail.nom : nomLocal

  const ouvrirEdition = () => {
    setRefusNom(null)
    setSaisie(nomAffiche ?? '')
    setEdition(true)
  }

  const enregistrerNom = async () => {
    const propre = (saisie || '').trim()
    // REFUS AVANT ENVOI : un nom vide n'est pas une requête à faire au
    // serveur, c'est une saisie à corriger — et le champ le dit lui-même.
    if (!propre) {
      setRefusNom('Le nom ne peut pas être vide : saisissez-en un, ou annulez.')
      return
    }
    setEnCours(true)
    setRefusNom(null)
    try {
      await calepinageApi.calepinages.update(detail.id, { [CHAMP_NOM]: propre })
      setNomLocal(propre)
      setEdition(false)
    } catch (erreur) {
      setRefusNom(refusChamp(erreur, CHAMP_NOM))
    } finally {
      setEnCours(false)
    }
  }

  const basculerModele = async () => {
    setEnCours(true)
    setRefusModele(null)
    const porte = estModele
      ? calepinageApi.calepinages.demarquerModele
      : calepinageApi.calepinages.marquerModele
    try {
      await porte(detail.id)
      setEstModele(!estModele)
    } catch (erreur) {
      setRefusModele(refusChamp(erreur, 'modele'))
    } finally {
      setEnCours(false)
    }
  }

  const lancerDuplication = async () => {
    setEnCours(true)
    setRefusCopie(null)
    try {
      const res = await calepinageApi.calepinages.dupliquer(
        detail.id, { avec_variantes: avecVariantes })
      const copie = res?.data?.calepinage ?? null
      setConfirmationCopie(false)
      // « Le bouton ouvre la copie » : l'atelier du NOUVEAU calepinage.
      if (copie) naviguer(`/calepinage/${copie}`)
    } catch (erreur) {
      setRefusCopie(refusChamp(erreur, 'calepinage'))
    } finally {
      setEnCours(false)
    }
  }

  const styleBouton = 'inline-flex items-center gap-2 border border-brass-400 '
    + 'px-5 py-3 text-base font-bold text-brass-300 '
    + 'disabled:cursor-not-allowed disabled:opacity-60'

  return (
    <div data-testid="cal-fiche-bloc">
      {/* LE BANDEAU QUI COUPE LES GESTES D'ÉCRITURE. Tant qu'il est là, le
          seul bouton offert est « Restaurer ». */}
      {archive && (
        <div className="mt-5 border border-brass-400/40 p-3"
          data-testid="cal-fiche-bandeau-archive" role="status">
          <p className="tech-label text-brass-300">Calepinage archivé</p>
          <p className="mt-1 text-sm text-lune-soft">
            Ce calepinage est dans la corbeille : il ne figure plus dans les
            listes et aucune modification n’est possible. La restauration le
            remet à l’identique.
          </p>
        </div>
      )}

      {/* CALX33 — LE BANDEAU QUI NOMME LE CHAMP FAUTIF. Il ne remplace pas le
          message sous le champ : il le double en haut de la fiche, pour qu'un
          refus ne passe jamais inaperçu. */}
      {refusNom && (
        <div className="mt-5 border border-alert-300/40 p-3"
          data-testid="cal-fiche-bandeau-nom" role="alert">
          <p className="tech-label text-alert-300">Nom</p>
          <p className="mt-1 text-sm text-alert-300">{refusNom}</p>
        </div>
      )}

      {peutGerer && (
        <div className="mt-5 flex flex-wrap items-start gap-3"
          data-testid="cal-fiche-actions">
          {archive ? (
            <button type="button" className={styleBouton} disabled={enCours}
              data-testid="cal-fiche-restaurer" onClick={lancerRestauration}>
              Restaurer
            </button>
          ) : (
            <>
              <button type="button" className={styleBouton} disabled={enCours}
                data-testid="cal-fiche-archiver" onClick={lancerArchivage}>
                {confirmation ? 'Confirmer l’archivage' : 'Archiver'}
              </button>
              {confirmation && (
                <button type="button" disabled={enCours}
                  className="text-sm text-lune-soft underline"
                  data-testid="cal-fiche-archiver-annuler"
                  onClick={() => { setConfirmation(false) }}>
                  Annuler
                </button>
              )}
            </>
          )}

          {/* CALX35 — DUPLIQUER, après une confirmation qui ÉNUMÈRE. */}
          {!archive && (
            <button type="button" className={styleBouton} disabled={enCours}
              data-testid="cal-fiche-dupliquer"
              onClick={() => { setRefusCopie(null); setConfirmationCopie(true) }}>
              Dupliquer
            </button>
          )}

          {confirmationCopie && !archive && (
            <div className="basis-full border border-brass-400/40 p-3"
              data-testid="cal-fiche-dupliquer-confirmation">
              <p className="tech-label text-brass-300">
                Ce que la copie NE reprend PAS
              </p>
              <ul className="mt-1 list-disc pl-5 text-sm text-lune-soft">
                <li>l’historique des versions ;</li>
                <li>
                  {avecVariantes
                    ? 'les variantes SUIVENT la copie (case cochée ci-dessous) ;'
                    : 'les variantes ;'}
                </li>
                <li>le lien vers le devis ;</li>
                <li>le fil d’activité ;</li>
                <li>les pièces produites (exports, documents).</li>
              </ul>
              <p className="mt-1 text-xs text-lune-faint">
                La copie reste dans votre société et garde le même lead ou
                client que l’original.
              </p>
              <label className="mt-2 flex items-center gap-2 text-sm text-lune-soft">
                <input type="checkbox" checked={avecVariantes}
                  disabled={enCours}
                  data-testid="cal-fiche-dupliquer-variantes"
                  onChange={(e) => { setAvecVariantes(e.target.checked) }} />
                Reprendre les variantes
              </label>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button type="button" className={styleBouton} disabled={enCours}
                  data-testid="cal-fiche-dupliquer-confirmer"
                  onClick={lancerDuplication}>
                  Confirmer la duplication
                </button>
                <button type="button" disabled={enCours}
                  className="text-sm text-lune-soft underline"
                  data-testid="cal-fiche-dupliquer-annuler"
                  onClick={() => { setConfirmationCopie(false) }}>
                  Annuler
                </button>
              </div>
              {refusCopie && (
                <div className="mt-3 border border-alert-300/40 p-3"
                  data-testid="cal-fiche-dupliquer-erreur">
                  <p className="tech-label text-alert-300">Dupliquer</p>
                  <p className="mt-1 text-sm text-alert-300" role="alert">
                    {refusCopie}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* CALX42 — LA BASCULE « MODÈLE ». Offerte seulement quand le
              drapeau a été LU (jamais sur un état supposé) et quand le
              calepinage n'est pas archivé. */}
          {!archive && estModele !== null && (
            <button type="button" className={styleBouton} disabled={enCours}
              data-testid="cal-fiche-modele" onClick={basculerModele}>
              {estModele
                ? 'Retirer des modèles'
                : 'Marquer comme modèle'}
            </button>
          )}

          {refusModele && (
            <div className="basis-full border border-alert-300/40 p-3"
              data-testid="cal-fiche-modele-erreur">
              <p className="tech-label text-alert-300">Modèle</p>
              <p className="mt-1 text-sm text-alert-300" role="alert">
                {refusModele}
              </p>
            </div>
          )}

          {confirmation && !archive && (
            <p className="basis-full text-xs text-lune-faint" role="status"
              data-testid="cal-fiche-archiver-confirmation">
              L’archivage place ce calepinage dans la corbeille : il sort des
              listes et reste restaurable. Cliquez une seconde fois pour
              confirmer.
            </p>
          )}

          {/* L'ERREUR SOUS LE GESTE FAUTIF, qui le NOMME — jamais ailleurs. */}
          {refus && (
            <div className="basis-full border border-alert-300/40 p-3"
              data-testid="cal-fiche-archivage-erreur">
              <p className="tech-label text-alert-300">
                {LIBELLE_GESTE[refus.geste]}
              </p>
              <p className="mt-1 text-sm text-alert-300" role="alert">
                {refus.message}
              </p>
            </div>
          )}
        </div>
      )}

      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-white/10 pt-5 sm:grid-cols-3"
        data-testid="cal-fiche-calepinage">
        <Champ cle="reference" label="Référence">{texte(detail.reference)}</Champ>
        {/* CALX33 — le nom, éditable SUR PLACE. Le droit de gérer commande le
            crayon ; un calepinage archivé n'offre plus aucune écriture. */}
        <Champ cle="nom" label="Nom">
          {edition ? (
            <span className="flex flex-wrap items-center gap-2">
              <label className="sr-only" htmlFor="cal-fiche-nom-champ">
                Nom du calepinage
              </label>
              <input id="cal-fiche-nom-champ" type="text" value={saisie}
                data-testid="cal-fiche-nom-champ" disabled={enCours}
                onChange={(e) => { setSaisie(e.target.value) }}
                className="border border-white/20 bg-transparent px-2 py-1 text-sm text-white" />
              <button type="button" disabled={enCours}
                className="text-sm font-semibold text-brass-300 underline"
                data-testid="cal-fiche-nom-enregistrer" onClick={enregistrerNom}>
                Enregistrer
              </button>
              <button type="button" disabled={enCours}
                className="text-sm text-lune-soft underline"
                data-testid="cal-fiche-nom-annuler"
                onClick={() => { setEdition(false); setRefusNom(null) }}>
                Annuler
              </button>
            </span>
          ) : (
            <span className="flex flex-wrap items-center gap-2">
              <span>{texte(nomAffiche)}</span>
              {peutGerer && !archive && (
                <button type="button" onClick={ouvrirEdition}
                  className="text-sm text-brass-300 underline"
                  data-testid="cal-fiche-nom-editer">
                  Renommer
                </button>
              )}
            </span>
          )}
          {/* L'ERREUR SOUS LE CHAMP FAUTIF — le motif du serveur, tel quel. */}
          {refusNom && (
            <span className="mt-1 block text-xs text-alert-300" role="alert"
              data-testid="cal-fiche-nom-erreur">
              {refusNom}
            </span>
          )}
        </Champ>
        <Champ cle="id" label="Identifiant technique">
          <span className="fig">{texte(detail.id)}</span>
        </Champ>

        <Champ cle="statut_libelle" label="Statut">{texte(detail.statut_libelle)}</Champ>
        <Champ cle="statut" label="Code de statut">
          <code className="text-xs text-lune-soft">{texte(detail.statut)}</code>
        </Champ>
        <Champ cle="responsable" label="Responsable">{personne(detail.responsable)}</Champ>

        <Champ cle="cree_par" label="Créé par">{personne(detail.cree_par)}</Champ>
        <Champ cle="cree_le" label="Créé le">{moment(detail.cree_le)}</Champ>
        <Champ cle="modifie_le" label="Modifié le">{moment(detail.modifie_le)}</Champ>

        {/* Rattachement — le lead ET le client peuvent coexister, ou manquer. */}
        <Champ cle="lead" label="Lead">
          {detail.lead
            ? <Link to={`/crm/leads/${detail.lead.id}`} className="underline">
              {texte(detail.lead.nom)}
            </Link>
            : '—'}
        </Champ>
        <Champ cle="client" label="Client">{texte(detail.client?.nom)}</Champ>
        <Champ cle="devis" label="Devis">
          {detail.devis
            ? <Link to={`/ventes/devis/${detail.devis.id}/design`} className="underline">
              {texte(detail.devis.reference)}
            </Link>
            : '—'}
        </Champ>

        {/* La conception — présence, empreinte, versions de schéma et de moteur. */}
        <Champ cle="layout_present" label="Conception enregistrée">
          {detail.layout_present ? 'Oui' : 'Non'}
        </Champ>
        <Champ cle="layout_hash" label="Empreinte de la conception">
          <code className="text-xs text-lune-soft">
            {detail.layout_hash ? detail.layout_hash.slice(0, 12) : '—'}
          </code>
        </Champ>
        <Champ cle="layout_schema_version" label="Version du schéma">
          {texte(detail.layout_schema_version)}
        </Champ>
        <Champ cle="version_moteur" label="Version du moteur">
          {texte(detail.version_moteur)}
        </Champ>

        {/* CAL188/CAL189 — la péremption vient du MÊME helper serveur que la
            fiche devis et que la liste : sans devis lié elle est INCONNUE
            (`null`), et « — » se lit là où un « à jour » inventé mentirait. */}
        <Champ cle="layout_stale" label="Conception à jour">
          {detail.layout_stale == null
            ? '—'
            : (detail.layout_stale ? 'Non — le devis a changé' : 'Oui')}
        </Champ>
        <Champ cle="layout_nb_panneaux" label="Panneaux posés">
          {detail.layout_nb_panneaux == null
            ? '—'
            : <span className="fig">{detail.layout_nb_panneaux}</span>}
        </Champ>

        <Champ cle="versions" label="Versions">
          {versions.total == null ? '—' : (
            <>
              <span className="fig">{versions.total}</span>
              {versions.courante_id != null && ` · courante #${versions.courante_id}`}
              {versions.derniere_le && ` · ${moment(versions.derniere_le)}`}
            </>
          )}
        </Champ>
        <Champ cle="variantes" label="Variantes">
          {variantes.total == null ? '—' : (
            <>
              <span className="fig">{variantes.total}</span>
              {variantes.retenue_id != null
                ? ` · retenue #${variantes.retenue_id}`
                : ' · aucune retenue'}
              {variantes.non_simulees ? ` · ${variantes.non_simulees} à simuler` : ''}
            </>
          )}
        </Champ>

        <Champ cle="image" label="Aperçu">
          {image.url
            ? <a href={image.url} className="underline" target="_blank" rel="noreferrer">
              Voir l’aperçu
            </a>
            : '—'}
        </Champ>

        <Champ cle="contexte_geographique" label="Contexte géographique">
          {geo.pin || geo.ville || geo.adresse
            ? [geo.adresse, geo.ville, geo.source && `source : ${geo.source}`]
              .filter(Boolean).join(' · ')
            : '—'}
        </Champ>
        <Champ cle="permissions" label="Vous pouvez">
          {gestes.length > 0 ? gestes.join(', ') : 'consulter seulement'}
        </Champ>
      </dl>
    </div>
  )
}
