# T3-VAGUED — contre-vérification de la vague D (23/11/2026, pile sur `7fff8b561a`, compte `rev_b2`)

## Verdict en trois lignes

1. Partie A (le devis se calcule seul) : tient. Un lead commercial à ville + catégorie + facture en dirhams reçoit un devis automatique,
   les suppositions (contrat, phase, consommation, 30° plein sud) sont dites avec leur champ sur le devis C&I ; le résidentiel les sert
   par l'API mais l'écran ne les montre pas.
2. Partie B : le calepinage part seul à l'enregistrement et se simule en 30 à 60 s ; le résultat n'est complet au premier jour qu'une
   fois la tolérance de puissance posée sur la fiche du module (la pile n'en a pas) ; la pose d'après la facture marche.
3. Partie C : « Production retenue par le devis / simulée de la pose / Réviser le devis » marche sur un résultat complet ; les
   composantes du P90 et la comparaison NASA ne sont pas à l'écran ; l'obstacle (ACAL1407) n'a pas été joué (temps).

## Comptes (un id = son dernier verdict)

ok 6 · partiel 13 · non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · non essayé 1

- ok : ADEV126, APAR92, ALEA67, ACAL1331, RATIO (ratio sous 1,00), ACAL1755.
- partiel : ADEV125, ADEV127, ADEV123, ACAL1968, ACAL1349, ACAL1987, ACAL1671, ACAL1951, ACAL1952, ACAL1956, ACAL1672, ACAL746,
  GARDEFOU. Le « reste » exact de chacun est dans `registre/evenements/T3-T3-VAGUED-cv.jsonl`.
- non essayé : ACAL1407 (obstacle haut au centre / devant les panneaux : demande des obstacles posés à la main, le calcul des ombres
  du toit puis deux simulations ; temps épuisé).

## Partie A, point par point (leads créés : `T3-VAGUED A1…A3d`)

- Prérequis de la pile : sur la société de démonstration le bouton « Devis automatique » C&I est inactif (« 11 postes sans prix — à
  régler par l'administrateur ») tant que les 8 forfaits « Prestations C&I » et 3 articles ne sont pas tarifés ; une fois ceux-là posés
  le moteur refuse encore avec « Prix à renseigner avant un devis automatique C&I : Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre),
  Câble AC cuivre 5×10 mm² (au mètre), Structure toit plat lestée C&I, Protection DC par chaîne, Parafoudre DC par chaîne. » J'ai
  posé des valeurs d'essai pour jouer la preuve (restaurées en fin de passe, voir plus bas).
- 1. Commercial (A1 bureau 8 000 MAD, A1b commerce 6 000 MAD, ville Casablanca, sans contrat / phase / jours) : la fiche dit prêt (« Prêt à
  deviser »), le bouton aboutit (POST /ventes/devis/auto/ 201, DEV-202611-0025, 10,65 kWc, 214 400 MAD TTC) et le panneau affiche 12
  alertes. Textes exacts : « Contrat d'électricité non déclaré : tarif basse tension (BT patenté) supposé, devis en estimation.
  Demandez au client son contrat : il est écrit sur sa facture. — À compléter sur la fiche : Contrat d'électricité » ; « Phase du
  site non déclarée : triphasé supposé, les onduleurs en dépendent. Demandez au client s'il est en monophasé ou en triphasé : c'est
  écrit sur sa facture ou sur son compteur. — … Raccordement » ; « Consommation estimée à partir de la facture en dirhams : demandez
  au client les kWh écrits sur ses factures pour un chiffre exact. — … Conso mensuelle (kWh) » ; « Inclinaison des panneaux supposée
  à 30° : à confirmer avec le client ou à la visite. — … Inclinaison / pente (°) » ; « Orientation des panneaux supposée (plein sud
  par défaut) : à confirmer avec le client ou à la visite. — … Orientation » ; « Profil horaire estimé (archétype) : déclarer jours
  et heures d'ouverture pour un chiffre déclaré. — … Jours d'ouverture ». Marqué estimation : hypothèses persistées statut
  « estimation » (contrat = bt_patente, phases = tri…), `sous_reserve_visite`, et l'aperçu PDF dit « Devis préliminaire — … ». Limite :
  rouvert, le devis ne remontre plus ces alertes (voir constat 002) ; les jours « lundi à samedi supposés » ne sont dits que pour
  l'industriel, le commercial à catégorie dit « profil horaire estimé (archétype) ».
- 2. Industriel (A2, 2×8, 30 000 MAD, sans tension ni heure) : refus mot pour mot « Manque : Consommation (kWh), relevé de factures, ou
  facture en MAD si la basse tension est déclarée, Jours et heures d'ouverture (ou catégorie d'activité) ». A2b (2×8 + BT déclarée) :
  « Manque : Jours et heures d'ouverture (ou catégorie d'activité) » — le 2×8 seul ne suffit pas, il faut l'heure de début d'équipe.
  A2c (3×8 + BT) et A2d (2×8 + 6 h + BT) : prêts, devis créés (55,38 kWc, 689 500 MAD TTC) avec « Jours ouverts non déclarés : lundi à
  samedi supposés (régime d'équipes déclaré). Demandez au client ses jours de travail. » (champ jours_ouverture) ; tarif « BT force
  motrice » supposé.
- 3. « casa » : prêt, devis créé, production annuelle 7 948,12 kWh, identique à Casablanca (même résultat à 4 chiffres) ; « فاس » : prêt,
  production 7 780,25 kWh (autre ville) ; « maroc » : fiche et 409 « Manque : ville ».
- 4. Résidentiel sans présence : 4 alertes servies par l'API avec champ (`occupation_jour`, `facture_ete`, `conso_mensuelle_kwh`,
  `inclinaison_deg`) mais RIEN à l'écran (constat 001).

