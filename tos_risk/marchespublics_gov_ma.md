# Scraper risk file — Portail Marocain des Marchés Publics (`marchespublics.gov.ma`)

> Fichier de risque exigé par la règle #5 volet (a) de `CLAUDE.md`, au format du
> gabarit de `tos_risk/README.md`. **Écrire ce fichier n'exécute aucun scraper.**
> La ligne « Founder approval » est délibérément VIDE : tant qu'elle l'est,
> aucune collecte automatique ne peut être lancée (le collecteur naît désarmé,
> `VEILLE_AO_COLLECTE_ACTIVE=0`, et son armement est une tâche distincte).

- **Target :** `https://www.marchespublics.gov.ma` — Portail Marocain des Marchés
  Publics (PMMP), exploité par la Trésorerie Générale du Royaume (TGR).
  Périmètre strictement limité aux **pages de recherche publiques, non
  authentifiées**, servies par le moteur PRADO du portail :
  - `GET  index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&searchAnnCons&keyWord=<motclé>`
  - `POST` sur **la même URL et la même jarre de cookies**, rejouant le postback
    PRADO (`PRADO_PAGESTATE`, `PRADO_POSTBACK_TARGET=ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop`,
    `ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop=500`) pour obtenir les
    lignes au-delà du plafond d'affichage de 10.
  - Les pages de **détail d'un avis** et les **dossiers de consultation (DCE)**
    ne sont ouverts **que sur clic humain**, un par un, jamais en masse (deux
    délais de 110 s ont été observés sur ce point de terminaison).

  **La requête est RESTREINTE par mots-clés métier** (`solaire`, `photovolta`,
  `pompage`…), ce qui ramène le résultat à **1 à 3 pages, soit moins de 10
  requêtes par jour**. Mesures du 2026-08-01 : `solaire` → 34 avis en cours,
  `photovolta` → 11.

  **CE QUI EST EXPLICITEMENT EXCLU, et doit rester impossible par construction :**
  un balayage complet des **3 380 avis ouverts** du portail. Il représenterait
  environ **338 requêtes POST par jour** — précisément la forme de trafic qu'un
  pare-feu est réglé pour attraper. Une requête sans mot-clé restrictif doit
  être refusée par le collecteur lui-même, pas seulement déconseillée.

- **Account used :** **AUCUN — accès anonyme uniquement.** Aucune page
  authentifiée n'est lue, aucun compte n'est créé ni utilisé par le dispositif
  automatique. **Jamais un compte personnel**, conformément à la règle #5. Si
  Taqinor ouvre par ailleurs un compte entreprise sur le portail (dépôt
  électronique obligatoire depuis le 01/09/2023), ce compte reste manuel et
  hors de portée du collecteur, et **les CGU de ce compte primeraient sur toute
  l'analyse ci-dessous** — c'est le seul chemin capable de créer une
  restriction contractuelle qui n'existe pas aujourd'hui.

