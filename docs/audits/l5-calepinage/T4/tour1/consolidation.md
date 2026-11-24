# T4 — tour 1 du test utilisateur : consolidation des constats (24/11/2026)

Sources : `registre/constats/T4-U1.jsonl` à `T4-U4.jsonl` (relecteurs neufs, clics réels, copie anonymisée), `T4/B4.md`
(relecteur des écrans contre les maquettes). Un constat = une ligne du registre ; ici, on les range par CAUSE, parce
qu'une cause se corrige une fois. Pile du tour 1 : `dev-ecrans-v2@35eae8c706` (avant les correctifs ci-dessous).

Lecture des colonnes : **Où ça se corrige** = lane de correction du jour, étape du « moteur unique » (C4), ou décision
du fondateur. **État** = corrigé (commit) / en lane / à l'étape En / décision / à remesurer.

## Classes de causes

| # | Cause | Constats | Gravité max | Où ça se corrige | État |
|---|---|---|---|---|---|
| K1 | **La facture imprimée n'est pas celle déclarée** : 900 MAD/mois déclarés, le PDF dit 831 (9 977 MAD/an). Cause lue : aucun niveau de consommation ne donne 900 MAD au barème sélectif (à 510 kWh la facture vaut 831,61 MAD, juste au-dessus elle saute à 954,59) ; le moteur garde le côté bas, exprès (« prudent », règle R2-07), et ne le dit qu'à l'écran interne | U1-001 | S1 | **décision du fondateur** sur la phrase que lit le client (trois formulations proposées) | diagnostiqué, rien changé |
| K2 | **Simulation sur un point que personne n'a choisi** : toit créé au centre de la carte (31,79 / −7,09, 737 m), simulation et rapport d'étude sans avertissement ; ville « casa » non reconnue et rien ne le dit avant le devis | U1-003, U2-017, U4-013, U1-002, U1-018, U3-013, U4-015, U4-011 | S1 | lane `site-facture` (serveur) ; pastille et toasts : lane écrans suivante | **corrigé côté serveur** (`1e381ebf01`, `0a246074df`, `511177924e`, `7a3d48c428`) : une seule définition de « épingle posée », le centre de carte n'est plus un site, ville de référence du devis dite dans le résultat, sinon refus ; alerte « ville non reconnue » au devis automatique. Reste : l'écran « Vérifier la ville » ne connaît pas la table d'orthographes du fondateur (« casa ») que le devis utilise — deux résolveurs |
| K3 | **Plusieurs chiffres pour une même valeur** entre devis, calepinage, étapes et PDF (production, puissance, consommation, couverture) ; la pose part sur « le plus de panneaux » ; le module du devis n'est pas proposé à la pose ; le calepinage n'est pas relié au devis envoyé ; « Générer le devis » crée un second brouillon à côté d'un devis envoyé ; « Réviser » copie la V1 | U1-004, U1-005, U1-007, U1-016, U1-021, U2-006, U2-012, U2-015, U4-001, U4-002, U4-004, U4-005, U4-006, U4-010, B4-004 | S2 | **moteur unique**, étapes E4 à E7 (ADEV142-153, ACAL2012-2023) : ces constats deviennent leurs cas d'acceptation | à l'étape |
| K4 | **Module et onduleur à désigner deux fois** : le module posé à l'étape 2 n'est pas celui de l'étape électrique ; « Raccorder automatiquement » ne fait rien ; identifiant brut « produit-23019 » ; le rapport dit « aucun onduleur désigné » alors qu'il est choisi | U1-006, U2-007, U2-014, U4-007, U4-008, B4-007 | S2 | lane `correctifs-b4` | en lane |
| K5 | **Plan décalé** : contour et cotes d'un côté, bâtiment et panneaux de l'autre (≈ 1 m) | U1-017, U4-003, planches B4 | S2 | lane `correctifs-b4` | en lane |
| K6 | **Devis agricole** : origine « mesuré en visite » perdue à l'enregistrement ; lignes à 0,00 imprimées au client ; générateur agricole parti du gabarit résidentiel ; premier clic muet ; refus qui ne dit pas quelle pompe ni qui peut saisir son prix ; option « calepinage » sans effet proposée ; panneau Pompage du calepinage vide | U3-001, U3-002, U3-004 à U3-009, U3-012 | S2 | lane `correctifs-agri` (U3-012 : lane calepinage suivante) | en lane |
| K7 | **Envoi au client** : « Copie impossible : sélectionnez le lien » sans lien affiché ; boutons grisés sans raison dite | U2-003, U3-011 | S3 | lane `correctifs-agri` | en lane |
| K8 | **Texte de développeur montré à l'utilisateur** : clés brutes (`electrique_societe.…`), codes de décision (« D-AGR-4 »), chemins de fichier, « Site.pin : », message anglais brut à l'échec du PDF, phrases internes de Résultats | U1-011, U1-018, U2-009, U2-013, U3-003, U3-013, U4-009, U4-015, B4-007 | S3 | lanes `correctifs-agri` et `correctifs-b4` | en lane |
| K9 | **Options sans / avec batterie** : une ligne ajoutée ne compte que dans un total sans le dire ; l'acceptation présélectionne « sans batterie » quand le devis recommande « avec » ; l'échéancier du « Devis final » est calculé sur la seule option avec batterie ; RIB absent sans rien dire | U1-010, U2-011, U1-014, U1-009 | S2 | étiquette de ligne : lane `correctifs-agri` ; présélection : lane suivante ; échéancier et RIB : **décision du fondateur** (le client le lit) | en lane / décision |
| K10 | **Un compte, plusieurs valeurs** (réglages vides : 20 / 6 / 4 / 16) ; tuile « Toit » cochée alors que deux points restent | B4-003, B4-010 | S2 | lane `correctifs-b4` | en lane |
| K11 | **Chargement interrompu sans nouvel essai** (catalogue des modules juste après « Créer le calepinage », liste des calepinages) | B4-002, B4-013 | S2 | lane `correctifs-b4` | en lane |
| K12 | **PDF du devis** : 4 pages au lieu de 3 (« Rentabilité » seule) ; 7 987 / 7 988 MAD selon la page ; nom du client en majuscules forcées dans un format et pas dans l'autre | U1-008, U1-019, U3-010 | S3 | lane `site-facture` (pages, arrondi) ; majuscules : **décision** | arrondi : corrigé (`e626d28a7c`) mais **dormant** — accroché au niveau de règles 15, non courant, donc aucun devis ne change tant que le fondateur n'a pas activé ce niveau ; 4 pages : **contesté** — voulu (la page « Rentabilité » passe seule quand les lignes de remise et d'arrondi commercial s'ajoutent aux deux options) ; c'est la mention « 3 pages » de CLAUDE.md et du dialogue PDF qui est périmée pour ce cas |
| K13 | **Suppositions non dites** : toit plat lesté supposé (structure et socles chiffrés) sans alerte ; raccordement supposé non dit en alerte | U2-001, U1-015 | S3 | moteur unique (ADEV134 : les suppositions sortent avec leur champ ; E4 les montre) | à l'étape |
| K14 | **Impasses** : aucun bouton pour ouvrir un ticket SAV (deux écrans se renvoient l'un à l'autre) ; « À compléter » sans objet ; formes du toit grisées sans raison dite | U2-016, U2-009, U2-005 | S3 | lane suivante | à lancer |
| K15 | **Lenteurs et délais** : liste des leads en échec (20 s) pour un rôle qui voit 518 leads ; la liste charge TOUS les leads (686, 4 pages de 200, ≈ 2,3 Mo) avant d'afficher ; ouvertures de 15 à 50 s ; pages blanches 50 s | U3-014, U1-012, U1-028, U1-030 | S2 | chargement complet de la liste : défaut réel (lane suivante) ; le reste **à remesurer au calme** (la pile d'essai servait huit navigateurs sur 2 processus) | à lancer / à remesurer |
| K16 | **Résultats physiquement douteux sans alerte** : 4 panneaux en une chaîne sur un onduleur hybride 5 kW — pertes 51,2 % dont « câbles et onduleur » −35,9 %, mai sous janvier ; aucun contrôle électrique ne le signale. Ombrage : l'étape Résultats dit « aucune ombre signalée » quand le mode Expert dit « 3 modules sur 6 couverts » | U4-012, U1-023 | S2 | lane calepinage serveur (cause à établir : chaîne sous la plage de l'onduleur à chaud ?) | à lancer |
| K17 | Divers d'écran : brouillon local reproposé après enregistrement ; bandeau tablette portrait ; thème sombre du plan ; deux noms pour un projet ; mot doublé ; « 0 projet » pendant le chargement ; puce « Facture mensuelle (MAD/kWh) » ; phrases « lead » sur un calepinage sans lead ; sélecteur trop étroit | U1-013, U1-020, U3-005, U4-014, B4-005, B4-006, B4-008, B4-009, B4-012 | S3 | lanes `correctifs-b4` et `correctifs-agri` ; reste : lane suivante | en lane |

