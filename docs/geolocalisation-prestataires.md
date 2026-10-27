# Géolocalisation des techniciens prestataires — cadre et formalités

Décision fondateur du 27/10/2026 : les techniciens sont des prestataires externes qui utilisent l'application
TAQINOR OS ; le suivi de position pendant leurs missions est **obligatoire et inévitable, jamais caché**. Ce
document regroupe ce que l'application fait, ce que le fondateur doit faire une fois, et la clause à mettre dans
chaque contrat de prestation. Ce n'est pas un avis juridique : faire relire par un conseil avant la mise en service.

## 1. Ce que fait l'application

- **Acceptation bloquante.** Un compte de terrain (technicien) ne peut pas ouvrir « Ma journée » ni partir en
  mission tant qu'il n'a pas lu et accepté les conditions d'utilisation (géolocalisation comprise). Le serveur refuse
  « Départ dépôt » et « Check-in » sans accord enregistré (date, adresse IP, version de la notice).
- **Suivi automatique, sans interrupteur.** Dès qu'une intervention est « en route » ou « sur site », la position
  remonte toute seule (au plus une par minute). Hors de ces périodes, rien n'est relevé.
- **Indication discrète.** Un indicateur « Suivi actif » dans « Ma journée » (la loi impose l'information
  préalable, pas un rappel permanent).
- **Interruptions détectées.** Si le téléphone cesse d'envoyer des positions pendant une mission (permission refusée,
  application fermée), le responsable reçoit une alerte « suivi interrompu » et la fiche l'affiche.
- **Rétention.** Positions brutes purgées après 30 jours ; entrées/sorties de périmètre et temps sur site conservés
  (plafond légal : un an).
- **Accès.** Responsables et administrateurs seulement ; le technicien consulte ses propres positions ; jamais le
  client.
- **Récépissé CNDP.** Saisi dans Suivi GPS → Consentements ; tant qu'il est vide, la notice dit « non encore
  déclaré ».

## 2. Formalités du fondateur (une fois)

1. **Déclaration CNDP** — formulaire de déclaration normale F211 (https://www.cndp.ma/formalites/), traitement
   « géolocalisation des intervenants pendant les missions », finalités : organisation des interventions, preuve de la
   prestation (arrivée, présence, durée), sécurité des intervenants isolés. Noter le numéro de récépissé dans
   l'application.
2. **Clause dans chaque contrat de prestation** (§3), signée avant le premier accès.
3. **Registre interne** : qui a accès (responsables), durée (30 j / 1 an), finalités — une page suffit.

## 3. Clause type pour le contrat de prestation

> **Article — Application de terrain et géolocalisation.** Le Prestataire exécute ses missions au moyen de
> l'application TAQINOR OS mise à disposition par TAQINOR. Pendant chaque mission, du départ du dépôt jusqu'au
> retour, la position de l'appareil utilisé par le technicien est relevée automatiquement par l'application afin
> d'organiser les interventions, d'établir la preuve de la prestation (heure d'arrivée, présence et durée sur site) et
> d'assurer la sécurité des intervenants. Aucune position n'est relevée en dehors des missions. Les positions sont
> conservées trente jours ; les franchissements de périmètre et la durée sur site au plus un an. Elles sont accessibles
> aux responsables et administrateurs de TAQINOR, jamais aux clients. Le technicien accède à ses propres positions dans
> l'application et peut exercer ses droits d'accès, de rectification et d'opposition pour motif légitime auprès de
> TAQINOR, ou introduire une réclamation auprès de la CNDP. Ce traitement est déclaré à la CNDP sous le n° de
> récépissé ____________. L'acceptation de ces conditions dans l'application est nécessaire pour accéder aux missions ;
> leur refus ou leur retrait met fin à cet accès.

## 4. Ce que l'on ne fait pas

- Aucun suivi sans information préalable (loi 09-08, art. 4-5-12 ; sanctions art. 52-56 : 10 000 à 200 000 DH).
- Aucun suivi hors mission, aucune position montrée au client, aucune conservation au-delà d'un an.
