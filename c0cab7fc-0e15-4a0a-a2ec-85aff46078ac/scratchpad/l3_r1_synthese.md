# L3 « best quote making machine » — R1 synthèse (24/10/2026)

Six lanes (A doc benchmark, B lien benchmark, C audit documents, D audit UX, E audit moteur, F audit lien) + lecture orchestrateur des rendus (hôtel p1-3 + une-page, pharmacie p1, usine industrielle p1-4 + une-page).

## Problèmes numérotés (preuve → lane)
P01 Page finance industrielle VIDE dans le cas courant (postes hors total ⇒ « Rentabilité non chiffrée ») — vu usine 1044 p3 (C-F3).
P02 « Investissement (clé en main) » imprimé alors que structure + câbles sont hors total ; retour recalculable (éco/an ÷ prix) ; une-page imprime Prix/kWc sur un prix incomplet (2 727 MAD/kWc usine) (C-F1, F2 ; vu).
P03 Bloc investissement cassé : « TTC »/« HT » orphelin, note en 3e cellule (C-F5 ; vu sur tous les rendus).
P04 Jargon client sur le PDF : « Baseline énergétique — kWh déclarés » (vu usine p1), « Analyse de rentabilité (CFO) — baseline, cashflow et payback », « Projection du moteur C&I », « Hypothèses du moteur », « grille ONEE publiée (repli, HT estimé ; capture du 16/02/2025, non reconfirmée 2026) », désignations brutes, « À confirmer : À chiffrer… », « Couverture conso », « prix à renseigner » (C-F6, F4).
P05 Autoconsommation / couverture jamais définies sur le document ; surplus jamais chiffré (C-F7, O7).
P06 Aucun graphique commercial, page 1 vide à 30 %, page 2 à moitié vide ; industriel 5 jalons seulement (C-O1, O3).
P07 Commercial sans aucune hypothèse (tarif + date, dégradation, indexation, horizon, O&M, onduleur, base de production 30°/sud) ; base de production jamais imprimée (C-O2, E-S1-1, S2-3).
P08 Couverture = catégorie, pas le projet ; contact = raison sociale ; téléphone brut ; aucun commercial nommé, aucun CTA/QR (C-F10, O5).
P09 Page 2 sans récapitulatif technique (modules × n, onduleurs, structure, surface) (C-O4).
P10 Périmètre / non compris / obligations client / durées absents ; CGV C&I = 3 puces (C-F8, F9).
P11 Moteur : production toujours 30° sud « free », jamais dit ; O&M = 0 dans le flux si non souscrit ; autoconso sur journées moyennes (biais haut à la marge) ; PR modélisé jamais câblé ; dégradation 0,5 % (source 2012) ; aucune incertitude par défaut ; règle des 10 ans = proxy non énoncé (E S1-1..4, S2-1..7).
P12 UX : bouton « Devis auto » actif puis 409 « prix à renseigner » sans issue (D-R1-01) ; aucun retour après le devis auto (D-R1-12) ; panneau sans envoi, 4 interfaces d'envoi (R1-13/14) ; phase dans une autre section sous un autre nom, questionnaire résidentiel affiché aux pros, 6 champs redondants, puce rythme sur les jours (R1-16/17/18/04) ; aides et refus en jargon (R1-09/10) ; générateur non pré-rempli, carte résultat d'ingénieur, concepts d'analyste avant toute valeur (R1-07/11/20) ; formats PDF qui créent des devis, catalogue préchargé pour rien, « Inclure l'étude » et options Éco/Max en C&I (R1-15/21/05/06) ; visite sans action (R1-19) ; ?auto=1 perd alertes/field (R1-02).
P13 Lien : IP de preuve peut-être Cloudflare (F-S1-a) ; signer = détenir le lien + un nom, aucune attestation de pouvoir, consentement citant la loi 31-08 (B2C) (F-S1-b) ; sceau sans l'étude, PDF signé non haché (F-S1-c) ; révocation manuelle seule, lien vivant 90 j après réception (F-S1-d) ; scanners B2B comptés comme ouvertures (F-S1-e) ; pas de refus explicite, confirmation à une seule adresse sans copie vendeur (F-S2-1/2).
P14 Benchmark (A, B) : fiche de décision p.1, flux 25 ans unique, sensibilités 3×3 + P90, annexe d'hypothèses, courbe de charge réelle, garantie de performance définie, risques à côté de la valeur, surplus 82-21 explicite (20 %, tarifs ANRE), e-signature + validité + pré-signature ; lien : GET rend / POST accepte, certificat aux deux parties, alertes commercial, « demander une modification », AR en bascule.

## Décisions fondateur à re-poser (non construites sans réponse)
Q1 O&M : déduire un « entretien minimum » saisi dans Paramètres (ou encrassement sans O&M) — CIQ342/D-CIQ-12.
Q2 Incertitude par défaut : P90 + 4 sensibilités seedées dans Paramètres — D-CIQ-10.
Q3 Postes hors total : « provision estimée » étiquetée plutôt qu'omission — D-ACI-2.
Q4 Moteur chiffres : autoconso 8760 h (série horaire PVGIS), dégradation courbe garantie (1 % an 1 puis 0,4 %), production selon pente/azimut/pose déclarés — nouveaux rendus seulement.
Q5 CO₂ évité : facteur réseau marocain sourcé (CIQ344).
Q6 Lien : signature qualifiée (PSCo) exigée au-delà d'un montant ? révocation automatique après refus/nouvelle version ?
Q7 « prix à renseigner » / « tarif à renseigner » sur le document client (D-ACI-12).

## Plan R2 (construit dans ce run, sans décision)
DOC (opus) : P01 (bloc analyse énergie + hypothèses à la place de la page vide), P02 (titre honnête, lignes hors total p.2, Prix/kWc supprimé, légende), P03, P04, P05, P06 (barres mensuelles prod/conso/autoconso SVG p.1 commercial, table 25 lignes industriel), P07 (tableau d'hypothèses + base de production + règle de taille énoncée), P08 (H1 projet, contact, téléphone, commercial nommé, prochaines étapes + QR si lien), P09, AR kicker.
UX-LEAD (sonnet) : R1-01 (catalogue_ci dans devis_auto, bouton désactivé avec motif + lien), R1-12 (bandeau de succès ; réponse auto enrichie), R1-13/14 (envoyer depuis l'aperçu, une boîte), R1-04/16/17/18 (phase dans Pro, questionnaire résidentiel masqué, puce → catégorie, raccourci), R1-09/10 (textes), R1-05/06/15/21 (nettoyages), R1-19 (planifier la visite), R1-02/08.
UX-GEN (sonnet) : R1-07 (pré-remplissage éditable), R1-11 (synthèse 4 chiffres), R1-20 (Affiner replié), R1-23.
LINK (opus) : F-S1-b (attestation de pouvoir + consentement B2B + email/tel signataire), S1-c (sceau = étude + hash PDF), S1-d (révocation auto refus/version/perte), S1-e (scanners), S2-1 (décliner / délai), S2-2 (confirmation signataire + copie vendeur + reçu).
MOI : F-S1-a (contrôle prod lecture seule puis correctif), E-S1-4 (PR câblé), tâches v3, acceptation live, R3 vérificateurs, R4 Fable.
