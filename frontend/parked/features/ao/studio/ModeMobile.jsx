import { CapturePhotoRepere } from './ModeChantier'
import { RAISONS_MOBILE } from './ModeMobile.constantes'

/* ============================================================================
   AOF190 — Mode MOBILE (375 px) : le refus EXPLICITE est un choix de design.
   ----------------------------------------------------------------------------
   Un atelier de calepinage — et plus largement l'atelier de géométrie de
   toiture (tracé, obstacles) — n'a PAS de version téléphone crédible : régler
   une allée ou tracer un contour au doigt sur 375 px produirait une géométrie
   fausse, pas une simplification honnête. Plutôt que de prétendre le
   contraire (un canvas rétréci « qui marche presque »), ce mode :
     1) rend les ateliers en LECTURE (mêmes données, aucune interaction lourde) ;
     2) garde la CAPTURE possible (photo → repère, réponses courtes — cf.
        `CapturePhotoRepere`, réutilisé tel quel depuis le mode CHANTIER) ;
     3) remplace CHAQUE action d'édition lourde par un refus EXPLICITE affichant
        sa raison — jamais un bouton mort sans explication.
   ========================================================================== */

export const MESSAGE_DISPONIBLE_ECRAN_LARGE = 'Disponible sur écran large'

// Remplace une action d'édition lourde : PAS un bouton mort — le libellé du
// refus ET sa raison sont TOUJOURS visibles ensemble (jamais révélés au survol
// seul, qui n'existe pas au doigt).
export function ActionIndisponibleMobile({ label, raisonCle, raison }) {
  const texte = raison || RAISONS_MOBILE[raisonCle] || 'action indisponible sur ce format.'
  return (
    <div
      role="note"
      aria-disabled="true"
      data-ao-tiroir={`refus-mobile-${raisonCle || 'action'}`}
      className="rounded-lg border border-dashed p-3 text-sm"
    >
      <p className="font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {MESSAGE_DISPONIBLE_ECRAN_LARGE} — {texte}
      </p>
    </div>
  )
}

// Enveloppe un atelier en LECTURE (le contenu reste visible/consultable, toute
// interaction d'édition est neutralisée) — même mécanique de `fieldset disabled`
// que `CalepinageLectureSeule` du mode CHANTIER, généralisée à N'IMPORTE quel
// atelier (toiture ou calepinage).
export function AtelierLectureMobile({ children, label, raisonCle }) {
  return (
    <div data-ao-tiroir={`atelier-lecture-mobile-${raisonCle || 'atelier'}`}>
      <fieldset disabled className="pointer-events-none opacity-80">
        {children}
      </fieldset>
      <ActionIndisponibleMobile label={label} raisonCle={raisonCle} />
    </div>
  )
}

export default function ModeMobile({
  toiture = null,
  calepinage = null,
  onPhoto = () => {},
  reponsesQr = null,
}) {
  return (
    <div data-ao-tiroir="mode-mobile" className="flex flex-col gap-3">
      {toiture && (
        <AtelierLectureMobile label="Tracer / poser un obstacle" raisonCle="tracer">
          {toiture}
        </AtelierLectureMobile>
      )}

      {calepinage && (
        <AtelierLectureMobile label="Régler le calepinage" raisonCle="calepinage">
          {calepinage}
        </AtelierLectureMobile>
      )}

      {/* La capture reste disponible : un technicien peut documenter le
          terrain depuis son téléphone même sans pouvoir éditer la géométrie. */}
      <CapturePhotoRepere onPhoto={onPhoto} />

      {reponsesQr}
    </div>
  )
}
