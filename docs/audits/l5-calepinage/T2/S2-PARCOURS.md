# Tour 2 — S2-PARCOURS (la commerciale à son premier jour, simplicité, bureau 1440 × 900 clair)

Compte `rev_parcours`, instrument http://127.0.0.1:5241 (`origin/main@bfb859c90`). Captures et scripts :
`C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/S2-PARCOURS/`
(`cap/` pour les captures). Leads créés : « S2-PARCOURS Villa Marrakech » (facture 900 MAD/mois, calepinage 1899,
devis DEV-202611-0001) et « S2-PARCOURS Riad sans facture » (calepinage 1921, aucun devis : confirmation refusée).

## 1. Verdict

La coque guidée est belle et proche des maquettes (rail, panneau d'étape, Documents « Prêt à envoyer ? »), mais le
parcours de la commerciale casse en cinq endroits : forme du toit refusée en silence, pose repavée à 246 % de la
consommation, « Matériel non désigné » après avoir tout choisi, aucun retour visible après « Générer le devis »,
et un résultat COMPLET hors de sa portée au premier jour. K6 n'est pas tenu.

## 2. Contre-vérification (29 jouées sur 54)

ok 18 · partiel 8 · non-fait 3 · faux 0 · régression 0 · déjà-présent 0 · non essayé 25.

- ok : ACAL852, 853, 860, 861, 867, 871, 893, 896, 937, 938, 948, 961, 964, 971, 1281, 1282, 1284, 1285.
- partiel : ACAL851 (avant tout choix, carte en 710 W et pose en 720 W), 858 (reste « non désigné » après le choix),
  864 (« le pan Zone 3 … non pavé », pousse à remplir le pan nord), 868 (pas de « Préparer les documents » à
  l'étape Résultats), 872 (« ? » ne s'ouvre pas à la touche Entrée), 1171 (ligne grise sans geste), 1283 (nom du
  lead absent du bandeau), 1311 (« Voir les valeurs » ouvre l'ancienne section, 4 contre 11 réglages).
- non-fait : ACAL866 (aucune carte « Devis … créé — Voir le devis » visible), 869 (pas de « Personnaliser la
  disposition »), 876 (aucun « ? » sur les chiffres de l'étape Panneaux).

Cases de matrice cassées : K-IMPASSE — « tapez l'adresse » (pas de champ en guidé), « Régler » matériel → Plan
importé, « Réglez-le dans Réglages › Site » (écran inexistant), résultat complet inatteignable ; K-JARGON — « Zone 2/3 »,
« repavé à ses cotes », « non pavé », « (non vendue) », phrase « repli assumé », clés brutes des fiches, même consigne
×4 ; K-ACTION-ENFOUIE — vue dézoomée après « 2 pans », « Enregistrer les réglages » à 11 094 px, Vidéo 10 s sous
« Avancé » ; K-DEFAUT-CHOIX — toit plat par défaut, pose « toit rempli » après changement de forme, 29° affiché contre
22° appliqué, gabarits français pour une société marocaine.

## 3. Constats neufs (`registre/constats/T2-S2-PARCOURS.jsonl`, 26 : S2 × 8, S3 × 18)

- 001 S3 — consigne « tapez l'adresse » sans champ d'adresse en mode guidé (il n'existe qu'en expert).
- 002 S2 — « 2 pans » cliqué avant « Créer le toit » refusé en silence → toit plat à 1 pan.
- 003 S3 — après « 2 pans », Largeur affiche 4,3 au lieu de 8,6 et la vue se dézoome.
- 004 S2 — le découpage repave le toit : 15 panneaux, ≈ 246 % de la consommation, recommandation (4) perdue.
- 005 S3 — l'atelier rouvre toujours sur l'étape 3 Électrique.
- 006 S3 — « Couvrir la facture » = « ≈ 65 % de la consommation ».
- 007 S3 — le panneau choisi ne vaut que pour « Zone 2 » ; « repavé à ses cotes ».
- 008 S3 — « En savoir plus » n'ajoute rien ; « (non vendue) » inexpliqué.
- 009 S2 — Résultats : 20 pertes, 7 listées, « 4 réglages vides » contre 11 ; après démarrage rapide encore 19.
- 010 S3 — ligne technique brute « longueur de dossier … repli assumé » ; « Le calepinage a changé » faux.
- 011 S2 — panneau et onduleur choisis, « Matériel non désigné » reste (cause servie, non montrée).
- 012 S2 — « Régler » du matériel ouvre le bloc Plan importé de l'étape Toit.
- 013 S3 — « pan Zone 3 non pavé → Remplir le pan » et pente « Zone 3 » à confirmer jamais proposée.
- 014 S3 — Réglages : JSON brut dans une valeur ; chaque valeur exige une source.
- 015 S2 — après « Générer le devis » (201), rien à l'écran ; « Devis lié » sans lien.
- 016 S3 — « Matériel désigné » ne passe au vert qu'après la génération du devis.
- 017 S2 — trois productions pour 4 panneaux (4 312 / « au plus » 6 277 / devis 4 636 « standard de la ville ») ;
  devis du 23/11 aux « règles d'avant le 21/11 » — à confirmer par l'orchestrateur.
- 018 S3 — « Réglez-le dans Réglages › Site » : écran inexistant.
- 019 S3 — même consigne « facture absente » dite quatre fois.
- 020 S3 — « Inclinaison 29° » affichée, « 22° appliquée » plus bas.
- 021 S3 — bandeau « Calepinage 1899 — Marrakech » : le nom du client n'apparaît nulle part.
- 022 S3 — « ? » : Entrée ne l'ouvre pas, Espace oui.
- 023 S3 — genres de gabarit français (Enedis, Consuel), aucun dossier marocain.
- 024 S3 — « Choose File No file chosen » en anglais dans l'atelier (jumeau d'ACAL971).
- 025 S3 — clés brutes (noct_c, bifacialite_pct, vmp_v…) dans Fiches incomplètes et Matériel électrique.
- 026 S2 — mesure K6 (ci-dessous) : résultat complet inatteignable.

### Mesure K6 (société au premier jour, lead avec facture)

Nouveau calepinage → lead → Créer (4 clics ; avec 20 leads et plus, il faut taper pour trouver le sien) · Toit :
2 saisies de cotes, Créer, « 2 pans » (après coup), Confirmer la pente (3 clics) · Panneaux : choix du panneau (2),
« Couvrir la facture » (1) pour défaire la pose à 15 · Électrique : onduleur (1 choix technique), Raccorder (1) ·
Résultats : « Voir les valeurs » (page de 15 écrans), « Remplir les 11 réglages vides », retour, Relancer (≈ 2 min) ·
Documents : Générer le devis (1) puis Ventes › Devis pour le retrouver (2). Total ≈ 22 clics, 2 saisies, 2 choix de
matériel, 5 étapes + 1 détour. Le résultat reste « au plus · 19 pertes » : il faut encore la poussière, le
vieillissement, les arrêts (tableau JSON), chacun avec sa source, et compléter deux fiches produit au catalogue.
Mots qu'elle ne comprend pas : non vendue, Zone 2/3, repavé, cotes, non pavé, source du repère, jeu de réglages
société, plafond, pertes, face arrière, écarts entre panneaux, réglage de la puissance de l'onduleur, fiche du
panneau, longueur de dossier, repli assumé, dossier électrique 19 points, chutes de tension, Fresnel, W/m²K.
Impasses : l'adresse à taper, la forme refusée, « Matériel non désigné » et son « Régler », le résultat incomplet
sans suite possible, l'absence de lien après le devis.

## 4. Ce qui est bien (à ne pas casser)

Coque plein écran fidèle (rail 113 px, bandeau 56 px, nom 16 px gras, aucun texte < 12 px mesuré) ; bouton
d'étape suivante dans la barre fixe (Toit, Panneaux, Électrique) ; carte de pente « 22° · face sud — À confirmer ·
Confirmer / Je ne la connais pas » ; lead sans facture : aucun « 0 MAD », contrôle orange « le toit est rempli :
17 kWc » puis cadre « Confirmer et générer » avec le total ; Documents « Prêt à envoyer ? » + documents, comme la
maquette ; liens « Choisir la norme » / « Renseigner » qui atterrissent sur le champ, focalisé ; page Démarrage
rapide avec sources citées ; vidéo 10 s (9,9 s, rotation, aucun prix) ; préréglages avec unités ; brouillon local
proposé à la reprise.

## 5. Non essayé, et pourquoi

- ACAL854, 855, 859, 873, 880, 894 : demandent une simulation complète (jamais atteinte au premier jour) ou PVGIS
  coupé.
- ACAL862 (cas orange) : il faut un document d'avant CALX110 ; seul le vert (2,84 kWc) a été vu.
- ACAL857 (porte rouge), 947, 959, 960 : il faudrait écrire des réglages de la société partagée (visite exigée,
  favoris, modèle) ; je ne l'ai pas fait.
- ACAL874, 875, 877, 878, 879, 883, 884, 885, 888, 890, 891, 897, 906, 863 : temps épuisé (897 demande aussi
  une photo calée).
- Lisibilité sur photo aérienne : fond gris sur cette pile (fiche de l'instrument).
- ATTENTION — écriture partagée : en mesurant K6 j'ai appliqué « Remplir les 11 réglages vides » du Démarrage
  rapide sur la société de démonstration (POST `profil-depart`, 200) ; elle est commune à tous les comptes `rev_*`,
  et ses calepinages ne sont plus « au premier jour ». Réversible par « Retirer le profil ». Je n'y ai pas touché
  ensuite.
- À vérifier par l'orchestrateur : 4 panneaux recommandés (≈ 2,84 kWc, 65 % de la consommation) pour 900 MAD/mois,
  là où la maquette dit ≈ 7 kWc ; le niveau de règles d'un devis neuf généré depuis l'atelier (constat 017).

## 6. Trois propositions

1. **Une pose qui suit la cible, toujours** (OpenSolar, conception automatique en 4 étapes) : le toit créé reçoit la
   recommandation, un changement de forme la garde, « Le plus de panneaux » reste un choix explicite, et un seul
   chiffre de production court de la barre au devis.
2. **Un premier jour qui donne un résultat complet** (Reonic, 6 étapes sans réglage technique) : le démarrage
   rapide remplit TOUT ce qui a une valeur publiée en un geste depuis l'étape Résultats (sans quitter l'atelier),
   et les fiches du catalogue de départ sont complètes (Vmp, Voc, NOCT, Uc/Uv). Ce qui reste est dit « pour
   l'ingénieur » et ne bloque pas la commerciale.
3. **Une fin de parcours qui conclut** (K2 Base, 5 étapes jusqu'à l'offre ; maquette Documents) : après « Générer le
   devis », une carte « Devis DEV-… créé » avec « Voir le devis » et « Télécharger le PDF », le nom du client dans
   le bandeau, et l'atelier qui rouvre là où elle s'est arrêtée.
