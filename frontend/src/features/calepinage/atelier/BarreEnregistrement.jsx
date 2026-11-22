import { formaterHeureBrouillon } from './contexteAtelier'
import { Icone } from './coque/primitives'

/* ACAL399 — l'enregistrement du calepinage et l'état de la scène (« Modifications non
   enregistrées » / « Enregistré à HH:MM »). État d'écran seulement : l'heure vient de la réponse
   2xx, rien n'est stocké, aucun enregistrement automatique n'est inventé.
   Coque (maquettes 22/11) — FORME BARRE DU HAUT : à droite du bandeau du projet. Scène propre et
   déjà enregistrée dans la session ⇒ « ✓ Enregistré à HH:MM » seul ; modifiée (ou heure inconnue)
   ⇒ le bouton « Enregistrer le calepinage » (+ l'état). `etatPropre` (« Simulation à jour · HH:MM »,
   lu sur le serveur par la coque) remplace « Enregistré à » quand l'étape le sert. Les messages
   (statut, erreur) s'affichent sous la barre. Le bouton de l'étape suivante n'est PLUS ici : il est
   au pied du panneau d'étape (un seul bouton « suivant » par étape). */
export default function BarreEnregistrement({
  libelle, enCours, desactive, onEnregistrer, modifiee, enregistreLe, statut, erreur,
  etatPropre = null,
}) {
  const heure = enregistreLe ? formaterHeureBrouillon(enregistreLe) : ''
  const propre = !modifiee && !enCours
  const textePropre = etatPropre || (heure ? `Enregistré à ${heure}` : null)
  const boutonVisible = !propre || !heure
  return (
    <div className="cal-barre-enregistrement" data-testid="cal-enregistrer-calepinage">
      {modifiee && (
        <p className="cal-etat-modifie" role="status" data-testid="cal-etat-enregistrement">
          Modifications non enregistrées
        </p>
      )}
      {propre && textePropre && (
        <p className="cal-etat-ok" role="status" data-testid="cal-etat-enregistrement">
          <Icone nom="coche" taille={16} epaisseur={2.2} />
          {textePropre}
        </p>
      )}
      {boutonVisible && (
        <button type="button" onClick={onEnregistrer} disabled={desactive} className="cal-bouton-enregistrer">
          {enCours && (
            <span aria-hidden="true"
              className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
          )}
          <span>{enCours ? 'Enregistrement en cours…' : libelle}</span>
        </button>
      )}
      {(statut || erreur) && (
        <div className="cal-barre-messages">
          {statut && <p className="text-sm text-muted-foreground" aria-live="polite">{statut}</p>}
          {erreur && (
            <p className="text-sm text-destructive" role="alert" data-testid="cal-erreur-enregistrement">{erreur}</p>
          )}
        </div>
      )}
    </div>
  )
}
