---
name: ci-decisions-2610
description: Décisions fondateur des 26-30/10/2026 sur le devis C&I (boulangerie, lead 1637) — onduleurs, taille, devis préliminaire, rendu client, batterie (banque par la règle marginale, horizon C&I 10 ans, 30/10), talon
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
- **30/10 — banque par la règle marginale, UN horizon C&I pour panneaux et batteries** (boulangerie, devis 461 : la banque « toute la nuit » donnait 15 Dyness 16 kWh et 144 panneaux, rejetée : « the battery should be full, I never said add 6 batteries… the calculator should calculate the right number of batteries ; if I add batteries manually I should get more panels to fill them » ; « both panels and batteries should follow the 7 years rule »). MÉCANIQUE tranchée : la banque monte module par module (modèle le moins cher par kWh utile), chaque module composé avec les panneaux qu'il tire pour se remplir (QJR612) et l'hybride éventuel, gardé si l'investissement ajouté est remboursé dans l'horizon par l'économie ajoutée (regard du 26/10 sur un module cher seul), puis la montée des panneaux par la même règle (`moteur_ci/batterie.py::_monter_banque`). **30/10 : horizon marginal 10 ans** (`moteur_ci/taille.py HORIZON_MARGINAL_CI`, = D-CIQ-2) pour les panneaux ET les batteries, batterie comptée avec ses panneaux tirés — Reda : « the 7 years was for residential, maybe for commercial the rule is 10 years internationally » (les 7 ans restent au stockage résidentiel). Boulangerie sans toit à 10 ans : sans 77 panneaux ; avec 13 PowerBrick 16 kWh, 131 panneaux, 5 × Deye 15 kW, retour 5,2 ans (à 7 ans : 9 modules, 105 panneaux) ; PR #1163.
- **Talon** (conso hors horaires) en % du niveau de jour, par type de commerce (BDEW / NREL ComStock, sinon 20 % défaut fondateur) ; réponse client Aucun/Un peu/Beaucoup = 5/20/50 % ; lead commercial sans catégorie = 20 % ; 23 activités (pâtisserie → boulangerie) ; vrai nom d'activité au PDF (PR #1074).

- **Toit plat : 30° par défaut, inclinaison modifiable** dans le générateur (10° ou autre) — annule D-CMP-4=a ; `toit.pente_deg` exposé par l'étude ; sans GPS le repli « journées moyennes » reste à 30° (Reda, 27/10 14:12 ; PR #1094).
- **Garanties montrées au client = UNE durée, celle qui vaut au Maroc**, sans « à confirmer » / « selon site » : onduleur Deye 5 ans, Huawei 10 ans, batterie Dyness DL5.0C 7 ans (datasheet V2, extensible 10), Dyness Powerbox 10 ans ; panneaux 12/30 ans seulement Canadian Solar (Reda, 27/10 ; PR #1105, #1106, RWEB #1131).
- **Provision de remplacement de l'onduleur = prix payé après remise**, niveau de règles 3 (RPDF #1114, 27/10).
- **Parallèle d'hybrides = même modèle seulement** (D-CMP-11, manuel Deye ; PR #1094) — à revoir.
- **Devis envoyés intouchés** : toute correction de chiffre du 27/10+ est gardée par `regles_au_moins(devis, REGLES_CORRIGEES_2710)` (= 3), jamais `calcul_corrige` (CEC #1096, #1126 ; CPDF #1130 : drapeau `regles_avant_2710` reposé par chaque renderer).
- **Catalogue (données fondateur, jamais inventées)** : aucun article `structure_sol`, taux INST-PMP absent, pas de pompe à courbe monophasée, pompes OSP sans prix ⇒ 0/10 devis agricoles auto chiffrables au 28/10 (AGM) ; le tableau Stock « prêt pour devis » (CCAT #1128) signale ces manques au lieu de les combler.
- **Rendu fidèle** = `builder.generate_premium_devis_pdf` → `registre_renderers()` (guide `docs/ci-l3-sessions.md` §4) ; le legacy direct n'est pas le chemin client.
- Les autres « décisions prises pour le fondateur (à revoir) » de la nuit du 27-28/10 sont listées dans `docs/claude-memory/passation-pc2/decisions-prises.txt` (PC1 + PC2).

**Why:** chaque point vient d'une erreur vue sur un vrai devis envoyable (2 × 15 kW au lieu de 1 × 50, double comptage des coffrets, prix vides, jargon interne au client, horaires ignorés).
**How to apply:** toute session C&I part de ces décisions sans les re-demander ; voir aussi [[ci-decisions-fondateur]].
