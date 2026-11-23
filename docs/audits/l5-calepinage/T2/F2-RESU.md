# T2 — F2-RESU — l'ingénieur qui lit l'étude (étape Résultats, axe fonction)

Relecteur neuf, compte `rev_resu`, pile `l5cal` (http://127.0.0.1:5241, `origin/main@bfb859c90`), bureau 1440 × 900 clair
(jumeaux sombres regardés sur l'état « au plus »). Scripts et captures :
`C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-RESU/`
(captures dans `cap/`).

Données créées : lead 2423 « F2-RESU Villa Casablanca » (GPS posé, factures 900/1100 MAD), calepinage **1898**
(contour tracé à la souris, 109 m², toit plat, 4 × Canadian Solar 710 W « Couvrir la facture », 30° sud),
postes de pertes saisis SUR LE CALEPINAGE (salissure 2 %, chaleur 6 %, LID 1,5 %, qualité 0,5 %, ohmique DC 1,5 %,
AC 0,5 %, onduleur 3 %, indisponibilité 1 %), variante 357 retenue, devis **DEV-202611-0002** ; lead 2461 + calepinage
1930 vide (refus « sans module »). Réglages société : j'ai saisi `mode_meteo = pluriannuel` et `fenetre_annees = [2014, 2023]`
(source « Réglage société ») ; le **profil de départ (Démarrage rapide) a été appliqué par un autre relecteur** entre
23:52 et 23:58 — à mon passage la page disait « Aucun réglage à remplir » : je ne l'ai pas appliqué moi-même.

## 1. Verdict

L'étape Résultats guidée est enfin un écran de résultat (pleine largeur, héros 40 px, cartes « Mois par mois » et « Du
soleil au réseau », état « au plus » fidèle à sa maquette) — mais l'ingénieur ne peut pas encore l'envoyer en confiance :
**la même production se lit 4 362, 4 542, 5 131 puis 5 173 kWh** selon l'écran, deux lignes contraires disent ce que le
devis imprime, la couverture vaut 66 % dans l'atelier et 48 % dans le PDF client, l'écart PVGIS « + 17,3 % » est un
artefact de méthode affiché comme un fait, et le mode expert tasse le tableau de production dans 270 px.

## 2. Comptes

Contre-vérification (54 tâches) : **ok 17 · partiel 13 · non-fait 1 · faux 0 · régression 0 · déjà-présent 0 · non essayé 23**.

- ok : ACAL940, 1305, 700, 745, 979, 708, 756, 772, 762, 753, 755, 750, 761, 768, 978, 748, 696.
- partiel : ACAL1304 (S1), 1302, 1303, 709, 698, 710, 773, 760, 697, 732, 995, 774, 970.
- non-fait : ACAL707 (le tableau mensuel expert n'a que « Mois · P50 »).

Cases de matrice cassées (sur ce calepinage) :

- **K-GRANDEUR-UNIQUE** — production annuelle « 1 pan Sud » : casse (T2-F2-RESU-012, -024) ; « devis généré → /proposal » :
  casse (-024) ; part de consommation : casse (-013, -025) ; écart PVGIS : casse (-008) ; diagramme Pertes « Énergie
  livrée » : casse (-022) ; comptes de l'état « au plus » : casse (-005).
- **K-RETOUR-FAUX** — « rien simulé » : enregistrement qui lance une simulation refusée en silence (-004) ; liste
  « Pour un résultat complet » qui ne nomme pas le vrai blocage (-003) ; bandeau/rail non rafraîchis après calcul (-009) ;
  export « horaire » journalier (-019) ; consigne impossible sur l'export ombrage (-020) ; motif de l'horizon sous
  « Ombres proches » au rapport (-016) ; variante identique retenue → simulation périmée (-026).
- **K-JARGON** — clé brute : casse (-001, -014, -015, -018, -021) ; chemin/code : casse (« core.calepinage.soleil (CALX146) »,
  « (CALX170) ») ; répété sur l'écran : casse (-006, -018) ; répété sur plusieurs onglets : casse (motifs des étapes omises
  en guidé, expert, rapport, fiche client) ; document client : casse (-023).

### Tableau K-GRANDEUR-UNIQUE — calepinage 1898 (même conception)

| Endroit | kWc | Panneaux | Production annuelle | Écart nommé ? |
|---|---|---|---|---|
| (a) Barre de résumé de l'atelier, AVANT simulation (étape Panneaux) | 2,84 | 4 | **4 542 kWh/an** « estimation de la pose » + « ≈ 66 % » de la conso | non |
| (a) Barre de résumé APRÈS simulation | 2,84 | 4 | 5 131 puis **5 173 kWh** « Production la première année » | — (= serveur) |
| (a') Colonne de l'atelier, mode expert (« TOTAL — TOUTES LES ZONES », « Dans la durée ») | 2,84 | 4 × 710 W | **4 362 kWh/an**, 5 158 MAD/an, « Année 25 ~3 867 » (dégradation 0,5 %/an inventée) | non (-012) |
| (b) Étape Résultats (P50) | 2,84 (en-tête) | 4 (en-tête) | 5 131 → **5 173 kWh** après génération du devis (onduleur posé par le devis) | — |
| (c) Fiche dans la liste `/calepinage` | 2,84 | 4 | 5 131 puis 5 173 kWh/an | ok (suit le serveur) |
| (d) Rapport d'étude PDF (19 p.) | 2,84 | 4 | 5 131,1 kWh (P50), P90 5 002,9 | ok à l'instant du rendu |
| (e) Devis `etude_params` | 2,84 | 4 | 4 541,81 kWh | — |
| (e) `/proposal` client | 2,84 | 4 × 710 W | **4 542 kWh/an**, couverture **48 %** | — |
| Bloc de provenance (expert) | — | — | « Devis : **4 362** (production imprimée au client) » ET « Le devis annonce : **4 542** » | contradiction (-024) |

Écarts nommés : P50 ↔ devis (+13,9 % ; « production standard de la ville » — D-ACAL-6) ; tout le reste ne l'est pas.

## 3. Constats neufs (registre `registre/constats/T2-F2-RESU.jsonl`)

- T2-F2-RESU-001 (S3, K-JARGON) — refus de simulation qui affiche `parametres.simulation.mode_meteo`, `tmy`.
- T2-F2-RESU-002 (S3, K-JARGON) — ligne 3 de « Pour un résultat complet » = phrase interne « repli assumé, jamais présenté comme un calcul ».
- T2-F2-RESU-003 (S3, K-RETOUR-FAUX) — la liste et le rail ne nomment pas le vrai blocage (mode météo) ; 1 / 4 / 2 comptes.
- T2-F2-RESU-004 (S3, K-RETOUR-FAUX) — « Enregistrer » lance une simulation 409 + erreur de console, rien à l'écran.
- T2-F2-RESU-005 (S3, K-GRANDEUR) — « 20 pertes » / 7 lignes / « 4 réglages vides » / « Aucun réglage à remplir ».
- T2-F2-RESU-006 (S3, K-JARGON) — même champ (coef. de température) listé deux fois, MPPT nommé « Réglage de la puissance de l'onduleur ».
- T2-F2-RESU-007 (S4) — encart « Démarrage rapide » clair en thème sombre.
- **T2-F2-RESU-008 (S2, K15)** — « Écart avec PVGIS + 17,3 % » : PVcalc reçoit les pertes TOTALES (IAM et chaleur comprises), comptées deux fois.
- T2-F2-RESU-009 (S3, K-RETOUR-FAUX) — après calcul, bandeau « Enregistré à 23:46 » et rail « 2 à régler » jusqu'au rechargement.
- T2-F2-RESU-010 (S3, K-JARGON) — motifs des étapes omises en langage de développeur.
- **T2-F2-RESU-011 (S2, K8)** — mode expert : onglet Production tassé dans 270 px (tuiles, graphique, tableau coupés).
- **T2-F2-RESU-012 (S2, K-GRANDEUR)** — atelier expert 4 362 kWh/an + dégradation inventée à côté de 5 131 kWh serveur.
- T2-F2-RESU-013 (S3, K-GRANDEUR) — « ≈ 66 % » à l'étape Panneaux, rien (ni tuile ni barres, ni motif) à l'étape Résultats.
- T2-F2-RESU-014 (S3, K-JARGON) — note « valeurs publiées » avec trois clés `electrique_societe.*`.
- T2-F2-RESU-015 (S3, K-JARGON) — rapport : postes du calepinage imprimés « saisie société », `texte`, `core.calepinage.soleil (CALX146)`.
- T2-F2-RESU-016 (S3, K-RETOUR-FAUX) — rapport p. 10-11 : étiquettes coupées, texte hors page, motif de l'horizon sous « Ombres proches ».
- T2-F2-RESU-017 (S3, K15) — « Année basse (9 fois sur 10) » = variabilité météo seule (−2,5 %), sans incertitude du modèle.
- T2-F2-RESU-018 (S3, K-JARGON) — « Où va l'énergie » (expert) : 6 motifs collés, même phrase ×5, « Production brute : non calculé ».
- **T2-F2-RESU-019 (S2, K-RETOUR-FAUX)** — export « Série horaire » au pas heure = une ligne par JOUR, sans le dire.
- T2-F2-RESU-020 (S3, K-RETOUR-FAUX) — export « Ombrage module par module » : « acces_modules : … calculez l'ombrage dans l'atelier » (jumeau d'ACAL732).
- T2-F2-RESU-021 (S3, K-JARGON) — onglet Pertes : « (CALX170) », `serie.colonne_energie`, `FicheTechnique.*`, source `texte`.
- T2-F2-RESU-022 (S3, K-GRANDEUR) — ligne « Énergie livrée » étiquetée « 19,6 % (pertes totales) ».
- **T2-F2-RESU-023 (S2, K-JARGON)** — fiche client « Pertes expliquées en 5 postes » remplie de motifs internes, 3 décimales.
- **T2-F2-RESU-024 (S2, K-GRANDEUR)** — « Devis : 4 362 kWh/an (production imprimée au client) » alors que le PDF imprime 4 542.
- **T2-F2-RESU-025 (S2, K-GRANDEUR)** — couverture 66 % dans l'atelier, 48 % dans le PDF client.
- T2-F2-RESU-026 (S3, K-RETOUR-FAUX) — retenir une variante identique périme la simulation et vide l'onglet Production.

## 4. Ce qui est bien (à ne pas casser)

- Le refus de simulation est UNIQUE et complet (`manquants[]`), chaque ligne ouvre son champ avec le focus (ACAL940).
- L'état « au plus » est le plus fidèle des écrans : chiffre + phrase dans la même carte, « n étapes sur N », lignes
  « Renseigner » qui posent le focus sur le bon champ de Réglages (`#calx69-salissure_mensuelle_pct`).
- L'étape Résultats guidée : pleine largeur, héros 40 px, aucun texte < 12 px, cartes lisibles, « Voir les 26 étapes »
  dépliable, bouton or « Préparer les documents », « Simulation à jour · HH:MM » servi.
- Les sommes tiennent : postes (−1,9 −5,7 −4,2 −7,8) = 19,6 % ; 12 mois = 5 130 ≈ P50 ; SVG « où va l'énergie »
  proportionnel ; rapport d'étude complet (synthèse, tableau mensuel PVsyst-like avec irradiations/T°/PR, table IAM,
  note de validation multi-sites, limites connues).
- Téléchargement du rapport (35,7 s) sans coupure, « Préparation en cours : jusqu'à 2 minutes ».
- « Remplir depuis une surface » (albédo) remplit valeur + source + référence sans rien enregistrer.

## 5. Non essayé, et pourquoi

- ACAL447 (onglet Batterie, semaine de mars) : aucune batterie sur le calepinage — faisable avec une Deye du stock, pas fait (temps).
- ACAL694 / ACAL710 branche « avec dégradation » : les deux fiches panneau du catalogue n'ont pas de dégradation ; je n'ai
  pas modifié une fiche catalogue partagée. La branche « motif » est vue (rapport p. 12).
- ACAL757 (avec courbe de charge), ACAL709 branche « 71 % » : aucune courbe horaire de consommation sur la pile.
- ACAL759 (photos), ACAL703 (bande « inhabituel » : `plages` = « aucune bande sourcée »), ACAL735 / 737 / 738 / 712 / 725
  (onduleur à tension de démarrage, ratio élevé, chaîne ombrée, optimiseurs), ACAL714 / 715 / 717 / 719 / 721 / 726 /
  727 / 728 / 729 / 731 / 754 (branche « ombrage calculé ») et la seconde moitié d'ACAL732 : demandent un obstacle avec
  hauteur, plusieurs pans et l'atelier 3D d'ombrage — **arrêté ici faute de temps**, la pile le permettrait.
- ACAL767 (export refusé à l'ouverture), ACAL769 (dépassement réel de 2 min) : non provoqués.
- À vérifier : pendant le téléchargement du rapport, un texte « La connexion a expiré. Vérifiez votre connexion et
  réessayez. » a été lu dans une région `[role=alert]` mais n'est visible sur aucune capture — non porté au registre.
- Fond de carte gris, aucune clé d'IA : sans effet sur mon périmètre.

## 6. Trois propositions pour rejoindre les meilleures références

1. **Un seul chiffre, son pedigree affiché (PVsyst 8, page « Main results »)** : PVsyst imprime UNE production
   (E_Grid), son productible et son PR, puis P50/P90 avec la liste des incertitudes comptées. Faire de la barre de
   résumé, de l'atelier expert, du bloc devis et du /proposal des LECTURES du même résultat servi, et afficher sous le
   héros « Production imprimée au client : 4 542 kWh (méthode du devis, −12 %) » — une seule ligne, jamais deux.
2. **Un vrai diagramme de pertes en cascade et un tableau mensuel de bilan (PVsyst 8 « Loss diagram » + « Balances and
   main results »)** dans l'étape Résultats elle-même (pas seulement au rapport) : GlobHor, GlobInc, IAM, température,
   EArray, E_Grid, PR par mois — les données sont déjà servies (`irradiation_mensuelle`, `bilan_mensuel`), seul l'écran
   manque (ACAL707) ; et comparer à PVGIS à pertes SYSTÈME égales, pas totales.
3. **Le récit des résultats d'Aurora / OpenSolar** : une phrase en tête (« Vos 4 panneaux produiront environ 5 200 kWh
   par an, soit 48 % de votre consommation »), puis les preuves dépliables ; les motifs d'étapes omises réécrits en
   une ligne de métier (« Ombrage non calculé : aucun obstacle saisi — Ajouter un obstacle »), le texte technique
   long réservé au rapport ingénieur et JAMAIS à la fiche client.
