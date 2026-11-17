---
name: calculateur-suppositions-dites
description: Règle fondateur du 17/11/2026 (lead « CPE Go Plus ») — toute information dont le calculateur de devis se sert et qu'il a dû supposer est dite à l'utilisateur avec le champ de la fiche ; option batterie C&I retenue tant que la consommation de nuit est inconnue ; câble AC supposé à 10 m avant la visite ; les deux options affichées côte à côte
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
- **Câble AC avant la visite : 10 m par onduleur, plus 30 m** (remplace la valeur du 26/10/2026). À 30 m, la
  limite de 1 % de chute de tension imposait 6 mm² à un onduleur de 15 kW ; à 10 m le calcul donne 2,5 mm²
  (15 kW) ou 4 mm² (20 kW). Le câble DC reste à 30 m par chaîne (non tranché le 17/11).
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