- **ToS summary :** vérifié en main le 2026-08-01.
  - **Pas de `robots.txt`** : l'URL `/robots.txt` sert la page d'accueil, il n'y
    a donc aucune directive d'exclusion à respecter ni à violer.
  - **Pas d'API, pas de flux RSS public, pas de jeu open data** : `data.gov.ma`
    ne publie rien sur ce portail et les adresses de flux candidates renvoient
    404. Un service d'abonnement RSS existe mais est annoncé comme **réservé
    aux inscrits** (derrière la connexion).
  - Les **conditions d'utilisation publiées sont purement techniques** (navigateurs
    supportés, prérequis de signature électronique) et **muettes sur l'accès
    automatisé** : elles ne l'autorisent ni ne l'interdisent.
  - **Loi 31-13** relative au droit d'accès à l'information, **article 6** :
    la réutilisation des informations publiées par un organisme public est
    autorisée. Le contenu visé (avis d'appels d'offres publics) est une
    publication légale obligatoire.
  - **MAIS — clause « InfoSite » :** le portail réserve la reproduction de ses
    pages à une autorisation préalable. **Neutralisation retenue : ne rien
    republier.** Usage strictement interne à Taqinor ; on ne stocke que des
    **FAITS** (référence de consultation, objet, acheteur public, lieu, dates
    de publication / de remise / d'ouverture, montants, lot) et non les pages,
    leur mise en forme ou leur code. Les faits bruts ne sont pas protégés par
    le droit d'auteur. Aucune diffusion externe, aucune revente, aucune
    republication sous quelque forme que ce soit.

- **Risk :** globalement **faible**, mais avec un point dur qui n'est pas
  minimisé ci-dessous.
  - **Blocage IP / coupure de service** : conséquence la plus probable d'un
    excès de cadence. Impact limité (perte de la veille automatique, repli sur
    les alertes officielles et la saisie manuelle).
  - **Dérive du HTML** : le portail peut changer sa structure à tout moment ;
    le parseur casse, la collecte s'arrête. Impact opérationnel, pas juridique.
  - **Exposition juridique** : aucun précédent connu d'action de la TGR contre
    les agrégateurs marocains, qui exploitent cette même donnée depuis 1984 et
    opèrent ouvertement (Datao, lesoffres.ma, Marché Facile, Sodipress, Aljady…).

  **LE POINT DUR, ÉCRIT TEL QUEL ET NON MINIMISÉ.** Le pare-feu du portail
  **refuse déjà les clients scriptés** : `curl` et `python-requests` reçoivent
  un **403 « Interdit »** avec identifiant de refus, et seuls les User-Agent de
  navigateur sont servis. **En l'absence de conditions d'utilisation traitant
  de l'accès automatisé, cette règle de refus est l'expression la plus
  probante de la volonté de l'exploitant** — c'est une preuve EN FAVEUR d'une
  restriction, pas un simple obstacle technique neutre.

  Cette lecture a une conséquence directe, qui est **la règle de conduite du
  dispositif et prime sur tout le reste** :

  > **Le client envoie un User-Agent HONNÊTE, déclarant Taqinor et une adresse
  > de contact. Si ce User-Agent est refusé (403), le client S'ARRÊTE
  > définitivement et remonte l'échec. Il ne réessaie JAMAIS avec un
  > User-Agent de navigateur. Jamais de maquillage.**

  Maquiller l'identité du client pour contourner un contrôle qui nous a
  explicitement refusés est **hors périmètre**. Le repli, dans ce cas, est la
  porte des **alertes e-mail officielles du portail** (canal fourni par
  l'exploitant, 100 % autorisé) et la saisie manuelle — jamais le déguisement.

  Cette règle a été posée après qu'une revue adversariale a **refusé la
  première version de ce plan** : elle prévoyait « une lecture polie avec un
  User-Agent identifié », ce qui est contradictoire ici, puisqu'un UA honnête
  du type `TaqinorBot/1.0` est exactement la forme que le pare-feu bloque.
  « Poliment identifié » et « réponse 200 » sont mutuellement exclusifs sur ce
  portail : le plan initial ne fonctionnait qu'en maquillant le client.

- **Mitigation :**
  1. **User-Agent honnête** déclarant Taqinor + une adresse de contact, et
     **arrêt définitif sur 403** — jamais de repli sur un UA de navigateur.
  2. **Requête restreinte par mots-clés métier** côté serveur : 1 à 3 pages de
     résultats, jamais un balayage du portail. Une requête sans mot-clé
     restrictif est refusée par le collecteur.
  3. **Volume plafonné : moins de 10 requêtes par jour**, cadence **≤ 1 requête
     toutes les 2 secondes**.
  4. **Aucune page authentifiée** n'est lue ; aucun compte, a fortiori aucun
     compte personnel, n'est utilisé.
  5. **Aucun téléchargement de DCE en masse** : les pages de détail et les
     dossiers ne sont récupérés que sur clic humain, un par un.
  6. **Interrupteur d'arrêt** : la collecte est pilotée par le drapeau
     `VEILLE_AO_COLLECTE_ACTIVE`, à `0` par défaut, et par le drapeau `actif`
     de la source en base — une source désactivée n'est jamais interrogée.
  7. **Aucune republication** : stockage de faits seuls, usage strictement
     interne (voir la clause InfoSite ci-dessus).
  8. **Journal d'exécution auditable** : chaque collecte enregistre sa date,
     ses mots-clés, son nombre de requêtes et son résultat, de sorte que le
     respect des plafonds ci-dessus soit vérifiable après coup et non promis.
  9. **Aucun contournement de contrôle d'accès** : ni CAPTCHA, ni rotation
     d'adresses IP, ni proxy, ni falsification d'en-têtes.

- **Réponse de l'exploitant :** *(section à remplir — aucune demande n'a encore
  reçu de réponse à la date de rédaction)*

  Une demande écrite doit être adressée à la TGR
  (`marchespublics@tgr.gov.ma`, 05 37 57 88 15), en tant que fournisseur
  marocain, pour demander : (1) s'il existe un flux, un export ou une interface
  de programmation permettant de consulter les avis ouverts ; (2) si une
  lecture automatisée quotidienne, à faible cadence, à usage de veille interne,
  est acceptable. **Sous la loi 31-13, l'administration doit une réponse.**

  Une réponse écrite est la pièce la plus forte que ce fichier puisse contenir :
  elle fait passer le dispositif de « défendable » à « **autorisé** ». Une
  réponse négative est tout aussi utile — elle clôt le sujet et bascule
  définitivement la veille sur les alertes officielles.

  - Date d'envoi de la demande : *(à compléter)*
  - Date et teneur de la réponse (ou constat d'absence de réponse après
    relance) : *(à compléter — recopier ici le texte intégral de la réponse)*

- **Founder approval :** *(VIDE — non approuvé)*

  Aucune exécution du collecteur n'est autorisée tant que cette ligne est vide.
  Son remplissage (date + « approuvé par le fondateur ») est un acte manuel du
  fondateur, qui ne peut être posé par aucun agent de sa propre initiative.
