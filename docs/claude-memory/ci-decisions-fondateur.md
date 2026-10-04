---
name: ci-decisions-fondateur
description: Décisions du fondateur du 03/10/2026 sur les devis COMMERCIAL et INDUSTRIEL — D-CIQ-0..22, base du Groupe CIQ de docs/PLAN.md et CIW de docs/WEB_PLAN.md ; ferme la question ouverte « 60 % vs 80 % »
metadata:
  type: project
---

Réponses de Reda (03/10/2026) aux questions de l'audit L3 des devis commercial et industriel. Elles fondent le
Groupe CIQ (docs/PLAN.md) et le Groupe CIW (docs/WEB_PLAN.md).

- **D-CIQ-0** Le chantier D10 est ouvert pour l'industriel et le commercial par la demande du 03/10 : UN moteur
  SERVEUR C&I (volet I/C de QJR113), comme D-AGR-1 pour l'agricole. Le JS ne garde que l'aperçu via l'endpoint.
- **D-CIQ-1** (ferme la question ouverte de [[ci-autoquote-conso-only]]) L'autoconsommation C&I se calcule HEURE
  PAR HEURE : production du site × profil DÉCLARÉ du client (jours/heures d'ouverture, équipes, fermetures,
  12 factures). Un profil type sourcé par catégorie ne sert qu'en repli, étiqueté « estimation ». Aucun taux fixe
  (ni 60 %, ni 80 %). Le résidentiel garde son modèle.
- **D-CIQ-2** Taille = la plus grande dont chaque tranche de 5 kWc se rembourse encore en ≤ `HORIZON_MARGINAL_PV`
  (10 ans, règle du 25/08) sur l'autoconsommation horaire ; jamais de panneaux pour un surplus non payé ; bornée
  par le toit, la puissance souscrite/raccordement, les onduleurs et la 82-21 si la revente est choisie. Une taille
  explicite reste souveraine (D-QJR5-13). Fin de « facture d'hiver ÷ 900 × 5 » pour le C&I.
- **D-CIQ-3** Champ déclaré « TVA récupérable oui/non » : économies, retour et TRI en HT/HT si oui, TTC si non
  (clinique exonérée sans déduction, CGI art. 91) ; le document garde la chaîne HT → TVA → TTC ; la saisie du
  générateur reste 100 % TTC.
- **D-CIQ-4** QXG6 (a)(c)(d) tranchés par sources primaires et marqués SOURCÉS (article/décision sur chaque
  constante) : tarifs MT ONEE confirmés, TVA électricité 20 % depuis 2026 ; 82-21 + décret 2.25.100 : déclaration
  < 11 kW, accord de raccordement 11 kW–5 MW, autorisation ≥ 5 MW ; plafond 20 % EN VIGUEUR (loi art. 12, ANRE
  04/26), rachat 18/21 cDH HT en MT/HT/THT seulement, sans déduction des frais réseau. QXG6 (b) (bande prix/kWc)
  reste au fondateur.
- **D-CIQ-5** Visite AVANT le devis final si site MT, ou si tension / puissance souscrite / toit (TGBT) restent
  inconnus après l'appel ; un BT aux faits connus reçoit son devis directement ; un devis indicatif reste possible,
  marqué « estimation sous réserve de visite ».
- **D-CIQ-6** (tranche CAD125 contre CAD163) La tâche 82-21 du playbook ne part que pour un site MT, un lead
  « régularisation 82-21 » ou un client qui veut revendre ; texte « raccordement et autorisations du site », jamais
  la loi ; un BT n'en reçoit aucune.
- **D-CIQ-7** Premier appel pro en 5 étapes : facture MAD ou kWh ; BT/MT + puissance souscrite ; activité + rythme
  (catégorie, horaires/équipes, jours, fermetures) ; surface + type de toit ; qui décide. Le reste va au
  questionnaire ou au rappel (Q21 tient).
