# Test utilisateur (T4) — suivi des constats

Généré par l'orchestrateur (`scratchpad/suivi_constats.py`) depuis les registres `registre/constats/T4-*.jsonl`,
les messages de commit qui citent l'identifiant du constat (sur `main`, puis dans le lot en cours) et les fichiers
de rejeu des relecteurs neufs (`T4/tour*/rejeu-*.json`). Un constat « corrigé — à rejouer » a un correctif testé
mais pas encore de rejeu par un relecteur qui n'a rien construit.

| État | Constats |
|---|---|
| corrigé sur main — à rejouer | 94 |
| OUVERT (aucun commit ne le cite) | 68 |
| corrigé | 68 |
| corrigé dans le lot en cours — à rejouer | 31 |
| rejoué « autre » | 7 |
| rejoué « pas-corrige » | 7 |
| rejoué « non-rejoue » | 1 |

| Gravité | corrigé sur main — à rejouer | OUVERT (aucun commit ne le cite) | corrigé | corrigé dans le lot en cours — à rejouer | rejoué « autre » | rejoué « pas-corrige » | rejoué « non-rejoue » |
|---|---|---|---|---|---|---|---|
| S1 | 2 | 1 | 2 | 1 | 0 | 0 | 0 |
| S2 | 32 | 17 | 19 | 7 | 2 | 2 | 0 |
| S3 | 46 | 43 | 38 | 18 | 3 | 4 | 1 |
| S4 | 14 | 7 | 9 | 5 | 2 | 1 | 0 |

