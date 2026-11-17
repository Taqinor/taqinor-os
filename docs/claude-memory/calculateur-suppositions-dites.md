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

**Décisions du même jour sur l'option « avec batterie » (questions interactives, 17/11/2026) :**

- **D-HYB-1 — limite de panneaux d'un onduleur HYBRIDE = la fiche constructeur.** Le moteur plafonnait tout
  onduleur à 1,35 × sa puissance AC (convention d'atelier non sourcée) : un Deye 20 kW ne portait que 27 kWc,
  d'où 2 × 15 kW pour 35 kWc. Reda : « the 20 kW version of Deye might handle higher number of panels… the
  remaining power would be used to charge the batteries and the inverter AC output is capped at 20 kW ». La
  fiche Deye (SUN-14-20K-SG05LP3-EU-SM2, révision 2026) donne « Max. PV access power » = 2 × l'AC (40 kW sur
  le 20 kW) et « Max. PV input power » 32 kW. Retenu : la puissance RACCORDABLE (access power), portée par
  `FicheTechnique.ond_dc_max_kwc` ; fiche muette ⇒ l'ancien 1,35. Les onduleurs RÉSEAU gardent leur règle.
  Quand un panneau de plus rend le champ câblable sur UN hybride au lieu de deux (49 → 50 panneaux de 715 Wc
  sur un 20 kW : deux trackers de deux chaînes égales), l'option prend ce panneau et le dit.
  LIMITE CONNUE au 17/11 : le bilan horaire ne plafonne pas la production à la puissance AC de l'hybride
  (sans effet tant que la charge du site reste sous cette puissance ; à modéliser — non tranché).
- **D-HYB-2 — Deye 15 et 20 kW triphasés : unités de la révision COURANTE** (36 A par MPPT sur les deux
  trackers, Isc 54 A, 2 chaînes par MPPT) — les valeurs stockées (20 A / 30 A) venaient de la fiche de juin 2024.
- **D-HYB-3 — haute tension seulement pour les grandes banques.** Le Deye 30 kW ne prend qu'une batterie HV,
  et la BOS-B est un empilage série (5 à 15 modules de 16 kWh d'après les notes du catalogue, ~80 kWh mini) :
  incompatible avec « une batterie pour commencer ». Sous ce minimum : basse tension, le plus gros hybride
  unique qui porte le champ, puis des hybrides identiques en parallèle. La composition HV automatique n'est
  PAS construite au 17/11 (il faut les valeurs de fiche de la BOS-B et un champ « modules minimum »).
- **D-HYB-4 — nombre de batteries AU CHOIX, de 1 au maximum calculé (révisé le 17/11/2026 après-midi).** Le matin
  Reda avait retenu « prêt pour la suite » (panneaux gardés pour la banque complète) ; en voyant l'écran il a
  tranché autrement : « i expect the number of panels to be reduced if we use only one battery… this number
  should be choosable… with the maximum calculated by the quote calculator (for this client the maximum should
  be 3) ». Retenu : sur l'écran du devis, un choix de 1 à R (R = banque calculée, mémorisée dans
  `etude_params.banque_recommandee`) ; les PANNEAUX sont redimensionnés pour le nombre choisi ; l'ONDULEUR
  hybride reste celui de la banque maximale (on ajoute batteries et panneaux plus tard sans le remplacer).
- **D-HYB-5 — l'onduleur gardé pour l'extension se DIT sur le devis.** « If we use an inverter just to fit
  future batteries and a smaller inverter can still be used this should be mentioned in the quote. » Quand un
  onduleur plus petit suffirait au champ réduit, le PDF client, la page client et l'écran le disent (FR/EN/AR
  sur le PDF) : « Onduleur hybride 20 kW retenu pour l'extension : l'installation peut recevoir jusqu'à 3
  batteries (2 à ajouter plus tard). Un onduleur de 15 kW suffirait pour l'installation de départ. »
- **D-SOC-1 — socles sur les devis C&I (17/11/2026).** « Why the calculator don't add socles, they should be
  added to the quote. » Le moteur C&I n'avait aucune règle de socles (le résidentiel en pose 2 par panneau).
  Retenu : 2 socles par panneau quand la pose est un toit plat LESTÉ, et aussi quand le type de toit n'est pas
  encore déclaré (le moteur suppose déjà cette pose) ; aucun socle sur bac acier, toiture inclinée, sol,
  ombrière ni toit plat fixé. Les socles s'AJOUTENT à la structure « toit plat lestée C&I » (450 MAD par
  panneau, inchangée), sur leur propre ligne, avec l'article « Socles » du catalogue.

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
