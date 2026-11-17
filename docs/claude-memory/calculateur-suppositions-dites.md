---
name: calculateur-suppositions-dites
description: Règle fondateur du 17/11/2026 (lead « CPE Go Plus ») — toute information dont le calculateur de devis se sert et qu'il a dû supposer est dite à l'utilisateur avec le champ de la fiche ; option batterie C&I retenue tant que la consommation de nuit est inconnue ; câble AC supposé à 10 m avant la visite et jamais sous 10 mm² ; les deux options affichées côte à côte
metadata:
  type: feedback
---

Décisions de Reda du 17/11/2026, prises sur le lead « CPE Go Plus » (1742, industriel, Nouaceur).

- **Tout ce que le calculateur suppose est DIT.** « All those kind of informations that are used by the
  calculator of quotes should be mentioned to user. » Toute entrée dont le calcul d'un devis se sert et
  qu'il n'a pas trouvée sur la fiche (consommation de nuit, puissance souscrite, kWh tirés d'une facture en
  dirhams, inclinaison, orientation…) est annoncée à la commerciale, en langage clair, avec le CHAMP DE LA
  FICHE qui la lève — jamais une supposition silencieuse, jamais le jargon du moteur (« talon », « borne »).
- **Option « avec batterie » C&I retenue tant que la consommation de nuit est inconnue.** Sans réponse à
  « Équipements hors horaires » ET sans activité qui donne une estimation, le moteur prenait une
  consommation étalée sur 24 h : prudente pour les panneaux, mais la PLUS favorable à la batterie (6 × 16 kWh
  composés ; 3 ou 4 une fois la question répondue). L'option n'est plus composée : l'offre réseau part seule
  et l'écran nomme la question. Si le client a demandé « avec » seule, le devis automatique est refusé en
  nommant ce champ.
- **Câble AC d'onduleur : 10 m supposés avant la visite (plus 30 m), et JAMAIS moins de 10 mm².** « I want 10 mm cable for 15 kW inverter — the same for 10 kW and 5 kW, I only use 10 mm cables. » Plancher commercial
  (`moteur_ci/composition.py` `SECTION_AC_MIN_MM2`), que le calcul dépasse dès que l'échauffement ou la chute de
  tension l'exigent (50 kW → 16 mm²). Le câble DC reste à 30 m par chaîne et à son plancher de 6 mm² (19/08).
  Les deux longueurs réelles se saisissent aussi sur l'écran du devis C&I, sans passer par le module Visites.
  Portée du plancher au 17/11 : les LIGNES du devis C&I ; le schéma électrique, le calepinage et les devis
  résidentiels calculent leur câble AC ailleurs et ne le portent pas encore (à trancher).
- **Un devis à deux options montre les DEUX.** L'économie annuelle et le retour de l'option « avec
  batterie » s'affichent à côté de ceux de l'offre réseau sur les écrans internes (bannière de création,
  carte du générateur), lus de l'étude stockée — le PDF et la page client le faisaient déjà.

**Why:** Reda a découvert les 6 batteries sans qu'aucun écran dise sur quoi elles reposaient, puis n'a vu que
les chiffres de l'offre réseau en ouvrant le devis. Le même jour, une puissance souscrite saisie à −12 kVA
bloquait l'option batterie avec un message accusant le catalogue (PR #1442).

**How to apply:** toute nouvelle supposition d'un moteur de devis (C&I d'abord ; même règle pour le
résidentiel et l'agricole quand on y touche) passe par une liste affichée qui nomme le champ de la fiche —
côté C&I : `apps/ventes/domain/suppositions_ci.py` (clé `champ_lead` sur les alertes de l'aperçu et du
journal du devis automatique). Interprétation de Claude, à confirmer : la retenue de l'option batterie vaut
quand RIEN ne dit la consommation de nuit ; un lead commercial dont l'activité donne une estimation
(décision « talon par activité » du 26-27/10) garde son option, et l'estimation est dite. Voir
[[ci-decisions-2610]], [[ci-decisions-fondateur]], [[checked-facts-only]].