| Constat | Gravité | Écran | Commits | État |
|---|---|---|---|---|
| T4-U1-001 | S1 | PDF devis premium (/proposal pdf_mode=full), page 1 et page 4 | — | OUVERT (aucun commit ne le cite) |
| T4-U1-002 | S2 | Création du lead › fiche du lead › Devis automatique › alertes du devis › PDF premium | d42bab8df2 | corrigé, rejoué par V1 |
| T4-U1-003 | S1 | Calepinage › Résultats et Documents › Rapport d'étude (PDF, 21 pages) | — | corrigé, rejoué par V1 |
| T4-U1-004 | S2 | Calepinage › étape 2 Les panneaux | — | OUVERT (aucun commit ne le cite) |
| T4-U1-005 | S2 | Calepinage › Résultats (et fiche du lead, devis DEV-202611-0097) | — | OUVERT (aucun commit ne le cite) |
| T4-U1-006 | S2 | Calepinage › étape 3 Le raccordement | — | corrigé, rejoué par X2 |
| T4-U1-007 | S2 | Calepinage › étape 2 › liste « Panneau » | — | OUVERT (aucun commit ne le cite) |
| T4-U1-008 | S3 | PDF devis premium — nombre de pages | — | OUVERT (aucun commit ne le cite) |
| T4-U1-009 | S2 | PDF « Devis final (paiement + RIB) » | 220de00e8b | corrigé sur main — à rejouer |
| T4-U1-010 | S2 | Générateur de devis › Lignes de produits | — | corrigé, rejoué par V2 |
| T4-U1-011 | S3 | Ventes › Devis (liste) › PDF ; liste des devis | a2e0ceb127 | corrigé sur main — à rejouer |
| T4-U1-012 | S3 | Lenteurs mesurées (pile partagée par plusieurs relecteurs) | — | OUVERT (aucun commit ne le cite) |
| T4-U1-013 | S3 | Calepinage › barre d'enregistrement | 19a03d161c | corrigé sur main — à rejouer |
| T4-U1-014 | S3 | Ventes › Devis › Accepter › fenêtre « Accepter le devis » | 1e65848940 | corrigé sur main — à rejouer |
| T4-U1-015 | S3 | Générateur › Alertes du devis automatique ; PDF avec étude page 3 | — | OUVERT (aucun commit ne le cite) |
| T4-U1-016 | S3 | Calepinage › étape 2 › bandeau « Production ÷ consommation » | — | OUVERT (aucun commit ne le cite) |
| T4-U1-017 | S2 | Calepinage › plan du toit (étapes 2 et 3) | — | corrigé, rejoué par V1 |
| T4-U1-018 | S4 | Calepinage (toutes étapes) et Résultats | b24a7e5dd0 | corrigé sur main — à rejouer |
| T4-U1-019 | S4 | PDF premium — économie avec batterie | — | OUVERT (aucun commit ne le cite) |
| T4-U1-020 | S4 | Fiche lead › Questionnaire d'appel › « Aussi à demander » | 4fc50f3196 | corrigé sur main — à rejouer |
| T4-U1-021 | S3 | Calepinage › étape 2 › Combien de panneaux ? | — | OUVERT (aucun commit ne le cite) |
| T4-U1-022 | S2 | Fiche lead › Profil énergétique ; bouton « Devis auto » ; calepinage › besoin | 346b736c94 6833ee7eb6 | corrigé sur main — à rejouer |
| T4-U1-023 | S2 | Calepinage 1940 › Résultats ; Expert › Accès solaire | 7795843087 7efaddf330 f6492427e6 | corrigé sur main — à rejouer |
| T4-U1-024 | S3 | Calepinage › Toit › Obstacles | f3bfd3ca99 | corrigé sur main — à rejouer |
| T4-U1-025 | S3 | Calepinage › Toit › obstacle sélectionné | f3bfd3ca99 | corrigé sur main — à rejouer |
| T4-U1-026 | S2 | Fiche lead › Devis automatique (panneau « Devis créé ») ; PDF premium | 5f7c599c2c | corrigé, rejoué par V2 |
| T4-U1-027 | S2 | Devis automatique d'un lead « batterie souhaitée » ; PDF premium | — | OUVERT (aucun commit ne le cite) |
| T4-U1-028 | S3 | Ouverture d'une fiche lead / d'une liste (WebKit téléphone, Chromium tablette) | — | OUVERT (aucun commit ne le cite) |
| T4-U1-029 | S4 | Panneau Devis automatique (téléphone) | a11368f4ae dbaa16c667 | corrigé sur main — à rejouer |
| T4-U1-030 | S3 | CRM › Leads (Commercial responsable) | a2e0ceb127 | corrigé sur main — à rejouer |
| T4-U1-031 | S4 | Fiche lead › Contact | — | corrigé, rejoué par V2 |
| T4-U2-001 | S3 | Devis automatique (fiche du lead, onglet Devis) puis PDF « Document commercial » DEV du le | — | OUVERT (aucun commit ne le cite) |
| T4-U2-002 | S3 | PDF « Document commercial » (3 pages) du devis automatique du lead U2-e | — | OUVERT (aucun commit ne le cite) |
| T4-U2-003 | S3 | Fiche du lead → onglet Devis → « Envoyer au client » | — | corrigé, rejoué par V2 |
| T4-U2-005 | S3 | Calepinage (atelier guidé) → étape 1 « Le toit » | 09c49390ff 4aa4a6800e | corrigé sur main — à rejouer |
| T4-U2-006 | S2 | Calepinage (atelier guidé) → étape 2 « Les panneaux » | — | OUVERT (aucun commit ne le cite) |
| T4-U2-007 | S3 | Calepinage (atelier guidé) → étapes 2, 3 et 4 | — | corrigé, rejoué par X2 |
| T4-U2-009 | S4 | Calepinage → étape 4 « Les résultats » → « Pour un résultat complet » | — | OUVERT (aucun commit ne le cite) |
| T4-U2-011 | S3 | Édition complète du devis → Lignes de produits | 010e1383e6 3e9fe631d2 a14622a91a | corrigé, rejoué par V2 |
| T4-U2-012 | S3 | Calepinage → étape 2 « Les panneaux » puis étape 4 « Les résultats » | — | OUVERT (aucun commit ne le cite) |
| T4-U2-013 | S4 | Calepinage → étape 4 « Les résultats » → « Du soleil au réseau » | c4c092b8cb | corrigé sur main — à rejouer |
| T4-U2-014 | S3 | Calepinage → étape 5 « Les documents » → Rapport d'étude (PDF, 22 pages) | 1a46bf3a39 | corrigé sur main — à rejouer |
| T4-U2-015 | S2 | Calepinage → étape 5 « Les documents » → bouton « Générer le devis » du pied de carte | — | OUVERT (aucun commit ne le cite) |
| T4-U2-016 | S3 | Tickets SAV (/sav) et fiche du chantier → onglet « Interventions » | 1884d31518 2f1351589b 8cc8137440 | corrigé sur main — à rejouer |
| T4-U2-017 | S3 | Calepinage → étape 1 « Le toit » puis étape 4 « Les résultats » | — | corrigé, rejoué par V1 |
| T4-U2-018 | S3 | Ventes → Devis (liste) et CRM → Leads (pipeline), serveur lent | a2e0ceb127 | corrigé sur main — à rejouer |
| T4-U2-019 | S2 | PDF « Document industriel » (4 pages) et « Devis une page » du devis automatique du lead U | 6c76c49a16 | corrigé sur main — à rejouer |
| T4-U2-020 | S3 | PDF « Document industriel » (4 pages), page 3 « Rentabilité sur 25 ans » | cfacac71ae | corrigé sur main — à rejouer |
| T4-U2-004 | S3 | Édition complète du devis → « Activité et horaires » → « Catégorie commerciale » | cf93caec39 | corrigé sur main — à rejouer |
| T4-U2-021 | S4 | Fiche du lead U2-h (moyenne tension) → onglet Devis puis « Nouveau devis (édition complète | a020916900 | corrigé sur main — à rejouer |
| T4-U3-001 | S3 | CRM → « + Nouveau lead », type Agricole, section Pompage | — | corrigé, rejoué par V2 |
| T4-U3-002 | S2 | Fiche du lead U3-i, section Pompage → « Origine du niveau d'eau » et « Origine du débit du | a91d2a9496 | rejoué « autre » par V2, puis corrigé — à rejouer |
| T4-U3-003 | S4 | Fiche du lead U3-i, colonne Devis (devis automatique bloqué) et section Pompage | — | rejoué « autre » par V2 |
| T4-U3-004 | S3 | Fiche du lead → « Devis automatique » (refus), générateur, Stock | — | rejoué « autre » par V2 |
| T4-U3-005 | S4 | Générateur, ligne de produit → sélecteur « — Produit — » | — | corrigé, rejoué par V2 |
| T4-U3-006 | S3 | Générateur en mode « Agricole (pompage) », tableau « Lignes de Produits » | 3e9fe631d2 | corrigé, rejoué par V2 |
| T4-U3-007 | S2 | PDF client « Document agricole complet » page 3 et « Version courte (1 page) » du devis DE | — | corrigé, rejoué par V2 |
| T4-U3-008 | S3 | Générateur, bouton « Créer le devis » (carte « Création du Devis » et rail) | ae99bf3139 b56876aa81 | corrigé, rejoué par V2 |
| T4-U3-009 | S3 | Liste des devis → fenêtre « Générer le PDF » d'un devis agricole | — | corrigé, rejoué par V2 |
| T4-U3-010 | S4 | PDF client du devis DEV-202611-0100 (complet et 1 page) | — | OUVERT (aucun commit ne le cite) |
| T4-U3-011 | S3 | Fiche du lead → « Envoyer au client » → « Copier le lien » | — | corrigé, rejoué par V2 |
| T4-U3-012 | S3 | Calepinage CAL-2611-1936 du lead U3-i → onglet Pompage (/calepinage/1936?onglet=pompage) | 16c60c458b 9403ef26b5 | corrigé sur main — à rejouer |
| T4-U3-013 | S4 | Atelier du calepinage (toasts) et onglet Pompage (résultat) | — | rejoué « autre » par X1 |
| T4-U3-014 | S2 | CRM → Leads (Commercial responsable, 518 leads visibles) et lien de fiche /crm/leads?lead= | a2e0ceb127 | corrigé sur main — à rejouer |
| T4-U3-015 | S2 | Fiche du lead U3-k (phase inconnue) → « Nouveau devis (édition complète)… » → « Créer le d | — | OUVERT (aucun commit ne le cite) |
| T4-U3-016 | S4 | Fenêtre du devis créé (édition complète, téléphone 390 px) | a11368f4ae dbaa16c667 | corrigé sur main — à rejouer |
| T4-U3-017 | S3 | Fiche du lead U3-l (facture 300 MAD/mois, 2 000 kWh/mois tapés) → « Devis automatique » | 1a4f4bfdeb | corrigé sur main — à rejouer |
| T4-U3-018 | S3 | Accueil des applications → tuile CRM → Leads (Technicien) | — | OUVERT (aucun commit ne le cite) |
| T4-U3-019 | S2 | Fiche du lead U3-m → champ « Ville / quartier » → « Vérifier la ville », puis « Devis auto | 1bf0ea7507 d42bab8df2 | corrigé sur main — à rejouer |
| T4-U3-020 | S3 | Fiche du lead U3-m (ville tapée « maroc ») | 1bf0ea7507 d42bab8df2 | corrigé sur main — à rejouer |
| T4-U3-021 | S3 | Fiche du lead U3-j → « Devis automatique » (refus) | 0ba28da18a ab71b0b1ee c6ec0fea90 | corrigé sur main — à rejouer |
| T4-U3-022 | S3 | Édition complète du devis de U3-j → Pompage solaire → Besoin en eau « Pompe actuelle » | 6d1e14a29d | corrigé, rejoué par X1 |
| T4-U3-023 | S3 | Fiche du lead U3-j (pompe actuelle conservée) → « À compléter » | 857753de95 | corrigé sur main — à rejouer |
| T4-U3-024 | S3 | Fiche du lead → « Devis automatique » → bandeau « Devis créé : … » | — | rejoué « autre » par V2 |
| T4-U4-001 | S3 | Atelier calepinage, étape 2 « Les panneaux », carte « Couvrir la facture (Recommandé) » | — | OUVERT (aucun commit ne le cite) |
| T4-U4-002 | S2 | Atelier calepinage, étape 2, bandeau « Production · estimation de la pose » et « Productio | — | OUVERT (aucun commit ne le cite) |
| T4-U4-003 | S3 | Atelier calepinage, vue Plan (étapes 1 et 2) | — | corrigé, rejoué par V1 |
| T4-U4-004 | S3 | Atelier calepinage, étape 2, sélecteur « Panneau » ; devis automatique DEV du lead U4-n | — | OUVERT (aucun commit ne le cite) |
| T4-U4-005 | S2 | Atelier calepinage, étapes Résultats et Documents ; feuille « Avancé » (fiche du calepinag | — | OUVERT (aucun commit ne le cite) |
| T4-U4-006 | S2 | Atelier calepinage, feuille « Avancé », ligne en tête | b7a5c60648 | corrigé sur main — à rejouer |
| T4-U4-007 | S2 | Atelier calepinage, étape 3 « Le raccordement », carte « Prêt à envoyer ? », ligne « Dossi | a2fcb38a59 acd5f3173f d2af5633f2 faaba16fae | corrigé, rejoué par X2 |
| T4-U4-008 | S3 | Atelier calepinage, étape 3 « Le raccordement » | — | corrigé, rejoué par V1 |
| T4-U4-009 | S3 | Atelier calepinage, étape 4 « Les résultats », encadré sous « Du soleil au réseau » | c4c092b8cb | corrigé sur main — à rejouer |
| T4-U4-010 | S2 | Fiche du lead, onglet « 1 devis », bouton « Réviser (nouvelle version) » ; PDF une page de | 74c0710fae | corrigé, rejoué par X4 |
| T4-U4-011 | S3 | Fiche du lead U4-n, colonne de gauche (pastilles et bloc Montant estimé) | — | OUVERT (aucun commit ne le cite) |
| T4-U4-012 | S2 | Atelier calepinage, étape 4 « Les résultats » et « Voir les 26 étapes » ; étape Documents  | f616c7a7a6 f841613842 | corrigé sur main — à rejouer |
| T4-U4-013 | S2 | Nouveau calepinage (onglet Client) → atelier, étape Toit ; PDF « Rapport d'étude » et « No | 2e7152fde8 770a77f4a8 | corrigé, rejoué par X2 |
| T4-U4-014 | S3 | Nouveau calepinage (onglet Client) ; atelier, étape Documents, « Pourquoi : Taille dimensi | f4b2ce3dec | corrigé sur main — à rejouer |
| T4-U4-015 | S4 | Atelier calepinage, étape Panneaux (calepinage sans épingle) ; barre projet « Enregistré à | b1cef0985f b24a7e5dd0 | corrigé, rejoué par X2 |
| T4-U4-016 | S3 | Atelier calepinage (mode Expert), onglets « Terrain » et « Ombrière » ; barre projet | 4cd499c4e3 53e8bea4aa a2fcb38a59 | corrigé sur main — à rejouer |
| T4-U4-017 | S2 | Atelier calepinage, feuille « Avancé » (ligne de tête), calepinage CAL 1941 du lead U4-p | b7a5c60648 | corrigé sur main — à rejouer |
| T4-U4-018 | S2 | Atelier calepinage, étape 3 « Le raccordement » (mode Guidé), calepinage avec champ au sol | 1e3015ff2f 4cd499c4e3 a2fcb38a59 de6f6fe900 | corrigé sur main — à rejouer |
| T4-U4-019 | S4 | Onglets « Terrain » et « Ombrière » (mode Expert) | f35763b43f | corrigé sur main — à rejouer |
| T4-U4-020 | S2 | Relevé de visite au téléphone (/calepinage/1941/releve), puis onglet « Relevé terrain » de | 57399684a3 | corrigé sur main — à rejouer |
| T4-U4-021 | S3 | Relevé de visite au téléphone ; même écran ouvert dans un autre navigateur | 2acdeffa83 | corrigé sur main — à rejouer |
| T4-U4-022 | S3 | Relevé de visite au téléphone | — | OUVERT (aucun commit ne le cite) |
| T4-U4-023 | S4 | Relevé de visite au téléphone, hors ligne | 74de4424c7 | corrigé sur main — à rejouer |
| T4-U4-024 | S3 | Atelier calepinage CAL 1941 (pan de toit + champ au sol + ombrière), barre projet, étape P | 4cd499c4e3 53e8bea4aa a2fcb38a59 | corrigé sur main — à rejouer |
| T4-U4-025 | S3 | Atelier calepinage ouvert dans deux navigateurs (CAL 1941) | 0bf394fff0 19a03d161c | corrigé sur main — à rejouer |
| T4-U4-026 | S4 | Atelier calepinage, étape Panneaux, quand le catalogue ne répond pas | 03bd4189d7 b24a7e5dd0 | corrigé sur main — à rejouer |
| T4-U4-027 | S4 | Atelier calepinage, utilisateur B après le refus de son enregistrement (409) | b24a7e5dd0 e115807fbe | corrigé sur main — à rejouer |
| T4-V1-001 | S3 | Fiche du lead › carte de gauche « RESPONSABLE » et onglet Suivi commercial « Responsable » | 61786f8c6d | corrigé, rejoué par X9 |
| T4-V1-002 | S3 | Devis › Édition complète › Lignes › « Ajouter ligne » › choix du produit | 30da8ad8dc | corrigé, rejoué par X4 |
| T4-V1-003 | S3 | Devis › Édition complète (même écran) : bas du tableau des lignes et carte de droite | b3ec24d12c | corrigé, rejoué par X4 |
| T4-V1-004 | S4 | Liste des devis › PDF › fenêtre « Générer le PDF » | a11368f4ae | corrigé, rejoué par X4 |
| T4-V1-005 | S2 | Calepinage 1959 › Résultats « Mois par mois » et Rapport d'étude p. 14 « Consommation et h | — | OUVERT (aucun commit ne le cite) |
| T4-V1-006 | S3 | Calepinage › Documents › Plan de pose pour l'équipe (PDF, page 1) | c92e9e62d4 | corrigé sur main — à rejouer |
| T4-V1-007 | S3 | Ventes › Devis (liste) › ligne DEV-202611-0115 (accepté) › colonne Total TTC | aa5abce0c0 | corrigé, rejoué par X4 |
| T4-V1-008 | S3 | Chantier CHT-202611-0006 › onglet Interventions › bloc « Tickets SAV » | 45be18d238 | corrigé, rejoué par X4 |
| T4-V1-009 | S2 | Toute la pile : fiche du lead, liste des leads, atelier calepinage, devis automatique, Rév | — | OUVERT (aucun commit ne le cite) |
| T4-V1-010 | S3 | Calepinage 1960 › Montrer au client (/calepinage/1960/client), bureau 1440 × 900 | ab2177c9d6 | corrigé, rejoué par X2 |
| T4-V1-011 | S2 | Calepinage › Nouveau calepinage › onglet « Client » › champ « Rechercher un client… » | 2879812fae | corrigé, rejoué par X2 |
| T4-V1-012 | S3 | Calepinage 1960 (lead V1-r sans GPS) › étape Résultats › « Lancer la simulation » | e240d72950 | rejoué « autre » par X2, puis corrigé — à rejouer |
| T4-V2-001 | S2 | Fiche du lead agricole V2-i1 › Pompage › « Débit du forage » / « Origine du débit du forag | 3078ede1b8 e1d93ea788 | corrigé, rejoué par X1 |
| T4-V2-002 | S2 | Fiche du lead agricole › onglet Devis › « Modifier » sur le devis automatique (édition com | b449871b76 | corrigé, rejoué par X1 |
| T4-V2-003 | S2 | Édition complète, nouveau devis agricole, encart des trois pompes (« Inférieure / Recomman | 243eb9af6a 273a498107 bf0c9fe467 | rejoué « pas-corrige » par X1, puis corrigé — à rejouer |
| T4-V2-004 | S4 | Fiche du lead → « Devis auto » (panneau « Alertes du devis automatique ») et édition compl | b143526675 | corrigé, rejoué par X1 |
| T4-V2-005 | S3 | Fiche du lead (ouverture depuis la liste / lien direct) | — | OUVERT (aucun commit ne le cite) |
| T4-V2-006 | S3 | PDF client « Document agricole complet » de DEV-202611-0113, pages 1 et 3 ; générateur agr | — | OUVERT (aucun commit ne le cite) |
| T4-V2-007 | S3 | Édition complète, nouveau devis agricole V2-i2 (monophasé) : « Paramètres Techniques » et  | e294eaed92 | corrigé, rejoué par X1 |
| T4-V2-008 | S3 | Liste des devis → « PDF » → fenêtre « Générer le PDF » → « Générer » (devis agricole DEV-2 | 2885898117 | rejoué « non-rejoue » par X4, puis corrigé — à rejouer |
| T4-V2-009 | S3 | PDF « Devis Final » (complet) de DEV-202611-0113, page 1 | — | OUVERT (aucun commit ne le cite) |
| T4-V2-010 | S3 | Devis auto (alertes) et édition complète d'un côté ; PDF 1 page et note de calcul (fiches  | b143526675 | rejoué « pas-corrige » par X1, puis corrigé — à rejouer |
| T4-V2-011 | S4 | Édition complète, nouveau devis agricole V2-i2 (pompe monophasée sans courbe) — encart de  | 91d5216077 b143526675 | corrigé, rejoué par X1 |
| T4-V2-012 | S3 | Édition complète, nouveau devis agricole V2-i2 — encart de dimensionnement | 91d5216077 | corrigé, rejoué par X1 |
| T4-V2-013 | S3 | Fiche du lead → « Devis auto » → bandeau « Devis créé : … » | 6cbb9ffa19 | corrigé, rejoué par X4 |
| T4-V2-014 | S2 | Toute la pile (fiche du lead, devis automatique, atelier du calepinage) | — | OUVERT (aucun commit ne le cite) |
| T4-V2-015 | S2 | Fiche du lead → « Devis auto » (panneau du devis automatique) et PDF Premium | 6cbb9ffa19 c3511fc111 | corrigé, rejoué par X4 |
| T4-V2-016 | S3 | Panneau du devis (après « Devis auto » ou « PDF ▾ › Premium ») au téléphone, barre d'actio | a11368f4ae | corrigé, rejoué par X4 |
| T4-V2-017 | S3 | Panneau du devis → case « Inclure l'étude » → « Télécharger le PDF » | a11368f4ae | corrigé, rejoué par X4 |
| T4-V2-018 | S2 | Édition complète du devis DEV-202611-0119 (onglet Technique) puis PDF Premium | 010e1383e6 b3ec24d12c | rejoué « autre » par X4, puis corrigé — à rejouer |
| T4-V2-019 | S3 | Fiche du lead → onglet devis → « Envoyer au client » → « Copier le lien » | b34924eef8 | corrigé, rejoué par X4 |
| T4-V2-020 | S3 | Atelier du calepinage CAL-2611-1964 (lead V2-c, Marrakech, sans GPS) — position du site | — | corrigé, rejoué par X2 |
| T4-V2-021 | S2 | Atelier du calepinage CAL-2611-1965 (lead V2-d, Rabat, toit plat), mode Expert, carte des  | 09796c9f60 | corrigé, rejoué par X2 |
| T4-V2-022 | S3 | Fiche « Nouveau lead » (Toiture & site) puis atelier du calepinage en mode Guidé | — | OUVERT (aucun commit ne le cite) |
| T4-V2-023 | S3 | Liste des factures, juste après « Émettre » l'acompte FAC-202611-0004 (DEV-202611-0120) | aa5abce0c0 | corrigé, rejoué par X4 |
| T4-V2-024 | S3 | Fiche du lead V2-c → onglet devis après « Réviser (nouvelle version) » | 74c0710fae | corrigé, rejoué par X4 |
| T4-V2-025 | S3 | Après-vente → Tickets SAV (Commercial, puis Administrateur) | 45be18d238 | corrigé, rejoué par X4 |
| T4-X1-001 | S1 | PDF premium résidentiel (fiche du lead › panneau du devis › « Télécharger le PDF »), pages | 6d4078a267 | corrigé sur main — à rejouer |
| T4-X1-002 | S1 | PDF « Inclure l'étude » (résidentiel), page 4 « Confiance, Garanties » | dc08ec1809 | corrigé sur main — à rejouer |
| T4-X1-003 | S2 | Liste des devis › fenêtre PDF › « Devis Final » (format premium, résidentiel) | a529caef05 e14d9877d6 | corrigé sur main — à rejouer |
| T4-X1-004 | S3 | Fiche du lead › onglet Devis › « Puissance cible (kWc) » + « Remise %… » | 1d34f121e4 4d88568cca | corrigé sur main — à rejouer |
| T4-X1-005 | S3 | PDF premium résidentiel, pages 1-2 contre page 4 | — | OUVERT (aucun commit ne le cite) |
| T4-X1-006 | S3 | Fenêtre PDF (résidentiel) : libellés « Devis premium (3 pages …) » et « sinon le PDF garde | — | OUVERT (aucun commit ne le cite) |
| T4-X1-007 | S3 | Fenêtre PDF › Calepinage › « Inclure la planche cotée » | 8d8b865d50 | corrigé sur main — à rejouer |
| T4-X1-008 | S3 | PDF agricole complet, page 1 « D'où viennent ces chiffres », après enregistrement de l'édi | 515540f934 | corrigé, rejoué par X9 |
| T4-X1-009 | S3 | Édition complète agricole monophasée (lead X1-m) › encart des tailles | a560f4dc5e | corrigé, rejoué par X9 |
| T4-X1-010 | S3 | Fiche du lead › onglet Devis › barre WhatsApp FR / Darija › « Aperçu du message WhatsApp » | 84e24843cf 86db7969e9 | corrigé sur main — à rejouer |
| T4-X1-011 | S3 | Fiche du lead résidentiel › « Devis auto » | 643bb3331d | corrigé sur main — à rejouer |
| T4-X1-012 | S3 | Liste des devis (colonne Validité) contre PDF | e63f6279ec | corrigé sur main — à rejouer |
| T4-X1-013 | S3 | Édition complète agricole (Options du kit) contre PDF agricole page 3 (Options du kit) | — | OUVERT (aucun commit ne le cite) |
| T4-X1-014 | S4 | Alertes du devis automatique agricole | 17b0403244 | corrigé, rejoué par X9 |
| T4-X1-015 | S4 | Fiche du lead › historique | — | OUVERT (aucun commit ne le cite) |
| T4-X1-016 | S4 | « Réviser (nouvelle version) » depuis le panneau du devis de la fiche du lead | d74519d132 | corrigé sur main — à rejouer |
| T4-X2-001 | S2 | Calepinage 1970 (lead X2-a, Rabat) › étape 2 Les panneaux › carte « Couvrir la facture » | 6a93963486 8e63cd111c | rejoué « pas-corrige » par X9, puis corrigé — à rejouer |
| T4-X2-002 | S3 | Calepinage 1970 › étape 2 Les panneaux › bande « Production · estimation de la pose » | 0ae2498ced bd4b2b68ab | rejoué « pas-corrige » par X9, puis corrigé — à rejouer |
| T4-X2-003 | S3 | Calepinage 1971 sans lead (client X2-o, adresse « Casablanca ») › bandeau du site et étape | — | OUVERT (aucun commit ne le cite) |
| T4-X2-004 | S3 | Calepinage 1970 › étape 3 Le raccordement › liste « Onduleur » et « Raccorder automatiquem | 2034a0c73d | corrigé, rejoué par X9 |
| T4-X2-005 | S3 | Calepinage 1971 sans lead (client à Casablanca, site non localisé) › Expert › réglages du  | fd63bc35b2 | corrigé, rejoué par X9 |
| T4-X2-006 | S3 | Calepinage 1971 › Expert › étape Toit : « TOTAL — TOUTES LES ZONES » et pied de l'outil (« | 209c438b18 8e63cd111c | rejoué « pas-corrige » par X9, puis corrigé — à rejouer |
| T4-X2-007 | S2 | Montrer au client (/calepinage/1970/client) face à l'atelier, étape 2 Les panneaux | 59af7b99a3 | corrigé, rejoué par X9 |
| T4-X2-008 | S3 | Calepinage 1970 (toit 2 pans 22°) › mode Expert › étape Toit › bloc « TYPE DE TOIT » | 1c91186d37 b4c2043839 dab243288a | corrigé, rejoué par X9 |
| T4-X2-009 | S2 | Calepinage 1970 › étape 2 Les panneaux (Guidé) : bande du haut de la carte face à la barre | 8e63cd111c | corrigé, rejoué par X9 |
| T4-X2-010 | S2 | Calepinage 1971 (toit plat 10 × 8, 24 panneaux enregistrés) › Expert › étape Toit : zones, | 47234e9fb1 | corrigé, rejoué par X9 |
| T4-X2-011 | S4 | Calepinage 1970 › carte (Guidé et Expert) › bouton boussole sous le zoom | 58ff412882 | corrigé, rejoué par X9 |
| T4-X3-001 | S3 | Réglages › Calepinage › Sources des paramètres (/calepinage/sources) face à Réglages simul | 7c1de9afd1 | corrigé dans le lot en cours — à rejouer |
| T4-X3-002 | S3 | Sources des paramètres › Dégagements, face à Réglages simulation › Retraits par type d'arê | 1554228623 | corrigé dans le lot en cours — à rejouer |
| T4-X3-003 | S3 | Réglages simulation › Site & imagerie (Altitude du site) face au Rapport d'étude (page 4 « | 973864ffea | corrigé dans le lot en cours — à rejouer |
| T4-X3-004 | S3 | Réglages simulation › Historique, puis Bibliothèque › Presets | 4435192801 | corrigé dans le lot en cours — à rejouer |
| T4-X3-005 | S4 | Sources des paramètres (Lestage, Dégagements) et Bibliothèque (Presets, Favoris matériel) | 214fb332d1 | corrigé dans le lot en cours — à rejouer |
| T4-X3-006 | S3 | Bibliothèque (/calepinage/bibliotheque) | 1c6d8e4092 | corrigé dans le lot en cours — à rejouer |
| T4-X3-007 | S3 | Atelier du calepinage, mode Guidé — liens profonds /calepinage/1976/<clé> et /calepinage/1 | 69a45ec992 | corrigé dans le lot en cours — à rejouer |
| T4-X3-008 | S2 | Calepinage X3-a : étape 3 Le raccordement et rapport d'étude, face à l'étape 5 Les documen | — | OUVERT (aucun commit ne le cite) |
| T4-X3-009 | S2 | Calepinage X3-a : étape 2 Les panneaux, étape 4 Les résultats, étape 5 (contrôle DC/AC), f | ba878975f8 ce3f0038ee | corrigé sur main — à rejouer |
| T4-X3-010 | S3 | Liste des calepinages (/calepinage) › champ « Rechercher un calepinage » (Client, ville ou | 64e3cfec0b | corrigé dans le lot en cours — à rejouer |
| T4-X3-011 | S3 | Liste des calepinages › Filtres › Tri « Titre », Ordre Croissant / Décroissant | 64e3cfec0b | corrigé dans le lot en cours — à rejouer |
| T4-X3-012 | S4 | Calepinage X3-a › Résultats (« Calcul à refaire ») et Comparaison (/calepinage/comparaison | 9c33978da8 | corrigé dans le lot en cours — à rejouer |
| T4-X3-013 | S3 | Sources des paramètres › Dégagements, face à Réglages › Allées | 1554228623 | corrigé dans le lot en cours — à rejouer |
| T4-X3-014 | S3 | Atelier › onglet Dossiers réglementaires (/calepinage/1976/dossiers), face à Réglages › Ga | 9c54aac797 | corrigé dans le lot en cours — à rejouer |
| T4-X3-015 | S3 | Réglages › Calepinage : Réglages simulation et Démarrage rapide, rôle Commercial | — | OUVERT (aucun commit ne le cite) |
| T4-X3-016 | S3 | Nouveau calepinage › menu « Responsable (facultatif) » | 431a34c848 | corrigé dans le lot en cours — à rejouer |
| T4-X3-017 | S4 | Barre du haut de l'ERP sur les écrans du calepinage (liste, nouveau calepinage) | — | OUVERT (aucun commit ne le cite) |
| T4-X3-018 | S3 | Réglages simulation (/calepinage/reglages) | 39efc90150 | corrigé dans le lot en cours — à rejouer |
| T4-X3-019 | S3 | Réglages simulation › « Perte LID déclarée par technologie de cellule (%) », « Coefficient | — | OUVERT (aucun commit ne le cite) |
| T4-X4-001 | S2 | Devis › Édition complète › Lignes (option sans batterie) | 1cd7a05dda db907fb5d6 | corrigé sur main — à rejouer |
| T4-X4-002 | S3 | Fiche du lead › Historique ; onglet « 1 devis » ; édition complète | — | OUVERT (aucun commit ne le cite) |
| T4-X4-003 | S3 | Fiche du lead › « Devis auto » | — | OUVERT (aucun commit ne le cite) |
| T4-X4-004 | S2 | Devis › Édition complète › Technique › carte « Tailles Éco / Recommandé / Max », onglet «  | a7b49100e9 a7f66ba39e e390c95388 | corrigé sur main — à rejouer |
| T4-X4-005 | S2 | Ventes › Devis (liste /ventes/devis) | 083d1ff256 972db8aa88 | corrigé, rejoué par X9 |
| T4-X4-006 | S3 | Devis › Édition complète, compteurs du haut (onglet Document) | d04df9f6ce | corrigé sur main — à rejouer |
| T4-X4-007 | S3 | Fiche du lead › devis › « PDF ▾ » › « Premium (PDF complet) » › « Télécharger le PDF » (ca | — | OUVERT (aucun commit ne le cite) |
| T4-X4-008 | S2 | PDF Premium de DEV-202611-0130 (page 1 et page 4) contre fiche du lead X4-r1 | 347e4e1154 | corrigé sur main — à rejouer |
| T4-X4-009 | S3 | Ventes › Devis (liste) › ligne DEV-202611-0136 › bouton « Envoyer » | 75ff219226 | corrigé sur main — à rejouer |
| T4-X4-010 | S3 | Ventes › Factures, carte « À ÉCHOIR ≤ 7 J » | 054f3e431a bad8dad930 | corrigé sur main — à rejouer |
| T4-X4-011 | S2 | Nouveau devis › Lignes › « Plusieurs propriétés ? » › « + Villas différentes » | 16fb2dd59f 4ce57f0645 50f6ef6ed1 | corrigé sur main — à rejouer |
| T4-X4-012 | S3 | Nouveau devis › « Créer » › fenêtre « Désignation modifiée » | 1255de47fb cb01462c4c | corrigé sur main — à rejouer |
| T4-X4-013 | S3 | Nouveau devis › Document › « Date de validité » | 90edbcf6c1 ba97fc0a25 fa3caba30d | corrigé sur main — à rejouer |
| T4-X4-014 | S3 | Nouveau devis › « Créer » › panneau « Devis enregistré » | 926b9c5955 | corrigé sur main — à rejouer |
| T4-X4-015 | S3 | Nouveau devis › « Créer » › fenêtre « Désignation modifiée » › « Renommer sur ce devis seu | 7a03fc1c7d | corrigé sur main — à rejouer |
| T4-X4-016 | S2 | Devis C&I › Édition complète › « Détails du calcul » › « Économies (moteur serveur) » | f8ff13eb13 | corrigé sur main — à rejouer |
| T4-X4-017 | S3 | Nouveau devis › Agricole › « Énergie actuelle et dépense déclarée » › « Mois d'irrigation  | 93bbc05f04 f6fcdc37ee | corrigé sur main — à rejouer |
| T4-X4-018 | S2 | Devis › Édition complète › Simulation › « Aperçu de la Simulation » (DEV-202611-0133, lead | 6fb47b1949 7f98aedb8d | corrigé sur main — à rejouer |
| T4-X4-019 | S3 | Devis › Édition complète › « Surcharges (registre) » (Administrateur) | 3db68368af bedb9c388c | corrigé sur main — à rejouer |
| T4-X4-020 | S2 | Devis › Édition complète › carte « Marge indicative (interne) » (Administrateur) | 4ce57f0645 | corrigé sur main — à rejouer |
| T4-X4-021 | S2 | Devis envoyé › Édition complète ouverte dans deux onglets (même utilisateur) | 2d5258bd87 | corrigé sur main — à rejouer |
| T4-X4-022 | S3 | Nouveau devis › Enregistrement › « Réinitialiser » | d93c796d08 | corrigé sur main — à rejouer |
| T4-X5-001 | S2 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | a516775dbd | corrigé, rejoué par X9 |
| T4-X5-002 | S2 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 93eeb00905 | corrigé sur main — à rejouer |
| T4-X5-003 | S2 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 70d6f32690 ae5726103d c096d3d9d1 | corrigé sur main — à rejouer |
| T4-X5-004 | S2 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | a723c5f232 a8a036fd8f | corrigé sur main — à rejouer |
| T4-X5-005 | S3 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 6da220f4ea b3ceb74d00 | rejoué « pas-corrige » par X9, puis corrigé — à rejouer |
| T4-X5-006 | S3 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 7da6328893 | corrigé, rejoué par X9 |
| T4-X5-007 | S4 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 16c59c532c 9ad4e034a7 | corrigé, rejoué par X9 |
| T4-X5-008 | S3 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | f4cf308feb | corrigé, rejoué par X9 |
| T4-X5-009 | S1 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | d5df62a70f | corrigé, rejoué par X9 |
| T4-X5-010 | S2 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 7a26fd5532 b064a874c1 | corrigé sur main — à rejouer |
| T4-X5-011 | S2 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | b34fcaa326 | corrigé sur main — à rejouer |
| T4-X5-012 | S2 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 137fca1713 4a46af30e2 | corrigé sur main — à rejouer |
| T4-X5-013 | S3 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 30b20898a0 | corrigé, rejoué par X9 |
| T4-X5-014 | S3 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 0dfbe0608e | corrigé, rejoué par X9 |
| T4-X5-015 | S3 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | 365457ea51 | corrigé sur main — à rejouer |
| T4-X5-016 | S3 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | d8f89863af | corrigé, rejoué par X9 |
| T4-X5-017 | S4 | Calepinage 1973 (lead X5-n, Casablanca, factures hiver 1 200 / été 700 MAD, présent en jou | b4c2043839 c9d0316c83 efcedcb5e3 | rejoué « pas-corrige » par X9, puis corrigé — à rejouer |
| T4-X6-001 | S4 | Fiche du lead → onglet Devis → « Devis automatique » (bandeau « Devis créé ») contre carte | fd8e7c2ca4 | corrigé dans le lot en cours — à rejouer |
| T4-X6-002 | S3 | PDF « Document commercial » page 1 contre carte « Conception » de la fiche du lead | 65f3c21a2e | corrigé dans le lot en cours — à rejouer |
| T4-X6-003 | S2 | PDF « Document industriel » (4 pages) et « Devis une page » du devis automatique industrie | — | OUVERT (aucun commit ne le cite) |
| T4-X6-004 | S3 | Liste des devis → PDF du devis automatique d'un site en moyenne tension → case « Devis Fin | 46ab9fb170 b1c1c58bdf | corrigé dans le lot en cours — à rejouer |
| T4-X6-005 | S3 | Ventes → Devis (liste), menu « Plus d'actions » d'une ligne | — | OUVERT (aucun commit ne le cite) |
| T4-X6-006 | S2 | Fiche du lead → carte « Conception » (colonne de droite) après le devis automatique, contr | 1d3456f6c0 87cf062aaf | corrigé dans le lot en cours — à rejouer |
| T4-X6-007 | S2 | Édition complète du devis C&I (fiche du lead → onglet « 1 devis » → « Modifier ») : cartes | 209a9d6b97 | corrigé dans le lot en cours — à rejouer |
| T4-X6-008 | S2 | Édition complète du devis C&I → « Consommation du site » 12 mois (kWh) → cartes « Option s | 209a9d6b97 | corrigé dans le lot en cours — à rejouer |
| T4-X6-009 | S2 | Édition complète du devis C&I → « Consommation du site » → « Factures (MAD) » | 7509897775 | corrigé dans le lot en cours — à rejouer |
| T4-X6-010 | S3 | Édition complète du devis C&I → aperçu de l'étude (cartes « Option sans / avec batterie ») | 53e8a0d040 | corrigé dans le lot en cours — à rejouer |
| T4-X6-011 | S4 | Édition complète du devis C&I → cartes de l'étude pendant l'aperçu | 53e8a0d040 | corrigé dans le lot en cours — à rejouer |
| T4-X6-012 | S2 | Édition complète du devis C&I après un changement de la facture du lead dans un autre ongl | 21cf53e62a af258cdba0 | corrigé dans le lot en cours — à rejouer |
| T4-X6-013 | S1 | Devis automatique commercial à deux options, PDF « Document commercial » page 2 (« Spécifi | 1d3456f6c0 87cf062aaf | corrigé dans le lot en cours — à rejouer |
| T4-X6-014 | S3 | Fiche du lead commercial (formulaire) et édition complète du devis en marché « Commercial  | — | OUVERT (aucun commit ne le cite) |
| T4-X6-015 | S3 | Édition complète d'un devis résidentiel dont le lead porte « Taille souhaitée (kWc) » (ban | — | OUVERT (aucun commit ne le cite) |
| T4-X6-016 | S3 | Édition complète d'un devis résidentiel → « Paramètres Techniques » et carte « Système »,  | — | OUVERT (aucun commit ne le cite) |
| T4-X6-017 | S3 | Fiche du lead → panneau du devis juste créé (édition complète, devis sans onduleur) | — | OUVERT (aucun commit ne le cite) |
| T4-X6-018 | S3 | Édition complète du devis (Administrateur) → « Surcharges (registre) » → « Option Recomman | — | OUVERT (aucun commit ne le cite) |
| T4-X6-019 | S2 | Édition complète du devis → « Ajouter le BOQ électrique » (GEN-LIG-007) | 4add15a19f | corrigé dans le lot en cours — à rejouer |
| T4-X8-001 | S2 | Relevé de visite au téléphone (/calepinage/:id/releve), calepinage 1978 du lead X8-q (rési | bce467cc6c | corrigé dans le lot en cours — à rejouer |
| T4-X8-002 | S3 | Relevé de visite au téléphone, calepinage 1978 du lead X8-q (résidentiel, Marrakech + GPS, | 22216447bd | corrigé dans le lot en cours — à rejouer |
| T4-X8-003 | S3 | Relevé de visite au téléphone, retour du réseau | 274ecbc8a9 | corrigé dans le lot en cours — à rejouer |
| T4-X8-004 | S3 | Relevé de visite au téléphone | 68aa5905e3 | corrigé dans le lot en cours — à rejouer |
| T4-X8-005 | S2 | « Montrer au client » (/calepinage/:id/client) au téléphone | — | OUVERT (aucun commit ne le cite) |
| T4-X8-006 | S2 | Atelier au téléphone › rail › « Avancé » | — | OUVERT (aucun commit ne le cite) |
| T4-X8-007 | S3 | Atelier au téléphone › « Montrer au client » | — | OUVERT (aucun commit ne le cite) |
| T4-X8-008 | S3 | Atelier au téléphone, mode Expert › Panneaux › Déplacer les panneaux › « ✥ Placement libre | — | OUVERT (aucun commit ne le cite) |
| T4-X8-009 | S4 | Atelier au téléphone › barre d’outils de la carte | — | OUVERT (aucun commit ne le cite) |
| T4-X8-010 | S3 | Atelier, bandeau « BROUILLON LOCAL » | — | OUVERT (aucun commit ne le cite) |
| T4-X8-011 | S3 | Étape 2 Les panneaux › « Combien de panneaux ? » › carte « Couvrir la facture » | — | OUVERT (aucun commit ne le cite) |
| T4-X8-012 | S3 | Mode Expert › Panneaux › bloc « Recommandation » | — | OUVERT (aucun commit ne le cite) |
| T4-X8-013 | S3 | Production de la pose 5 panneaux · 3,55 kWc | — | OUVERT (aucun commit ne le cite) |
| T4-X8-014 | S2 | Technicien : lanceur, application VENTES, /ventes/devis/nouveau | — | OUVERT (aucun commit ne le cite) |
| T4-X8-015 | S3 | Technicien : /ventes/factures | — | OUVERT (aucun commit ne le cite) |
| T4-X8-016 | S3 | Technicien : fiche du lead par adresse | — | OUVERT (aucun commit ne le cite) |
| T4-X8-017 | S3 | Technicien : calepinage, relevé, visites | — | OUVERT (aucun commit ne le cite) |
| T4-X9-001 | S4 | Calepinage 1974 › Expert › Documents › « Importer une conception » avec un fichier sans to | 9f4cbd14b0 | corrigé sur main — à rejouer |
| T4-X9-002 | S4 | Calepinage 1974 › étape 3 Le raccordement › liste « Onduleur » | 408a33f68a 41acb18caf 42750763ef | corrigé sur main — à rejouer |
| T4-X9-003 | S2 | Calepinage 1974 › Expert › carte « TOTAL — TOUTES LES ZONES » (et carte Recommandation) | 230dd4fc70 | corrigé sur main — à rejouer |
| T4-X9-004 | S2 | Calepinage 1974 › Expert › colonne de droite, sous « Affiner ma consommation » | 77e4609403 | corrigé sur main — à rejouer |
| T4-X9-005 | S2 | Calepinage 1974 › étape 2 Les panneaux (carte « Couvrir la facture ») + étape 4 + « Montre | 6a93963486 | corrigé sur main — à rejouer |
| T4-X9-006 | S4 | Calepinage 1974 › étape 2 Les panneaux › bande du haut (bureau 1440 × 900) | fc663d50de | corrigé sur main — à rejouer |
| T4-X9-007 | S3 | Calepinage 1974 › Expert › cartes Recommandation et TOTAL | 18926a9670 | corrigé sur main — à rejouer |
| T4-X9-008 | S2 | Calepinage 1974 › étape 4 Les résultats › jauge « De la consommation » | d8d07e0ddb | corrigé sur main — à rejouer |
| T4-X9-009 | S2 | Fiche du lead X9-n › carte « Conception » (et pastille kWc), après enregistrements au cale | 3eab6b88ad 438b50856c | corrigé sur main — à rejouer |
| T4-X9-010 | S3 | Calepinage 1974 › Expert › Résultats › Avancé › « Comparer les variantes » › « Retenir » | 16c59c532c | corrigé sur main — à rejouer |
| T4-X9-011 | S3 | Calepinages › Nouveau calepinage (mode Client) | 204ebed5a3 c9367d9677 e390c95388 | corrigé sur main — à rejouer |
| T4-X9-012 | S3 | Calepinage 1975 › Expert › Toit › tableau « SITE — PANS DE TOIT ET SURFACES DE POSE » face | 07ff1935ee | corrigé sur main — à rejouer |
| T4-X9-013 | S3 | Calepinage 1975 sans lead (client X9-o) › bandeau du haut et bande de l'étape Panneaux, ap | 05c7f86a10 1a65ad77bd 9ab1323c9a | corrigé sur main — à rejouer |
| T4-X9-014 | S3 | Ventes › Devis (liste /ventes/devis) | — | OUVERT (aucun commit ne le cite) |
| T4-X9-015 | S4 | Ventes › Devis (en-tête et pagination) | 4b9a41c93f cc426a8565 | corrigé dans le lot en cours — à rejouer |
| T4-X9-016 | S3 | Fiche du lead X9-n › carte « Conception », après « Devis auto » | 3eab6b88ad c7131af98a | corrigé sur main — à rejouer |
| T4-X9-017 | S4 | Fiche du lead X9-n › haut de la colonne de gauche | — | OUVERT (aucun commit ne le cite) |