- **D-CIQ-8** Site : étape « Affiner » FACULTATIVE après la porte de contact (BT/MT avec « je ne sais pas »,
  puissance souscrite si connue, kWh plutôt que MAD pour l'industriel) ; la coupe du 18/08 tient pour le parcours
  obligatoire.
- **D-CIQ-9** PDF commercial : 3 pages, complétées du retour (calcul serveur), de la production annuelle, de
  l'échéancier et de la validité.
- **D-CIQ-10** PDF industriel (4 pages, D-QJR5-12), page finance : 25 ans + jalons 5/10/15/20/25, TRI avec son
  horizon, coût du kWh solaire vs tarif du client, VAN seulement sur le taux d'actualisation DÉCLARÉ par le client
  (sinon omise), sensibilités seulement avec des valeurs saisies par Reda dans Paramètres (aucune par défaut).
- **D-CIQ-11** Client « entreprise » (raison sociale, ICE, RC, siège) ; ICE demandé au devis sans jamais le
  bloquer, obligatoire à l'acceptation en ligne et à la facture ; l'acceptation demande raison sociale, nom et
  qualité du signataire, ICE, avec une case « cachet » sur le PDF signé.
- **D-CIQ-12** Garanties fabricants + suivi de production avec délai d'intervention saisi par Reda (aucun défaut)
  + option O&M nommée sur chaque devis C&I (nettoyages, inspection, thermographie, test des protections ; prix et
  délais saisis par Reda) ; aucune garantie de production imprimée sans validation assureur/juriste ; PR de
  recette affiché à titre d'information.
- **D-CIQ-13** Échéanciers par défaut (réglages société, éditables par devis — D-QJR5-10) : commercial 40/50/10
  (commande / livraison / mise en service) ; industriel 30/40/20/10 (commande / livraison / mise en service /
  réception définitive) ; variante crédit-bail (le bailleur paie à la réception signée).
- **D-CIQ-14** Retenue de garantie seulement à la demande du client (option du devis, taux saisi, libérée à la
  réception définitive) ; caution et pénalités au cas par cas, plafonnées, jamais par défaut ; on construit la
  liste des réserves et la date de réception définitive.
- **D-CIQ-15** Financement : bloc FACULTATIF sur la proposition C&I, construit uniquement depuis l'offre ÉCRITE
  d'un prêteur/bailleur saisie par le vendeur (loyer, durée, apport) — loyer mensuel vs économie mensuelle +
  pro forma bailleur ; jamais de taux inventé ni de banque nommée sans son offre ; avis juridique sur le
  crédit-bail sous 82-21 avant toute mention du crédit-bail (PV80 tient pour le résidentiel).
- **D-CIQ-16** Pas d'offre tiers-investisseur / vente de kWh : le client est l'autoproducteur (comptant, crédit,
  crédit-bail) ; un montage loi 13-09 reste parqué jusqu'à un avis juridique ; le vendeur dispose d'une comparaison
  sourcée face à une offre concurrente de ce type.
- **D-CIQ-17** SR500 : candidater d'abord (participation + critères écrits, manuel) ; puis indicateur interne de
  pré-éligibilité sur données déclarées ; la phrase client en dernier, avec les mots de l'opérateur, jamais un
  montant (Q22) ; jamais de cumul SR500 + autre aide + revente.
- **D-CIQ-18** TAQINOR monte bien le dossier 82-21 (accord de raccordement) ET assure le suivi de production des
  sites pros : les promesses du site restent, avec leur périmètre exact.
- **D-CIQ-19** Reda modifie le formulaire Meta « pour mon entreprise » (question activité + tranches de facture
  au-delà de 4 000 DH) ; l'ERP lit les nouvelles réponses et ne stocke jamais une tranche ouverte comme un montant.
- **D-CIQ-20** Réglage « responsable des leads commerciaux et industriels », vide par défaut ; notification plus
  visible pour un lead pro.
- **D-CIQ-21** Les anciens devis commerciaux/industriels sont OUBLIÉS : aucun essai à blanc, aucune réparation,
  aucune compatibilité ascendante ; seuls les nouveaux devis doivent être bons.
- **D-CIQ-22** Priorité : le Groupe CIQ se place JUSTE AVANT le Groupe AGR dans docs/PLAN.md (la priorité 0 SOLMVP
  et la priorité 1 CAD restent devant) ; les couches génériques d'AGR que CIQ réutilise restent liées par `@after`.

**Why:** tranchées en séance interactive le 03/10/2026 sur la base de constats vérifiés (audit L3 : 13 lanes,
26 vérificateurs ; production lue en lecture seule ; sources primaires : loi 82-21 BO 7400, décret 2.25.100
BO 7489, décisions ANRE 04/26, 02/26, 03/26, page ONEE « Tarif Général (MT) », CGI 2026, KliK SR500 02/03/2026).
**How to apply:** ne pas les re-demander ; toute tâche CIQ/CIW les applique. Voir [[agricole-decisions-fondateur]],
[[qjr5-decisions-fondateur]], [[kwh-declare-vs-factures]], [[ci-autoquote-conso-only]].
