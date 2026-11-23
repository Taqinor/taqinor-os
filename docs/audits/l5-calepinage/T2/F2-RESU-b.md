# T2 — F2-RESU-b — contre-vérification de l'étape Résultats (reste de la liste F2-RESU)

Vérificateur F2-RESU-b, compte `rev_b1`, pile `l5cal` (http://127.0.0.1:5241), bureau 1440 × 900 clair.
Scripts, captures et pièces : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-RESU-b/`
(captures dans `cap/`). Verdicts : `registre/evenements/T2-F2-RESU-b-cv.jsonl` ; constats : `registre/constats/T2-F2-RESU-b.jsonl`.

## Ce que j'ai construit (données de démonstration, préfixe « F2-RESU-b »)

- Lead 2467 + calepinage **1936** « Villa Rabat » : toit 2 pans (13 × 4,5 m), module `F2-RESU-b Module 700W 3 sous-chaines`
  (produit 22984, fiche 2793 : 3 sous-chaînes, NOCT/Uc saisis), 13 panneaux (9,1 kWc) sur le pan sud, un obstacle 3 × 3 × 8 m
  au sud-ouest, onduleur Deye 5 kW, 2 batteries Dyness 10 kWh (couplage AC, stratégie autoconsommation), courbe de consommation
  saisie (33,4 kWh/j), postes de pertes saisis sur le calepinage, deux photos de site, une carte de chaleur déposée.
  Lead 2466 + calepinage 1935 : toit 4 pans de départ, abandonné.
- **Réglages société modifiés (partagés)** : `seuil_acces_retrait` 0,6, `ombrage_borne_courant_pct` 5, `ombrage_borne_importante_pct` 10,
  `seuil_derivation_acces` 0,85 (source « Réglage société »). Laissés tels quels : à remettre à vide si les autres relecteurs en sont gênés.
- La dernière simulation de 1936 n'a pas abouti (PVGIS 502 puis un calcul resté à 5 % plus de 8 min) : le calepinage 1936 est « à refaire ».

## 1. Verdict

Sur 23 corrections : onze sont réellement livrées et justes (export ombrage par module, bandes d'accès, sous-chaînes du catalogue,
section autoconsommation et photos du rapport, seuils société de l'atelier, message de délai dépassé). Mais trois chaînes ne
tiennent pas jusqu'à l'utilisateur : la carte de chaleur jointe est une vue 3D sans couleurs (ACAL726), le rapport d'ombrage
ne peut jamais être téléchargé depuis la liste Documents, et la dégradation du module qui alimente la table pluriannuelle (ACAL694)
n'est saisissable nulle part. La météo « pluriannuelle » rend en outre muettes toutes les courbes horaires (batterie, journée type).

## 2. Comptes

**ok 11 · partiel 7 · non-fait 1 · faux 0 · régression 0 · déjà-présent 0 · non essayé 4** (ACAL767, 703, 712, 738) — 23 au total.

- ok : ACAL754, 721, 731, 735, 714, 715, 717 (courbe trop petite), 727, 757, 759, 769.
- partiel : ACAL447, 694, 719, 725, 728, 729, 737.
- non-fait : ACAL726 (image sans couleur).
- Non essayé, avec la raison :
  - **ACAL767** : il fallait une simulation fraîche ; la mienne n'a pas abouti (PVGIS 502, puis calcul bloqué). Avec une simulation périmée l'onglet
    Production n'appelle même pas l'export (aucune requête, aucun toast).
  - **ACAL703** : `cascade.plages` = « aucune bande sourcée » sur cette pile ; aucune pastille à voir.
  - **ACAL712** : la carte « chaîne touchée par l'ombre » exige `ecart_bornes_pct` > 0 ; mes modules les plus ombrés (79,7 %) donnent deux
    bornes égales (écart 0,0) donc aucune carte, ce qui est le comportement prévu pour « sans écart » ; le cas avec carte n'a pas pu être fabriqué.
  - **ACAL738** : en météo pluriannuelle la série est servie au pas du jour (colonne `heure` vide) : il n'y a pas de journée type ni de courbe de puissance des panneaux.
  - Branches non rejouées dans les verdicts partiels : courbe SOC du 8 au 14 mars (ACAL447), table pluriannuelle (ACAL694), 2 heures sous démarrage (ACAL735).

## 3. Verdicts qui ne sont pas « ok » (une ligne chacun)

- **ACAL447 partiel** — carte « État de charge de la batterie » et choix du mois présents ; en pluriannuel l'export est agrégé au jour : « courbe horaire indisponible : série agrégée au jour » (motif OK), la courbe elle-même non vue.
- **ACAL694 partiel** — branche motif imprimée au rapport ; table (année, production, facteur, garantie) inatteignable : `degradation_*` n'existent ni dans l'API fiche (PATCH ignoré en silence) ni dans un écran.
- **ACAL719 partiel** — la ligne heure légale existe, mais fausse en hiver (UTC+0 au lieu de UTC+1 : « 12 h 25 » au lieu de « 13 h 25 ») et le champ date dit 2028.
- **ACAL725 partiel** — contrôle « Optimiseur » présent, sélection par glisser OK ; « Affecter la sélection » avec Oui n'a produit aucun effet visible (essai non concluant).
- **ACAL728 partiel** — tri OK à deux pans (96 % puis « non calculé ») ; second clic, trois pans et visite d'un autre pan non joués.
- **ACAL729 partiel** — « Accès solaire 97 % (année entière) · Ombrage : 8 heure(s)… » vu ; la partie « chaîne n » jamais vue.
- **ACAL737 partiel** — phrase « 12,1 % de l'énergie des panneaux est perdue : l'onduleur plafonne à 5 kW », table et légende OK ; le graphe est tronqué dans la colonne de 270 px (la « Borne » et tout ce qui dépasse 3,25 kW sont hors écran).
- **ACAL726 non-fait** — « Joindre la carte de chaleur » dépose bien une image (201) et remet la carte, mais l'image est la vue 3D ordinaire, panneaux noirs, sans teinte.

## 4. Constats neufs (registre `T2-F2-RESU-b.jsonl`)

- **-003 (S2, K-GRANDEUR)** — ratio DC/AC 1,26 (6,3 kWc : 9 modules câblés) contre écrêtage 12,1 % et production calculés sur 13 modules (9,1 kWc, ratio 1,82) : « 4 modules en réserve » comptés dans la production, pas dans le ratio.
- **-004 (S2)** — heure légale fausse en hiver : `soleil-legal` rend `decalage_utc_min` 0 le 20/12 (60 en juin) ; Maroc = UTC+1 hors Ramadan.
- **-006 (S2, K-RETOUR-FAUX)** — à la réouverture d'un calepinage enregistré, le panneau Accès solaire dit « non renseigné — aucune obstruction n'a été saisie » alors que l'obstacle est dessiné et enregistré, jusqu'à ce qu'on retouche sa hauteur.
- **-007/-008 (S2, K-RETOUR-FAUX)** — le rapport d'ombrage est déclaré indisponible (« Aucun accès solaire par module mesuré ») alors que `solarAccess.values` existe ; le PDF répond pourtant 200 par son URL. Cause lue : `valeur_au_chemin` ne gère pas un `[]` au milieu du chemin (-007 attribuait à tort la cause au pan vide, corrigé par -008).
- **-010 (S2, K-RETOUR-FAUX)** — la dégradation du module est demandée partout et saisissable nulle part.
- **-011 (S2, K-GRANDEUR)** — rapport d'étude : « Consommation annuelle 121 976,8 kWh » (dix ans cumulés) à côté de 12 197,68 kWh dans la section voisine.
- -001 (S3) « Heures sans import réseau 79 919 h » en tuile annuelle ; -002 (S4) intro de l'onglet Séries « les trois fichiers » avec quatre cartes ; -005 (S3) champ date 2028 / phrase 2026 ;
  -009 (S3) rapport d'ombrage PDF : « Accès solaire moyen (%) 0,9 », « 0,7968412048994717 % » ; -012 (S3) « Modifications non enregistrées » dès l'ouverture sans édition ;
  -013 (S3) panneau Affectation : même avertissement norme répété trois fois ; -014 (S3) 4,90 kWc / 4,97 kWc et « Plusieurs modèles posés » à tort ; -015 (S3) série horaire pluriannuelle sans explication.

## 5. Ce qui est bien (à ne pas casser)

- Export « Ombrage module par module » : les 7 lignes du CSV égalent les valeurs du document au millième (0,941 / 0,927 …) ; provenance et résolution dites.
- `bandes` écrites par l'atelier : 7 listes de 3 valeurs alignées sur `values`, bande aval plus basse ; `sousChaines` servi à 3 pour ma fiche, `null` pour les trois autres.
- Seuils société lus par l'atelier : sans réglage « Retrait proposé : aucun seuil réglé… » ; avec réglage, « dont 4 sous le seuil de votre société (95 %) », proposition et bouton « Retirer ces modules » ; phrase d'ombrage « 4,3 % … lecture « faible » ».
- Message de délai dépassé : indication « jusqu'à 2 minutes » pendant l'attente, puis message en rouge sur la carte qui dit quoi faire, sans toast, après un vrai dépassement de 120 s.
- Rapport d'étude : sections « Autoconsommation et batterie » (couverture 66,09 % = tuile Production) et « Photos du site » (légendes et dates) conformes ; légende 0-100 % du rapport d'ombrage avec rampe rouge-jaune-vert.

## 6. Non essayé

Voir le point 2. Fond de carte gris et absence de clé d'IA sans effet sur ce périmètre.

## 7. Trois propositions

1. **Un seul chiffre de puissance et de production (PVsyst 8, « Main results ») :** ratio, écrêtage, production et ligne « modules en réserve » du même nombre de modules câblés, avec la liste des exclus nommée.
2. **Heure et ombre lisibles (Aurora Solar, vue ombrage) :** courbe de perte d'ombrage de 120 px au moins, heure légale juste (fuseau Africa/Casablanca, +1 h), et la carte de chaleur jointe réellement teintée.
3. **Fiche module complète (OpenSolar, bibliothèque de modules) :** champs dégradation/garantie de performance saisissables dans la fiche produit, puis la table 25 ans du rapport d'étude devient atteignable.
