import { Link, useLocation, useParams } from 'react-router-dom'
import { PARAM_ONGLET, ongletParChemin, ongletParCle } from './onglets'

/* ============================================================================
   CALX55 — LE RETOUR VERS L'ATELIER DEPUIS UN LIEN PROFOND.
   ----------------------------------------------------------------------------
   CONSTAT QUI JUSTIFIE CE FICHIER. Les treize panneaux contextuels du module
   sont servis à la fois comme onglets de l'atelier (`?onglet=<cle>`, CALX1) et
   comme routes profondes `/calepinage/:id/<cle>` — un lien envoyé par message
   ouvre donc le panneau SEUL, et la lecture des treize composants ne trouvait
   AUCUN lien de retour : y arriver par une URL partagée imposait le bouton
   « Précédent » du navigateur. Un écran sans sortie est une impasse.

   IL NE S'AFFICHE QUE LÀ OÙ IL SERT. Monté dans un panneau ouvert DANS
   l'atelier (le rail, CALX1), il ne rend RIEN : le fil d'Ariane pointerait sur
   la page qu'on regarde déjà. C'est le chemin qui tranche — pas un drapeau à
   tenir à jour dans treize fichiers.

   IL N'INVENTE AUCUN TEXTE (D-CALX 7). Le titre du calepinage n'est affiché que
   si le panneau le CONNAÎT et le passe ; sans lui, le fil d'Ariane dit
   simplement « Calepinage », jamais un titre fabriqué ni un numéro présenté
   comme une référence. Le libellé de l'onglet courant vient du registre
   `atelier/onglets.js`, seule source des treize noms.
   ========================================================================== */

export default function RetourAtelier({
  calepinageId: idPropose = null, cle: clePropose = null, titre = null,
}) {
  const { id: idUrl } = useParams()
  const { pathname } = useLocation()

  const calepinageId = idPropose ?? idUrl ?? null
  /* La clé EXPLICITE l'emporte (un panneau peut se savoir monté ailleurs) ;
     sinon on la déduit du chemin. Une clé inconnue du registre ne retombe
     JAMAIS sur le premier onglet ici : un fil d'Ariane qui renverrait vers un
     autre panneau que celui qu'on lit mentirait. */
  const onglet = clePropose ? ongletParCle(clePropose) : ongletParChemin(pathname)

  if (!calepinageId || !onglet) return null

  const parametres = new URLSearchParams()
  parametres.set(PARAM_ONGLET, onglet.cle)
  const cible = `/calepinage/${calepinageId}?${parametres.toString()}`

  return (
    <nav
      aria-label="Fil d’Ariane"
      data-testid="cal-retour-atelier"
      className="mb-4 flex flex-wrap items-center gap-2 text-sm"
    >
      <Link
        to={cible}
        data-testid="cal-retour-atelier-lien"
        className="font-semibold text-brass-300 underline"
      >
        {titre ? `← Calepinage ${titre}` : '← Calepinage'}
      </Link>
      <span aria-hidden="true" className="text-lune-faint">/</span>
      <span className="text-lune-soft" data-testid="cal-retour-atelier-onglet">
        {onglet.libelle}
      </span>
    </nav>
  )
}
