# Partie 2 — constats relevés pendant la préparation (24/11/2026), AVANT le premier tour de relecteurs

Ce ne sont pas des verdicts : chaque ligne est un candidat, à rejouer par un relecteur neuf au tour 1 puis à ranger
au registre (`../registre/`). Source : le préparateur (clics réels, compte `anon_admin`, pile `l5t`, code
`origin/main@cdaf0d30b1`), les lanes d'écran et l'orchestrateur.

## Vus à l'écran par le préparateur (copie anonymisée)

| # | Où | Geste | Attendu | Vu |
|---|---|---|---|---|
| P1 | `/admin/users`, `/parametres` | ouvrir la page | la page s'affiche | page blanche 15 à 20 s ; 11 signalements « timeout 20000ms » sur `GET /notifications/attention-summary/` |
| P2 | `/login` | se connecter | connexion immédiate | « Connexion en cours… » 10 à 20 s ; une fois « Identifiants incorrects » avec les bons identifiants (non reproduit) |
| P3 | Démarrage rapide | lire l'état des lignes | « Déjà renseigné » pour une valeur saisie | l'état n'apparaît jamais ; on lit « Posée par le profil (retirable) » |
| P4 | Réglages › Simulation | enregistrer le mode météo sans « Source » | un refus qui dit quoi choisir | le refus cite des codes bruts : « societe, mesure, saisie, texte » |
| P5 | Réglages › Simulation | saisir la fenêtre d'années | un champ qui dit son format | texte libre sans format ; `[2014, 2023]` deviné ; deux notices reviennent en toast à chaque enregistrement |
| P6 | Paramètres › Devis | lire l'échéancier « Industriel » | 100 % | 50 + 39 + 10 = 99 % (donnée de la production recopiée) |
| P7 | Accueil, rôle Technicien | lire la carte « Prise en main » | rien sur le profil de l'entreprise | « Compléter le profil de l'entreprise » proposé à un technicien |
| P8 | Menu, liste des utilisateurs | lire le rôle affiché | le nom du rôle | « UTILISATEUR » pour Commercial et Technicien ; `anon_admin` dit « Directeur » dans la liste et « Administrateur » dans son menu |
| P9 | `/parametres` | changer d'onglet | seuls les champs de l'onglet | les champs des onglets précédents restent dans le DOM (visibilité à vérifier) |
| P10 | Nouvel utilisateur | créer un compte | nom, prénom, poste | le formulaire ne demande ni nom, ni prénom, ni poste |

## Relevés par les lanes d'écran et l'orchestrateur

| # | Où | Constat |
|---|---|---|
| O1 | Simulation | une simulation lancée sur un calepinage SANS point GPS échoue dans le worker à 5 % (`EntreeInvalide` : « sans point GPS, aucune production ne peut être demandée ») au lieu d'être refusée avant le lancement, avec le champ à remplir ; deux lanes l'ont prise pour une panne de PVGIS |
| O2 | Vignette de la liste, exemple du contrat | les sommets du toit de l'exemple de contrat sont en mètres, pas en longitude / latitude : un calepinage créé depuis cet exemple a une surface absurde (7e11 m²) et rien ne se dessine |
| O3 | Étape Panneaux, vue client | la maquette v2 écrit « 82 % de votre facture » ; l'écran écrit « Production ÷ consommation » (c'est la grandeur servie) — libellé à trancher par le fondateur (texte lu par un client) |
| O4 | Documents | la colonne des cartes défile encore de 23 px à 1440 × 900 (la carte DXF est coupée) |
| O5 | Démarrage rapide | 16 réglages servis pour 6 dessinés par la maquette ; la carte défile à l'intérieur |
| O6 | Réglages du calepinage après le démarrage rapide | 28 lignes de simulation et 18 lignes électriques restent vides (aucune valeur proposée) ; à vérifier : aucun résultat ne doit être « incomplet » à cause d'elles |
