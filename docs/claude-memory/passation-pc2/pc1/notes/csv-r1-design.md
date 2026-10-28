# CSV — R1 : constats prouvés + solutions proposées (à valider R3)

Pile : instance CSV (code origin/main e0fe749cc copié dans un conteneur, base de dev partagée), demo_admin.
Leads de démo créés sur la base de DEV locale : 2232 (hôtel), 2233 (bureau).

## Constats (preuve en direct)
- C1 (S1) Hôtel : la question « Réponses propres à l'activité » (`reponses_categorie`, nature `objet`) s'affiche comme un champ texte ; « 60 » → 400 « Un objet JSON est attendu ». La 2e clé (« Piscine chauffée ») s'affiche comme une consigne grise. L'étape 3 reste bloquée (jours/heures n'apparaissent qu'en « Ensuite… »). Code : panneau_appel.py::_question (nature='objet') ; PanneauScriptAppel.jsx::Question (aucun rendu objet).
- C2 (S1) Ordre : facture (MAD) est posée AVANT BT/MT. Lead 2232 : facture_hiver=5000 puis tension=mt ⇒ le script ne pose plus ni kWh ni phase ; la carte devis auto dit manquants = conso kWh + phase. Impasse.
- C3 (S1) Contrat d'électricité jamais posé par le script (help_text « Question à l'appel » existe, CIQ666). Lead 2233 (BT, tout répondu sauf C1) : devis_auto.pret=false, manquants = conso (MAD ne compte qu'avec contrat BT) + contrat.
- C4 (S1) Phase (`raccordement`) servie seulement commercial non-MT ; exigée pour tout C&I (devis_auto.champs_requis, ADEV89).
- C5 (S2) Talon / équipements hors horaires : absent du script (et sur main). #1074 ajoute `equipements_hors_horaires` au questionnaire, pas au script.
- C6 (S2) Garde-fous périmés pour pro : AUCUNE_ESTIMATION_SEGMENT (« le calcul ne sait pas encore le traiter ») et MENTION_D7 (« orientation, inclinaison… pas au chiffre ») — faux pour le C&I (devis auto existe ; le moteur lit pente/orientation).
- C7 (S2) Discours visite pro (visiteGuidance.js PHASE_GUIDANCE_PRO[2]) : « pour verrouiller le prix, pas pour le changer » — contredit le bandeau fondateur du 26/10 « Devis préliminaire — les prix pourront être ajustés après la visite technique ».
- C8 (S2) Visite C&I : pas de phase mono/tri dans le gabarit `ci` ; pas de retour vers lead.raccordement.
- C9 (S1, CORC) aucun chemin visite validée → devis révisé (lignes). Envoyé à CORC.
- C10 (S2, CMP) sémantique longueurs câble visite vs composition. Envoyé à CMP.

## Solutions proposées (fichiers CSV = propriétaire lead)
- S1 : `panneau_appel.py` sert pour `reponses_categorie` une liste `sous_questions` [{cle, libelle, nature, choix}] (clés encore vides, ≤3) ; l'écran rend une entrée par clé et écrit l'objet fusionné {…existant, cle: valeur}. Contrat `crm/contract_samples/panneau_appel.json` réaligné.
- S2 : ETAPES_PRO réordonnées : raccordement (tension → contrat [BT] → option [force motrice] → phase → puissance) PUIS facture ; la question facture = kWh si industriel ou MT ; l'étape facture n'est « répondue » que si la conso COMPTE pour le moteur (même règle que `devis_auto._facture_mad_compte`, réutilisée, jamais copiée).
- S3 : `contrat_electricite` (BT ou tension inconnue) + `option_tarifaire_bt` (si force motrice) servis dans l'étape raccordement.
- S4 : `raccordement` servi pour TOUT C&I (industriel compris, MT compris : « site en moyenne tension, donc triphasé — je confirme ? »). Décision prise pour le fondateur (à revoir).
- S5 : (après merge #1074) `equipements_hors_horaires` servi dans l'étape activité ; libellé catégorie dérivé des choix (23).
- S6 : garde-fous pro : retirer AUCUNE_ESTIMATION_SEGMENT de la famille pro ; MENTION_D7 non affichée pour pro (texte pro : l'ombrage se relève à la visite).
- S7 : discours visite pro aligné sur le bandeau du 26/10 (prix ajustable après visite, devis définitif). Décision prise pour le fondateur (à revoir).
- S8 : visite C&I : champ `phases` (mono/tri) dans `comptage` du gabarit `ci` (+ schéma front `MESURES_SCHEMA_CI`), retour vers `lead.raccordement` (provenance mesure_visite) via `visites_retour_lead.appliquer_releve_ci`.

## Ajout (visite en vrai, mobile 390 px, visite 23 du lead 2233 « Bureaux »)
- C11 (S2) La visite C&I redemande « Catégorie du site » et « Horaires et jours d'ouverture » (REQUIS, vides) alors que le lead les porte déjà (categorie_commerciale=bureau). Pas de pré-remplissage (visite_checklist.py::_categorie_site_commerce ; grep prefill visites : 0). Liste figée à 10 catégories (CATEGORIES_COMMERCIALES, test_ciq651). Libellé « (optionnel) (optionnel) » doublé sur le slot secours (libellé contient déjà « (optionnel) » + l'écran l'ajoute).
- S9 : servir dans la checklist, pour chaque mesure qui a un équivalent sur le lead (catégorie, horaires, groupe électrogène, tension, puissance souscrite), la valeur DÉCLARÉE (`declare: {valeur, libelle, source}`) ; l'écran affiche « Déclaré au téléphone : … » + bouton « Confirmer » (une touche) ou corriger. Le technicien ne ressaisit plus.

## Ajout (CMP, D-CMP-2) — sémantique des longueurs
- longueur_dc_m = distance ALLER SIMPLE champ → onduleur ; câble DC = 2 × chaînes × distance. longueur_ac_m = distance onduleur → TGBT par onduleur.
- S10 (CSV) : libellés du relevé visite `cheminement.trajets` : « Distance champ → onduleur (m, un sens) », « Distance onduleur → TGBT (m) » (backend visite_checklist.py + schéma front MESURES_SCHEMA_CI). Plusieurs trajets → `_couche_visite` doit prendre le PLUS LONG (CORC).

## Mission élargie (coordinatrice 27/10) : script d'appel + suivi pour les 3 segments (C&I, résidentiel, agricole). Checklist visite agricole → future session AGV (module neuf visite_checklist_pompage.py ; appel d'une ligne posé par CSV sur demande).

## R3 lentille « Meryem + client » — décisions retenues
- Ordre retenu (S2 révisé) : tension (mots simples : compteur ordinaire / poste) → facture (MAD si BT, kWh si MT ou industriel) → contrat (lu sur la facture, issue « ne sait pas ») → option (force motrice seulement) → puissance souscrite → phase. Si contrat « ne sait pas » : la facture MAD ne compte pas → l'étape facture redemande les kWh (règle devis_auto réutilisée). Décision prise pour le fondateur (à revoir) : amende l'ORDRE de D-CIQ-7 (mêmes 5 étapes).
- Phase pour un site MT : question « Vos machines tournent en triphasé ? » (pas « je confirme »). Proposé à CVL/CORC : MT déclarée ⇒ triphasé implicite (devis_auto.champs_requis / ADEV89).
- Discours visite pro (S7) : « Le devis que vous avez reçu est préliminaire, établi à partir de vos factures. Quand le technicien passe, il relève la structure du bâtiment, l'accès à la toiture et le tableau électrique, et c'est avec ça qu'on confirme le prix définitif — il peut être ajusté. »
- POUR CQST (questionnaire.py::_manquantes_pro) : `_vide` tient « ne_sait_pas » (contrat) / « inconnu » (phase) pour RÉPONDU, alors que devis_auto les compte vides → le questionnaire ne redemande pas le contrat alors que le devis reste bloqué.

## R1 résidentiel + agricole (lecture, à rejouer en direct en vague 2)
Résidentiel : R1 « été différent ? Non » jamais clos (BooleanField default False = « pas répondu ») ; R2 pas de question parlée pour l'été ; R3 facture bimestrielle enregistrée ×2 (l'écran n'envoie jamais `facture_periodicite`) ; R5 grandeurs d'équipement (clim kW, VE…) jamais posées → couches omises ; ville jamais posée (refus `ville` si ni ville ni GPS) ; type_bien/objectif posés sans effet chiffre (cadence seulement) ; D-RES-2710-2 (VE possédé) non construit (moteur, hors CSV).
Agricole : G1 un lead rempli par le seul script est refusé : `pompe_hmt_m` et `raccordement` jamais posés ; G2 surface+culture ne comblent pas champs_requis (CVL/devis_auto) ; G3 `electricite_sur_place` ≠ `raccordement` ; G4 heures de la pompe actuelle posées même si « aucune » ; G5 `pompe_actuelle_debit_m3h` jamais posé ; G6 butane sans jours/semaine ; G7 dépense électrique posée non consommée ; garde-fous affichés à tort (AUCUNE_ESTIMATION, bloc « ne compte pas »).
Découpage : vague 1 = C&I (S1-S4, S6, S7) + garde-fous par segment + visite C&I (S8-S10) ; vague 2 = résidentiel + agricole ; vague 3 = visite → devis révisé (après contrat CORC).