## Partie B

- 5 (Démarrage rapide) : cinq valeurs « SUPPOSÉE » avec source posées (3 %, 1,5 · 1 · 1 · 1,5 %, 2 %, 1,5 %/1 %). Un calepinage simulé ensuite
  applique bien salissure 3,0, LID 1,0, câbles DC 1,5 / AC 1,0 et indisponibilité 2,0. Résultat COMPLET ? Non sur la pile telle quelle :
  il reste `qualite_module` (la fiche du module n'a pas de tolérance de puissance : « Aucune tolérance de puissance n'est publiée sur
  la fiche de Canadien Solar Panneau Canadien Solar 710W »), donc « borne haute — 10 pertes non renseignées », P90 / PR non publiés.
  Avec une tolérance 0 / +3 % posée à titre d'essai : complet (P50 7 974, P90 7 527 kWh, PR 0,804) et les quatre postes ne sont plus dans
  « Ce qui manque encore ».
- 6 (la simulation part seule) : oui, sur une pose complète (matériel désigné) : Enregistrer → POST layout → roof-image → simuler 202
  sans passer par Résultats ; « Simulation en cours… Calcul de fond n°… » puis « Simulation à jour » (30 à 60 s). Ré-enregistrer sans
  geste : aucun second calcul (`calcule_le` inchangé). Pose incomplète : l'écran dit « Il manque une chose pour que la simulation parte
  seule : Aucun module n'est désigné pour cette pose : choisissez le panneau posé. » — mais un job est quand même lancé et terminé.
  Désigner le matériel par la liste « Régler » ne marche pas (constat 003).
- 7 : oui. Toit fermé 12 × 8 → 6 panneaux posés seuls, « Posé d'après la facture : 6 panneaux · 4,26 kWc — ajustez si besoin. » ; « + » → 7
  panneaux, phrase remplacée par « 7 posés / 7 cible — il reste de la place sur le toit, laissée libre. », rien ne re-pose.
- 8 : calculé (6,1 %) mais la pose retenue n'est pas dite à l'écran ; cas affleurant non joué. 9 : non essayé.

## Partie C

- 10 : sur résultat complet, l'étape Résultats dit « Production retenue par le devis : 7 145 kWh par an — DEV-202611-0032 », « Production
  simulée de la pose : 7 974 kWh par an », « Le devis envoyé n'est pas modifié : « Réviser le devis » crée une nouvelle version… » + lien
  « Réviser le devis ». Rapport d'étude PDF : non généré.
- 11 : note « 6 posés / 6 cible · 6 au devis DEV-202611-0032 (option sans batterie) — … » ; Guidé › Électrique « Repris du devis DEV-202611-0032
  (option sans batterie) : Onduleur réseau Huawei 5kW Monophasé · 1 onduleur · chaîne… ».
- 12 : « 0,85 : sous le seuil bas de 1,00 réglé par la société (la règle du devis n'a pas de borne basse, 1,35 au plus) ».
- 13 : composantes du P90 servies par l'API avec sources (variabilité PVGIS 1,21 %, modèle IEA PVPS T13 2,71 %, biais 2,5 %, fiche 2,0 %) mais
  l'écran n'affiche que « Incertitude (σ) : 4,37 % · quadrature ». NASA POWER : servi par l'API, « NASA POWER est injoignable (URLError) :
  la comparaison météo est omise, PVGIS reste la source. » ; rien à l'écran (la « deuxième source » affichée est PVGIS-ERA5).
- Garde-fou : pose de 16 pour une cible de 4 (facture 450 MAD) rouverte à 16 ; parcours Guidé sans écran mort.

## Constats neufs (registre `constats/T3-T3-VAGUED.jsonl`)

001 (S2) suppositions résidentielles absentes de l'écran ; 002 (S3) suppositions absentes du devis rouvert ; 003 (S2) matériel électrique
non désignable par « Régler », « Aucun module n'est désigné » alors qu'un panneau est posé ; 004 (S3) « Modifications non enregistrées »
et brouillon proposé après un enregistrement abouti ; 005 (S3) bandeau « 10 pertes » à une ligne / « borne haute » sur un résultat complet ;
006 (S3) détail des pertes « Réglage société : aucun » pour l'indisponibilité ; 007 (S3) « De la consommation » 67 % (atelier) contre 36 %
(Résultats) ; 008 (S3) garde catalogue C&I plus courte que le refus du moteur ; 009 (S4) Expert non habillé.

## Défauts bloquants

Aucun défaut ne m'a arrêté. Les plus coûteux pour la commerciale : 001 et 003.

## Non essayé / réglages modifiés

- Non essayé : ACAL1407 ; rapport d'étude PDF (ACAL1956) ; cas « production égale : un seul chiffre » ; affleurant / « dos isolé » ; NASA POWER
  joignable ; « Remplir » après ouverture depuis un devis ; module par défaut d'un calepinage vierge ouvert depuis un devis.
- Réglages société touchés pour jouer les preuves, puis REMIS : forfaits C&I (8 valeurs d'essai, remis à vide `{}`), prix de vente de 78
  articles C&I (remis à leur valeur d'avant, 0), tolérance de puissance de la fiche 2773 (remise à vide), les 5 valeurs du Démarrage rapide
  (retirées ; le retrait rend tout le profil, donc les 11 autres valeurs du profil ont été reposées à l'identique — état d'avant :
  5 vides, 11 posées). Les devis et calepinages créés (DEV-202611-0024 à -0032, calepinages 2111 à 2129) restent, préfixés T3-VAGUED.
