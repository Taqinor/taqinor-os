---
name: ci-decisions-2610
description: Décisions fondateur des 26-27/10/2026 sur le devis C&I (boulangerie, lead 1637) — onduleurs, taille, devis préliminaire, rendu client, batterie, talon
metadata:
  type: project
---

Décisions de Reda prises en construisant le devis automatique d'une boulangerie (lead 1637), 26-27/10/2026 :

- **Onduleurs** : le moins d'appareils d'abord, puis le moins cher ; jamais au-dessus de la puissance souscrite déclarée si une autre combinaison tient dessous (PR #1061).
- **Taille** : un palier cher seul (saut d'onduleur) est gardé si, avec les paliers suivants, l'ensemble se rembourse en 10 ans (C&I seulement ; PR #1063).
- **Devis préliminaire, jamais un prix vide** : câble DC = 2 × chaînes × 30 m, câble AC = 30 m par onduleur, toit inconnu = toit plat lesté (450 HT/panneau) ; un seul bandeau « Devis préliminaire — les prix pourront être ajustés après la visite technique » (PR #1061).
- **Aucune incertitude imprimée** côté client (« fiche muette », « hypothèse », « à confirmer », « prix ferme » retirés ; valeurs gardées).
- **Aucun « C&I »** dans ce que lit le client ; même article au même prix = une ligne.
- **« Installation clé en main »** : une ligne client regroupe les 8 prestations ; le devis interne garde le détail (PR #1069).
- **Coffrets** au barème par onduleur + par panneau (`prix_fixe_ht` = par onduleur) ; câbles AC « 5×S mm² », marque Nexans.
- **Deux options sans / avec batterie** par défaut (choix du lead souverain) : hybrides Deye BT triphasés + Dyness (banque homogène), batterie = conso du soir/nuit, panneaux ajoutés jusqu'à batterie pleine puis règle des 10 ans (l'option « avec » peut être plus grande) ; batterie sans prix ⇒ offre « sans » seule + alerte interne ; phrase « Le soir et la nuit, votre consommation reste fournie par le réseau ; l'option avec batterie la couvre. » (PR #1070).
- **Talon** (conso hors horaires) en % du niveau de jour, par type de commerce (BDEW / NREL ComStock, sinon 20 % défaut fondateur) ; réponse client Aucun/Un peu/Beaucoup = 5/20/50 % ; lead commercial sans catégorie = 20 % ; 23 activités (pâtisserie → boulangerie) ; vrai nom d'activité au PDF (PR #1074).

**Why:** chaque point vient d'une erreur vue sur un vrai devis envoyable (2 × 15 kW au lieu de 1 × 50, double comptage des coffrets, prix vides, jargon interne au client, horaires ignorés).
**How to apply:** toute session C&I part de ces décisions sans les re-demander ; voir aussi [[ci-decisions-fondateur]].