| K18 | **Lead en kWh sans facture** : devis automatique refusé « Manque : facture hiver, facture été » malgré 450 kWh saisis ; pas de champ kWh d'été | U1-022 | S2 | moteur unique, ALEA70 (la garde du CRM lit ce que le MOTEUR dit manquer) ; champ d'été : lane écrans suivante | à l'étape |
| K19 | **Bandeau « 6 kWc » pour un devis de 5,5 kWc** (arrondi à l'entier) | U1-026 | S2 | lane `correctifs-agri` | en lane |
| K20 | **Révision et second devis** : « Réviser » reste muet 4 s puis copie la V1 ; depuis Documents, « Générer le devis » crée sans question un second brouillon (253 300 MAD) à côté du devis envoyé (82 900 MAD) et le rail du lead bascule dessus | U4-010, U2-015 | S2 | moteur unique, E6-E7 (ACAL2019, ADEV150 : un devis envoyé ne se double pas, une révision est proposée) | à l'étape |
| K21 | Obstacles : cheminée acceptée hors du toit ; taille dessinée remplacée par 1,0 × 1,0 au choix du type | U1-024, U1-025 | S3 | lane écrans suivante | à lancer |

## Ce qui n'est PAS un défaut du produit (dit par les relecteurs, vérifié)
- Fond de carte gris, recherche d'adresse indisponible : clé de carte factice de la pile d'essai.
- U2-002 (le PDF C&I ne dit pas que le contrat, le triphasé et les horaires sont supposés) : décision du fondateur des
  26-27/10 — « rien d'incertain côté client » ; le PDF dit déjà « Devis préliminaire » et « estimation ». Pas de changement.

## Décisions à porter au fondateur (aucune prise sans lui quand le client lit le résultat)
1. **Facture actuelle au PDF (U1-001)** — le client déclare 900 MAD/mois, le PDF dit « ≈ 831 MAD/mois » parce que 900 tombe dans un saut du barème et que le moteur garde le côté bas. Trois formulations : (a) garder les chiffres et le dire (« votre facture déclarée de 900 MAD/mois tombe dans un saut du barème : calcul fait sur 831 MAD/mois, côté prudent ») ; (b) imprimer les 900 déclarés et recalculer l'économie dessus (moins prudent) ; (c) renommer 831 « facture recalculée au barème ». Script de comptage des devis concernés prêt (lecture seule), pas encore joué.
2. **Échéancier du « Devis final » (U1-009)** : il suit déjà la décision D9 (avant acceptation, l'option « avec ») — rien à décider, sauf si le fondateur veut les deux options chiffrées. Le RIB : la ligne est vide sans rien dire quand le profil société n'a ni RIB ni banque — une alerte interne au dialogue PDF sera ajoutée (rien côté client).
3. **Nom du client (U3-010)** : tel que saisi, ou mis en forme (le PDF complet met des majuscules, la version une page non).
4. **Batterie souhaitée (U1-027)** : le devis automatique ne porte que l'option « avec batterie », sans comparaison — voulu, ou les deux options ?
5. **« 3 pages »** : la mention de CLAUDE.md et du dialogue PDF est fausse pour un devis à deux options avec remise et arrondi (4 pages, voulu par la mise en page) — corriger la mention, ou la mise en page ?

## Choix pris par l'orchestrateur ce tour (comportement interne, réversible)
- Une ligne de devis à prix 0 avec une quantité : alerte au générateur, envoi au client refusé tant qu'elle existe
  (mesuré sur la copie : aucun devis réel n'en porte ; seuls les devis d'essai du jour). Le brouillon reste enregistrable.
- Sans épingle de site posée, la simulation ne part jamais sur le centre de la carte : ville de référence du lead, dite
  dans le résultat, sinon refus qui dit quoi faire.

## État des corrections au 24/11, 20 h 15 UTC

**Dans la PR Taqinor/taqinor-os#1552 (lot 1)** — lanes `correctifs-b4`, `site-facture`, `correctifs-agri` :
K2 (site, côté serveur), K4 (module désigné une fois), K5 (plan aplati), K6 et K7 (agricole, envoi), K8 (textes
techniques, pour l'essentiel), K10, K11, K17 (en partie), K19. Le correctif « fermer le tracé au premier coin » (B4-005)
avait une régression (un 4e coin proche du premier était avalé) : vue par la CI, corrigée avant fusion — seul un CLIC
sur la pastille du premier coin ferme.

**Sur la branche du lot 2 (`dev-lot2`, pas encore en PR)** :
- lane `calepinage-serveur` — K16 : la chute de 51 % venait de la chaîne de 4 panneaux qui passe sous le bas de la
  plage de l'onduleur dès 51,7 °C de cellule (9 368 heures sur 43 295 hors plage sur le calepinage rejoué) ; un
  contrôle « Tension des chaînes par forte chaleur » le dit maintenant, jumeau de celui du grand froid ; ombres non
  mesurées dites quand le toit porte des obstacles ; cause vraie quand aucune chaîne n'est calculée ; UN résolveur de
  ville (« casa », « kech » reconnus par la table d'orthographes du fondateur ; plus de point posé à 600 km) ; valeurs de
  pompage du lead servies au calepinage.
- lane `atelier-suite` (15 points) — l'atelier renvoyait TOUT le document chaque seconde sans changement (un horodatage
  refait à chaque sérialisation) : 15 envois par minute au repos → 0 ; « Le devis annonce » seulement quand un devis est
  lié ; chaque « Régler » mène à son point ; un seul compte toit + sol + ombrière ; brouillon local effacé après
  l'enregistrement ; obstacle hors du toit signalé ; forme du toit choisie avant « Créer le toit » ; phrases du conflit
  d'enregistrement dites une fois ; panneau Pompage prérempli depuis la fiche ; clés brutes remplacées par les noms.
- lane `front-suite` (18 commits) — K15 : la liste des leads lisait des pages de 200 et la fiche attendait la liste
  (première ligne plus tôt, fiche indépendante, message de délai en français) ; relevé au téléphone : plus rien de tapé
  hors ligne n'est perdu (K : U4-020 à 023) ; SAV : chaque écran dit qui peut ouvrir un ticket ; acceptation : aucune
  option présélectionnée sauf celle que le devis recommande ; dialogue de ville : rien de coché d'office ; alerte interne
  quand le RIB manque au « Devis final ».
- étape 3 du moteur (relance, filet, remplissage, garde du CRM) — relue par un relecteur indépendant : NON fusionnable
  en l'état (un effacement légal était défait par la relance en file) ; corrections en cours dans la lane du moteur.

**Reste côté serveur (lane `serveur-suite`, en vol)** : champ au sol et ombrière dans le raccordement électrique ;
blocage électrique qui nomme sa cause ; deux phrases du PDF industriel (« horaires déclarés » quand ils sont supposés ;
« bases du calcul ci-dessous » sans section) — accrochées au niveau de règles 15, donc dormantes ; nom de l'article
sans prix dans le refus agricole ; motif vrai d'un site en moyenne tension.

**Pas encore traité** : K3, K13, K18, K20 (étapes E4 à E7 du moteur) ; U3-015 (devis manuel d'un site à phase
inconnue : décision) ; U3-022 (débit de la pompe actuelle non repris) ; « Enregistré à 16:10 » pour un
enregistrement de 16:20 (U4-015) ; colonne technique de « Réglages utilisés » en mode Expert.
