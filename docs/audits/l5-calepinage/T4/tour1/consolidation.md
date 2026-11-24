# T4 — tour 1 du test utilisateur : consolidation des constats (24/11/2026)

Sources : `registre/constats/T4-U1.jsonl` à `T4-U4.jsonl` (relecteurs neufs, clics réels, copie anonymisée), `T4/B4.md`
(relecteur des écrans contre les maquettes). Un constat = une ligne du registre ; ici, on les range par CAUSE, parce
qu'une cause se corrige une fois. Pile du tour 1 : `dev-ecrans-v2@35eae8c706` (avant les correctifs ci-dessous).

Lecture des colonnes : **Où ça se corrige** = lane de correction du jour, étape du « moteur unique » (C4), ou décision
du fondateur. **État** = corrigé (commit) / en lane / à l'étape En / décision / à remesurer.

## Classes de causes

| # | Cause | Constats | Gravité max | Où ça se corrige | État |
|---|---|---|---|---|---|
| K1 | **La facture imprimée n'est pas celle déclarée** : 900 MAD/mois déclarés, le PDF dit 831 (9 977 MAD/an) | U1-001 | S1 | lane `site-facture` | en lane |
| K2 | **Simulation sur un point que personne n'a choisi** : toit créé au centre de la carte (31,79 / −7,09, 737 m), simulation et rapport d'étude sans avertissement ; ville « casa » non reconnue et rien ne le dit avant le devis | U1-003, U2-017, U4-013, U1-002, U1-018, U3-013, U4-015, U4-011 | S1 | lane `site-facture` (serveur) ; pastille et toasts : lane écrans suivante | en lane |
| K3 | **Plusieurs chiffres pour une même valeur** entre devis, calepinage, étapes et PDF (production, puissance, consommation, couverture) ; la pose part sur « le plus de panneaux » ; le module du devis n'est pas proposé à la pose ; le calepinage n'est pas relié au devis envoyé ; « Générer le devis » crée un second brouillon à côté d'un devis envoyé ; « Réviser » copie la V1 | U1-004, U1-005, U1-007, U1-016, U1-021, U2-006, U2-012, U2-015, U4-001, U4-002, U4-004, U4-005, U4-006, U4-010, B4-004 | S2 | **moteur unique**, étapes E4 à E7 (ADEV142-153, ACAL2012-2023) : ces constats deviennent leurs cas d'acceptation | à l'étape |
| K4 | **Module et onduleur à désigner deux fois** : le module posé à l'étape 2 n'est pas celui de l'étape électrique ; « Raccorder automatiquement » ne fait rien ; identifiant brut « produit-23019 » ; le rapport dit « aucun onduleur désigné » alors qu'il est choisi | U1-006, U2-007, U2-014, U4-007, U4-008, B4-007 | S2 | lane `correctifs-b4` | en lane |
| K5 | **Plan décalé** : contour et cotes d'un côté, bâtiment et panneaux de l'autre (≈ 1 m) | U1-017, U4-003, planches B4 | S2 | lane `correctifs-b4` | en lane |
| K6 | **Devis agricole** : origine « mesuré en visite » perdue à l'enregistrement ; lignes à 0,00 imprimées au client ; générateur agricole parti du gabarit résidentiel ; premier clic muet ; refus qui ne dit pas quelle pompe ni qui peut saisir son prix ; option « calepinage » sans effet proposée ; panneau Pompage du calepinage vide | U3-001, U3-002, U3-004 à U3-009, U3-012 | S2 | lane `correctifs-agri` (U3-012 : lane calepinage suivante) | en lane |
| K7 | **Envoi au client** : « Copie impossible : sélectionnez le lien » sans lien affiché ; boutons grisés sans raison dite | U2-003, U3-011 | S3 | lane `correctifs-agri` | en lane |
| K8 | **Texte de développeur montré à l'utilisateur** : clés brutes (`electrique_societe.…`), codes de décision (« D-AGR-4 »), chemins de fichier, « Site.pin : », message anglais brut à l'échec du PDF, phrases internes de Résultats | U1-011, U1-018, U2-009, U2-013, U3-003, U3-013, U4-009, U4-015, B4-007 | S3 | lanes `correctifs-agri` et `correctifs-b4` | en lane |
| K9 | **Options sans / avec batterie** : une ligne ajoutée ne compte que dans un total sans le dire ; l'acceptation présélectionne « sans batterie » quand le devis recommande « avec » ; l'échéancier du « Devis final » est calculé sur la seule option avec batterie ; RIB absent sans rien dire | U1-010, U2-011, U1-014, U1-009 | S2 | étiquette de ligne : lane `correctifs-agri` ; présélection : lane suivante ; échéancier et RIB : **décision du fondateur** (le client le lit) | en lane / décision |
| K10 | **Un compte, plusieurs valeurs** (réglages vides : 20 / 6 / 4 / 16) ; tuile « Toit » cochée alors que deux points restent | B4-003, B4-010 | S2 | lane `correctifs-b4` | en lane |
| K11 | **Chargement interrompu sans nouvel essai** (catalogue des modules juste après « Créer le calepinage », liste des calepinages) | B4-002, B4-013 | S2 | lane `correctifs-b4` | en lane |
| K12 | **PDF du devis** : 4 pages au lieu de 3 (« Rentabilité » seule) ; 7 987 / 7 988 MAD selon la page ; nom du client en majuscules forcées dans un format et pas dans l'autre | U1-008, U1-019, U3-010 | S3 | lane `site-facture` (pages, arrondi) ; majuscules : **décision** | en lane / décision |
| K13 | **Suppositions non dites** : toit plat lesté supposé (structure et socles chiffrés) sans alerte ; raccordement supposé non dit en alerte | U2-001, U1-015 | S3 | moteur unique (ADEV134 : les suppositions sortent avec leur champ ; E4 les montre) | à l'étape |
| K14 | **Impasses** : aucun bouton pour ouvrir un ticket SAV (deux écrans se renvoient l'un à l'autre) ; « À compléter » sans objet ; formes du toit grisées sans raison dite | U2-016, U2-009, U2-005 | S3 | lane suivante | à lancer |
| K15 | **Lenteurs et délais** : liste des leads en échec (20 s) pour un rôle qui voit 518 leads ; ouvertures de 15 à 50 s | U3-014, U1-012 | S2 | **à remesurer au calme** (la pile d'essai sert huit navigateurs sur 2 processus) avant de conclure | à remesurer |
| K16 | **Résultats physiquement douteux sans alerte** : pertes 51,2 % dont « câbles et onduleur » −35,9 % sur une petite pose | U4-012 | S2 | cause à lire (lane `site-facture` la note) puis lane calepinage serveur | à lancer |
| K17 | Divers d'écran : brouillon local reproposé après enregistrement ; bandeau tablette portrait ; thème sombre du plan ; deux noms pour un projet ; mot doublé ; « 0 projet » pendant le chargement ; puce « Facture mensuelle (MAD/kWh) » ; phrases « lead » sur un calepinage sans lead ; sélecteur trop étroit | U1-013, U1-020, U3-005, U4-014, B4-005, B4-006, B4-008, B4-009, B4-012 | S3 | lanes `correctifs-b4` et `correctifs-agri` ; reste : lane suivante | en lane |

## Ce qui n'est PAS un défaut du produit (dit par les relecteurs, vérifié)
- Fond de carte gris, recherche d'adresse indisponible : clé de carte factice de la pile d'essai.
- U2-002 (le PDF C&I ne dit pas que le contrat, le triphasé et les horaires sont supposés) : décision du fondateur des
  26-27/10 — « rien d'incertain côté client » ; le PDF dit déjà « Devis préliminaire » et « estimation ». Pas de changement.

## Décisions à porter au fondateur (aucune prise sans lui quand le client lit le résultat)
1. Échéancier du « Devis final » quand deux options sont proposées (U1-009) : sur quelle option, ou les deux.
2. RIB absent du « Devis final » : d'où vient-il, et que dire quand il manque (U1-009).
3. Nom du client : tel que saisi, ou mis en forme (U3-010).
4. Formulation « facture actuelle » si la lane `site-facture` conclut à un choix de modèle et non à un défaut (U1-001).

## Choix pris par l'orchestrateur ce tour (comportement interne, réversible)
- Une ligne de devis à prix 0 avec une quantité : alerte au générateur, envoi au client refusé tant qu'elle existe
  (mesuré sur la copie : aucun devis réel n'en porte ; seuls les devis d'essai du jour). Le brouillon reste enregistrable.
- Sans épingle de site posée, la simulation ne part jamais sur le centre de la carte : ville de référence du lead, dite
  dans le résultat, sinon refus qui dit quoi faire.
