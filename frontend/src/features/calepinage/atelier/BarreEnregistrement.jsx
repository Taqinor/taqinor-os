import { formaterHeureBrouillon } from './contexteAtelier'
import { Icone } from './coque/primitives'

/* ACAL399 — l'enregistrement du calepinage et l'état de la scène (« Modifications non
   enregistrées » / « Enregistré à HH:MM »). État d'écran seulement : l'heure vient de la réponse
   2xx, rien n'est stocké, aucun enregistrement automatique n'est inventé.
   Coque (maquettes 22/11) — FORME BARRE DU HAUT : à droite du bandeau du projet.
   - Scène PROPRE et état connu (« Enregistré à HH:MM », ou « Simulation à jour · HH:MM » que la
     coque lit sur le serveur) : la barre se lit exactement comme la maquette, « ✓ Enregistré à
     14:32 » en vert, SANS bouton « Enregistrer le calepinage » visible. Cet état reste le MÊME
     élément bouton (nom accessible « … · Enregistrer le calepinage à nouveau ») : un clic ré-écrit
     la conception à l'identique (geste des specs qui forcent une écriture complète), au survol il
     le dit (« Enregistrer à nouveau »). Rien n'est caché : le geste est nommé, au clavier comme à
     la souris.
   - Scène MODIFIÉE (ou jamais enregistrée) : « Modifications non enregistrées » + le bouton
     « Enregistrer le calepinage » plein.
   Les messages (statut, erreur) s'affichent sous la barre. Le bouton de l'étape suivante n'est
   PLUS ici : il est au pied du panneau d'étape (un seul bouton « suivant » par étape). */
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
  actionErreur = null, // T4-B4-002 — `{libelle, onClick}` : le geste qui lève l'erreur (jamais un message mort)
  etatPropre = null,
  derniereVersionLe = null, // l'heure de la DERNIÈRE VERSION servie (`versions.derniere_le`), tant que la session n'a rien écrit
  refus = null, // T4-U4-027 — l'enregistrement REFUSÉ (409 modifié ailleurs) : la barre le dit, jamais « ✓ Enregistré »
}) {
  // T4-U4-015 — UNE source : l'heure SERVEUR de la dernière version enregistrée (relue après chaque enregistrement) ;
  // l'heure de la réponse ne sert que le temps de cette relecture. Un renvoi à l'identique (« Aucun changement »)
  // n'enregistre rien : l'heure reste celle de la version — la même qu'à la réouverture.
  const heure = derniereVersionLe || enregistreLe
  const propre = !modifiee && !enCours && !refus
  const textePropre = etatPropre || texteEnregistre(heure)
  // Scène propre et état connu : l'état SE LIT comme la maquette (« ✓ Enregistré à HH:MM ») et porte le geste.
  const etatSeul = propre && !!textePropre
  return (
    <div className="cal-barre-enregistrement" data-testid="cal-enregistrer-calepinage">
      {(modifiee || refus) && (
        <p className="cal-etat-modifie" role="status" data-testid="cal-etat-enregistrement">
          {refus || 'Modifications non enregistrées'}
        </p>
      )}
      <button type="button" onClick={onEnregistrer} disabled={desactive}
        className={etatSeul ? 'cal-bouton-enregistrer cal-bouton-enregistrer-etat' : 'cal-bouton-enregistrer'}
        aria-label={etatSeul ? `${textePropre} · ${libelle} à nouveau` : undefined}
        title={etatSeul ? 'Enregistrer à nouveau' : undefined}>
        {enCours && (
          <span aria-hidden="true"
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
        )}
        {etatSeul ? (
          <span className="cal-etat-ok" role="status" data-testid="cal-etat-enregistrement">
            <Icone nom="coche" taille={16} epaisseur={2.2} />
            {textePropre}
          </span>
        ) : <span>{enCours ? 'Enregistrement en cours…' : libelle}</span>}
      </button>
      {(statut || erreur) && (
        <div className="cal-barre-messages">
          {statut && <p className="text-sm text-muted-foreground" aria-live="polite">{statut}</p>}
          {erreur && (
            <p className="text-sm text-destructive" role="alert" data-testid="cal-erreur-enregistrement">
              {erreur}
              {actionErreur && (
                <button type="button" className="ml-2 inline-flex min-h-11 items-center font-semibold underline" onClick={actionErreur.onClick}>
                  {actionErreur.libelle}
                </button>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
