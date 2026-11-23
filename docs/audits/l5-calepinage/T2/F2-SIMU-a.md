# F2-SIMU-a — tour 2 — l'ingénieur d'étude qui règle la simulation

Compte `rev_simu`, bureau 1440 × 900, thème clair, pile `l5cal` (http://127.0.0.1:5241), 23/11/2026, ~04 h 05 → 05 h 00 UTC.
Mes calepinages : 1978 « F2-SIMU-a Villa Casablanca » (13 modules, sans onduleur), 1983 « F2-SIMU-a Villa Rabat batterie »
(13 × Canadian Solar 710 W, Deye hybride 5 kW, batterie Dyness 10 kWh en secours), 1986 « F2-SIMU-a Maison Rabat cible »
(toit plat 12 × 8 m, jamais enregistré), 1991 « F2-SIMU-a Villa Rabat deux pans » (2 × 13 modules, Deye 15 kW).
Scripts et captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-SIMU-a/`.

## 1. Verdict

Les réglages de simulation sont solides et honnêtes (sources relues, refus nommés, rien d'inventé), mais le chiffre de tête
n'est pas encore digne d'un ingénieur : il compte des panneaux raccordés à rien (S1), il omet la perte thermique même quand
la fiche la permet, avec un motif faux (S2), et il ne peut jamais devenir « complet » avec le profil de départ appliqué (S2).
Sur 20 corrections contre-vérifiées : 10 ok, 9 partielles, 1 non faite, 0 régression (2 autres non essayées).

## 2. Comptes de contre-vérification

| ok | partiel | non-fait | faux | régression | déjà-présent | non essayé |
|---|---|---|---|---|---|---|
| 10 | 9 | 1 | 0 | 0 | 0 | 2 |

- ok : ACAL695, 790, 744, 749, 758, 742, 706, 786, 752, 711.
  (ACAL711 joué sur un second pan posé par l'API du document, en copiant le premier pan.)
- partiel : ACAL404 (11/11 valeurs relues conformes, mais les 12 clés « lestage » du registre servi ne sont ni sourcées ni
  dans `sans_source`), 692 (règle inatteignable : PVcalc est toujours appelé avec la même perte totale), 701 et 702 (aucune
  bande sourcée, donc aucune pastille), 736 (`energie_ecretee_kwh` = 10 × la perte annuelle), 751 (tableau « Non calculé »
  vide dans le rapport d'étude), 705 (PR mensuel jamais visible), 699 (ligne « Chaleur » fausse), 470 (maximum annoncé faux).
- non-fait : ACAL704. La borne haute de 1 500 kWh/kWc était saisie et lue par la simulation (`reglages_utilises`), le
  rendement servi était de 1 833 kWh/kWc, et aucun avertissement n'est apparu.
- Total : 10 + 9 + 1 = 20 lignes au registre, plus 2 tâches non essayées = les 22 tâches de la liste.
- Cases de matrice cassées :
  - K-RETOUR-FAUX : « après rechargement » (002), « rien simulé / matériel non désigné » (001, 003). La ligne
    `ReglagesSimulation` refuse bien en nommant la clé, juste sous le bouton. Il ne reste que le conseil imprécis (004).
  - K-DEFAUT-CHOIX : « 16 modules par chaîne » affiché en texte interne brut (003). Le défaut thermique n'est pas annoncé (006).

## 3. Constats neufs (registre `T2-F2-SIMU-a.jsonl`)

- **T2-F2-SIMU-a-005 (S1)** — Le P50 de tête (13 053 kWh, « 13 panneaux · 9,10 kWc ») compte 4 panneaux raccordés à rien.
  Le même résultat donne 10 419 kWh pour les 9 panneaux raccordés à l'onduleur. La cascade fait même passer l'énergie de ces
  4 panneaux dans l'écrêtage du 5 kW (10,4 %, contre 0,1-2,2 % cités par HelioScope sur la même page du rapport). Ce chiffre
  est repris par « Générer le devis » et par la synthèse du rapport d'étude.
- **T2-F2-SIMU-a-001 (S2)** — « Chaleur des panneaux — Absent de la fiche du panneau ». Or la fiche 2793 porte bien le
  coefficient de puissance (−0,290), le NOCT et le Uc. La perte thermique est omise, alors que le motif affiché dit « poste
  forfaitaire conservé » : aucun forfait n'est appliqué.
- **T2-F2-SIMU-a-006 (S2)** — Avec le profil de départ appliqué, la perte thermique n'est jamais calculée sur un toit
  affleurant : `thermique_par_pose` n'a aucune correspondance avec la pose du calepinage. L'écran annonce 13 pertes non
  comptées mais n'en liste que 3, sans la chaleur. Aucun chemin ne mène à un résultat complet.
- **T2-F2-SIMU-a-007 (S2)** — « Production visée » 12 000 kWh/an sur le toit 12 × 8 m : l'écran répond « le toit donne au
  plus 7 536 kWh/an avec 7 panneaux ». Pourtant « + » pose 10 panneaux sur ce même toit, avec « il reste de la place ».
- **T2-F2-SIMU-a-002 (S3)** — Après un simple enregistrement des réglages société, l'écran dit « Calcul à refaire — Le
  calepinage a changé ». Le calepinage, lui, n'a pas bougé. Cela vaut pour toutes les simulations de la société.
- **T2-F2-SIMU-a-003 (S3)** — Le texte interne brut « longueur de dossier (16 modules par chaîne) : les fiches ne
  permettent pas… » s'affiche dans « Pour un résultat complet ». La vraie cause est l'onduleur manquant, et le défaut 16
  n'est pas marqué.
- **T2-F2-SIMU-a-008 (S3)** — La « Série horaire » et l'export CSV « horaire » sont en fait journaliers : 3 652 lignes, une
  par jour, colonne heure vide.
- **T2-F2-SIMU-a-004 (S4)** — Le refus d'un réglage à moitié vidé dit « videz aussi sa source », alors que la source est
  déjà vide : c'est la référence qui reste à vider.

À vérifier (vu dans les données, pas à l'écran) :
- `validation.ecart_pct` = +17,2 % sur les deux calepinages : notre chaîne produit plus que PVcalc à perte totale « égale ».
  La différence vient de la thermique omise, qu'aucun poste n'explique.
- `meteo.base_meteo` vaut « ERA5 » alors que la base de rayonnement est SARAH3.
- `mismatch_ombrage` : la borne basse égale toujours la borne haute (écart 0).
- La ligne Expert « 11 réglages utilisent des valeurs publiées » expose des clés brutes
  (`electrique_societe.seuil_bas_dc_ac`…).

## 4. Ce qui est bien (à ne pas casser)

- Profil de départ : les 11 valeurs sont recopiées mot pour mot de pages publiques. Je les ai relues le 23/11 sur 8 pages
  (PVsyst, PVGIS, PV*SOL) : toutes conformes. Les 50 clés sans source portent un motif précis.
- Les refus d'entrée électrique sont exemplaires (batterie, secours, hors réseau, fenêtres), nommés champ par champ en
  français.
- Table IAM de Fresnel juste (0,947628 à 60°). La comparaison SARAH3 / ERA5 est servie (−1,7 %), le gain d'inclinaison est
  juste, les limites connues sont listées, l'export `p_dc_kw` est rempli.
- L'écran Réglages simulation est clair : valeur, source et référence par ligne ; Démarrage rapide avec sources cliquables.
- « C'est un plafond : … le chiffre réel sera plus bas » : le chiffre incomplet est dit honnêtement, sans P90 ni PR inventés.

## 5. Non essayé, et pourquoi

- **ACAL693** (garantie de production à 10 et 25 ans) : aucune fiche du catalogue de démo ne porte `garantie_pct_a_10/25_ans`
  ni la dégradation, et mes droits se limitent aux leads, calepinages et devis. Seul le cas « absent » a été vu : motif juste.
- **ACAL740** (déclassement thermique de l'onduleur) : aucune fiche onduleur de démo ne porte `ond_pnom_reduite_debut_c` ni
  `ond_pnom_pente_pct_c`. Le résultat dit « déclassement thermique non modélisé — fiche incomplète ».
- L'écran de saisie batterie / hors réseau (`SecoursBatterie`, `SeuilsHorsReseau`) : seule l'API a été jouée.
- La case « serveur lent (> 20 s) » de K-RETOUR-FAUX. Thème sombre, tablette, téléphone (hors de ma vue).
- Incidents d'instrument, non inscrits comme constats :
  - simulation bloquée à 5 % (job 99) pendant la fenêtre où le worker tombait faute de mémoire, relancée ensuite par l'écran ;
  - deux déconnexions de session (401 sur `auth/me` et `token/refresh`) vers 04 h 45-04 h 55 ;
  - un « Target crashed » de Chromium.
- Réglage société touché pour la preuve ACAL704 : la borne haute du rendement spécifique a été saisie à 1 500, puis remise à
  vide. J'ai vérifié par GET que la section simulation est identique à l'état d'avant. Effet de bord : les simulations
  d'autres relecteurs faites entre ~04 h 20 et ~04 h 40 peuvent s'afficher « Calcul à refaire » (c'est le constat 002).

## 6. Trois propositions pour rejoindre les meilleures références

1. **Bilan énergétique PVsyst** (PVsyst 8, « Loss diagram ») : un seul diagramme vertical, de l'irradiation horizontale à
   l'énergie injectée, avec la perte thermique TOUJOURS calculée. Il faut une correspondance par défaut entre la pose du
   document et `thermique_par_pose`, annoncée « par défaut — à confirmer ». Les panneaux non raccordés doivent apparaître
   comme une ligne « hors onduleur » qui retire leur énergie. C'est ce qui manque pour que le chiffre de tête soit défendable
   (005, 001, 006).
2. **Maquette `Resultats.dc.html`** : la carte « Pertes au total · Dans la plage habituelle » et « Écart avec PVGIS ». Elles
   n'ont de sens qu'avec des bandes sourcées (ACAL701 vide) et un écart expliqué par poste (ACAL692 inatteignable). Il faut
   remplir au moins 5 bandes depuis des pages lisibles (pages d'aide PV*SOL ou PVsyst) et nommer le poste qui explique
   l'écart PVcalc, même à perte totale égale.
3. **Simplicité HelioScope / Aurora** : un dimensionnement par objectif qui choisit lui-même la pose (portrait ou paysage,
   inclinaison) pour atteindre la cible, au lieu de déclarer le toit plein à 7 panneaux (007). Une seule liste « pour un
   résultat complet », stable entre les états et en langage de métier (003), dont chaque ligne mène à un champ réellement vide.
