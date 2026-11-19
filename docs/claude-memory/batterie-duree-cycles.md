---
name: batterie-duree-cycles
description: Décision fondateur du 19/11/2026 (D-BATCYC-1) — sur le flux 25 ans de l'option C&I « avec batterie », la batterie n'est plus remplacée à la fin de sa garantie mais quand ses cycles publiés sont épuisés au rythme réel de l'étude (cycles publiés ÷ cycles par an) ; aucun remplacement au-delà de 25 ans ; niveau de règles 13 ; cycles publiés saisis en prod le 19/11 sur quatre fiches batterie (à la demande de Reda)
metadata:
  type: project
---

Décision de Reda du 19/11/2026, sur le devis C&I DEV-202611-0080 (option « avec batterie »).

- **Ce qu'il a dit.** Le calculateur remplaçait la batterie en année 11 (l'année après la garantie de
  10 ans). Reda : « why would be replace the battery after 10 years ? the 16kwh have 8000 cycle so it is
  roughly 20 to 25 years ! ». Question posée, réponse retenue : **« Published cycles, real usage »**.
- **La règle.** Année de remplacement = ⌊cycles publiés de la fiche ÷ cycles par an de l'étude⌋ + 1, où
  cycles par an = `bilan.batterie.restitue_kwh_an ÷ bilan.batterie.capacite_utile_kwh` du client (seule
  formule). La garantie n'est PLUS un plafond. Au-delà de l'horizon de 25 ans : aucun remplacement compté.
  Exemple : 8 000 ÷ ≈ 289 cycles/an ≈ 27,7 → année 28 → aucun remplacement sur 25 ans.
  Sans cycles publiés sur la fiche : fin de garantie + 1 (comme avant) ; ni l'un ni l'autre : le défaut
  étiqueté de 10 ans ; étude sans cycles annuels utilisables : la règle d'avant.
- **Où.** `apps/ventes/economie_ci_options.py` (`annee_remplacement_batterie`, `cycles_par_an_du_bilan`,
  clé publique `batterie_duree` du flux) ; `apps/ventes/domain/etude_ci_batterie.py` (`regle_remplacement`) :
  la MÊME année sert le flux 25 ans, la montée de la banque (bilan du candidat) et le verdict « non rentable ».
  Le PDF imprime dans « Bases du calcul » « Durée de vie de la batterie : 8 000 cycles publiés, environ 289
  cycles par an — aucun remplacement sur 25 ans » (fr/en/ar), sous le nom de l'option batterie.
- **Nouveaux rendus seulement : niveau de règles 13** (`REGLES_CYCLES_BATTERIE_1911`, migration 0158 :
  seuls les brouillons jamais envoyés passent de 12 à 13). Un devis envoyé garde l'année que le client a reçue.
- **Fiches en production (fait le 19/11/2026, sur ordre de Reda : « you can do this yourself »).** Le champ
  `bat_cycles_publies` était vide sur les fiches (le nombre n'existait qu'en texte libre de garantie) ; saisi
  par la session, valeur lue sur le texte de garantie de chaque produit : Dyness PowerBrick SC 16 kWh = 8000 ;
  Deye BOS-B Pro haute tension 16 kWh, Dyness 5 kWh et Dyness 10 kWh = 6000. Une batterie sans ce champ garde
  la fin de garantie. Toute nouvelle batterie au catalogue : renseigner ce champ sur sa fiche.
- **Effet sur la taille de la banque.** La montée de la banque juge chaque candidat avec SON année de
  remplacement : une grande banque cycle moins, donc dure plus longtemps — les nouveaux devis peuvent retenir
  une banque différente de celle d'avant le niveau 13.
