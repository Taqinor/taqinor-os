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
/** « Enregistré à HH:MM » (aujourd'hui) ou « Enregistré le JJ/MM à HH:MM » ; rien si l'horodatage est illisible. */
function texteEnregistre(iso) {
  const heure = iso ? formaterHeureBrouillon(iso) : ''
  if (!heure) return null
  const jour = new Date(Date.parse(iso))
  if (jour.toDateString() === new Date().toDateString()) return `Enregistré à ${heure}`
  return `Enregistré le ${jour.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })} à ${heure}`
}

export default function BarreEnregistrement({
  libelle, enCours, desactive, onEnregistrer, modifiee, enregistreLe, statut, erreur,
  etatPropre = null,
  derniereVersionLe = null, // l'heure de la DERNIÈRE VERSION servie (`versions.derniere_le`), tant que la session n'a rien écrit
}) {
  const heure = enregistreLe || derniereVersionLe
  const propre = !modifiee && !enCours
  const textePropre = etatPropre || texteEnregistre(heure)
  // Scène propre et heure connue : le bouton reste là (13 specs l'actionnent au chargement), mais DISCRET
  // (texte seul) — l'état « ✓ Enregistré à » porte la lecture, comme la maquette.
  const discret = propre && !!heure
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
      {(
        <button type="button" onClick={onEnregistrer} disabled={desactive}
          className={discret ? 'cal-bouton-enregistrer cal-bouton-enregistrer-discret' : 'cal-bouton-enregistrer'}>
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
