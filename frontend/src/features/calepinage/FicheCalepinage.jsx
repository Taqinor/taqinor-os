import { Link } from 'react-router-dom'
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

export default function FicheCalepinage({ detail }) {
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

  return (
    <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-white/10 pt-5 sm:grid-cols-3"
      data-testid="cal-fiche-calepinage">
      <Champ cle="reference" label="Référence">{texte(detail.reference)}</Champ>
      <Champ cle="nom" label="Nom">{texte(detail.nom)}</Champ>
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
  )
}
