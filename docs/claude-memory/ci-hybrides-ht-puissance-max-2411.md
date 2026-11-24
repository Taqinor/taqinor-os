---
name: ci-hybrides-ht-puissance-max-2411
description: 24/11/2026 — devis industriel : l'option « avec batterie » choisit aussi parmi les hybrides haute tension (Deye 80 kW + BOS-B Pro 16 kWh), la consommation s'estime depuis la puissance maximale appelée à 50 % de charge par défaut, un produit se reconnaît à son rôle et à sa fiche avant son nom
metadata:
  type: project
---

**Point de départ (Reda, 24/11/2026, lead industriel « Karim Hasnaoui »)** : il ajoute au catalogue l'onduleur hybride
« DEYE SUN-80K-SG02HP3-EU-EM6 » (rôle déclaré, fiche complète, 80 kW, batterie 160–1000 V). L'écran du devis continue
d'écrire « il faudrait N onduleurs hybrides de 30 kW (au plus 8 en parallèle) … ajoutez au catalogue un onduleur hybride
plus puissant ». Le même client ne connaît de sa consommation que sa puissance maximale : 380 kVA.

**Ce qui a été trouvé (lecture seule de la production)** :
- Le message venait de l'écran, qui lisait la famille et la puissance d'un onduleur dans son NOM (« onduleur » +
  « hybride », « 30kW »). Un nom de référence ne dit ni l'un ni l'autre : le rôle déclaré et la fiche étaient ignorés.
- En commercial / industriel, l'option « avec batterie » est composée par le calcul serveur, qui n'acceptait que les
  hybrides basse tension (port batterie ≤ 60 V, décision du 26/10 « Deye BT + Dyness ») et écartait un hybride haute
  tension sans le dire.
- 90 000 kWh par mois, saisis sur la fiche, étaient le plafond (puissance maximale × heures d'ouverture), pas une
  estimation : à ce niveau le calcul pose environ 750 panneaux, à 44 000 kWh environ 370.

**Décisions de Reda (24/11/2026, par questions)** — ne pas re-demander :
- **L'option « avec batterie » industrielle choisit aussi parmi les hybrides haute tension.** La batterie posée avec
  eux est la **Deye BOS-B Pro 16 kWh** du catalogue ; sa fiche se complète depuis la fiche technique publiée par Deye ;
  tout article manquant (boîtier de contrôle…) lui est signalé, jamais sous-chiffré.
- **Consommation estimée depuis la puissance maximale appelée** : la fiche lead reçoit « puissance maximale appelée
  (kVA) » et « charge moyenne pendant les heures d'ouverture (%) » ; sans saisie, le calcul suppose **50 %**
  (modifiable). Le devis automatique peut partir de cette seule puissance. Une vraie donnée de consommation (kWh,
  relevé, facture) passe toujours devant, et l'estimation est toujours dite.
- **Les trois corrections dans la même PR** (choisi contre « l'estimation d'abord, la haute tension ensuite »
  recommandé).
- **Boîtier de contrôle et rack = articles à part** (« créer l'article de Deye manquant »), un jeu par grappe de
  batteries : boîtier haute tension BOS-B-PDU-2-A, « rack et câbles de puissance ».
- **Prix : achat fournisseur + 30 %** (devis Solarex Maroc n° S26/001708 du 27/07/2026, prix hors taxes) : batterie
  28 000 → 36 400 DH HT ; boîtier 11 200 → 14 560 ; rack et câbles 6 000 → 7 800. La batterie était à 40 000 DH HT
  « rack et control box inclus » : elle baisse, les deux autres se chiffrent à part.

**Choix pris par l'orchestrateur, à confirmer par Reda** : la basse tension reste essayée d'abord, la haute tension
seulement quand elle ne compose aucune option (aucun devis existant ne change) ; cos φ supposé à 0,9 quand la fiche
ne le donne pas ; un devis sorti du brouillon avant le 25/11/2026 garde l'option qu'il a reçue, un brouillon jamais
envoyé reçoit la haute tension ; le prix du rack relevé pour une grappe de 6 modules est appliqué à toute grappe.

**Ce que les fiches Deye publient (lu le 24/11/2026)** : SUN-80K-SG02HP3 — 2 entrées batterie, 80 + 80 A, jusqu'à
10 appareils en parallèle, 160 kW de puissance PV maximale ; BOS-B Pro-A3 (module BOS-B-Pack16-A3, 51,2 V, 16,08 kWh)
— 5 à 15 modules en série derrière un onduleur hybride, 16 grappes en parallèle au plus. Sur une fiche du Stock non
seedée (le 80 kW de Reda), ces champs se saisissent à la main.

**Why :** un produit correctement déclaré dans le Stock doit être reconnu sans avoir à porter les bons mots dans son
nom, et un site dont on ne connaît que la puissance doit pouvoir recevoir un devis préliminaire honnête.

**How to apply :** rôle et fiche d'abord, nom en repli (`role_devis_effectif`, `specs_solaire.ac_kw`) dans tout nouveau
code qui classe un produit ; « puissance souscrite » (plafonne les onduleurs) et « puissance maximale appelée » (estime
la consommation) sont deux champs distincts ; toute valeur supposée par un calcul de devis reste annoncée avec le champ
de la fiche qui la lève ([[calculateur-suppositions-dites]]).

Related: [[ci-decisions-fondateur]], [[ci-decisions-2610]], [[devis-envoyes-nouveaux-rendus]], [[batterie-duree-cycles]]
