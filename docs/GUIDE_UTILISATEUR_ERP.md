<!-- GUIDE UTILISATEUR TAQINOR OS — généré le 2026-07-18 à partir de l'audit complet des modules ; destiné à une conversion PDF -->

# Guide utilisateur — TAQINOR OS

TAQINOR OS est le logiciel de gestion tout-en-un de votre entreprise solaire. Il
réunit dans une seule application, accessible depuis un navigateur, l'ensemble
de vos métiers : prospection commerciale (CRM), devis et ventes, facturation et
comptabilité, gestion du stock et des achats, suivi des chantiers et des
interventions, service après-vente, ressources humaines et paie, flotte de
véhicules, qualité-sécurité-environnement, contrats, documents, reporting et
bien plus. Toutes vos données sont propres à votre société : chaque utilisateur
ne voit que ce que son rôle l'autorise à voir, et vos informations ne sont
jamais mélangées avec celles d'une autre entreprise.

Ce guide s'adresse à tous les utilisateurs — commercial, technicien, comptable,
responsable RH, direction — quel que soit votre niveau de familiarité avec
l'informatique. Il décrit, écran par écran, comment réaliser vos tâches
quotidiennes.

## Comment lire ce guide

Le guide est organisé par métier : chaque chapitre correspond à un grand domaine
d'activité, et chaque fonctionnalité y est présentée selon le même modèle en
trois points, pour aller droit au but :

1. **Ce que ça fait** — à quoi sert la fonctionnalité, en une phrase.
2. **Où la trouver** — le chemin dans le menu (et, quand c'est utile, l'adresse
   de l'écran, par exemple `/ventes/devis`).
3. **Comment l'utiliser** — les étapes concrètes, numérotées.

Quelques repères de lecture :

- Les noms de menus, d'onglets et de boutons sont écrits **en gras**.
- Certaines fonctions sont réservées aux profils **Responsable** et
  **Administrateur** : c'est précisé à chaque fois.
- Ce guide ne décrit que les fonctionnalités vérifiées comme pleinement
  opérationnelles. Les modules encore en cours de construction n'y figurent pas
  (voir l'annexe en fin de document).

---

## Premiers pas

Ce chapitre couvre l'essentiel pour démarrer : se connecter, sécuriser son
compte, se repérer dans l'application, et — pour les responsables — créer les
comptes de l'équipe et régler les permissions.

### Se connecter à l'application

**Ce que ça fait.** Ouvre votre session de travail avec votre identifiant et
votre mot de passe. Si la double authentification (2FA) est activée sur votre
compte, un code à 6 chiffres vous est demandé après le mot de passe.

**Où la trouver.** L'adresse de l'ERP vous amène directement sur l'écran de
connexion (`/login`).

**Comment l'utiliser.**
1. Saisissez votre **nom d'utilisateur** (ou e-mail) et votre **mot de passe**.
2. Cliquez sur **Se connecter**.
3. Si un code vous est demandé, ouvrez votre application d'authentification
   (Google Authenticator ou équivalent), tapez le code à 6 chiffres, puis
   validez.
4. Après connexion, vous arrivez sur le **Tableau de bord**. Si votre session
   avait expiré sur une page précise, vous y êtes automatiquement ramené.
5. Pour quitter, utilisez **Se déconnecter** depuis votre menu.

Astuce sécurité : après plusieurs mots de passe erronés, votre compte peut être
temporairement verrouillé (message « Compte temporairement verrouillé »).
Patientez quelques minutes puis réessayez. En cas de page introuvable, un écran
« 404 » clair s'affiche ; en cas d'accès refusé, un écran « 403 » explique le
refus au lieu d'un renvoi silencieux.

### Sécuriser mon compte (2FA, mot de passe, sessions)

**Ce que ça fait.** Regroupe la protection de **votre** compte : activer la
double authentification, changer votre mot de passe, et voir ou fermer les
appareils connectés.

**Où la trouver.** Menu **Paramètres**, onglet **Sécurité du compte**.

**Comment l'utiliser.**
- **Activer la 2FA** : cliquez sur **Activer**, scannez le QR-code avec votre
  application d'authentification, saisissez le code à 6 chiffres pour confirmer.
  Ce code vous sera demandé à chaque connexion.
- **Désactiver la 2FA** : cliquez sur **Désactiver** et confirmez.
- **Changer de mot de passe** : saisissez l'ancien puis le nouveau, validez.
- **Sessions actives** : consultez la liste des appareils connectés et cliquez
  sur **Révoquer** pour déconnecter immédiatement un appareil suspect.

### Se repérer dans l'application (menu latéral)

**Ce que ça fait.** Le menu latéral de gauche regroupe toutes les sections
auxquelles votre rôle a droit. Il s'adapte automatiquement : un module désactivé
pour votre société, ou réservé à un rôle supérieur, n'apparaît pas.

**Où la trouver.** Colonne de gauche, présente sur tous les écrans une fois
connecté.

**Comment l'utiliser.**
1. En haut du menu se trouvent les raccourcis permanents : **Tableau de bord**,
   **Ma file** (votre file de travail personnelle) et **Messages**.
2. En dessous s'affichent les grands domaines (Stock, CRM, Ventes, Chantiers,
   Après-vente), puis **Documents**, **Intelligence** (OCR, Agent IA), les
   modules complémentaires activés, et enfin **Analyse** et **Administration**.
3. Cliquez sur une entrée pour ouvrir l'écran correspondant. Sur mobile, une
   barre en bas d'écran et un tiroir « Plus » reprennent les mêmes rubriques.

### Rechercher et créer rapidement (raccourcis)

**Ce que ça fait.** La **recherche globale** retrouve instantanément n'importe
quelle fiche (leads, clients, devis, factures, chantiers, équipements, tickets,
bons de commande, contrats, produits…) depuis un seul champ. La **création
rapide** permet de créer un lead, un client, un produit ou un ticket sans
quitter la page où vous êtes.

**Où la trouver.** L'icône loupe dans l'en-tête (recherche globale) ; la palette
de commandes s'ouvre au clavier avec **Ctrl + K** (Windows) ou **⌘ + K** (Mac),
ou via le bouton ⌘K de l'en-tête.

**Comment l'utiliser.**
1. Pour rechercher : tapez au moins 2 caractères ; les résultats apparaissent
   groupés par type. Cliquez sur un résultat pour ouvrir la fiche.
2. Pour créer : ouvrez la palette (**Ctrl/⌘ + K**), choisissez « Créer un lead /
   client / produit / ticket », remplissez le mini-formulaire et validez — vous
   restez sur la page en cours.
3. Le widget **Récents** du tableau de bord affiche vos dernières fiches
   consultées, pour y revenir en un clic.

### Les notifications (la cloche)

**Ce que ça fait.** La cloche vous prévient en temps réel des événements qui
vous concernent : un lead qui vous est assigné, un devis accepté, une facture en
retard, une garantie qui expire bientôt, un message où vous êtes mentionné. Un
badge rouge affiche le nombre d'éléments qui attendent une action (activités en
retard, garanties expirant sous 90 jours, factures impayées, contrats de
maintenance à renouveler, visites de maintenance dues).

**Où la trouver.** L'icône en forme de cloche, en haut à droite de l'en-tête,
visible sur toutes les pages.

**Comment l'utiliser.**
1. Cliquez sur la cloche pour ouvrir la liste de vos notifications.
2. Cliquez sur une notification pour aller directement à l'enregistrement
   concerné.
3. Cliquez sur la coche pour marquer une notification comme lue, ou sur **Tout
   marquer comme lu**.

Vous pouvez choisir sur quels canaux (application, WhatsApp, e-mail) recevoir
chaque type d'alerte : voir le chapitre « Messagerie & Notifications ».

### Changer de société active (comptes multi-sociétés)

**Ce que ça fait.** Si votre compte est rattaché à plusieurs sociétés, bascule
l'affichage de l'ERP d'une société à l'autre sans vous reconnecter.

**Où la trouver.** Le sélecteur de société dans l'en-tête / la barre latérale
(n'apparaît que si vous avez au moins deux sociétés).

**Comment l'utiliser.** Cliquez sur le nom de la société en cours, choisissez la
société cible : toutes les données affichées basculent sur celle-ci.

### Gérer les utilisateurs (équipe)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Crée les comptes de vos collaborateurs, modifie leur rôle,
leur poste, leur photo, leur responsable hiérarchique, active ou désactive un
compte, et réinitialise leur mot de passe.

**Où la trouver.** Menu **Administration → Utilisateurs** (`/admin/users`).

**Comment l'utiliser.**
1. Cliquez sur **Utilisateurs** dans la barre latérale.
2. Pour **ajouter** un collaborateur : bouton **Nouvel utilisateur**, renseignez
   le nom d'utilisateur, l'e-mail, le mot de passe et le **rôle**. Cochez
   « Demander un changement de mot de passe à la première connexion » pour qu'il
   choisisse lui-même le sien.
3. Pour **modifier** : cliquez sur la ligne d'un utilisateur, changez son rôle,
   son poste, son responsable ou sa photo (laissez le mot de passe vide pour ne
   pas le changer).
4. Pour **désactiver** un compte : basculez l'interrupteur **Actif** — le compte
   ne peut plus se connecter, sans être supprimé.

### Gérer les rôles et les permissions

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Définit **qui a le droit de faire quoi** (voir / créer /
modifier / supprimer / exporter) module par module, à l'aide d'une grille de
permissions. L'ERP fournit sept rôles prêts à l'emploi (Directeur,
Administrateur, Commercial responsable, Commercial, Technicien responsable,
Technicien, Viewer), tous personnalisables.

**Où la trouver.** Menu **Administration → Rôles** (`/admin/roles`).

**Comment l'utiliser.**
1. Cliquez sur **Rôles**.
2. Pour **créer** un rôle : donnez-lui un nom, puis cochez les permissions
   voulues dans la grille module × action.
3. Pour **modifier** un rôle existant : cliquez dessus et ajustez les cases.
4. Pour **affecter** un rôle : réassignez des utilisateurs depuis l'écran Rôles,
   ou compte par compte depuis **Utilisateurs**.

Garde-fous automatiques : les rôles « système » ne peuvent pas être supprimés,
un rôle encore attribué à quelqu'un ne peut pas être supprimé, et vous ne pouvez
pas vous auto-attribuer des permissions sensibles en modifiant votre propre
rôle.

### Bien démarrer : la checklist « Premiers pas »

**Ce que ça fait.** Affiche sur le tableau de bord une petite liste des
premières actions à réaliser pour bien démarrer (créer un devis, encaisser un
paiement…), avec une barre de progression. Certaines étapes se cochent
automatiquement dès que l'action correspondante a été faite dans l'ERP.

**Où la trouver.** Directement sur la page d'accueil (**Tableau de bord**), sous
forme d'une carte « Premiers pas ».

**Comment l'utiliser.**
1. Cliquez sur une étape non cochée pour être amené directement à l'écran
   correspondant.
2. Les étapes « Créer votre 1er devis » et « Encaisser votre 1er paiement » se
   cochent automatiquement une fois l'action réalisée.
3. Vous pouvez masquer une étape (icône **×**) ou cliquer sur **Tout ignorer**
   pour faire disparaître la carte.

### Aide et lexique

**Ce que ça fait.** Un glossaire des termes métier utilisés dans l'application.

**Où la trouver.** Les bulles d'aide « ? » présentes sur les écrans renvoient au
lexique (`/aide/lexique`), où chaque terme est défini.

### Les pages publiques partagées aux clients

Plusieurs pages sont accessibles **sans connexion**, via un lien sécurisé
(jeton) que vous envoyez à un client ou à une équipe terrain. Il suffit de
partager le lien : le destinataire ouvre la page directement, sans compte.
Ces pages sont décrites dans leurs chapitres respectifs ; en voici la liste :

- **Signature électronique** d'un document ou d'un contrat.
- **Portail « Mes contrats »** (le client consulte ses contrats).
- **Réservation d'une visite / d'un rendez-vous**.
- **Dépôt de fichier** demandé à un tiers.
- **Kiosque de pointage** pour le personnel.
- **Suivi d'un ticket SAV** (avec note de satisfaction).
- **Signaler un problème** via un QR-code posé sur un équipement ou un chantier.
- **Article de base de connaissances** partagé.

---

## CRM & prospection

Le module CRM suit chaque prospect à travers les étapes du tunnel de vente :
Nouveau → Contacté → Devis envoyé → Relance → Signé (ou Froid).

### Gérer vos leads (pistes commerciales)

**Ce que ça fait.** Crée, modifie et suit chaque prospect tout au long du tunnel
de vente.

**Où la trouver.** Menu **CRM → Leads** (`/crm/leads`). Chaque lead a aussi sa
propre page adressable `/crm/leads/<numéro>`, que vous pouvez partager par lien.

**Comment l'utiliser.**
1. Depuis la liste des leads, cliquez sur **Nouveau lead** et remplissez les
   coordonnées du prospect.
2. Faites glisser la carte du lead d'une colonne à l'autre dans la vue Kanban
   pour changer son étape, ou changez l'étape depuis sa fiche.
3. Cliquez sur un lead pour ouvrir sa fiche complète.

### Historique et notes d'un lead

**Ce que ça fait.** Journalise automatiquement chaque changement de champ
(étape, responsable…) et vous permet d'ajouter des notes manuelles, visibles par
toute l'équipe.

**Où la trouver.** Sur la fiche d'un lead, section **Historique**.

**Comment l'utiliser.**
1. Ouvrez la fiche du lead.
2. Faites défiler jusqu'à **Historique** pour voir tous les changements et les
   notes.
3. Utilisez le champ de note en bas de cette section pour écrire un commentaire.

### Créer un devis depuis un lead

**Ce que ça fait.** Quand vous créez un devis depuis un lead, le système retrouve
automatiquement le bon client (s'il existe déjà, par e-mail ou téléphone) ou en
crée un nouveau — sans jamais dupliquer de fiche client.

**Où la trouver.** Sur la fiche d'un lead, panneau **Devis**.

**Comment l'utiliser.**
1. Ouvrez la fiche du lead.
2. Ouvrez le panneau Devis et choisissez **Devis automatique** (rapide) ou
   **Édition complète** (pour tout ajuster).
3. Le client est relié automatiquement au devis — rien de plus à faire à cette
   étape.

### Détecter et fusionner les doublons

**Ce que ça fait.** Repère les leads probablement en double (même téléphone, même
e-mail ou même nom) et permet de les fusionner en un seul sans rien perdre :
devis, historique et pièces jointes sont tous transférés, et les fiches
absorbées sont archivées, jamais supprimées.

**Où la trouver.** Depuis la liste des leads, bouton **Doublons** (un badge
indique le nombre de groupes détectés). Une fiche lead affiche aussi ses propres
doublons potentiels.

**Comment l'utiliser.**
1. Cliquez sur **Doublons** depuis la liste des leads.
2. Pour chaque groupe détecté, choisissez la fiche à garder (le survivant).
3. Cliquez sur **Fusionner le groupe** et confirmez.

### Archiver ou restaurer un lead

**Ce que ça fait.** Retire un lead de vos vues actives sans le supprimer
(réversible à tout moment).

**Où la trouver.** Sur la fiche du lead, ou depuis les actions rapides de la
liste / du Kanban.

**Comment l'utiliser.**
1. Ouvrez le lead, cliquez sur **Archiver**.
2. Pour le récupérer : filtrez sur « Archivés » dans la liste, ouvrez la fiche,
   cliquez sur **Restaurer**.

### Points de contact d'un lead (Insights)

**Ce que ça fait.** Montre par quels canaux (publicité, WhatsApp, site web…) un
lead vous a contacté, avec la chronologie complète du premier au dernier contact.

**Où la trouver.** Depuis la vue Liste des leads, panneau **Insights** d'un lead.

**Comment l'utiliser.** Ouvrez le panneau Insights et consultez la chronologie
des points de contact ainsi que le résumé premier-contact / dernier-contact.

### Programme de parrainage

**Ce que ça fait.** Suit les clients qui recommandent de nouveaux prospects, avec
le statut de la récompense.

**Où la trouver.** Menu **CRM → Parrainage** (`/crm/parrainage`).

**Comment l'utiliser.**
1. Ouvrez la page Parrainage.
2. Créez un parrainage en indiquant le client parrain et le lead/client filleul.
3. Suivez le statut (en attente → converti → récompense versée).

### Rejouer les leads du site web

**Ce que ça fait.** Si un lead envoyé depuis le site taqinor.ma n'a pas pu être
créé automatiquement, cette page permet de le rejouer sans le perdre.

**Où la trouver.** Menu **CRM** (`/crm/payloads-site-web`).

**Comment l'utiliser.**
1. Ouvrez la page et repérez les entrées non traitées.
2. Cliquez sur **Rejouer** pour retenter la création du lead.

### Équipes commerciales

*Réservé aux administrateurs.*

**Ce que ça fait.** Permet de créer des équipes de commerciaux et de suivre leurs
statistiques.

**Où la trouver.** Menu **Paramètres → Leads**, section « Équipes commerciales ».

**Comment l'utiliser.** Créez une équipe et ajoutez-y des membres.

---

## Devis & Ventes

Tout ce qui concerne la préparation et l'envoi des devis solaires se trouve dans
la section **VENTES** du menu de gauche.

### Créer un devis solaire

**Ce que ça fait.** Génère un devis chiffré (résidentiel, industriel/commercial
ou agricole/pompage) avec le dimensionnement solaire calculé automatiquement
(kWc, production, économies — ou débit/HMT pour le pompage).

**Où la trouver.** Menu **VENTES → Devis**, bouton **Nouveau**
(`/ventes/devis/nouveau`). Raccourci clavier : tapez `c` puis `d`. Vous pouvez
aussi partir d'un client depuis sa fiche (bouton « Nouveau devis »).

**Comment l'utiliser.**
1. Choisissez le marché (Résidentiel / Industriel / Agricole).
2. Sélectionnez le client (ou créez-le à la volée).
3. Ajoutez les lignes de produits : les prix et le dimensionnement se
   pré-remplissent. Si une liste de prix négociée existe pour ce client, elle
   s'applique automatiquement.
4. Vérifiez les totaux (tout est en TTC) et enregistrez. Le devis est créé d'un
   seul coup, sans brouillon incomplet même si la connexion coupe.

### Envoyer le devis au client (PDF, e-mail, WhatsApp)

**Ce que ça fait.** Produit le PDF premium du devis et l'envoie au client, avec
un lien web sécurisé où il peut consulter la proposition et **signer en ligne**.

**Où la trouver.** Dans la liste **VENTES → Devis**, sur la ligne du devis (menu
d'actions / aperçu PDF).

**Comment l'utiliser.**
1. Ouvrez l'aperçu PDF pour vérifier le rendu (format 1 page, complet, ou avec
   étude).
2. Cliquez sur **Envoyer par e-mail** ou **Envoyer par WhatsApp** : le client
   reçoit le PDF et un lien de proposition, et le devis passe en statut
   « Envoyé ».
3. Vous pouvez aussi simplement **copier le lien de partage** pour l'envoyer
   vous-même.

### Suivre la décision du client (accepter / refuser / réviser)

**Ce que ça fait.** Enregistre la réponse du client et fait avancer le dossier.

**Où la trouver.** Liste **VENTES → Devis**, actions sur le devis.

**Comment l'utiliser.**
- **Accepter** : saisissez la date et le nom du signataire ; cela déclenche la
  suite (bon de commande / chantier).
- **Refuser** : indiquez le motif (il est journalisé).
- **Réviser** : crée une nouvelle version (v2, v3…) sans perdre l'ancienne.
- **Variantes** : dupliquez le devis en 2-3 dimensionnements pour comparaison.
- Chaque action est tracée dans l'**historique** du devis, où vous pouvez aussi
  ajouter des notes.

### Approbation de remise

**Ce que ça fait.** Quand la remise dépasse un seuil, le devis demande une
validation hiérarchique avant l'envoi. Un bloc **Approbation de remise**
apparaît alors sur la fiche du devis.

**Où la trouver.** Sur la fiche du devis (le bloc n'apparaît que s'il y a une
étape à traiter).

**Comment l'utiliser.** Le responsable clique **Approuver** (ou **Rejeter** avec
un motif). Tant qu'une étape reste en attente, l'envoi est bloqué.

### Transformer un devis accepté en bon de commande

**Ce que ça fait.** Crée le bon de commande client à partir du devis accepté.

**Où la trouver.** Liste **VENTES → Devis** (action **Convertir en BC**), puis
**VENTES → Bons de commande** pour le suivi.

**Comment l'utiliser.**
1. Le devis doit être au statut **Accepté**.
2. Cliquez sur **Convertir en BC** (un seul bon de commande par devis).
3. Dans **Bons de commande**, suivez le cycle : **Confirmer → Marquer livré**
   (le stock est décrémenté), avec livraison partielle possible, ou **Annuler**.
   Vous pouvez imprimer le PDF du bon de commande et **créer la facture** depuis
   le BC.

### Conception de toiture 3D

**Ce que ça fait.** Place les panneaux sur la toiture (calepinage 3D) et rattache
le plan au devis, avec un aperçu de la proposition pour le client.

**Où la trouver.** Depuis le devis (accès à l'outil de conception 3D).

**Comment l'utiliser.** Dessinez l'implantation puis finalisez le plan ; il est
stocké sur le devis et sert à la proposition client.

### Modèles de devis (presets)

**Ce que ça fait.** Enregistre un devis comme modèle réutilisable, pour aller
plus vite sur les affaires récurrentes.

**Où la trouver.** Panneau des modèles sur le devis.

**Comment l'utiliser.** **Enregistrer comme modèle**, puis **Appliquer un
modèle** sur un nouveau devis.

---

## Facturation & Recouvrement

Une fois le bon de commande en place, la facturation, les encaissements et les
relances se pilotent depuis la section **VENTES**.

### Facturer (échéancier acompte / matériel / solde)

**Ce que ça fait.** Génère les factures de tranches à partir du devis (acompte,
puis matériel, puis solde), numérotées automatiquement sans collision.

**Où la trouver.** Action **Générer facture** sur le devis, puis section
**VENTES → Factures**.

**Comment l'utiliser.**
1. Cliquez sur **Générer facture** : la première fois crée l'acompte, les fois
   suivantes les tranches suivantes.
2. Dans **Factures**, gérez le cycle : **Émettre**, **Marquer payée**,
   **Annuler**, générer/télécharger le **PDF**, envoyer par **e-mail** ou
   **WhatsApp**.
3. Une vue **Kanban** est disponible, ainsi que des **actions en masse**
   (émettre / relancer / e-mail / PDF sur une sélection).

### Encaissements (paiements)

**Ce que ça fait.** Enregistre les règlements reçus (espèces, virement, chèque,
carte, prélèvement) et met à jour le reste à payer.

**Où la trouver.** Menu **VENTES → Encaissements**, ou directement sur une
facture.

**Comment l'utiliser.** Sur la facture, cliquez sur **Enregistrer un paiement**
(montant, date, mode). La liste **Encaissements** montre tous les règlements de
la société.

### Avoirs (notes de crédit)

**Ce que ça fait.** Émet un avoir sur une facture (remboursement ou annulation
partielle) qui réduit ce que le client doit.

**Où la trouver.** Menu **VENTES → Avoirs**, ou action **Créer un avoir** sur la
facture.

**Comment l'utiliser.** Créez l'avoir depuis la facture (motif + montants), puis
depuis **Avoirs** vous pouvez l'annuler ou télécharger son PDF.

### Relances et impayés

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Liste les factures en retard, prépare les lettres de relance
et la balance âgée. L'outil prépare et imprime — il n'envoie jamais tout seul.

**Où la trouver.** Menu **VENTES → Relances / Impayés**.

**Comment l'utiliser.**
1. Consultez les factures à relancer et la **balance âgée**.
2. **Relancer** une facture (l'action est consignée), ou l'**exclure** des
   relances.
3. Imprimez la **lettre de relance** (standard ou premium niveau 1/2/3) et le
   **relevé de compte client**.
4. Les paliers de relance (J+7 / J+15 / J+30) se règlent dans **Paramètres
   entreprise**.

### Journal des ventes et numérotation

**Ce que ça fait.** Exporte le **journal des ventes** (Excel, avec résumé TVA et
option grand-livre CGNC) et permet de voir le **prochain numéro** de pièce.

**Où la trouver.** Export du journal des ventes depuis l'espace Factures ; aperçu
de numérotation dans **Paramètres entreprise**.

**Comment l'utiliser.** Choisissez la période et exportez le fichier Excel pour
le fiduciaire.

Remarque : l'export de conformité **DGI** et le lien **« Payer en ligne »**
existent mais restent désactivés par défaut ; ils n'apparaissent que si votre
administrateur les active.

---

## Comptabilité

*Tous les écrans de comptabilité sont réservés aux profils Responsable et
Administrateur.* On y accède par le menu latéral, rubrique **COMPTABILITÉ**.

### Cockpit financier

**Ce que ça fait.** Votre tableau de bord de finances : trésorerie, indicateurs
clés et alertes du jour, en un coup d'œil.

**Où la trouver.** Menu **COMPTABILITÉ → Cockpit** (`/comptabilite`).

**Comment l'utiliser.**
1. Ouvrez le menu Comptabilité ; le Cockpit est la première ligne.
2. Les chiffres se chargent automatiquement. Une alerte de trésorerie s'affiche
   chaque matin (relances et ruptures calculées à l'aube).

### Plan comptable

**Ce que ça fait.** Gère votre plan comptable marocain (CGNC) : la liste des
comptes, les journaux (ventes, achats, banque, caisse, OD…) et les plans.

**Où la trouver.** Menu **COMPTABILITÉ → Plan comptable** (`/comptabilite/plan`).

**Comment l'utiliser.**
1. Consultez la liste des comptes et journaux.
2. Ajoutez ou modifiez un compte / journal via les boutons de la page.

### Écritures

**Ce que ça fait.** Le grand livre : saisir, consulter, valider et **extourner**
(annuler par contre-passation) des écritures comptables. Une écriture doit être
équilibrée (débit = crédit).

**Où la trouver.** Menu **COMPTABILITÉ → Écritures**
(`/comptabilite/ecritures`).

**Comment l'utiliser.**
1. Filtrez par journal et par période (date début / date fin).
2. Cliquez sur **Nouvelle écriture**, choisissez le journal et la date, puis
   saisissez les lignes (compte, libellé, débit/crédit) jusqu'à l'équilibre, et
   enregistrez.
3. Sur une écriture, **Valider** la fige ; **Extourner** crée son annulation.
   Une période clôturée bloque toute modification.

### États CGNC

**Ce que ça fait.** Édite tous les états comptables légaux : **balance, CPC
(compte de produits et charges), bilan, ESG, ETIC, grand livre**, plus les
exports fiscaux (**FEC**, liasse fiscale, export fiduciaire, relevé des
déductions de TVA).

**Où la trouver.** Menu **COMPTABILITÉ → États CGNC** (`/comptabilite/etats`).

**Comment l'utiliser.**
1. Choisissez l'état voulu et la période (ou l'exercice).
2. Consultez à l'écran, puis **Exporter** pour télécharger le fichier (FEC pour
   la DGI, liasse ou fiduciaire au format tableur).

### Trésorerie

**Ce que ça fait.** Suivi de la trésorerie : comptes de banque, **caisses** (avec
mouvements et clôture de caisse), virements internes et **prévisionnel** de
trésorerie (position à 13 semaines).

**Où la trouver.** Menu **COMPTABILITÉ → Trésorerie**
(`/comptabilite/tresorerie`).

**Comment l'utiliser.**
1. Naviguez par onglet (caisses, virements, prévisionnel…).
2. Sur une caisse : enregistrez un mouvement, puis **Clôturer** en fin de
   journée.
3. Consultez la position de trésorerie prévisionnelle pour anticiper les
   besoins.

### Fiscalité

**Ce que ça fait.** Prépare et suit vos déclarations : **déclaration de TVA**,
**retenues à la source** (RAS) et **timbres fiscaux**. Les montants de TVA sont
calculés automatiquement à partir du grand livre.

**Où la trouver.** Menu **COMPTABILITÉ → Fiscalité**
(`/comptabilite/fiscalite`).

**Comment l'utiliser.**
1. Onglet **Déclarations TVA** : cliquez sur **Préparer** pour une période — le
   système agrège la TVA collectée et déductible et calcule le montant à
   déclarer ; puis **Exporter** le bordereau.
2. Onglet **Retenues à la source** : consultez les retenues, éditez le
   **bordereau de versement** et l'**attestation**, et marquez **Versé**.
3. Onglet **Timbres fiscaux** : marquez un timbre **Versé** une fois réglé.

### Immobilisations

**Ce que ça fait.** Registre des immobilisations (véhicules, matériel, mobilier,
informatique…) avec **plan d'amortissement** (linéaire ou dégressif) et
**cession/rebut**. Les dotations et cessions se comptabilisent en écriture
équilibrée.

**Où la trouver.** Menu **COMPTABILITÉ → Immobilisations**
(`/comptabilite/immobilisations`).

**Comment l'utiliser.**
1. Créez une immobilisation (libellé, catégorie, coût HT, taux TVA, date
   d'acquisition).
2. Générez son **plan d'amortissement**, puis **Poster** une dotation annuelle.
3. Pour une sortie : **Céder** (vente ou rebut) puis **Poster** l'écriture de
   cession.

### Rapprochements bancaires

**Ce que ça fait.** Pointe les lignes du relevé bancaire contre le grand livre,
accepte des **suggestions** automatiques, puis **clôture** le rapprochement.

**Où la trouver.** Menu **COMPTABILITÉ → Rapprochements**
(`/comptabilite/rapprochements`).

**Comment l'utiliser.**
1. Ouvrez un rapprochement ; ajoutez les lignes du relevé.
2. **Pointez** les correspondances (ou **Accepter les suggestions** proposées).
3. **Clôturer** une fois l'écart soldé.

### Notes de frais

**Ce que ça fait.** Traitement comptable des **notes de frais** et **indemnités
de chantier** des employés : validation, remboursement, reçu PDF et
refacturation.

**Où la trouver.** Menu **COMPTABILITÉ → Notes de frais**
(`/comptabilite/notes-de-frais`).

**Comment l'utiliser.**
1. Consultez les notes soumises ; **Valider** ou **Rejeter**.
2. **Rembourser** une note validée (écriture générée automatiquement).
3. Éditez le **reçu PDF** ; utilisez **Refacturer** pour répercuter au client.

### Effets et règlements

**Ce que ça fait.** Gestion des **effets** (traites/chèques à recevoir ou à
payer), des **bordereaux de remise en banque** et des **campagnes de règlement
fournisseurs** (payment runs) avec fichier de virement.

**Où la trouver.** Menu **COMPTABILITÉ → Effets & règlements**
(`/comptabilite/effets`).

**Comment l'utiliser.**
1. Sur un effet : **Encaisser**, **Payer**, **Rejeter**, **Escompter** ou
   **Endosser**.
2. Créez un **bordereau** de remise, puis **Poster** l'encaissement.
3. Pour les fournisseurs : préparez un **payment run** (**Proposer → Figer →
   Poster**), puis téléchargez le **fichier de virement**.

### Engagements

**Ce que ça fait.** Suivi des **retenues de garantie** (retenues sur marchés,
libérées à échéance) et des **cautions bancaires** (provisoires/définitives, avec
mainlevée).

**Où la trouver.** Menu **COMPTABILITÉ → Engagements**
(`/comptabilite/engagements`).

**Comment l'utiliser.**
1. Consultez les **échéances** à venir (retenues et cautions).
2. **Libérer** une retenue de garantie arrivée à terme.
3. Enregistrer une **mainlevée** sur une caution bancaire.

### Répertoire des tiers (Appels d'offres)

**Ce que ça fait.** Le répertoire unifié « Tiers » (une fiche par client,
fournisseur, partenaire ou sous-traitant) alimente le champ « Maître d'ouvrage »
des dossiers d'Appel d'offres, avec recherche instantanée par nom.

**Où la trouver.** Menu **Comptabilité → Appels d'offres** (page Engagements),
lors de la création ou de la modification d'un dossier de soumission.

**Comment l'utiliser.**
1. Dans le formulaire d'un dossier d'Appel d'offres, cliquez sur le champ
   **Maître d'ouvrage / client**.
2. Tapez quelques lettres du nom : la liste se filtre parmi les fiches du
   répertoire tiers de votre société.
3. Sélectionnez la fiche voulue — le nom est enregistré sur le dossier.

Chaque matin, l'application recalcule automatiquement les alertes de rupture de
trésorerie et prépare les relances du jour ; les résultats apparaissent dans le
Cockpit et la Trésorerie.

---

## Stock & Achats

Le module Stock gère votre catalogue, vos fournisseurs, vos mouvements de stock,
vos commandes et réceptions fournisseur, ainsi que votre outillage durable.

### Catalogue produits

**Ce que ça fait.** La liste centrale de tous vos articles (panneaux, onduleurs,
batteries, câbles…) : nom, référence (SKU), prix de vente, prix d'achat (visible
en interne seulement), quantité en stock, seuil d'alerte. Vous pouvez créer,
modifier, archiver ou dupliquer un produit, faire une modification groupée sur
une sélection, ou exporter la liste en Excel.

**Où la trouver.** Menu **STOCK → Produits** (`/stock`).

**Comment l'utiliser.**
1. Ouvrez STOCK → Produits.
2. Cliquez sur **Nouveau produit** pour créer une fiche, ou sur une ligne pour
   la modifier.
3. Pour dupliquer un produit existant, utilisez l'action **Dupliquer** sur sa
   fiche.
4. Pour modifier plusieurs produits ensemble (catégorie, prix…), cochez les
   lignes puis utilisez la modification en masse.
5. Le bouton d'export génère un fichier Excel de la sélection.

### Catégories et marques

**Ce que ça fait.** Gère les catégories de classement du catalogue et les marques
(fabricants) utilisées sur les fiches produit.

**Où la trouver.** Menu **STOCK → Catégories & marques** (`/stock/categories`).

**Comment l'utiliser.** Ajoutez, renommez ou réordonnez une catégorie. Une marque
déjà utilisée sur un produit ne peut pas être supprimée (protection).

### Fournisseurs

**Ce que ça fait.** La fiche de chaque fournisseur (nom, contact, e-mail,
téléphone, adresse). Vous pouvez comparer les prix de plusieurs fournisseurs pour
un même produit et consulter une note de performance par fournisseur.

**Où la trouver.** Menu **STOCK → Fournisseurs** (`/stock/fournisseurs`).

**Comment l'utiliser.**
1. Créez ou modifiez une fiche fournisseur depuis la liste.
2. Sur la fiche d'un produit ayant plusieurs fournisseurs, utilisez la
   comparaison de prix pour repérer le moins cher.

### Mouvements de stock

**Ce que ça fait.** L'historique de chaque entrée / sortie / transfert /
ajustement de quantité sur un produit — la traçabilité complète du stock.

**Où la trouver.** Menu **STOCK → Mouvements** (`/stock/mouvements`).

**Comment l'utiliser.** Consultez la liste (filtrable), ou exportez-la en Excel.

### Commandes fournisseur

**Ce que ça fait.** Le document que vous envoyez à un fournisseur pour commander
du matériel. Suit tout le cycle : brouillon → envoyé → reçu, avec envoi par
WhatsApp ou e-mail, annulation motivée, duplication, fusion de plusieurs
commandes du même fournisseur, facturation directe et PDF.

**Où la trouver.** Menu **STOCK → Commandes fournisseur**
(`/stock/bons-commande-fournisseur`).

**Comment l'utiliser.**
1. Créez une commande, ajoutez vos lignes (produit, quantité, prix d'achat).
2. Cliquez sur **Envoyer** pour la passer en statut « Envoyé », ou utilisez les
   boutons WhatsApp / E-mail pour l'envoyer au fournisseur avec le PDF joint.
3. À l'arrivée de la marchandise, utilisez **Recevoir** (réception totale ou
   partielle) : le stock est automatiquement incrémenté.
4. En cas d'erreur, **Annuler** (un motif est obligatoire) ; une commande annulée
   sans réception peut être **rouverte**.
5. **Dupliquer** recrée un brouillon identique ; **Fusionner** regroupe plusieurs
   brouillons du même fournisseur.
6. **Facturer** génère directement une facture fournisseur depuis la commande.

### Modèles de commande fournisseur

**Ce que ça fait.** Des modèles réutilisables de commande (une liste d'articles
standard) pour ne pas ressaisir toujours les mêmes lignes.

**Où la trouver.** Menu **STOCK → Modèles de commande** (`/stock/modeles-bcf`).

**Comment l'utiliser.** Créez un modèle avec ses lignes, puis **Générer** pour
créer une nouvelle commande fournisseur brouillon à partir de ce modèle.

### Réceptions fournisseur

**Ce que ça fait.** Trace précisément ce qui a été réellement livré (total ou
partiel). À la confirmation, le stock est incrémenté et le statut de la commande
avance automatiquement. Un scan de code-barres/QR permet de préremplir la
réception.

**Où la trouver.** Menu **STOCK → Réceptions fournisseur**
(`/stock/receptions-fournisseur`).

**Comment l'utiliser.**
1. Créez une réception depuis une commande fournisseur.
2. Renseignez les quantités reçues par ligne (et, si besoin, numéros de série ou
   de lot / date de péremption).
3. **Confirmer** : le stock est mis à jour ; une confirmation déjà faite ne
   recrée jamais de mouvement en double.

### Factures fournisseur et paiements

**Ce que ça fait.** Les factures reçues de vos fournisseurs et leur règlement. Le
solde dû se recalcule automatiquement à chaque paiement. Une facture peut aussi
être créée depuis une réception confirmée, ou pré-remplie à partir d'un scan
(OCR) de facture papier.

**Où la trouver.** Menu **STOCK → Factures fournisseur**
(`/stock/factures-fournisseur`) et **STOCK → Import OCR** (`/stock/ocr-import`).

**Comment l'utiliser.**
1. Créez une facture fournisseur manuellement, depuis une réception confirmée
   (bouton « Facturer »), ou en important un scan/PDF via **Import OCR** (les
   champs sont pré-remplis, à vérifier avant validation).
2. Enregistrez un paiement sur la facture (montant, mode, date) — le solde dû et
   le statut se mettent à jour seuls.
3. Le PDF de la facture est disponible depuis sa fiche.

### Retours fournisseur

**Ce que ça fait.** Enregistre le retour d'articles défectueux ou erronés à un
fournisseur. À la validation, le stock est décrémenté automatiquement.

**Où la trouver.** Menu **STOCK → Retours fournisseur**
(`/stock/retours-fournisseur`).

**Comment l'utiliser.** Créez un retour (lié ou non à une commande d'origine),
indiquez le motif par ligne, puis **Valider** (ou **Annuler** si besoin).

### Pilotage du stock (réapprovisionnement)

**Ce que ça fait.** Un panneau d'aide à la décision sur la page Produits : liste
des articles à réapprovisionner (sous le seuil d'alerte), prévisions de rupture,
rotation du stock, et articles approchant de leur date de péremption. Un bouton
génère directement une commande fournisseur brouillon pour les manques.

**Où la trouver.** Menu **STOCK → Produits** (`/stock`), panneau **Pilotage
stock** (bouton dédié en haut de la liste).

**Comment l'utiliser.** Ouvrez le panneau, consultez les articles en manque, puis
cliquez pour générer une commande fournisseur brouillon (à compléter et envoyer
ensuite).

### Kits produit (nomenclatures)

**Ce que ça fait.** Un kit regroupe plusieurs produits du catalogue en un seul
ensemble (par exemple un kit de structure de fixation). Vous pouvez voir sa
composition détaillée et sa disponibilité réelle.

**Où la trouver.** Menu **Paramètres → Données** (onglet Kits produit), ou dans
les ateliers d'installation.

**Comment l'utiliser.** Consultez la liste des kits, cliquez sur **Exploser**
pour voir le détail des composants et les quantités nécessaires.

### Sessions d'inventaire physique

**Ce que ça fait.** Permet de faire un inventaire physique (comptage réel en
entrepôt) et de le comparer au stock théorique, avec ajustement automatique des
écarts à la validation.

**Où la trouver.** Menu **Paramètres → Données** (onglet Inventaire).

**Comment l'utiliser.** Créez une session, saisissez les comptages, puis
**Valider** pour appliquer les ajustements (ou **Annuler** pour abandonner sans
rien changer).

### Fiches techniques (datasheets)

**Ce que ça fait.** Rattache des documents techniques (fiches produit fabricant)
à un article du catalogue.

**Où la trouver.** Menu **Paramètres → Données** (onglet Fiches techniques).

**Comment l'utiliser.** Depuis un produit, ajoutez, modifiez ou supprimez ses
fiches techniques.

### Nomenclatures et règles de code-barres

**Ce que ça fait.** Configure comment les codes-barres/QR de vos produits sont
générés et interprétés (utile pour l'impression d'étiquettes et le scan en
réception).

**Où la trouver.** Menu **Paramètres → Stock**.

**Comment l'utiliser.** Créez une nomenclature de code-barres et ses règles ;
elles sont ensuite utilisées automatiquement par l'impression d'étiquettes et le
scan de réception.

### Outillage — parc d'outils durables

**Ce que ça fait.** Le registre de tout votre outillage durable (perceuses,
échelles, multimètres…), distinct du stock vendable : jamais vendu, jamais
consommé. Chaque outil a un statut (disponible / en intervention / en réparation
/ perdu) et un emplacement (dépôt ou camionnette).

**Où la trouver.** Menu **CHANTIERS → Outillage** (`/outillage`).

**Comment l'utiliser.** Ajoutez un outil (nom, catégorie, étiquette d'inventaire,
numéro de série, emplacement) et mettez à jour son statut au fil du temps.

### Kits d'outillage

**Ce que ça fait.** Des listes types d'outils nécessaires pour un genre
d'intervention (pose de structure, raccordement électrique, mise en service).
Trois kits par défaut sont créés automatiquement et restent modifiables.

**Où la trouver.** Menu **Paramètres → Kits d'outillage**.

**Comment l'utiliser.** Renommez, réordonnez ou (dés)activez un kit, ajoutez-y
les outils nécessaires, et associez-le à un type d'intervention pour qu'il soit
proposé automatiquement au technicien.

### Préparation d'intervention — matériel et outils

**Ce que ça fait.** Au moment de préparer une intervention chantier, l'ERP propose
automatiquement le bon kit d'outillage (selon le type d'intervention) et la liste
du matériel nécessaire (depuis la nomenclature du chantier), avec les manques
signalés. Le technicien coche ce qu'il charge réellement avant de partir.

**Où la trouver.** Menu **CHANTIERS → Interventions** (`/interventions`) ou **Ma
journée** (`/ma-journee`), sur la fiche d'une intervention.

**Comment l'utiliser.**
1. Ouvrez la fiche de préparation d'une intervention.
2. Le kit d'outillage est déjà pré-sélectionné (modifiable si besoin).
3. Cochez le matériel et les outils chargés au fur et à mesure.
4. **Confirmer le chargement** valide la préparation avant le départ.

---

## Chantiers & Interventions

Ce chapitre couvre le suivi des chantiers, le planning terrain des techniciens,
le magasin, la logistique et l'atelier.

### Création automatique du chantier à la signature du devis

**Ce que ça fait.** Dès qu'un devis passe au statut « accepté », le chantier
correspondant est créé automatiquement — adresse, client, puissance et matériel
(nomenclature) sont repris du devis. Si le devis est ré-accepté par erreur, aucun
chantier en double n'est créé.

**Où la trouver.** Rien à faire — c'est automatique. Le nouveau chantier apparaît
directement dans **CHANTIERS → Chantiers** (`/chantiers`).

**Comment l'utiliser.**
1. Faites accepter le devis normalement (côté Ventes).
2. Ouvrez **CHANTIERS → Chantiers** : le nouveau chantier est en tête de liste,
   statut « Signé ».
3. Vous pouvez aussi créer un chantier manuellement depuis la fiche du devis
   (bouton « Créer le chantier ») ou depuis la fiche du lead.

### Fiche chantier

**Ce que ça fait.** Liste et fiche détaillée de chaque chantier : informations
client, site, matériel, historique et notes, annulation / réactivation.

**Où la trouver.** Menu **CHANTIERS → Chantiers** (`/chantiers`).

**Comment l'utiliser.**
1. Cliquez sur un chantier dans la liste pour ouvrir sa fiche.
2. Utilisez les onglets pour voir l'historique, ajouter une note, ou annuler /
   réactiver le chantier (motif obligatoire à l'annulation).

### Parcours d'étapes du chantier

**Ce que ça fait.** Affiche le chantier comme un parcours guidé, étape par
étape : chaque étape indique si elle est bloquée et pourquoi, et propose l'action
suivante — jusqu'à la recette de mise en service et le pack de remise client.

**Où la trouver.** Fiche chantier, section **Parcours du chantier**.

**Comment l'utiliser.**
1. Ouvrez un chantier et faites défiler jusqu'à « Parcours du chantier ».
2. Chaque étape configurée par votre société s'affiche avec son état.
3. Si une étape est prête, l'action pour avancer est proposée directement.

### Checklist d'exécution du chantier

**Ce que ça fait.** Liste de tâches à cocher pendant l'exécution (pose, contrôle,
mise en service…), selon un gabarit choisi automatiquement en fonction du type
d'installation.

**Où la trouver.** Fiche chantier, section **Checklist**. Les gabarits eux-mêmes
se gèrent dans **Paramètres → Checklist**.

**Comment l'utiliser.** Ouvrez le chantier et cochez chaque étape au fur et à
mesure de sa réalisation.

### Interventions (planning terrain)

**Ce que ça fait.** Chaque sortie sur le terrain (pose, raccordement, mise en
service, contrôle, dépannage) est une « intervention », avec son propre statut
(à préparer → prête → en route → sur site → terminée → validée), indépendant du
statut du chantier.

**Où la trouver.** Menu **CHANTIERS → Interventions** (`/interventions`) — vue
Kanban par statut.

**Comment l'utiliser.**
1. Glissez-déposez une carte d'intervention d'une colonne à l'autre pour changer
   son statut.
2. Cliquez sur une intervention pour réassigner le technicien, voir l'historique
   ou ajouter une note.

### Capture terrain sur une intervention

**Ce que ça fait.** Depuis le terrain (mobile), le technicien peut : cocher et
signer les consignes de sécurité, prendre les photos requises (selon la
shot-list configurée), enregistrer le matériel consommé, pointer son arrivée et
son départ (GPS), signaler une réserve ou une anomalie, et faire signer le client
sur le compte-rendu.

**Où la trouver.** Ouvrez une intervention depuis **Interventions**, écran de
saisie terrain.

**Comment l'utiliser.**
1. Ouvrez l'intervention du jour.
2. Suivez les sections dans l'ordre : sécurité → photos → matériel consommé →
   compte-rendu → signature client.
3. Le compte-rendu final génère un PDF consultable via son lien.

### Planification (charge, conflits, camionnettes)

**Ce que ça fait.** Vue consolidée de la charge de travail par technicien
(capacité vs interventions affectées), des doubles réservations (même technicien
ou même camionnette sur deux interventions le même jour), de propositions de
rééquilibrage, et du planning des camionnettes.

**Où la trouver.** Menu **CHANTIERS → Planification** (`/planification`).

**Comment l'utiliser.**
1. Choisissez la période à consulter.
2. La page affiche la charge par équipe, les conflits détectés (surlignés) et
   les camionnettes réservées par jour.
3. Les suggestions de rééquilibrage sont proposées en lecture seule — à vous
   d'appliquer le changement d'affectation si vous l'acceptez.

### Demandes d'achat de chantier

**Ce que ça fait.** Depuis un chantier ou une intervention, demander l'achat de
matériel manquant, avec un circuit soumission → approbation → refus.

**Où la trouver.** Menu **CHANTIERS → Demandes d'achat**
(`/chantiers/demandes-achat`), ou directement depuis l'écran de capture terrain
d'une intervention.

**Comment l'utiliser.**
1. Créez une demande (produits + quantités).
2. Soumettez-la pour approbation.
3. Le responsable approuve ou refuse (avec motif) depuis la même liste.

### Documents après-vente (PV, bon de livraison, dossier de remise, attestation)

**Ce que ça fait.** Génère à la demande les PDF client de fin de chantier : PV de
réception, bon de livraison, dossier de remise, attestation (installation ou fin
de travaux). Ces PDF ne contiennent jamais de prix d'achat ni de marge.

**Où la trouver.** Fiche chantier, section **Documents après-vente**.

**Comment l'utiliser.**
1. Ouvrez le chantier concerné.
2. Cliquez sur le document voulu : le PDF s'ouvre dans un aperçu, prêt à
   télécharger ou imprimer.
3. Certains boutons peuvent être grisés tant que le chantier n'a pas atteint
   l'étape nécessaire (une info-bulle explique pourquoi).

L'ensemble des documents d'un chantier peut aussi être consulté en lecture seule
depuis son **archive documentaire** (bouton dédié sur la fiche chantier).

### Magasin (casiers, rangement, prélèvements, colisage)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Gestion physique de l'entrepôt : arborescence des casiers de
rangement, suggestion de rangement à la réception, listes de prélèvement pour
préparer une sortie, et colisage / contrôle avant expédition.

**Où la trouver.** Menu **MAGASIN** (`/magasin`).

**Comment l'utiliser.**
1. **Cockpit** : vue d'ensemble.
2. **Casiers** : consultez l'arborescence emplacement → zone → allée → casier.
3. **Rangement** : confirmez le rangement suggéré pour chaque réception.
4. **Prélèvements** : suivez les listes de prélèvement en cours.
5. **Colisage** : préparez et contrôlez les colis avant expédition.

### Atelier (kits, ordres d'assemblage / démontage)

**Ce que ça fait.** Suivi des kits de composants prêts à assembler, des ordres
d'assemblage et de démontage, avec contrôle qualité et disponibilité des
composants.

**Où la trouver.** Menu **CHANTIERS → Atelier** (`/atelier`).

**Comment l'utiliser.**
1. Consultez les kits actifs, lancez et suivez un ordre d'assemblage ou de
   démontage.
2. Le contrôle qualité et l'historique sont accessibles depuis chaque ordre.

### Logistique (livraisons, comptages, transferts)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Planification des livraisons du jour (avec preuve de
livraison signée), comptages cycliques de stock, et demandes de transfert entre
dépôts.

**Où la trouver.** Menu **LOGISTIQUE** (`/logistique`).

**Comment l'utiliser.**
1. **Cockpit** : vue du jour (livraisons, comptages en cours, transferts en
   attente).
2. **Livraisons** : expédiez / livrez, capturez la preuve de livraison
   (signature ou photo).
3. **Comptages cycliques** : démarrez un comptage, ajustez les lignes,
   terminez-le.
4. **Transferts** : créez une demande de transfert entre dépôts, puis
   approuvez, refusez ou exécutez.

### Configuration des chantiers (Paramètres)

**Ce que ça fait.** Les réglages qui pilotent les écrans terrain.

**Où la trouver.** Menu **Paramètres**, onglets dédiés :
- **Types d'intervention** — la liste des types proposés (pose, raccordement…) ;
- **Checklist** — les gabarits de checklist par type d'installation ;
- **Shot-list** — les photos obligatoires par phase ;
- **Sécurité terrain** — les consignes de sécurité à cocher et signer sur
  intervention.

**Comment l'utiliser.** Ajoutez, modifiez ou réordonnez les entrées depuis chaque
onglet ; les changements s'appliquent immédiatement aux écrans terrain.

---

## SAV & Parc installé

Le module Après-vente suit tout le matériel posé chez vos clients, les demandes
de dépannage et d'entretien, et la production réelle des installations.

### Équipements (parc installé)

**Ce que ça fait.** Le registre de tout le matériel posé chez vos clients
(onduleurs, pompes, batteries…) : numéro de série, date de pose, garantie
calculée automatiquement, statut (en service / remplacé / hors service).

**Où la trouver.** Menu **APRÈS-VENTE → Équipements** (`/equipements`).

**Comment l'utiliser.**
1. Ouvrez la liste des équipements depuis le menu.
2. Cliquez sur un équipement pour voir sa fiche : garantie, historique de
   pannes, disponibilité.
3. Bouton **Mettre au rebut** sur un équipement en fin de vie (motif
   obligatoire) ; bouton **Réactiver** pour annuler un rebut fait par erreur.
4. Bouton **Registre des garanties** en haut de la liste : l'échéancier de
   toutes les fins de garantie du parc, pratique pour anticiper les expirations.

### Fiche fiabilité d'un équipement

**Ce que ça fait.** Pour un équipement précis : temps moyen entre pannes (MTBF),
temps moyen de réparation (MTTR), historique d'immobilisation, disponibilité
en %, et relevés de compteur (heures ou kWh).

**Où la trouver.** Depuis **Équipements**, ouvrez la fiche d'un équipement — le
panneau « Fiabilité » apparaît directement sur la fiche.

**Comment l'utiliser.**
1. Consultez les indicateurs affichés (MTBF/MTTR, disponibilité sur 30 jours).
2. Bouton **Ouvrir une immobilisation** quand l'équipement tombe en panne (sans
   ticket forcément) ; bouton **Clôturer** quand il repart.
3. Section « Relevés compteur » : saisissez un relevé (heures ou kWh) — il sert à
   déclencher un entretien préventif basé sur l'usage réel, pas seulement sur le
   calendrier.

### Tickets SAV

**Ce que ça fait.** Le suivi de chaque demande d'après-vente : panne, maintenance
préventive, réclamation. Cycle de vie complet (Nouveau → Planifié → En cours →
Résolu → Clôturé), avec annulation possible à tout moment.

**Où la trouver.** Menu **APRÈS-VENTE → Tickets SAV** (`/sav`).

**Comment l'utiliser.**
1. Créez un ticket depuis la liste (client, équipement si connu, type correctif
   ou préventif, priorité).
2. Sur la fiche du ticket, utilisez les boutons de transition : **Planifier**,
   **Démarrer**, **Résoudre**, **Clôturer**, **Réouvrir**, **Replanifier**.
3. Pour traiter plusieurs tickets d'un coup (statut, technicien, priorité,
   annulation), sélectionnez-les dans la liste et utilisez les **actions
   groupées**.
4. Ajoutez des notes dans l'historique du ticket ; des **réponses types**
   (macros) permettent d'insérer un message pré-rédigé en un clic.
5. Onglet **Pièces** : enregistrez les pièces consommées ou retirées (retour en
   stock, retour fournisseur, ou mise au rebut).
6. Boutons **Créer un devis** (réparation hors garantie) et **Générer facture** :
   le système calcule automatiquement si l'intervention est couverte par la
   garantie, par un contrat, ou facturable.
7. Actions avancées (panneau « Plus ») : suivre / ne plus suivre le ticket,
   fusionner un doublon, voir les tickets résolus similaires, lancer un triage
   assisté par IA (une proposition, jamais automatique), convertir en
   opportunité commerciale, mettre en pause « en attente client » (l'horloge
   s'arrête).
8. Bouton **Rapport d'intervention (PDF)** pour télécharger un compte rendu sans
   prix d'achat.
9. Checklist de visite de maintenance : cochez les étapes directement sur le
   ticket si un modèle de checklist est disponible.

### Action requise (file de tickets à traiter)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Regroupe tous les tickets ouverts par « action attendue » (à
planifier, à démarrer, à résoudre…) pour prioriser le travail de l'équipe.

**Où la trouver.** Menu **APRÈS-VENTE → Action requise** (`/sav/action-requise`).

**Comment l'utiliser.** Ouvrez la page : les tickets sont déjà groupés par action
attendue. Cliquez sur un ticket pour l'ouvrir directement.

### Contrats de maintenance

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Les abonnements de visites préventives par client (mensuel,
trimestriel, semestriel ou annuel), avec génération en un clic des tickets de
visite quand ils sont dus (bouton « Générer les visites dues »).

**Où la trouver.** Menu **APRÈS-VENTE → Contrats maintenance** (`/sav/contrats`).

**Comment l'utiliser.**
1. Créez un contrat : client, périodicité, date de début, prix, chantier et
   durée (optionnels).
2. Vue **À venir (dus)** : ne montre que les contrats dont la visite est due
   maintenant.
3. Vue **À renouveler** : les contrats ayant atteint leur date de renouvellement.
4. Bouton **Générer les visites dues** : crée en un clic tous les tickets
   préventifs pour les contrats arrivés à échéance.
5. Bouton **Rapport PDF** sur une ligne : télécharge le compte rendu de la
   visite (vous pouvez choisir la date affichée).
6. Éditez (crayon) ou désactivez un contrat directement dans le tableau.

### Garanties fournisseur (RMA)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Le suivi des réclamations envoyées à un fournisseur (Huawei,
VEICHI, fabricant de panneaux…) pour un équipement sous garantie : statut,
référence RMA, résolution (remplacement / avoir / réparation / refus).

**Où la trouver.** Menu **APRÈS-VENTE → Garanties fournisseur (RMA)**
(`/sav/warranty-claims`).

**Comment l'utiliser.** Créez une réclamation en liant l'équipement concerné ;
suivez son statut jusqu'à résolution ; filtrez par statut.

### Base de connaissances SAV

**Ce que ça fait.** Une bibliothèque d'articles internes (codes d'erreur, pannes
récurrentes, procédures de résolution) pour capitaliser le savoir de l'équipe
technique.

**Où la trouver.** Menu **APRÈS-VENTE → Base de connaissances SAV** (`/sav/kb`).

**Comment l'utiliser.** Recherchez par mot-clé ; créez ou éditez un article
(titre, contenu, tags, produit et catégorie associés).

### Alarmes onduleur

**Ce que ça fait.** Suivi des défauts remontés par les onduleurs (codes d'erreur
avec gravité), distinct des tickets SAV classiques.

**Où la trouver.** Menu **APRÈS-VENTE → Alarmes onduleur** (`/sav/alarmes`).

**Comment l'utiliser.**
1. Filtrez par statut (active / acquittée / escaladée / résolue).
2. Bouton **Acquitter** pour signaler que vous avez vu l'alarme.
3. Bouton **Escalader** pour ouvrir (ou relier) un ticket SAV qui traitera le
   défaut.

### Rapport SLA SAV

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Vue agrégée de la conformité aux délais de service
(indicateurs de performance de l'équipe SAV).

**Où la trouver.** Menu **APRÈS-VENTE → Rapport SLA SAV** (`/sav/sla-rapport`).

**Comment l'utiliser.** Ouvrez la page ; les indicateurs se chargent
automatiquement.

### Paramètres SAV

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Gestion des listes de référence utilisées partout dans le
module SAV : catégories de ticket, causes et remèdes de panne, réponses types
(macros), équipes de maintenance, catégories d'équipement.

**Où la trouver.** Menu **APRÈS-VENTE → Paramètres SAV** (`/sav/parametres`).

**Comment l'utiliser.** Choisissez l'onglet correspondant, puis ajoutez, éditez
ou archivez les entrées. Ces listes apparaissent ensuite dans les menus
déroulants des tickets et équipements.

### Page publique de signalement et suivi client

**Ce que ça fait.** Deux pages accessibles sans connexion, à partager avec vos
clients :
- une page de **suivi de ticket** (lien unique par ticket) où le client voit
  l'avancement et peut noter sa satisfaction une fois le ticket résolu ;
- une page **« Signaler un problème »** accessible via un QR-code posé sur un
  équipement (l'impression de ces étiquettes QR d'équipement depuis l'interface
  n'est pas encore disponible — voyez avec l'équipe technique pour les obtenir).

**Où la trouver.** Liens envoyés au client (générés automatiquement pour le
suivi de ticket).

**Comment l'utiliser.** Partagez le lien avec le client ; il consulte le statut
de sa demande et, une fois le ticket résolu, peut laisser une note de
satisfaction (1 à 5) et un commentaire libre.

### Production — Supervision (Monitoring)

**Ce que ça fait.** Le suivi de la production réelle des installations solaires
posées chez vos clients : relevés d'énergie, détection de sous-performance, vue
du parc, analytique O&M, garanties de production, CO₂ évité, nettoyages,
rapports périodiques et portail client.

**Où la trouver.** Menu principal → **Production** (`/production`). Un bandeau
d'onglets en haut de l'écran (« Relevés », « Vue parc », « Analytique O&M »,
« Garanties », « CO₂ », « Nettoyages », « Rapports O&M », « Portail client »)
permet de naviguer entre les écrans de la suite.

**Comment l'utiliser.**
1. **Relevés** : sélectionnez une installation et saisissez un relevé de
   production manuel (date, kWh, nombre de jours couverts).
2. **Vue parc** : tableau de bord multi-systèmes — production totale, kWc
   installés, PR moyen, alertes de sous-performance.
3. **Analytique O&M** : pour un système précis, ratio de performance (PR),
   disponibilité, encrassement, dégradation dans le temps.
4. **Garanties** : configurez la garantie de production d'un système (kWh
   garanti par an, tolérance, compensation) et consultez l'écart réel/garanti
   année par année.
5. **CO₂** : le CO₂ total évité sur l'ensemble du parc.
6. **Nettoyages** : enregistrez la date de nettoyage des panneaux d'un système ;
   l'écran estime la perte due à l'encrassement depuis le dernier nettoyage.
7. **Rapports O&M** : générez un rapport périodique (mensuel ou trimestriel) en
   PDF, ou envoyez-le par e-mail au client directement depuis l'écran.
8. **Portail client** : la synthèse environnementale cumulée des systèmes d'un
   client, à lui montrer ou partager.

Remarque : tant que les connecteurs automatiques des fabricants d'onduleurs ne
sont pas branchés par l'équipe technique, la saisie manuelle des relevés
fonctionne normalement.

### Réglage de sous-performance

**Ce que ça fait.** Définit à partir de quel pourcentage sous la production
attendue un système est considéré « sous-performant », et si un ticket SAV doit
être créé automatiquement dans ce cas.

**Où la trouver.** Menu **Paramètres**, section Monitoring.

**Comment l'utiliser.** Réglez le seuil (% sous l'attendu) et activez ou non la
case « créer un ticket automatiquement ». Par défaut, rien n'est créé tant que
cette case n'est pas activée.

---

## Point de vente (Caisse)

La caisse permet la vente comptoir rapide d'accessoires, avec facture légale et
mise à jour du stock automatiques.

### Vente comptoir rapide

**Ce que ça fait.** Vend un accessoire (câble, connecteur, petit matériel…)
directement au comptoir, sans passer par un devis : on cherche le produit, on
l'ajoute au panier, on encaisse — le système crée automatiquement la facture
légale, enregistre le règlement et décrémente le stock.

**Où la trouver.** Menu **CAISSE → Caisse** (`/pos`). Accessible à tout
utilisateur autorisé à vendre.

**Comment l'utiliser.**
1. Dans le champ de recherche, tapez le nom ou la référence du produit puis
   cliquez dessus (ou appuyez sur Entrée) pour l'ajouter au panier.
2. Ajustez la quantité avec les boutons **+ / −** si besoin.
3. Sélectionnez un client existant, ou cliquez sur **+ Nouveau client** pour en
   créer un rapidement (le nom suffit). **Important** : une facture légale exige
   toujours un client — choisissez-en toujours un (même un client générique)
   avant d'encaisser, sinon l'encaissement final échouera.
4. Cliquez sur **Encaisser**. Choisissez un ou plusieurs modes de paiement
   (espèces, carte…) et saisissez les montants. Le système affiche
   automatiquement la monnaie à rendre ou le solde restant.
5. Cliquez sur **Confirmer l'encaissement**. La vente est validée : le stock est
   mis à jour et la facture est créée.
6. Une fois la vente validée, vous pouvez : imprimer le **ticket PDF**, l'envoyer
   vers l'**imprimante de caisse**, ou générer un **lien partageable** du ticket
   (à envoyer au client par WhatsApp par exemple).

### Sessions de caisse (ouverture / clôture)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Encadre la journée de caisse : on déclare le fond de caisse
au départ (ouverture), puis en fin de journée on compte les espèces et le
terminal carte pour calculer l'écart. Un rapport « Z » récapitule le total des
ventes de la session par mode de paiement.

**Où la trouver.** Menu **CAISSE → Sessions de caisse** (`/pos/session`).

**Comment l'utiliser.**
1. Cliquez sur **Ouvrir une caisse**, choisissez la caisse comptable concernée,
   indiquez le fond de caisse de départ, puis **Ouvrir**.
2. Les ventes comptoir réglées en espèces s'ajoutent automatiquement à cette
   session tant qu'elle reste ouverte.
3. En fin de journée, cliquez sur **Clôturer**, saisissez le montant réel
   d'espèces compté (et le montant carte compté le cas échéant), ajoutez un
   commentaire si un écart doit être justifié, puis **Clôturer**.
4. À tout moment, cliquez sur **Rapport Z** pour voir le nombre de ventes et le
   total par mode de paiement de la session.

### Tableau de bord des ventes comptoir

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Vue d'ensemble des ventes comptoir : nombre de ventes,
chiffre d'affaires TTC, panier moyen, taux de retour, avec répartition par jour,
par caissier, par mode de paiement, par catégorie et par produit.

**Où la trouver.** Menu **CAISSE → Tableau de bord** (`/pos/dashboard`).

**Comment l'utiliser.**
1. Choisissez une période avec les champs **Du** / **Au**, puis **Filtrer**
   (laissez vide pour voir toutes les ventes).
2. Consultez les indicateurs en haut de page et les répartitions détaillées en
   dessous.
3. Cliquez sur **Exporter (xlsx)** pour télécharger un fichier Excel des ventes
   de la période (sans aucune donnée de marge — toujours sûr à partager).

### Configuration de l'imprimante de caisse

**Ce que ça fait.** Permet de brancher une imprimante à tickets réseau pour
imprimer directement les tickets de caisse, plutôt que de toujours passer par un
PDF.

**Où la trouver.** Menu **CAISSE → Matériel de caisse** (`/pos/config-materiel`).

**Comment l'utiliser.**
1. Saisissez l'adresse IP de l'imprimante sur le réseau local et le port
   (9100 par défaut).
2. Activez le bouton **Imprimante active**, puis **Enregistrer**.
3. Tant que l'imprimante n'est pas configurée et activée, le ticket reste
   disponible en PDF comme avant.

---

## RH (Ressources humaines)

Le module RH couvre le suivi des dossiers employés, le recrutement, le temps de
travail et l'espace personnel de chaque collaborateur.

### Cockpit RH

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Tableau de bord d'ensemble des ressources humaines :
échéances à venir (habilitations, certifications, visites médicales, EPI, fins
de CDD) et indicateurs HSE (accidents, presqu'accidents).

**Où la trouver.** Menu **RH → Cockpit RH** (`/rh`).

**Comment l'utiliser.** Ouvrez le menu RH puis « Cockpit RH » : la page se
charge automatiquement avec les échéances proches et les indicateurs de sécurité
du moment.

### Annuaire et fiche employé (consultation)

**Ce que ça fait.** Liste de tous les dossiers employés de l'entreprise, avec
pour chacun une fiche détaillée (documents, habilitations, formations suivies,
historique du dossier).

**Où la trouver.** Menu **RH → Employés** (`/rh/employes`), puis cliquez sur une
ligne pour ouvrir la fiche.

**Comment l'utiliser.**
1. Ouvrez « Employés » : le tableau liste matricule, nom, poste, contrat, date
   d'embauche et statut.
2. Cliquez sur un employé pour voir sa fiche complète.
3. Depuis la fiche, vous pouvez télécharger le certificat de travail, confirmer
   la fin de période d'essai, ou marquer l'employé comme déclaré (CNSS).

À savoir : cette liste est en lecture seule. La création d'un nouveau dossier
employé passe aujourd'hui par le Recrutement (ci-dessous).

### Recrutement — embaucher un candidat

**Ce que ça fait.** Transforme une candidature retenue en un vrai dossier
employé — c'est aujourd'hui la façon de créer un nouvel employé dans
l'application.

**Où la trouver.** Menu **RH → EPI & recrutement** (`/rh/recrutement`).

**Comment l'utiliser.**
1. Ouvrez « EPI & recrutement » et repérez la candidature à embaucher.
2. Cliquez sur l'action **Embaucher** : le dossier employé est créé et lié
   automatiquement à la candidature (sans risque de doublon même en cliquant
   deux fois).

### Temps & présence

**Ce que ça fait.** Suivi des pointages (arrivée/départ), heures
supplémentaires, planning d'équipe, présence chantier, et gestion des terminaux
de pointage (kiosques).

**Où la trouver.** Menu **RH → Temps & présence** (`/rh/temps`).

**Comment l'utiliser.**
1. Ouvrez « Temps & présence » pour voir les pointages, les heures
   supplémentaires et le planning.
2. Un pointage peut être corrigé manuellement (motif obligatoire).
3. Un import CSV d'une pointeuse externe est possible.
4. Pour émettre ou révoquer un terminal kiosque, utilisez la section « Devices
   kiosque » du même écran.

**Le kiosque de pointage (borne physique)** est accessible séparément à
l'adresse `/kiosque`, sans connexion : l'employé saisit son code PIN sur la
borne.

### Mon portail RH

**Ce que ça fait.** L'espace personnel de **chaque** employé, quel que soit son
rôle : consultation de ses informations, solde et historique de congés, notes de
frais, EPI attribués, habilitations, bulletins de paie, et participation aux
campagnes de sondage interne anonyme.

**Où la trouver.** Menu **RH → Mon portail** (`/rh/portail`).

**Comment l'utiliser.**
1. Ouvrez « Mon portail ».
2. Utilisez les onglets en haut (Congés / Frais / etc.) pour naviguer entre vos
   informations personnelles.
3. Si une campagne de sondage anonyme est active, une invitation apparaît en
   haut de la page.

### Demander une attestation de travail

**Ce que ça fait.** Permet à un employé de demander lui-même une attestation de
travail, puis de la télécharger une fois traitée.

**Où la trouver.** Menu **RH → Mon portail** (`/rh/portail`), onglet des
demandes.

**Comment l'utiliser.**
1. Depuis « Mon portail », lancez une demande d'attestation en précisant le
   motif si besoin.
2. Suivez le statut de la demande sur la même page.
3. Une fois traitée, téléchargez le document depuis le lien fourni.

### Causeries sécurité (fiche imprimable bilingue FR/AR)

**Ce que ça fait.** Génère un PDF imprimable bilingue français/arabe d'une
causerie sécurité, avec feuille d'émargement pour les participants.

**Où la trouver.** Menu **RH → HSE**, onglet **Causeries** (`/rh/hse`).

**Comment l'utiliser.**
1. Sur une causerie de sécurité, cliquez sur le bouton de téléchargement PDF.
2. Choisissez la langue (français ou arabe) ; le PDF se télécharge.

---

## Paie

Le module Paie traite la paie mensuelle marocaine de bout en bout, des bulletins
aux déclarations légales.

### Run de paie (assistant de génération)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** L'assistant complet pour traiter la paie mensuelle : créer
une période, importer les éléments RH (absences, heures supplémentaires…),
générer les bulletins, les valider, gérer une gratification hors cycle, et
clôturer la période.

**Où la trouver.** Menu **PAIE → Run de paie** (`/paie`).

**Comment l'utiliser.**
1. Créez une nouvelle période (année + mois).
2. Importez les éléments RH de la période (congés, heures sup, absences).
3. Vérifiez les avertissements affichés avant de générer.
4. Générez les bulletins pour les profils de paie actifs.
5. Validez chaque bulletin (ou en lot).
6. Clôturez la période une fois tous les bulletins validés.

### Bulletins de paie

**Ce que ça fait.** Liste et détail de tous les bulletins de paie, avec
génération de PDF (bulletin, attestation) et possibilité d'annuler un bulletin
erroné.

**Où la trouver.** Menu **PAIE → Bulletins** (`/paie/bulletins`), puis cliquez
sur une ligne pour le détail.

**Comment l'utiliser.**
1. Filtrez par période dans la liste des bulletins.
2. Cliquez sur un bulletin pour voir le détail complet.
3. Téléchargez le PDF du bulletin ou l'attestation depuis le détail.
4. Un bulletin peut être annulé si une erreur est détectée (avant clôture de la
   période).

### Mes bulletins (coffre-fort personnel)

**Ce que ça fait.** Chaque employé peut consulter et télécharger ses propres
bulletins de paie en toute confidentialité.

**Où la trouver.** Menu **PAIE → Mes bulletins** (`/paie/mes-bulletins`).
Visible pour tous les rôles.

**Comment l'utiliser.**
1. Ouvrez « Mes bulletins » : la liste affiche tous les bulletins déjà émis pour
   l'employé connecté.
2. Cliquez sur un bulletin pour télécharger son PDF.

### Déclarations & virements de paie

**Ce que ça fait.** Le centre des obligations légales de la paie marocaine :
déclaration CNSS, fichier DAMANCOM, état IR, ordres de virement bancaire (SIMT),
déclaration CIMR, registre des congés, coût employeur, rapprochement avec la
comptabilité, et saisies-arrêts sur salaire.

**Où la trouver.** Menu **PAIE → Déclarations** (`/paie/declarations`).

**Comment l'utiliser.**
1. Sélectionnez la période concernée.
2. Selon le besoin, générez : la déclaration CNSS, le fichier DAMANCOM, l'état
   IR (mensuel ou annuel), la déclaration CIMR.
3. Pour payer les salariés : générez l'ordre de virement, puis émettez-le ; le
   fichier bancaire (SIMT) peut ensuite être téléchargé.
4. En cas de virement rejeté (RIB invalide), la ligne concernée peut être
   rejetée puis réémise avec un RIB corrigé.
5. Les onglets complémentaires donnent accès à l'état des charges sociales, au
   rapprochement grand-livre, au coût employeur global et au registre des
   congés.

### Simulateur net/brut

**Ce que ça fait.** Calcule rapidement, pour une période donnée, le salaire brut
correspondant à un salaire net souhaité (ou l'inverse), sans créer de bulletin
réel.

**Où la trouver.** Menu **PAIE → Paramètres** (`/paie/parametres`), onglet
**Simulateur net/brut**.

**Comment l'utiliser.**
1. Ouvrez l'onglet « Simulateur net/brut ».
2. Choisissez la période de référence.
3. Saisissez le montant à simuler ; le résultat s'affiche immédiatement.

---

## Flotte (véhicules & engins)

Le module Flotte gère le parc de véhicules de l'entreprise : fiches véhicules,
affectations aux conducteurs, entretien et carburant.

### Véhicules — créer et suivre un véhicule

**Ce que ça fait.** Gère la fiche complète de chaque véhicule immatriculé du
parc (immatriculation, marque, modèle, énergie, kilométrage, statut) et suit son
cycle de vie (commande → actif → maintenance → réforme/vendu), avec ses coûts
d'exploitation (TCO), son amortissement et sa TSAV/vignette.

**Où la trouver.** Menu **FLOTTE → Véhicules & engins** (`/flotte/vehicules`).

**Comment l'utiliser.**
1. Cliquez sur **Nouveau véhicule** en haut à droite.
2. Renseignez l'immatriculation, la marque, le modèle, l'énergie et le
   kilométrage (vous pouvez aussi choisir un modèle du catalogue pour
   pré-remplir certaines informations).
3. Enregistrez : le véhicule apparaît dans la liste avec le statut « Actif ».
4. Cliquez sur une ligne du tableau pour ouvrir la fiche détaillée (coût total
   de possession, amortissement, historique des changements de statut).
5. Utilisez les filtres en haut de la liste (statut, énergie) pour retrouver
   rapidement un véhicule.

### Conducteurs & affectations — attribuer un véhicule à un chauffeur

**Ce que ça fait.** Relie un chauffeur (déjà enregistré) à un véhicule pour une
période donnée, avec un contrôle automatique de la validité du permis :
l'affectation est bloquée si le permis est expiré ou de catégorie inadaptée au
véhicule.

**Où la trouver.** Menu **FLOTTE → Conducteurs** (`/flotte/conducteurs`), onglet
**Affectations**.

**Comment l'utiliser.**
1. Cliquez sur **Nouvelle affectation**.
2. Choisissez le conducteur, le véhicule et la date de début (date de fin
   facultative).
3. Si le permis du conducteur n'est pas valide pour ce véhicule, un message
   clair s'affiche et l'enregistrement est refusé.
4. Validez : l'affectation apparaît dans la liste avec son statut (Active /
   Terminée).

Note : seuls les conducteurs déjà existants peuvent être affectés — la création
d'un nouveau conducteur depuis cet écran n'est pas encore disponible (voyez avec
l'équipe technique en attendant).

### Réaffectation en masse

**Ce que ça fait.** Réaffecte plusieurs couples véhicule/conducteur en une seule
opération (utile lors d'une réorganisation de la flotte).

**Où la trouver.** Même écran, onglet **Affectations**, bouton **Réaffectation
en masse**.

**Comment l'utiliser.**
1. Cliquez sur **Réaffectation en masse** et saisissez la date de début commune.
2. Pour chaque ligne, choisissez le véhicule et le nouveau conducteur (vous
   pouvez ajouter plusieurs lignes).
3. Cliquez sur **Réaffecter** : toutes les lignes sont traitées en une fois.

### Entretien — garages

**Ce que ça fait.** Enregistre la liste des garages/ateliers (internes ou
externes) utilisés pour les réparations, avec leurs coordonnées et identifiants
fiscaux (ICE/IF).

**Où la trouver.** Menu **FLOTTE → Entretien** (`/flotte/entretien`), onglet
**Garages**.

**Comment l'utiliser.**
1. Cliquez sur **Nouveau garage**.
2. Renseignez le nom, l'adresse, le téléphone et, si disponibles, l'ICE
   (15 chiffres) et l'identifiant fiscal.
3. Enregistrez : le garage pourra être choisi lors de l'ouverture d'un ordre de
   réparation.

### Signaler une anomalie et la transformer en réparation

**Ce que ça fait.** Permet à un conducteur ou un responsable de signaler un
problème constaté sur un véhicule ou un engin, puis de transformer ce
signalement en ordre de réparation formel à envoyer au garage.

**Où la trouver.** Même écran, onglet **Signalements**.

**Comment l'utiliser.**
1. Cliquez sur **Signaler un problème**.
2. Choisissez le véhicule/engin concerné, décrivez le problème et indiquez sa
   gravité, puis enregistrez.
3. Quand le problème est confirmé, cliquez sur **Convertir en ordre de
   réparation** : un ordre de réparation est créé et lié au signalement.
4. Une fois le devis du garage reçu, retrouvez l'ordre dans l'onglet **Ordres de
   réparation** et cliquez sur **Approuver le devis** pour valider la dépense.

### Carburant — enregistrer un plein (avec lecture automatique du reçu)

**Ce que ça fait.** Enregistre chaque plein de carburant (véhicule, date,
kilométrage, quantité, coût, station). Une photo du reçu de station peut être
téléversée pour pré-remplir automatiquement le formulaire.

**Où la trouver.** Menu **FLOTTE → Carburant & télématique**
(`/flotte/carburant`), onglet **Carburant**.

**Comment l'utiliser.**
1. Cliquez sur **Nouveau plein**.
2. (Optionnel) Téléversez une photo du reçu de station : les champs (date,
   quantité, montant, station) se remplissent automatiquement si la lecture
   réussit — vérifiez toujours les valeurs proposées avant d'enregistrer.
3. Choisissez le véhicule, vérifiez le kilométrage, la quantité et le coût.
4. Enregistrez : le plein sert ensuite au calcul de la consommation moyenne du
   véhicule.

---

## QHSE & ESG

Le module QHSE suit la qualité, la sécurité et l'environnement (non-conformités,
actions correctives, incidents, observations terrain), et le volet ESG/RSE
consolide vos indicateurs de responsabilité sociétale.

### Non-conformités (NCR)

**Ce que ça fait.** Enregistre un écart qualité, sécurité ou environnement :
gravité, origine, chantier concerné. Permet de suivre son traitement jusqu'à la
clôture, avec un historique complet (qui a fait quoi et quand).

**Où la trouver.** Menu **QHSE → Non-conformités**, onglet **Non-conformités**
(`/qhse/non-conformites`).

**Comment l'utiliser.**
1. Cliquez sur **Nouvelle NCR**.
2. Remplissez le titre, la description, la gravité (mineure / majeure /
   critique) et, si besoin, le chantier concerné.
3. Vous pouvez utiliser le bouton **Suggérer la gravité (IA)** après avoir écrit
   la description, pour obtenir une proposition — à valider vous-même.
4. Une NCR peut aussi être créée directement depuis une réserve de fin de
   chantier (champ « Depuis réserve »).
5. Ouvrez une NCR pour voir son détail : l'historique, poser une **disposition**
   (rebut, retouche, retour fournisseur, accepté en l'état, tri/recontrôle), et
   **clôturer** une fois le traitement terminé. Le système refuse la clôture
   tant que les actions correctives liées ne sont pas vérifiées efficaces.

### Actions correctives / préventives (CAPA)

**Ce que ça fait.** Suit les actions lancées pour corriger une NCR ou un
incident : responsable, échéance, vérification d'efficacité.

**Où la trouver.** Menu **QHSE → Non-conformités**, onglet **CAPA**.

**Comment l'utiliser.**
1. Le registre liste toutes les CAPA en cours. Le bouton **En retard** n'affiche
   que celles dont l'échéance est dépassée.
2. **Relancer les retards** envoie une notification groupée pour toutes les CAPA
   en retard.
3. Sur une CAPA réalisée, ouvrez **Vérifier l'efficacité**, indiquez si l'action
   a été efficace et ajoutez un commentaire. Une CAPA jugée inefficace repasse
   automatiquement « en cours ».

Note : une CAPA se crée toujours depuis son origine (une NCR, une analyse
d'incident, une observation terrain convertie…) — il n'y a pas de bouton
« nouvelle CAPA » séparé.

### Contrôle qualité à la réception fournisseur

**Ce que ça fait.** Quand une réception fournisseur est confirmée dans le module
Stock, le système ouvre automatiquement les contrôles qualité prévus. Un
contrôle statué « refusé » lève automatiquement une non-conformité.

**Où la trouver.** Menu **QHSE → Inspections & audits**, onglet **Contrôle
réception** (`/qhse/inspections`).

**Comment l'utiliser.**
1. Les contrôles en attente apparaissent automatiquement après une réception
   fournisseur.
2. Cliquez sur **Statuer**, choisissez le verdict (Accepté / Refusé /
   Quarantaine) et ajoutez des notes si besoin.
3. Un verdict « Refusé » crée automatiquement une non-conformité liée.

### Accidents du travail — checklist légale CNSS

**Ce que ça fait.** Pour un accident du travail déclaré à la CNSS, affiche la
checklist des étapes légales obligatoires (loi 18-12) avec leurs échéances, et
permet de cocher chaque étape faite.

**Où la trouver.** Menu **QHSE → Risques, permis & incidents**, onglet
**Incidents**, colonne « Déclarations CNSS » (`/qhse/risques`).

**Comment l'utiliser.**
1. Sur une déclaration CNSS, cliquez sur **Checklist légale AT/MP**.
2. Pour chaque étape « à faire », cliquez sur **Fait** une fois réalisée.

### Observations sécurité comportementales (BBS)

**Ce que ça fait.** Convertit une observation de terrain (bonne pratique ou
comportement à risque) en action corrective (CAPA) ou en non-conformité (NCR) en
un clic.

**Où la trouver.** Menu **QHSE → Risques, permis & incidents**, onglet
**Observations BBS**.

**Comment l'utiliser.** Sur une observation listée, utilisez **Convertir en
CAPA** ou **Convertir en NCR** selon le besoin.

### Signalement QR public (chantier)

**Ce que ça fait.** Génère un lien/QR-code à imprimer et afficher sur un
chantier, permettant à quiconque (ouvrier, sous-traitant, visiteur) de signaler
un danger ou un incident sans compte utilisateur.

**Où la trouver.** Menu **QHSE → Risques, permis & incidents**, onglet
**Signalement QR**.

**Comment l'utiliser.**
1. Cliquez sur **Nouveau lien**, donnez-lui un libellé et, si besoin, le
   chantier concerné.
2. Sur le lien créé, cliquez sur **Générer QR** pour télécharger l'image du
   QR-code à imprimer.
3. Les signalements reçus via ce QR-code apparaissent dans le tableau
   « Signalements reçus », en lecture pour l'équipe interne.

### Cockpit QHSE (tableau de bord)

**Ce que ça fait.** Vue d'ensemble : taux de fréquence et de gravité des
accidents (TF/TG), score de préparation ISO 9001:2015 avec détail par critère,
Pareto des défauts qualité les plus fréquents, et un centre d'échéances
(inspections, permis, déclarations CNSS à venir).

**Où la trouver.** Menu **QHSE → Cockpit QHSE** (`/qhse`).

**Comment l'utiliser.** Écran de lecture : consultez les indicateurs, et cliquez
sur une échéance du panneau de droite pour être redirigé vers l'écran
correspondant.

### Cockpit ESG / RSE

**Ce que ça fait.** Vue consolidée de la couverture du référentiel GRI-lite par
pilier (Environnement / Social / Gouvernance), un badge de maturité ESG
(auto-évaluation interne, pas une certification), et la liste des périodes de
reporting avec téléchargement du rapport (PDF ou Excel).

**Où la trouver.** Menu **ESG / RSE → Cockpit ESG** (`/esg`).

**Comment l'utiliser.**
1. Consultez la couverture par pilier et le badge de maturité.
2. Sur une période « brouillon », cliquez sur **Figer la période** pour geler
   définitivement les chiffres (action irréversible, confirmation demandée).
3. Cliquez sur **PDF** ou **xlsx** pour télécharger le rapport de la période.

### Matrice de matérialité ESG (parties prenantes RSE)

**Ce que ça fait.** Registre des parties prenantes RSE (clients, fournisseurs,
collaborateurs, collectivité, actionnaires) avec leur niveau d'influence et
d'intérêt, affiché sous forme de matrice visuelle.

**Où la trouver.** Menu **ESG / RSE → Matrice de matérialité**
(`/esg/materialite`).

**Comment l'utiliser.**
1. Dans le formulaire « Ajouter une partie prenante », renseignez le nom, la
   catégorie, les enjeux prioritaires et deux scores de 1 à 5 (influence et
   intérêt).
2. Cliquez sur **Ajouter** — la partie prenante apparaît immédiatement sur la
   matrice et dans le registre en bas de page.
3. Utilisez l'icône de suppression pour retirer une partie prenante du registre.

---

## Contrats & Litiges

Le module Contrats gère le cycle de vie de vos contrats (approbation, signature,
avenants, résiliation, renouvellement) et la location de matériel. Le module
Litiges enregistre les réclamations clients.

### Cycle de vie d'un contrat

**Ce que ça fait.** Fait avancer un contrat dans son cycle de vie (Brouillon →
En approbation → Signé → Actif → Suspendu → Résilié/Expiré), selon les
transitions autorisées à chaque instant.

**Où la trouver.** Menu **CONTRATS → Contrats**, puis cliquez sur un contrat
pour ouvrir sa fiche.

**Comment l'utiliser.**
1. Ouvrez la fiche d'un contrat.
2. Dans la barre d'actions en haut, les boutons affichés correspondent aux
   seules transitions possibles depuis le statut actuel.
3. Cliquez sur le statut cible souhaité — le contrat bascule immédiatement.

### Signature électronique d'un contrat

**Ce que ça fait.** Enregistre la signature électronique (nom dactylographié,
valable selon la loi marocaine 53-05) d'une partie du contrat (client,
prestataire, témoin). Quand le client ET le prestataire ont signé, le contrat
passe automatiquement à « Signé », puis à « Actif » si la date de début est
atteinte.

**Où la trouver.** Fiche d'un contrat → onglet **Signatures**.

**Comment l'utiliser.**
1. Ouvrez l'onglet Signatures et cliquez sur **Signer**.
2. Saisissez le nom complet du signataire et choisissez son rôle (Client,
   Prestataire, Témoin).
3. Validez — la signature apparaît dans le tableau avec la date et l'heure.
4. Une fois toutes les parties requises signées, le statut du contrat change
   automatiquement.

### Approbation interne d'un contrat

**Ce que ça fait.** Fait suivre un contrat par un circuit d'approbation interne
(un ou plusieurs responsables doivent valider) avant signature.

**Où la trouver.** Fiche d'un contrat → onglet **Approbation**.

**Comment l'utiliser.**
1. Cliquez sur **Lancer l'approbation** — le système crée les étapes requises
   selon les règles configurées pour votre société.
2. Chaque étape « En attente » peut être **Approuvée** ou **Rejetée** par un
   responsable.

Note : les règles qui déterminent quand une approbation est requise (seuils de
montant, type de contrat) doivent être configurées au préalable par votre équipe
technique. Sans règle configurée, le message « Aucune règle ne couvre ce
contrat » s'affiche.

### Historique et notes d'un contrat

**Ce que ça fait.** Trace automatiquement chaque changement de statut et permet
d'ajouter des notes libres.

**Où la trouver.** Fiche d'un contrat, panneau **Historique**.

**Comment l'utiliser.** Tapez votre note et cliquez sur **Noter**. La timeline
affiche les transitions de statut et vos notes, du plus récent au plus ancien.

### Avenants

**Ce que ça fait.** Enregistre une modification contractuelle (objet, variation
de montant, date d'effet) sans réécrire tout le contrat.

**Où la trouver.** Fiche d'un contrat → onglet **Avenants**.

**Comment l'utiliser.**
1. Cliquez sur **Créer un avenant**.
2. Renseignez l'objet (obligatoire), une description, la date d'effet et la
   variation de montant si applicable.
3. Validez — l'avenant est numéroté et journalisé automatiquement.

### Résiliation

**Ce que ça fait.** Met fin à un contrat de façon tracée (motif, date d'effet,
préavis, solde de tout compte).

**Où la trouver.** Fiche d'un contrat → onglet **Résiliations**.

**Comment l'utiliser.**
1. Cliquez sur **Résilier le contrat**.
2. Renseignez le motif, la date d'effet, le préavis et le solde si nécessaire.
3. Confirmez — l'action est irréversible.

### Renouvellement manuel

**Ce que ça fait.** Prolonge la date de fin d'un contrat, soit en saisissant une
nouvelle date, soit en ajoutant un nombre de mois.

**Où la trouver.** Fiche d'un contrat → bouton **Renouveler**.

**Comment l'utiliser.** Cliquez sur **Renouveler**, saisissez une nouvelle date
de fin OU une durée en mois, puis validez. Les contrats à préavis proche ou à
reconduction tacite sont aussi traités automatiquement chaque nuit (voir
« Échéances & alertes »).

### Tableau de bord des contrats

**Ce que ça fait.** Vue d'ensemble (nombre de contrats, actifs, à renouveler,
valeur active/totale, revenu récurrent), mouvements du mois (nouveaux,
expansion, contraction, résiliations), exceptions de facturation à rejouer, et
cohortes de rétention.

**Où la trouver.** Menu **CONTRATS → Tableau de bord**.

**Comment l'utiliser.** La page se charge automatiquement. Pour une exception de
facturation en échec, cliquez sur **Rejouer**. Pour une révision tarifaire en
masse, cliquez sur **Campagne de révision**, saisissez un pourcentage,
prévisualisez, puis appliquez si le résultat convient (un avenant d'indexation
est créé par contrat couvert).

### Échéances & alertes

**Ce que ça fait.** Centralise les contrats dont le préavis ou l'échéance
approche, les alertes planifiées, jalons, obligations et engagements de service
existants.

**Où la trouver.** Menu **CONTRATS → Échéances & alertes**.

**Comment l'utiliser.**
1. Le centre d'échéances en haut de page liste les contrats à traiter bientôt
   (cliquez pour ouvrir la fiche).
2. **Générer les alertes** crée les alertes dues sur une fenêtre de 30 jours ;
   **Déclencher les alertes dues** les envoie.
3. Dans les onglets Jalons / Obligations, un bouton permet de marquer un élément
   existant comme atteint/réalisé.

Ces mêmes traitements (alertes, reconduction tacite) tournent aussi
automatiquement chaque nuit, sans action manuelle.

### Finances de contrat

**Ce que ça fait.** Affiche les retenues de garantie, cautions, échéanciers de
paiement, indexations de prix et pièces de conformité enregistrés pour vos
contrats.

**Où la trouver.** Menu **CONTRATS → Finances**.

**Comment l'utiliser.**
- Onglet **Retenues** : cliquez sur **Libérer** pour une retenue de garantie
  arrivée à échéance.
- Onglet **Lignes** : cliquez sur **Pointer payé** pour une échéance réglée.
- Onglet **Conformité** : cliquez sur **Marquer fournie** pour une pièce reçue.

### Location de matériel

**Ce que ça fait.** Gère un ordre de location d'équipement de bout en bout :
réservation, enlèvement, caution, retour avec inspection, retard, facturation
récurrente pour la longue durée, bons PDF.

**Où la trouver.** Menu **CONTRATS → Location matériel**.

**Comment l'utiliser.**
1. Cliquez sur **Nouvel ordre**, choisissez le produit, le client et les dates.
2. Suivez le cycle : **Enlever** → **Retourner** (avec inspection) →
   **Clôturer**.
3. Pour la caution : **Encaisser**, **Restituer** ou **Retenir** (partiellement,
   avec motif).
4. Pour une location longue durée : **Facturer le cycle**, **Prolonger** ou
   **Écourter**.
5. Les bons d'enlèvement et de restitution PDF sont téléchargeables depuis la
   fiche de l'ordre.

### Réglages de la location

**Ce que ça fait.** Configure les plans de facturation récurrente réutilisables,
le référentiel des motifs de résiliation et les paramètres généraux de la
location (durée minimale, frais de retard par défaut).

**Où la trouver.** Menu **CONTRATS → Réglages location**.

**Comment l'utiliser.** Dans chaque onglet (Plans récurrents / Motifs de
résiliation / Paramètres), remplissez le formulaire et cliquez sur **Ajouter**
(ou enregistrez directement pour les paramètres).

### Portail client — « Mes contrats »

**Ce que ça fait.** Permet à un client, sans se connecter, de consulter ses
contrats et de demander un renouvellement ou une résiliation. La demande est
transmise à votre équipe — le statut du contrat ne change jamais
automatiquement.

**Où la trouver.** Lien sécurisé envoyé au client.

**Comment l'utiliser (côté client).** Ouvrir le lien, consulter la liste des
contrats, cliquer sur **Demander le renouvellement** ou **Demander la
résiliation**, ajouter un message optionnel, envoyer.

### Registre des réclamations (Litiges)

**Ce que ça fait.** Enregistre toute réclamation ou litige client (financier,
qualité, délai, commercial, recouvrement), avec montant contesté et blocage
optionnel des relances de facture.

**Où la trouver.** Menu **LITIGES → Litiges & réclamations**.

**Comment l'utiliser.**
1. Cliquez sur **Nouvelle réclamation**.
2. Renseignez l'objet, le type, la gravité, le montant contesté et une
   description.
3. Cochez ou décochez « Bloquer les relances automatiques » selon le besoin.
4. Enregistrez.

### Suivi d'une réclamation (prise en charge → résolution)

**Ce que ça fait.** Fait avancer une réclamation d'Ouverte à En traitement, puis
Résolue ou Rejetée, avec journalisation automatique.

**Où la trouver.** Cliquez sur une réclamation dans le registre pour ouvrir sa
fiche.

**Comment l'utiliser.**
1. Sur la fiche, les boutons d'action disponibles dépendent du statut actuel
   (**Prendre en charge**, **Résoudre**, **Rejeter**).
2. Cliquez sur l'action souhaitée.
3. L'onglet **Historique** trace chaque transition ; vous pouvez y ajouter une
   note libre.

### Tableau de bord litiges

**Ce que ça fait.** Affiche en un coup d'œil le nombre de réclamations ouvertes,
le montant total contesté et le délai moyen de résolution.

**Où la trouver.** En haut de la page **Litiges & réclamations**.

**Comment l'utiliser.** Consultation seule, mise à jour automatique à chaque
chargement de la page.

### Analyse concurrents (affaires perdues)

**Ce que ça fait.** Agrège les litiges sur lesquels un concurrent gagnant et un
motif de perte ont été saisis, pour identifier qui vous bat et pourquoi.

**Où la trouver.** Page **Litiges & réclamations**, sélecteur de vue **Analyse
concurrents**.

**Comment l'utiliser.**
1. Lors de la création ou de l'édition d'une réclamation, renseignez la section
   « Deal perdu » (concurrent gagnant, prix, motif).
2. Basculez sur la vue « Analyse concurrents » pour voir les statistiques
   agrégées par concurrent et par motif.

### Aperçus qualité liés (NCR / audit de chantier)

**Ce que ça fait.** Affiche, sur une réclamation qualité, un aperçu de la
non-conformité et/ou de l'audit fin de chantier liés (module QHSE).

**Où la trouver.** Fiche d'une réclamation → onglet **NCR / Audit lié**.

**Comment l'utiliser.** Lors de la création ou de l'édition, renseignez
l'identifiant de la NCR et/ou de l'audit concernés (section « Rattachement
QHSE ») ; l'aperçu s'affiche automatiquement sur la fiche.

---

## GED & Base de connaissances

La GED (gestion électronique de documents) est votre espace documentaire
central ; la Base de connaissances rassemble les procédures et le savoir-faire
interne.

### Documents (GED) — navigateur de base

**Ce que ça fait.** Un espace documentaire central organisé en Cabinets →
Dossiers → Documents. Chaque document peut avoir plusieurs versions (avec
horodatage et auteur) ; on peut le déplacer, le verrouiller pendant une
modification, et faire des actions groupées sur plusieurs documents à la fois.

**Où la trouver.** Menu **Documents (GED)** (`/ged`).

**Comment l'utiliser.**
1. Créez un **Cabinet** (une armoire, ex. « Administratif », « Technique »).
2. À l'intérieur, créez des **Dossiers** (« Nouveau dossier »).
3. Cliquez sur un dossier puis sur **Téléverser** pour ajouter un fichier.
4. Pour remplacer un fichier par une nouvelle version, ouvrez le document et
   téléversez la nouvelle version — l'ancienne reste consultable dans
   l'historique des versions.
5. Pour éviter que deux personnes modifient le même document en même temps,
   utilisez **Extraire** avant modification, puis **Réintégrer** une fois
   terminé.
6. Pour déplacer un document ou un dossier, faites glisser ou utilisez le menu
   « Déplacer ».

### Rechercher un document

**Ce que ça fait.** Recherche un document par son nom, sa description, ses tags
et — lorsque le contenu a été indexé — dans le texte lui-même (recherche
intelligente).

**Où la trouver.** La barre de recherche en haut de la page **Documents (GED)**.

**Comment l'utiliser.** Tapez un mot-clé pour filtrer instantanément les
documents visibles.

### Tags et liens vers les fiches métier

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Relie un document GED à une fiche métier existante (un lead,
un client, un devis, un chantier, un ticket SAV…) pour le retrouver facilement
depuis les deux côtés. Permet aussi d'appliquer des tags organisés en catégories
(ex. « Juridique / Contrats »).

**Où la trouver.** Menu **Documents · Avancé → Tags & liens** (`/ged/tags`).

**Comment l'utiliser.**
1. Pour lier un document : cliquez sur **Nouveau lien**, choisissez le document,
   le type de cible (ex. un devis) puis la fiche concernée, et cliquez sur
   **Créer le lien**.
2. Pour retirer un lien, cliquez sur l'icône de suppression à côté du lien.
3. Pour gérer les tags : créez un tag (nom + couleur), puis affectez-le à un
   document via **Affecter un tag**.

### Approbation et signature de documents

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Deux choses liées : faire relire et valider un document en
interne (cycle brouillon → en revue → approuvé → archivé), et faire signer un
document électroniquement par un ou plusieurs signataires (internes ou
externes), avec suivi des relances et de l'expiration.

**Où la trouver.** Menu **Documents · Avancé → Approbation & signature**
(`/ged/approbation`).

**Comment l'utiliser.**
- **Demander une revue** : choisissez un document brouillon et cliquez sur
  **Demander une revue**. L'approbateur reçoit la demande dans cette même page
  et peut **Approuver** ou **Rejeter** (avec commentaire).
- **Envoyer un document à signer** : cliquez sur **Nouvelle demande de
  signature**, choisissez le document, ajoutez un ou plusieurs signataires (nom,
  rôle, e-mail/téléphone), puis envoyez. Chaque signataire reçoit son propre
  lien de signature — aucun compte à créer.
- Le tableau de bord de la page liste les demandes en attente, signées et
  expirées, avec la possibilité d'**annuler** une demande en cours.

### Rétention et archivage

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Gère combien de temps garder chaque catégorie de documents
(politiques de rétention), l'archivage légal à valeur probante (un document
devient définitivement inaltérable), les mises sous séquestre légal (qui
empêchent temporairement la suppression), le partage public d'un document via un
lien à durée limitée, le suivi du quota de stockage et le journal des accès.

**Où la trouver.** Menu **Documents · Avancé → Rétention & archivage**
(`/ged/retention`).

**Comment l'utiliser.**
- **Créer une politique de rétention** : définissez la durée de conservation et
  l'action à l'échéance (par défaut « Signaler » — rien n'est supprimé
  automatiquement). La liste « Documents échus » montre ce qui a dépassé le
  délai, pour décision humaine.
- **Archiver légalement un document** : sélectionnez-le et cliquez sur
  **Archiver** — attention, cette action est définitive et rend le document et
  ses versions impossibles à modifier ou supprimer.
- **Poser une rétention légale** : gèle temporairement la suppression d'un
  document (ex. pendant un litige) ; levable plus tard avec **Lever**.
- **Partager un document publiquement** : créez un partage (avec expiration et
  mot de passe optionnels), copiez le lien généré ; **Révoquer** l'annule à tout
  moment.
- Le **quota de stockage** et le **journal des accès** s'affichent en lecture
  seule sur la même page.

### Corbeille

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Une suppression « douce » : un document mis à la corbeille
disparaît des listes mais reste récupérable.

**Où la trouver.** Menu **Documents · Avancé → Corbeille** (`/ged/corbeille`).

**Comment l'utiliser.**
1. Pour récupérer un document supprimé par erreur, cliquez sur **Restaurer**.
2. Pour l'effacer définitivement, cliquez sur **Purger** (irréversible — un
   document sous archivage légal ou rétention légale ne peut pas être purgé).

### Numériser (scan mobile vers PDF)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Permet de prendre des photos avec le téléphone ou la
tablette (plusieurs pages) et de les assembler automatiquement en un seul PDF,
classé directement dans la GED.

**Où la trouver.** Menu **Documents · Avancé → Numériser** (`/ged/numeriser`).

**Comment l'utiliser.**
1. Prenez une photo par page du document papier.
2. Une fois toutes les pages capturées, cliquez sur **Assembler en PDF** — le
   PDF est créé et classé automatiquement dans le dossier choisi.

### Base de connaissances — articles

**Ce que ça fait.** Une bibliothèque d'articles internes (procédures, notes
techniques…) avec statut (brouillon / publié / obsolète), historique de
versions, organisation en arborescence, modèles réutilisables, export
PDF/Markdown et suivi de qui a lu quoi.

**Où la trouver.** Menu **Base de connaissances** (`/kb`). Tous les rôles en
lecture ; création et édition selon les droits.

**Comment l'utiliser.**
1. Cliquez sur **Nouvel article**, rédigez le contenu, puis **Publier** quand il
   est prêt.
2. Cliquez sur un article pour voir son détail : versions précédentes, documents
   liés et droits d'accès.
3. Le bouton **Marquer comme lu** enregistre votre lecture — la page affiche
   aussi qui d'autre l'a déjà lu.
4. Un responsable peut restreindre un article à certains rôles (ou personnes
   précises) via le panneau **Droits d'accès** ; sans restriction posée,
   l'article reste visible de tous.
5. Pour relier un article à un produit, un équipement ou un type
   d'intervention, utilisez **Lier** dans le détail de l'article.

### Base de connaissances — parcours (intégration)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Crée une séquence d'articles à lire dans un ordre donné et
l'assigne nominativement à un ou plusieurs collaborateurs (ex. parcours
d'intégration d'un nouveau technicien), avec suivi de progression.

**Où la trouver.** Menu **Base de connaissances → Parcours** (`/kb/parcours`).

**Comment l'utiliser.**
1. Créez un parcours et ajoutez les articles dans l'ordre souhaité.
2. Assignez le parcours à un ou plusieurs collaborateurs.
3. La progression de chaque personne (articles lus / restants) s'affiche sur la
   même page.

### Pièces jointes, activités et commentaires sur une fiche

**Ce que ça fait.** Sur la fiche de n'importe quel enregistrement (lead, client,
chantier, ticket SAV…), un panneau commun permet d'ajouter une pièce jointe
(photo, PDF…), une tâche ou un rappel avec échéance, ou un commentaire — sans
passer par la GED complète.

**Où la trouver.** Directement sur la fiche détail d'un lead, d'un client, d'un
chantier ou d'un ticket. Votre liste personnelle de tâches est dans **Ma file**
(`/activites`).

**Comment l'utiliser.**
1. Sur la fiche d'un enregistrement, ouvrez la section **Pièces jointes** et
   cliquez sur **Ajouter** pour téléverser un fichier.
2. Dans **Ma file**, retrouvez toutes vos tâches et rappels à faire (tous
   modules confondus), marquez-les **Fait**, ou reportez-les avec **Plus tard**.

---

## Rapports & Tableaux de bord

La section **ANALYSE** du menu regroupe les tableaux de bord, les rapports
détaillés, le journal d'activité et la boîte d'approbations.

### Tableau de bord principal (Reporting)

**Ce que ça fait.** Vue d'ensemble en un coup d'œil : CA encaissé, CA en
attente, nombre de clients actifs, valeur du stock, évolution du CA sur les 12
derniers mois, top 5 des produits vendus, répartition des factures, tunnel de
conversion devis → facture, alertes de stock bas, et liste des créances clients
(factures impayées).

**Où la trouver.** Menu **ANALYSE → Reporting** (`/reporting`).

**Comment l'utiliser.**
1. La page se charge automatiquement avec les chiffres de votre société.
2. Cliquez sur une tuile KPI (ex. « CA encaissé ») pour ouvrir directement la
   liste filtrée correspondante.
3. Utilisez les boutons 6 mois / 12 mois / Tout au-dessus du graphique de CA
   mensuel pour changer la période.
4. Le bouton **Exporter Excel** télécharge un fichier avec les mêmes chiffres ;
   **Actualiser** recharge les données en temps réel.

### Hub Rapports (Ventes, Stock, Service, Insights, Mes rapports)

**Ce que ça fait.** Cinq onglets de rapports détaillés : entonnoir de vente par
étape et par responsable, valorisation et alertes de stock, activité des
chantiers et du SAV, des analyses avancées (revenu récurrent des contrats
d'entretien, coût de revient par chantier, délais moyens lead → signature →
mise en service, commissions commerciales), et un onglet pour créer et planifier
vos propres rapports.

**Où la trouver.** Menu **ANALYSE → Rapports** (`/rapports`).

**Comment l'utiliser.**
1. Choisissez un onglet en haut de la page (Ventes & pipeline, Stock, Service,
   Insights, Mes rapports).
2. Filtrez par période avec les champs **Du** / **Au**.
3. Chaque carte a son propre bouton **Exporter Excel**.
4. Dans **Mes rapports**, cliquez sur **Nouveau rapport** pour enregistrer un
   modèle de rapport et, si vous le souhaitez, activer un envoi automatique par
   e-mail (quotidien ou hebdomadaire) à une ou plusieurs adresses. Cochez
   « Épingler sur le tableau de bord » pour le retrouver rapidement.

### Journal d'activité (qui a fait quoi)

**Ce que ça fait.** Trace toutes les actions importantes de l'équipe :
créations, modifications, suppressions, changements de statut, connexions, PDF
générés, e-mails/WhatsApp envoyés, exports. Réservé aux comptes disposant de la
permission « Voir le journal » (Directeur par défaut, activable pour d'autres
rôles dans Paramètres → Rôles).

**Où la trouver.** Menu **Journal d'activité** (`/journal`).

**Comment l'utiliser.**
1. Choisissez la période (Jour / Semaine / Mois) et une date de référence.
2. Filtrez par utilisateur, type d'action ou module, ou tapez un mot-clé dans
   « Rechercher ».
3. Le graphique en haut montre le volume d'activité ; le tableau liste chaque
   événement (date, utilisateur, action, objet concerné, détail).
4. Cliquez sur la référence d'un objet (ex. un numéro de devis) pour ouvrir
   directement sa fiche.
5. Cliquez sur l'icône horloge (« Historique à cette date ») sur une ligne pour
   voir à quoi ressemblait l'objet à une date passée — utile pour retrouver un
   ancien statut ou une ancienne valeur.

### Boîte d'approbations centralisée

**Ce que ça fait.** Rassemble en un seul endroit tout ce qui attend votre
décision à travers l'ERP : automatisations, étapes de contrats, demandes de
documents (GED), demandes d'achat chantier, et étapes de workflow. Chaque
demande affiche son ancienneté et si elle est en retard (au-delà du délai
configuré, 3 jours ouvrés par défaut).

**Où la trouver.** Menu **ANALYSE → Approbations** (`/approbations`).

**Comment l'utiliser.**
1. Onglet **File** : filtrez par source (automatisation, contrats, GED,
   installations, workflow) ou par priorité, ou triez par urgence, ancienneté ou
   montant.
2. Cliquez sur **Approuver** ou **Refuser** sur une ligne (un motif est
   obligatoire pour un refus). La décision est appliquée immédiatement à
   l'élément d'origine.
3. Sélectionnez plusieurs lignes pour une décision en masse. Approuver ou
   refuser une demande « Installations » ou « Contrats » nécessite le rôle
   Responsable ou Administrateur.
4. Onglet **Délégations** : pendant une absence, désignez un collègue
   (suppléant) et une période — il verra et pourra décider vos demandes en
   attente à votre place. Cliquez sur **Révoquer** pour mettre fin à une
   délégation avant terme.

### Tableau de bord commercial

**Ce que ça fait.** Trois vues pour piloter l'équipe commerciale : entonnoir de
conversion avec temps moyen passé à chaque étape, classement des commerciaux
(CA signé, taux de victoire, affaire moyenne, kWc), et analyse gains/pertes par
canal marketing avec le top des motifs de perte.

**Où la trouver.** Menu **ANALYSE → Tableau commercial**
(`/reporting/commercial`).

**Comment l'utiliser.**
1. Basculez entre les trois onglets : Entonnoir & vélocité, Classement,
   Gains / Pertes.
2. Dans l'onglet Classement, le bouton **Exporter** télécharge le classement
   affiché.

### Balance âgée (créances clients)

**Ce que ça fait.** Liste chaque client avec ses factures dues, réparties par
tranche d'âge (0-30 j, 31-60 j, 61-90 j, 90 j+) et le total dû.

**Où la trouver.** Menu **ANALYSE → Balance âgée** (`/reporting/balance-agee`).

**Comment l'utiliser.** La page affiche la liste directement ; utilisez le
bouton d'export pour obtenir le fichier Excel à partager en interne.

### Classeurs (mini-tableur avec données en direct)

**Ce que ça fait.** Un vrai petit tableur intégré à l'ERP : vous créez des
cellules avec des formules, et certaines plages peuvent être liées à une requête
sauvegardée qui se réactualise à chaque ouverture — fini les exports Excel
obsolètes dès le lendemain.

**Où la trouver.** Menu **ANALYSE → Classeurs** (`/reporting/classeurs`).

**Comment l'utiliser.**
1. Créez un nouveau classeur et donnez-lui un titre.
2. Ouvrez-le et saisissez vos données et formules cellule par cellule.
3. Utilisez **Actualiser** pour recalculer toutes les cellules (y compris les
   plages liées à des données en direct).
4. Cochez « Partagé » pour le rendre visible à toute la société, ou gérez un
   partage plus fin (utilisateur ou rôle précis) depuis l'écran du classeur.

### Alertes KPI (seuils configurables)

**Ce que ça fait.** Vous êtes notifié automatiquement (une fois par jour) quand
un indicateur franchit un seuil que vous définissez : DSO (délai moyen de
recouvrement), encours client échu total, ou valeur totale du stock.

**Où la trouver.** Menu **Paramètres**, onglet des alertes KPI.

**Comment l'utiliser.**
1. Créez une alerte : choisissez le KPI, l'opérateur (>, >=, <, <=) et le seuil.
2. Choisissez les destinataires : un rôle entier, ou des utilisateurs précis.
3. L'alerte se réarme automatiquement dès que la valeur repasse du bon côté du
   seuil — vous serez re-notifié au prochain dépassement, jamais spammé en
   continu.

### Configuration du tableau de bord

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Personnalise quelles cartes (KPI, CA mensuel, top produits,
pipeline…) s'affichent sur le Reporting principal, soit pour vous
personnellement, soit comme défaut pour tout un palier de rôle.

**Où la trouver.** Écran de configuration des tableaux de bord
(`/reporting/dashboards`).

**Comment l'utiliser.** Cochez ou décochez les cartes à afficher, puis
enregistrez soit comme préférence personnelle, soit comme défaut pour un palier
de rôle donné.

### Analytics terrain & Scorecard technicien

**Ce que ça fait.** Deux tableaux de bord dédiés au service après-vente et à
l'équipe technique : « Analytics terrain » consolide les KPI d'intervention
(résolution au premier passage, délai moyen de réparation, ponctualité,
récidive, temps de trajet vs temps sur site) ; « Scorecard technicien » compare
chaque technicien à la moyenne de l'équipe (utile pour le coaching).

**Où les trouver.** Menu **ANALYSE** : Analytics terrain
(`/reporting/field-service`) et Scorecard technicien
(`/reporting/scorecard-technicien`).

**Comment les utiliser.** Ouvrez la page ; pour le scorecard, sélectionnez un
technicien dans la liste pour voir son détail comparé à la moyenne.

### Conformité SLA SAV

**Ce que ça fait.** Suit le respect des délais d'intervention SAV : retards
accumulés, part de préventif vs correctif, ponctualité des visites.

**Où la trouver.** Menu **ANALYSE → SLA SAV** (`/reporting/sav-sla`).

### Calendrier / Agenda

**Ce que ça fait.** Un agenda unique regroupant poses prévues, mises en service,
interventions terrain, visites de maintenance préventive et activités de suivi
(relances). Vous pouvez glisser un événement sur une autre date pour le
reprogrammer (sauf les visites de maintenance, calculées automatiquement).

**Où la trouver.** Menu **Calendrier** (`/calendrier`).

**Comment l'utiliser.**
1. Filtrez par assigné ou par type d'événement.
2. Glissez-déposez un événement modifiable vers une nouvelle date pour le
   reprogrammer.
3. Depuis la page, récupérez le lien d'abonnement ICS pour voir votre agenda
   directement dans Google Agenda ou Outlook.

### Carte

**Ce que ça fait.** Affiche sur une carte tous vos leads, clients et chantiers
géolocalisés, filtrables par type et statut.

**Où la trouver.** Menu **Carte** (`/carte`).

### Dashboards TV (affichage plein écran)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Affiche les tableaux de bord partagés en plein écran, pour
un écran mural (rotation et rafraîchissement automatiques).

**Où la trouver.** Menu **ANALYSE → Dashboards TV** (`/dashboards-tv`).

**Comment l'utiliser.** Ouvrez la page sur l'écran dédié ; elle tourne toute
seule, sans barre de menu.

---

## Messagerie & Notifications

Ce chapitre couvre la messagerie d'équipe interne, vos préférences de
notifications et les règles automatiques. La cloche de notifications est
présentée au chapitre « Premiers pas », et la boîte d'approbations au chapitre
« Rapports & Tableaux de bord ».

### Messagerie interne (Discuter)

**Ce que ça fait.** Une messagerie d'équipe façon WhatsApp/Slack, entre
collègues de la même société : discussions en tête-à-tête (messages directs) ou
canaux nommés (par équipe ou projet). Vous pouvez envoyer du texte, des images,
des fichiers, des mémos vocaux, réagir avec des emojis, épingler un message
important, mentionner un collègue avec « @ », et partager une fiche de l'ERP (un
lead, un devis, un chantier…) directement dans la conversation.

**Où la trouver.** Menu **Messages** (`/messages`) ; l'icône bulle de message
dans l'en-tête signale les nouveaux messages.

**Comment l'utiliser.**
1. **Démarrer une conversation** : cliquez sur « Nouvelle conversation »,
   choisissez un collègue (message direct) ou créez un canal nommé avec
   plusieurs membres.
2. **Écrire** : tapez votre message dans la zone de saisie et appuyez sur
   Entrée.
3. **Joindre un fichier ou une image** : bouton pièce jointe du composeur.
4. **Envoyer un message vocal** : bouton micro — enregistrez puis envoyez. Le
   message est automatiquement transcrit en texte quand cette fonction est
   activée (voir le chapitre « Assistant IA & OCR »).
5. **Mentionner un collègue** : tapez « @ » suivi du nom ; il sera notifié.
6. **Réagir** à un message : survolez-le et choisissez un emoji.
7. **Épingler** un message important : ouvrez son menu et choisissez
   « Épingler » — il reste visible en haut du canal.
8. **Partager une fiche** : depuis la fiche d'un lead, d'un devis ou d'un
   chantier (ou depuis le composeur), utilisez « Partager dans Discuter » et
   choisissez la conversation cible.
9. **Commandes rapides** : tapez « / » dans la zone de saisie pour lancer une
   commande de l'assistant (voir le chapitre « Assistant IA & OCR »).
10. **Gérer les membres d'un canal** : ouvrez les paramètres du canal pour
    ajouter ou retirer des membres, ou le quitter.

### Mes préférences de notifications

**Ce que ça fait.** Vous choisissez, pour chaque type d'événement (nouveau lead,
devis accepté, facture en retard…), sur quels canaux vous voulez être prévenu :
dans l'application (activé par défaut), par WhatsApp ou par e-mail.

**Où la trouver.** Menu **Paramètres → Notifications**
(`/parametres/notifications`).

**Comment l'utiliser.**
1. Pour chaque type d'événement de la liste, cochez ou décochez les canaux
   souhaités (application / WhatsApp / e-mail).
2. Le changement est enregistré automatiquement, sans bouton « Enregistrer ».

### Automatisations (règles « si ceci → alors cela »)

**Ce que ça fait.** Crée des règles automatiques sans écrire de code : par
exemple « quand un devis est accepté → créer une activité de suivi » ou « quand
le stock d'un produit passe sous le seuil → envoyer un e-mail ». Chaque règle
peut être activée ou désactivée, et chaque exécution est journalisée.

Déclencheurs disponibles : changement d'étape d'un lead, devis accepté, chantier
atteignant un statut, facture en retard, garantie proche d'expirer, visite de
maintenance due, stock sous le seuil. Actions disponibles : envoyer un WhatsApp,
un e-mail, un SMS, créer une activité/tâche, assigner un enregistrement, mettre
à jour un champ, créer un ticket SAV.

**Où la trouver.** Menu **Paramètres → Automatisations**.

**Comment l'utiliser.**
1. Consultez la liste des règles existantes ; activez ou désactivez-les avec le
   bouton dédié, ou supprimez-en une avec la corbeille.
2. Pour créer une règle : donnez-lui un nom, choisissez le déclencheur et
   l'action dans les listes déroulantes, cochez « Exiger une approbation » si
   nécessaire, puis cliquez sur **Ajouter la règle**.
3. Vous pouvez aussi partir d'un modèle prédéfini (bouton **Créer depuis un
   modèle**) ou demander à l'assistant IA de proposer un brouillon de règle
   (bouton **Générer une règle (IA)**) — dans les deux cas, la règle est créée
   désactivée : relisez-la puis activez-la vous-même.
4. Une règle qui exige une **approbation** ne s'exécute qu'après validation :
   la demande apparaît dans la boîte d'approbations et dans la section
   **Approbations en attente** de cet écran (boutons **Approuver** /
   **Rejeter**).
5. La section **Journal d'exécutions** montre chaque déclenchement récent
   (réussi, sans effet, en attente d'approbation, échoué) avec un message
   explicatif — utile pour vérifier qu'une règle fonctionne comme prévu.

---

## Assistant IA & OCR

TAQINOR OS embarque un assistant intelligent : lecture automatique de documents
(OCR), questions en langage naturel sur vos données, et actions proposées à
votre confirmation. Certaines de ces fonctions nécessitent qu'une clé de service
soit configurée par votre administrateur — sans cette clé, l'écran affiche un
message clair (« configuration manquante ») plutôt qu'une erreur.

### L'assistant Copilote (actions confirmées)

**Ce que ça fait.** Depuis la petite fenêtre « Assistant » présente sur chaque
écran, vous pouvez demander à l'assistant de faire certaines actions à votre
place : créer un lead, créer un devis, générer le PDF d'une proposition, ouvrir
un ticket SAV, préparer un bon de commande, planifier une visite… L'assistant ne
fait JAMAIS l'action directement : il vous montre d'abord un résumé de ce qu'il
va faire et attend votre confirmation.

**Où la trouver.**
- Le bouton de l'assistant (Copilote) est visible en permanence sur toutes les
  pages de l'ERP, une fois connecté.
- Dans la messagerie interne, vous pouvez aussi taper des commandes rapides qui
  commencent par « / » directement dans la zone de texte (par exemple `/lead` ou
  `/devis`).

**Comment l'utiliser.**
1. Ouvrez la fenêtre de l'assistant (ou la messagerie).
2. Écrivez votre demande en langage naturel (« crée un lead nommé Ahmed à
   Casablanca ») ou tapez une commande rapide.
3. L'assistant affiche une carte récapitulative de l'action proposée.
4. Cliquez sur **Confirmer** pour que l'action soit réellement exécutée. Sans
   cette confirmation, rien n'est créé ni modifié.
5. Seules les actions autorisées par votre rôle vous sont proposées — un
   commercial ne verra pas les actions réservées à un administrateur.

### Agent IA — poser des questions en langage naturel

**Ce que ça fait.** Vous posez une question en français (« Quels produits sont
en rupture de stock ? », « Quel est le chiffre d'affaires du mois ? », « Affiche
les factures impayées ») et l'assistant consulte vos données — uniquement celles
de votre entreprise — pour vous répondre en langage clair.

**Où la trouver.** Trois accès :
- Page dédiée : menu **Intelligence → Agent IA** (`/ia/agent`), réservée au rôle
  Administrateur.
- Le tiroir **Copilote**, accessible depuis n'importe quel écran.
- La messagerie interne, via les commandes rapides « / ».

**Comment l'utiliser.**
1. Tapez votre question en français (des suggestions sont proposées pour
   démarrer).
2. Lisez la réponse. Si l'assistant propose une action, **Confirmer** l'exécute
   et **Annuler** l'écarte — rien ne se passe sans votre accord.
3. Vous pouvez aussi dicter votre question au micro : l'assistant transcrit
   votre voix en texte.
4. Un bouton permet d'effacer l'historique de conversation à tout moment.

À savoir : l'assistant ne répond qu'avec les données de votre propre entreprise,
ne montre jamais le prix d'achat ni la marge sans autorisation spécifique, et ne
peut jamais modifier ou supprimer des données sans confirmation explicite pour
les actions sensibles.

### OCR — lire automatiquement un document

**Ce que ça fait.** Vous prenez en photo (ou scannez) une facture, un devis ou
un bon de livraison, et l'assistant lit le document pour vous : il en extrait le
texte, le type de document, le numéro, la date, le montant, la TVA. Vous pouvez
enregistrer le résultat pour le retrouver plus tard, ou l'utiliser pour créer
directement un lead — voire un lead accompagné d'un devis brouillon — sans
ressaisie manuelle.

**Où la trouver.** Menu **Intelligence → OCR** (`/ia/ocr`), réservé aux rôles
Responsable et Administrateur.

**Comment l'utiliser.**
1. Cliquez sur la zone d'import et choisissez une photo (JPEG, PNG, TIFF, WEBP)
   ou un PDF de moins de 10 Mo.
2. Attendez quelques secondes : le texte et les informations extraites
   s'affichent.
3. Vérifiez les champs proposés (nom, téléphone, adresse, numéro, montant,
   TVA…).
4. Choisissez de créer un simple lead, ou un lead accompagné d'un devis
   brouillon — la fiche apparaît directement dans le CRM / la liste des devis,
   prête à être complétée.
5. Ou cliquez sur **Enregistrer** pour garder une trace du document dans
   l'historique (consultable et supprimable depuis la même page).

À savoir : l'analyse est limitée à 20 documents par heure et par utilisateur.

### OCR — importer un bon de livraison ou une facture fournisseur dans le stock

**Ce que ça fait.** Au lieu de saisir manuellement chaque ligne d'un bon de
livraison ou d'une facture fournisseur, vous importez une photo ou un PDF du
document : les lignes de produits (référence, désignation, quantité, prix, TVA)
sont proposées automatiquement pour créer un mouvement d'entrée de stock.

**Où la trouver.** Menu **STOCK → Import OCR** (`/stock/ocr-import`), réservé
aux rôles Responsable et Administrateur.

**Comment l'utiliser.**
1. Choisissez le type de document (bon de livraison, facture d'achat, bon de
   sortie) si vous le connaissez — cela améliore la qualité de la lecture.
2. Importez la photo ou le PDF du document fournisseur.
3. Relisez les lignes de produits proposées : référence, nom, quantité, prix
   unitaire HT, TVA.
4. Corrigez si besoin, puis validez pour créer le mouvement de stock.

À savoir : si le document est un scan de mauvaise qualité, le système tente
automatiquement une seconde lecture page par page pour récupérer un maximum de
lignes.

### Transcription automatique des messages vocaux

**Ce que ça fait.** Quand un collègue vous envoie un message vocal dans la
messagerie interne, le système peut automatiquement le transcrire en texte sous
l'enregistrement audio — pratique pour lire rapidement sans écouter, ou pour
retrouver un message vocal par mot-clé.

**Où la trouver.** Directement dans la messagerie interne, sous chaque message
vocal reçu.

**Comment l'utiliser.** Rien à faire : sous le message, un texte
« Transcription… » apparaît quelques instants puis se remplace par le texte
transcrit. Cette fonction doit être activée au niveau du serveur ; si elle ne
l'est pas, le message vocal reste utilisable normalement, simplement sans
transcription.

### Générer un brouillon de planning de projet depuis un devis

**Ce que ça fait.** À partir d'un devis déjà signé, l'assistant propose un
brouillon de planning de chantier (les grandes tâches, dans quel ordre, sur
combien de jours) adapté au type d'installation. Vous relisez et modifiez ce
brouillon avant de le valider — rien n'est créé dans le projet tant que vous
n'avez pas confirmé.

**Où la trouver.** Depuis la fiche d'un projet, dans le module de gestion de
projet (bouton de génération de plan par IA).

**Comment l'utiliser.**
1. Ouvrez la fiche d'un projet rattaché à un devis.
2. Cliquez sur le bouton de génération de plan par IA.
3. Relisez les tâches proposées (libellé, phase, durée en jours, dépendances).
4. Modifiez si besoin, puis confirmez pour créer réellement les tâches et jalons
   dans le projet.

À savoir : si le service IA n'est pas configuré, un message clair vous l'indique
et vous pouvez toujours créer le planning manuellement.

---

## Publicité & Marketing

Le module **PUBLICITÉ** pilote vos campagnes Meta (Facebook/Instagram) ; le
module **MARKETING** gère vos campagnes d'e-mailing, séquences de relance,
événements et programme de fidélité.

### Publicité — principe de fonctionnement

Le moteur publicitaire ne fonctionne qu'une fois la connexion Meta configurée
par un administrateur — tant qu'elle ne l'est pas, tous les écrans restent
vides mais utilisables. Règle d'or du module : **rien ne part jamais tout
seul** — chaque action proposée par le moteur (budget, texte, réponse à un
commentaire…) passe par la boîte d'Approbations avant d'être appliquée.

### Connexion & garde-fous

**Ce que ça fait.** Enregistre les identifiants Meta (compte publicitaire, page,
pixel) et les plafonds de sécurité (budget quotidien/mensuel maximum, bande
d'auto-approbation). Les identifiants ne sont jamais ré-affichés une fois
enregistrés (sécurité).

**Où la trouver.** Menu **PUBLICITÉ → Connexion & garde-fous**
(`/publicite/connexion`).

**Comment l'utiliser.**
1. Renseignez l'identifiant du compte publicitaire, celui de la Page et
   (optionnel) le Pixel, puis enregistrez.
2. Définissez les garde-fous : dépense max/jour, dépense max/mois, seuils
   d'auto-approbation.
3. Le voyant de santé en haut de l'écran confirme si tout est bien relié.

### Tableau de bord publicitaire

**Ce que ça fait.** Affiche le chiffre clé — le coût par signature (dépense
publicitaire ÷ ventes réellement signées) — avec l'état du budget et les alertes
actives.

**Où la trouver.** Menu **PUBLICITÉ → Tableau de bord**
(`/publicite/tableau-de-bord`).

**Comment l'utiliser.** Consultez le chiffre du jour ; cliquez sur une alerte
pour voir le détail ; le détail « leads » montre la liste réelle des prospects
derrière chaque chiffre — traçabilité totale, jamais une boîte noire.

### Cockpit par publicité

**Ce que ça fait.** Une ligne par publicité active avec toutes ses métriques
combinées (dépense, leads, conversations, signatures).

**Où la trouver.** Menu **PUBLICITÉ → Cockpit par ad** (`/publicite/cockpit`).

**Comment l'utiliser.** Triez et filtrez pour repérer vite les publicités qui
performent ou qui doivent être coupées.

### Approbations publicitaires

**Ce que ça fait.** L'écran central du module : chaque action que le moteur
propose (changer un budget, modifier un texte, renommer…) atterrit ici avant
d'être appliquée sur Meta.

**Où la trouver.** Menu **PUBLICITÉ → Approbations**
(`/publicite/approbations`).

**Comment l'utiliser.**
1. Chaque carte montre l'avant/après réel (aperçu créatif, écart de budget) et
   la raison en français.
2. Cochez une ou plusieurs cartes pour une approbation groupée, ou traitez-les
   une par une.
3. Pour rejeter, choisissez un motif dans la liste proposée.
4. Une fois approuvée, l'action quitte immédiatement la boîte.

### Campagnes Meta

**Ce que ça fait.** Liste vos campagnes Meta (miroir en lecture, synchronisé
depuis Meta) avec un bouton de synchronisation immédiate et un classement des
créatifs par performance. En cliquant sur une campagne, vous accédez à sa
hiérarchie complète (campagne → groupes d'annonces → annonces).

**Où la trouver.** Menu **PUBLICITÉ → Campagnes** (`/publicite/campagnes`).

**Comment l'utiliser.** Cliquez sur **Synchroniser** pour rafraîchir depuis
Meta, puis sur une campagne pour explorer son détail.

### Bibliothèque créative

**Ce que ça fait.** Centralise vos visuels et vidéos publicitaires, vérifie
qu'ils respectent la politique interne avant utilisation, et peut générer des
variantes. Un créatif non conforme ne peut jamais partir en production.

**Où la trouver.** Menu **PUBLICITÉ → Bibliothèque créative**
(`/publicite/creatifs`).

**Comment l'utiliser.** Déposez un fichier, lancez la vérification de
conformité, puis générez des variantes si besoin.

### Commentaires

**Ce que ça fait.** Boîte de réception unique des commentaires sur vos
publications et publicités (masquer, répondre, répondre en privé, supprimer).

**Où la trouver.** Menu **PUBLICITÉ → Commentaires**
(`/publicite/commentaires`).

**Comment l'utiliser.** Chaque action (masquer / répondre / supprimer) crée une
proposition qui passe par la boîte d'Approbations avant d'être appliquée.

### Instagram

**Ce que ça fait.** Gère vos publications, commentaires et quota de publication
sur le compte Instagram Business relié.

**Où la trouver.** Menu **PUBLICITÉ → Instagram** (`/publicite/instagram`).

**Comment l'utiliser.** Consultez le quota restant, publiez ou gérez les
commentaires ; toute écriture passe aussi par les Approbations.

### Expérimentations (tests A/B)

**Ce que ça fait.** Suivi des tests A/B avec un journal qui explique pourquoi le
moteur a favorisé une variante.

**Où la trouver.** Menu **PUBLICITÉ → Expérimentations**
(`/publicite/experimentations`).

**Comment l'utiliser.** Ouvrez une expérience pour voir les statistiques par
variante et l'historique de décision.

### Plan de vol

**Ce que ça fait.** Compose un plan de lancement sur plusieurs mois (phases
pré-construites), avec une vérification préalable avant toute autonomie.

**Où la trouver.** Menu **PUBLICITÉ → Plan de vol** (`/publicite/plan-de-vol`).

**Comment l'utiliser.** Choisissez un gabarit de phases, validez le plan, puis
lancez une simulation avant l'activation réelle.

### Backlog créatif

**Ce que ça fait.** File d'attente des créatifs par campagne (autonomie de
production restante, diversité des angles) avec approbation par lot.

**Où la trouver.** Menu **PUBLICITÉ → Backlog** (`/publicite/backlog`).

**Comment l'utiliser.** Déposez un visuel dans le backlog d'une campagne, puis
approuvez le lot de recombinaisons proposé.

### Règles & anomalies

**Ce que ça fait.** Catalogue de règles prêtes à l'emploi avec simulation « à
blanc » avant application, plus le flux des anomalies détectées.

**Où la trouver.** Menu **PUBLICITÉ → Règles & anomalies**
(`/publicite/regles`).

**Comment l'utiliser.** Choisissez un gabarit de règle, lancez la simulation
pour voir l'effet sans rien appliquer, et consultez le journal d'exécution pour
comprendre chaque décision passée.

### Simulation

**Ce que ça fait.** Rejoue visuellement un scénario pour comprendre l'effet
d'une décision avant de l'appliquer pour de vrai.

**Où la trouver.** Menu **PUBLICITÉ → Simulation** (`/publicite/simulation`).

### Reporting publicitaire

**Ce que ça fait.** Tableaux détaillés — comparaison de variantes, entonnoir de
conversion, cohortes, classement des créatifs — avec export CSV et un audit de
compte à la demande.

**Où la trouver.** Menu **PUBLICITÉ → Reporting** (`/publicite/reporting`).

**Comment l'utiliser.** Ouvrez l'onglet qui vous intéresse ; le bouton **Lancer
l'audit** déclenche une vérification complète du compte (structure, budget,
fatigue créative) — elle ne se lance jamais automatiquement.

### Brief hebdomadaire

**Ce que ça fait.** Résumé automatique en français de la semaine publicitaire,
généré chaque semaine sans intervention.

**Où la trouver.** Menu **PUBLICITÉ → Brief hebdomadaire** (`/publicite/brief`).

### Journal d'actions

**Ce que ça fait.** Historique complet de toutes les actions proposées,
approuvées, rejetées ou appliquées par le moteur.

**Où la trouver.** Menu **PUBLICITÉ → Journal d'actions**
(`/publicite/journal`).

### Marketing — campagnes (e-mail / SMS / WhatsApp)

**Ce que ça fait.** Crée et envoie des campagnes groupées vers un segment de
contacts, avec test A/B automatique, envoi de test, aperçu avant envoi et suivi
des ouvertures, clics et retour sur investissement.

**Où la trouver.** Menu **MARKETING → Campagnes** (`/marketing/campagnes`).

**Comment l'utiliser.**
1. Créez une campagne (nom, canal, objet, message).
2. Envoyez un test à vous-même avant l'envoi réel.
3. Lancez la vérification préalable, puis planifiez ou envoyez.
4. Ouvrez la campagne pour suivre les envois destinataire par destinataire, le
   résultat du test A/B et le ROI.

### Marketing — séquences de relance

**Ce que ça fait.** Enchaîne automatiquement plusieurs étapes (WhatsApp, e-mail,
appel) après l'entrée d'un prospect dans une étape du pipeline commercial (ex.
J0 WhatsApp → J3 e-mail → J7 appel). Un prospect sort automatiquement de la
séquence dès que son devis est accepté ou refusé.

**Où la trouver.** Menu **MARKETING → Séquences** (`/marketing/sequences`).

**Comment l'utiliser.** Créez une séquence, ajoutez ses étapes avec leur délai,
activez-la. Ouvrez une séquence pour voir les participants en cours et la trace
de chaque étape exécutée.

### Marketing — segments

**Ce que ça fait.** Définit des groupes de contacts réutilisables selon des
critères (comportement, données du prospect), avec prévisualisation en direct du
nombre de contacts concernés.

**Où la trouver.** Menu **MARKETING → Segments** (`/marketing/segments`).

### Marketing — listes de diffusion

**Ce que ça fait.** Listes nommées de contacts, avec import en masse
(CSV/Excel).

**Où la trouver.** Menu **MARKETING → Listes de diffusion**
(`/marketing/listes`).

**Comment l'utiliser.** Créez une liste, importez un fichier de contacts, ou
consultez la liste des abonnés.

### Marketing — événements

**Ce que ça fait.** Gère un événement marketing (webinaire, portes ouvertes…) :
inscriptions, pointage à l'arrivée et badge PDF de chaque participant.

**Où la trouver.** Menu **MARKETING → Événements** (`/marketing/evenements`).

**Comment l'utiliser.** Créez l'événement ; ouvrez-le pour voir la liste des
inscrits, pointer leur arrivée et imprimer leur badge.

### Marketing — enquêtes

**Ce que ça fait.** Constructeur d'enquêtes de satisfaction personnalisées, avec
page de résultats et export.

**Où la trouver.** Menu **MARKETING → Enquêtes** (`/marketing/enquetes`).

**Comment l'utiliser.** Construisez l'enquête (questions), consultez les
résultats agrégés, exportez-les si besoin.

### Marketing — fidélité

**Ce que ça fait.** Suit le solde de points et le palier (bronze / argent / or /
platine) de chaque client, et propose un onglet dédié aux règles de vente
additionnelle suggérées par contexte commercial.

**Où la trouver.** Menu **MARKETING → Fidélité** (`/marketing/fidelite`).

**Comment l'utiliser.** Ouvrez la fiche d'un client pour créditer des points ;
basculez sur l'onglet « Règles d'upsell » pour gérer les suggestions.

### Marketing — domaine d'envoi & supports imprimés

**Ce que ça fait.** Vérifie la configuration technique d'envoi d'e-mails
(SPF/DKIM/DMARC) pour éviter les spams, et gère les supports imprimés (flyers,
QR-codes) avec suivi des scans.

**Où la trouver.** Menu **MARKETING → Domaine d'envoi** (dans Paramètres,
`/parametres/marketing`). Les supports imprimés s'ouvrent depuis ce même écran.

---

## Verticaux métiers

TAQINOR OS embarque des modules verticaux pour des activités spécifiques :
agriculture, santé, immobilier, innovation interne, pilotage budgétaire (FP&A)
et assurances d'entreprise. Ils n'apparaissent dans le menu que s'ils sont
activés pour votre société.

### Agriculture — démarrer une campagne culturale

**Ce que ça fait.** Lance un nouveau cycle de culture (semis → récolte) sur une
parcelle qui n'est pas déjà en culture. Le système refuse automatiquement de
démarrer une deuxième campagne sur une parcelle déjà « en cours ».

**Où la trouver.** Menu **AGRICULTURE → Parcelles** (`/agriculture/parcelles`).

**Comment l'utiliser.**
1. Repérez une parcelle dont le statut n'est pas « En culture » (jachère ou
   préparation).
2. Cliquez sur l'action **Démarrer une campagne** sur sa ligne.
3. Renseignez la culture (ex. « Tomate »), la variété (optionnel), la date de
   semis et la date de récolte prévue.
4. Cliquez sur **Démarrer la campagne**.

### Agriculture — traitements et étapes de campagne (alerte DAR)

**Ce que ça fait.** Enregistre une étape datée d'une campagne (semis, traitement
phytosanitaire, irrigation, désherbage, fertilisation, récolte). Pour les
traitements phytosanitaires, le système vérifie en direct le **délai avant
récolte (DAR)** de l'intrant choisi : si l'application prévue dépasse la date de
récolte compte tenu du DAR, l'enregistrement est **bloqué** avec un message
explicite — conformité ONSSA garantie, jamais un simple avertissement ignorable.

**Où la trouver.** Menu **AGRICULTURE → Intrants** (`/agriculture/intrants`).

**Comment l'utiliser.**
1. Dans le sélecteur en haut à droite, choisissez la campagne concernée.
2. Cliquez sur **Ajouter un traitement**.
3. Choisissez le type d'étape (par défaut « Traitement »).
4. S'il s'agit d'un traitement, choisissez l'intrant appliqué dans la liste (le
   délai avant récolte de chaque intrant est affiché).
5. Renseignez la date, une description et un coût optionnels.
6. Une bannière verte confirme que le délai est respecté ; une bannière rouge
   bloque l'enregistrement s'il ne l'est pas.
7. Cliquez sur **Enregistrer**.

### Agriculture — pointage journalier de la main-d'œuvre

**Ce que ça fait.** Enregistre, jour par jour, qui a travaillé (équipe
saisonnière ou travailleur libre nommé), sur quelle parcelle, pour quelle tâche,
combien de journées et à quel taux journalier. Ces données alimentent le calcul
du coût de main-d'œuvre de la campagne.

**Où la trouver.** Menu **AGRICULTURE → Main d'œuvre & Matériel**
(`/agriculture/ressources`), onglet **Pointage**.

**Comment l'utiliser.**
1. Cliquez sur **Nouveau pointage**.
2. Choisissez une équipe existante, OU laissez « Aucune » et saisissez un nom de
   travailleur libre.
3. Choisissez la parcelle concernée (obligatoire) et, si pertinent, la campagne.
4. Renseignez la date, la tâche effectuée, le nombre de journées et le taux
   journalier (MAD).
5. Cliquez sur **Enregistrer**.

### Agriculture — utilisation du matériel agricole

**Ce que ça fait.** Enregistre une utilisation journalière d'un engin (tracteur,
moissonneuse, pulvérisateur, outil) : heures utilisées et coût de carburant
optionnel. Les heures moteur cumulées de l'engin sont mises à jour
automatiquement.

**Où la trouver.** Même écran, onglet **Matériel**.

**Comment l'utiliser.**
1. Repérez l'engin concerné dans la liste.
2. Cliquez sur **Enregistrer une utilisation** sur sa ligne.
3. Choisissez la campagne (optionnel), la date, les heures utilisées et le coût
   de carburant (optionnel), puis enregistrez.

### Santé — réception (rechercher ou enregistrer un patient)

**Ce que ça fait.** Recherche un patient existant (par nom, CIN ou téléphone) ou
en crée un nouveau en quelques secondes. Le numéro de dossier est attribué
automatiquement par le système.

**Où la trouver.** Menu **SANTÉ → Réception** (`/sante/reception`).

**Comment l'utiliser.**
1. Pour rechercher : tapez un nom, un CIN ou un numéro de téléphone dans la
   barre de recherche, puis cliquez sur **Rechercher**.
2. Pour créer un nouveau patient : remplissez le formulaire « Nouveau patient »
   (nom, prénom, CIN, téléphone) et cliquez sur **Enregistrer**.

### Santé — rendez-vous et agenda multi-praticiens

**Ce que ça fait.** Planifie un rendez-vous du jour depuis la Réception,
visualise l'agenda multi-praticiens par colonnes, replanifie un rendez-vous en
le glissant-déposant vers un autre praticien, et marque un patient « arrivé »
(mise en salle d'attente). Le système refuse toujours un créneau déjà pris par
le même praticien ou la même salle.

**Où la trouver.** Menu **SANTÉ → Réception** (planification + arrivées du jour)
et **SANTÉ → Agenda** (`/sante/agenda`, vue multi-praticiens).

**Comment l'utiliser (depuis la Réception).**
1. Dans la section « Planifier un RDV aujourd'hui », renseignez l'identifiant du
   patient (affiché après une recherche ou création), choisissez un praticien et
   une heure.
2. Cliquez sur **Planifier**.
3. Le rendez-vous apparaît dans la liste « Aujourd'hui » ; cliquez sur **Patient
   arrivé** dès son arrivée.

**Comment l'utiliser (vue Agenda).**
1. Choisissez une date en haut de l'écran.
2. Chaque colonne correspond à un praticien ; chaque carte est un rendez-vous.
3. Pour replanifier un rendez-vous vers un autre praticien, glissez sa carte
   vers la colonne du praticien souhaité.

### Santé — nomenclature des actes médicaux

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Gère la liste des actes médicaux proposés (libellé,
catégorie, tarif de base) et permet de les activer ou désactiver sans jamais les
supprimer définitivement (un acte déjà utilisé ne peut plus être supprimé,
seulement désactivé).

**Où la trouver.** Menu **SANTÉ → Nomenclature des actes**
(`/sante/nomenclature-actes`).

**Comment l'utiliser.**
1. Pour ajouter un acte : utilisez le formulaire de création (libellé,
   catégorie, tarif de base TTC).
2. Pour retirer un acte de la liste active : action **Désactiver** sur sa ligne
   (et **Activer** pour le remettre en service).

### Immobilier — rentabilité par actif

**Ce que ça fait.** Affiche, pour un site ou un bâtiment, les indicateurs de
rentabilité : revenus, charges, travaux, marge nette et taux d'occupation, avec
un tableau du revenu par local.

**Où la trouver.** Menu **IMMOBILIER → Rentabilité**
(`/immobilier/rentabilite`).

**Comment l'utiliser.**
1. Dans le menu déroulant en haut de la page, sélectionnez un **site**.
2. Les indicateurs et le tableau par local s'affichent automatiquement.
3. Si aucune donnée n'apparaît, c'est que le site sélectionné n'a pas encore de
   patrimoine (bâtiments/locaux) enregistré. La page **Patrimoine** (premier
   lien du menu IMMOBILIER) permet de consulter l'arborescence Site → Bâtiment
   → Niveau → Local.

### Immobilier — budget de charges et régularisation annuelle

**Ce que ça fait.** Compare, poste par poste (ascenseur, gardiennage,
électricité des communs…), le budget prévu et les dépenses réelles d'un bâtiment
sur un exercice. Permet ensuite de calculer et d'émettre la régularisation
annuelle des charges auprès des locataires (facture complémentaire ou avoir,
selon le solde de chacun).

**Où la trouver.** Menu **IMMOBILIER → Charges** (`/immobilier/charges`).

**Comment l'utiliser.**
1. Sélectionnez un **bâtiment**, indiquez l'**exercice** (année), puis cliquez
   sur **Charger**.
2. Le tableau (poste / budgété / réel / écart %) et le graphique s'affichent.
3. Pour lancer la régularisation de fin d'année : cliquez sur **Lancer la
   régularisation**. Un aperçu apparaît, indiquant pour chaque bail s'il faut
   rembourser le locataire, lui facturer un complément, ou si le solde est
   neutre — rien n'est encore émis à ce stade.
4. Vérifiez l'aperçu, puis cliquez sur **Confirmer l'émission** pour créer
   réellement les factures et avoirs côté ventes. Cette étape est irréversible
   pour les lignes émises.

### Innovation — proposer une idée

**Ce que ça fait.** Permet à tout collaborateur connecté de soumettre une idée
(amélioration, suggestion), avec un contexte (ex. « CRM », « Stock »), une
description, la possibilité de l'enregistrer en brouillon (visible uniquement
par vous jusqu'à publication) ou de la lier à un devis, un ticket SAV ou un
chantier en cours.

**Où la trouver.** Menu **INNOVATION → Boîte à idées**, bouton pour proposer une
idée (`/innovation/proposer`).

**Comment l'utiliser.**
1. Remplissez le **titre** et la **description**. Le champ **contexte** suggère
   automatiquement les 5 contextes les plus utilisés.
2. Si une idée très similaire existe déjà, elle vous est proposée — vous pouvez
   voter pour elle au lieu de créer un doublon.
3. Cochez **Enregistrer en brouillon** pour la garder privée pour l'instant
   (publiable plus tard depuis sa page de détail).
4. Cliquez sur **Envoyer** (ou **Enregistrer en brouillon**).

### Innovation — consulter, voter, suivre

**Ce que ça fait.** Liste toutes les idées proposées dans la société (sauf les
brouillons des autres et les idées masquées), avec leur statut et le nombre de
votes. Permet de voter, de consulter le détail et l'historique, et — pour les
rôles Responsable/Administrateur — de faire avancer une idée dans son cycle de
vie (Ouverte → Examinée → Retenue → Réalisée / Fermée).

**Où la trouver.** Menu **INNOVATION → Boîte à idées** (`/innovation/idees`) ;
chaque idée a sa propre page de détail. La vue **Mes idées**
(`/innovation/mes-idees`) liste uniquement vos propositions et vos votes.

**Comment l'utiliser.**
1. Cliquez sur une idée pour ouvrir son détail.
2. Cliquez sur **Voter** pour la soutenir (vous ne pouvez pas voter pour vos
   propres idées).
3. Onglet **Historique** : tous les changements de statut et les notes.
4. Bouton **Lier à devis/ticket/chantier** : associez l'idée à un document
   existant.
5. Auteur d'un brouillon : bouton **Publier** pour le rendre visible à toute la
   société.
6. Responsable/Administrateur : boutons **Examiner**, **Retenir**, **Réaliser**,
   **Fermer** (avec note optionnelle) et **Masquer** (modération, sans
   suppression) selon le statut actuel.

### Innovation — tableau de bord

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Vue de pilotage : nombre d'idées par statut (ouvertes,
examinées, retenues, total) et graphique d'évolution du nombre d'idées proposées
par jour.

**Où la trouver.** Menu **INNOVATION → Tableau de bord**
(`/innovation/tableau-bord`).

**Comment l'utiliser.** Cliquez sur une carte (ex. « Ouvertes ») pour aller
directement à la liste filtrée correspondante.

### Envoyer un retour produit (bouton flottant)

**Ce que ça fait.** Un petit bouton discret, présent sur tous les écrans, permet
d'envoyer directement un retour à l'équipe fondatrice (bug, idée d'amélioration,
remarque sur la performance ou l'ergonomie) — ce canal est privé, visible
seulement par l'équipe fondatrice, pas par vos collègues.

**Où la trouver.** Bouton flottant visible sur toutes les pages (généralement en
bas de l'écran).

**Comment l'utiliser.**
1. Cliquez sur le bouton, choisissez un thème (UX, Performance, Fonctionnalité,
   Bug, Autre), rédigez votre message.
2. Envoyez — votre retour est traité en interne par l'équipe fondatrice.

### FP&A — saisie budgétaire (cycles par département)

*Le menu **FP&A** est visible pour les profils Directeur et Administrateur.*

**Ce que ça fait.** Crée un cycle budgétaire (ex. « Budget 2027 »), l'ouvre à la
saisie, permet de remplir le budget mois par mois et par catégorie pour chaque
département, puis de le soumettre pour validation. Une fois le cycle clôturé,
plus aucune ligne ne peut être modifiée.

**Où la trouver.** Menu **FP&A → Saisie budgétaire** (`/fpa/saisie`).

**Comment l'utiliser.**
1. Créez ou sélectionnez un cycle budgétaire.
2. Cliquez sur **Ouvrir à la saisie** pour permettre aux responsables de
   département de remplir leurs lignes.
3. Chaque responsable remplit ses lignes (mois × catégorie : masse salariale,
   marketing, IT, frais généraux, investissement, autre).
4. Une fois prêt, le responsable clique sur **Soumettre** — ses lignes sont
   verrouillées en attendant la décision.
5. Un Directeur valide ou rejette (un rejet réouvre la saisie avec le motif
   visible).
6. Un cycle peut être dupliqué d'une année sur l'autre (bouton **Dupliquer**)
   et exporté en Excel.

À savoir : un responsable de département ne voit et ne modifie que le budget de
son propre département (et de ses sous-départements) ; seuls Directeur et
Administrateur voient tout.

### FP&A — prévisions glissantes

**Ce que ça fait.** Génère automatiquement une projection sur 12 ou 18 mois à
partir de la moyenne réelle des 3 derniers mois comptables, catégorie par
catégorie. Tout ajustement saisi à la main est conservé lors d'une nouvelle
génération, jamais écrasé.

**Où la trouver.** Menu **FP&A → Prévisions glissantes** (`/fpa/previsions`).

**Comment l'utiliser.**
1. Choisissez un département (ou laissez vide pour une vue globale) et un
   horizon (12 ou 18 mois).
2. Cliquez sur **Générer** — les mois futurs se remplissent à partir du réel
   comptable.
3. Ajustez manuellement une valeur si besoin : elle est marquée « manuelle » et
   ne sera plus écrasée par une régénération future.

### FP&A — analyse des écarts

**Ce que ça fait.** Compare, pour un cycle et un mois donnés, le budget
**prévu**, le **réel** comptable et la dernière **prévision** glissante, par
département et par catégorie. Les dépassements de plus de 10 % sont surlignés.

**Où la trouver.** Menu **FP&A → Analyse des écarts** (`/fpa/variance`).

**Comment l'utiliser.**
1. Sélectionnez un cycle budgétaire et un mois, puis cliquez sur **Actualiser**.
2. Le tableau prévu / réel / prévision s'affiche ; les lignes en dépassement
   apparaissent en rouge.
3. Cliquez sur une ligne pour ouvrir son détail et lire ou ajouter un
   commentaire expliquant l'écart (utile pour la revue avec la Direction).

### FP&A — scénarios budgétaires (« et si… »)

**Ce que ça fait.** Teste des variantes du budget (« +10 % sur le marketing »,
« gel des recrutements ») sans jamais modifier le budget réel tant que le
scénario n'est pas promu. Comparaison côte à côte de plusieurs scénarios et
analyse de sensibilité.

**Où la trouver.** Menu **FP&A → Scénarios** (`/fpa/scenarios`).

**Comment l'utiliser.**
1. Créez un scénario sur un cycle budgétaire et donnez-lui un nom.
2. Ajoutez des variations (pourcentage ou montant) sur une catégorie ou une
   ligne précise, avec une raison.
3. Comparez plusieurs scénarios côte à côte pour voir l'écart total par rapport
   au budget de base.
4. Si un scénario doit devenir la nouvelle référence, cliquez sur **Promouvoir
   en base** — il remplace les montants du cycle (l'ancien scénario de base est
   archivé automatiquement).

### FP&A — tableau de bord

**Ce que ça fait.** Vue exécutive d'un cycle budgétaire : revenu prévisionnel,
dépenses totales, marge brute prévisionnelle, revenu déjà engagé (carnet de
commandes), cascade revenu → charges → marge, et répartition des dépenses par
catégorie.

**Où la trouver.** Menu **FP&A → Tableau de bord** (`/fpa/dashboard`).

**Comment l'utiliser.** Sélectionnez un cycle budgétaire dans la liste
déroulante ; les indicateurs et graphiques se chargent automatiquement.

### Assurances d'entreprise (registre des polices)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Liste toutes les polices d'assurance de la société (RC pro,
décennale, multirisque, cyber, homme-clé — hors assurances véhicules, gérées
dans la Flotte), avec filtre par type et statut, badge coloré d'échéance (rouge
si moins de 7 jours, ambre si moins de 30 jours) et un bandeau d'alerte si des
polices ou attestations expirent bientôt.

**Où la trouver.** Menu **Assurances → Polices** (`/assurances`).

**Comment l'utiliser.**
1. Ouvrez l'écran « Polices » ; le bandeau en haut signale les échéances
   proches.
2. Filtrez par type ou par statut (active, suspendue, résiliée, expirée) si
   besoin.
3. Cliquez sur une police pour ouvrir sa fiche détaillée : onglets **Garanties**
   (plafonds d'indemnisation et franchises), **Actifs couverts**, **Échéancier
   de primes** (avec un bouton « Proposer écriture » pour transmettre une
   échéance à la comptabilité), **Attestations** et **Historique**.
4. Le bouton **Renouveler** en haut de la fiche crée automatiquement la police
   suivante (mêmes garanties, mêmes actifs couverts, échéancier régénéré) et
   archive l'ancienne en « résiliée ».

À savoir : cet écran permet aujourd'hui de consulter et renouveler des polices
existantes ; la création d'une toute nouvelle police se fait avec l'aide de
votre équipe technique.

---

## Import de données

### Import de fichiers (CSV / Excel)

**Ce que ça fait.** Importe en masse des fiches depuis un fichier CSV ou Excel,
avec un aperçu des 10 premières lignes et la correspondance colonne → champ
avant toute création réelle. Rien n'est jamais écrasé silencieusement : les
doublons sont signalés et ignorés, sauf si vous choisissez explicitement le mode
« mise à jour » ou « créer ou mettre à jour » (disponible pour les leads et les
clients).

Fiches prises en charge aujourd'hui : leads, clients, produits, fournisseurs,
équipements.

**Où la trouver.** Bouton **Importer** présent sur les listes concernées :
Produits (Stock), Fournisseurs (Stock), Équipements (Après-vente), Clients (CRM)
et Leads (CRM).

**Comment l'utiliser.**
1. Ouvrez la liste concernée (ex. **STOCK → Produits**) et cliquez sur
   **Importer**.
2. Choisissez le mode d'import : « Créer seulement » (par défaut — les doublons
   sont ignorés), « Mettre à jour seulement » ou « Créer ou mettre à jour »
   (ces deux derniers uniquement pour les leads et les clients).
3. Sélectionnez votre fichier `.csv` ou `.xlsx` : un aperçu des 10 premières
   lignes s'affiche, avec les colonnes reconnues automatiquement et celles qui
   ne l'ont pas été (vérifiez vos en-têtes si des colonnes manquent).
4. (Optionnel) Donnez un nom à cette correspondance de colonnes pour la
   réutiliser automatiquement lors d'un prochain import du même type de
   fichier.
5. Cliquez sur **Importer N ligne(s)**.
6. Le résultat s'affiche : nombre de fiches créées, mises à jour et ignorées
   (avec la raison de chaque ligne ignorée). Si des lignes ont échoué, vous
   pouvez télécharger un fichier CSV contenant uniquement ces lignes, prêt à
   corriger et ré-importer.

### Export & sauvegarde des données

**Ce que ça fait.** Exporte les données de la société (par objet ou en
sauvegarde complète ZIP), sans jamais inclure les prix d'achat ni les marges.

**Où la trouver.** Menu **Paramètres → Export & sauvegarde**.

**Comment l'utiliser.**
1. Cochez les objets à exporter (tout est coché par défaut pour une sauvegarde
   complète en un clic).
2. Choisissez le format d'export.
3. Cliquez sur **Sauvegarder** pour télécharger un fichier ZIP contenant tous
   les objets choisis, ou exportez un objet individuel si vous n'avez besoin que
   d'un seul fichier.

---

## Administration & Paramètres

Ce chapitre s'adresse principalement aux administrateurs. La gestion des
utilisateurs et des rôles est décrite au chapitre « Premiers pas ».

### Profil de l'entreprise (RIB, TVA, identifiants légaux, logo)

**Ce que ça fait.** La fiche d'identité unique de votre société : nom, adresse,
coordonnées, RIB/banque, identifiants légaux marocains (ICE, IF, RC, Patente,
CNSS), logo, signature électronique et couleur d'accent. Ces informations
apparaissent automatiquement dans l'en-tête et le pied de page de tous vos devis
et factures PDF — vous ne les saisissez qu'une seule fois ici.

**Où la trouver.** Menu **Paramètres**, onglet **Société & identité**
(`/parametres`).

**Comment l'utiliser.**
1. Renseignez le nom, l'adresse, l'e-mail et le téléphone de l'entreprise.
2. Dans le bloc « Informations légales », entrez votre RIB/IBAN et votre banque.
3. Dans « Identifiants légaux (Maroc) », renseignez l'ICE (obligatoire sur
   facture — un avertissement s'affiche tant qu'il est vide), l'IF, le RC, la
   Patente et le numéro CNSS.
4. Dans « Apparence PDF », choisissez la couleur principale qui habillera vos
   documents.
5. Téléversez votre logo (en-tête des PDF) et votre signature électronique (bas
   des PDF) dans le bloc « Médias ».
6. Cliquez sur **Enregistrer** — un message « Enregistré ! » confirme la
   sauvegarde.

### Structure de l'entreprise (entités)

*Réservé au rôle Administrateur.*

**Ce que ça fait.** Représente l'organisation interne de votre société sous
forme d'arbre (holding → filiales → agences), avec autant de niveaux que
nécessaire. Chaque entité a un nom et un code unique.

**Où la trouver.** Menu **Entités** (`/parametres/entites`).

**Comment l'utiliser.**
1. Cliquez sur **Ajouter une entité** pour lancer l'assistant en 3 étapes :
   nom et code, entité « parente » éventuelle (laissez vide pour créer une
   racine), puis récapitulatif et **Créer**.
2. L'arbre affiche vos entités avec une indentation par niveau.
3. Pour renommer une entité : bouton **Renommer** sur sa ligne.
4. Pour la retirer : bouton **Désactiver** (confirmation demandée) — une entité
   désactivée n'est jamais supprimée définitivement et peut être réactivée par
   le support.
5. Le système empêche automatiquement de créer une boucle (rattacher une entité
   à l'un de ses propres descendants).

### API & Webhooks (connecter d'autres logiciels)

**Ce que ça fait.** Connecte TAQINOR OS à d'autres logiciels : vous générez des
« clés API » que des applications externes peuvent utiliser pour lire vos
leads, devis, factures et chantiers (jamais les prix d'achat), et vous
configurez des « webhooks » — des notifications automatiques envoyées à une
autre application dès qu'un événement se produit chez vous (nouveau lead, devis
accepté, chantier terminé, facture payée…).

**Où la trouver.** Menu **Paramètres**, onglet **API & Webhooks**.

**Comment l'utiliser.**
- **Créer une clé API** : cliquez sur « Nouvelle clé », donnez-lui un nom et
  cochez les droits qu'elle doit avoir (lire les leads, lire les devis…). La
  clé complète ne s'affiche **qu'une seule fois**, au moment de la création —
  notez-la immédiatement.
- **Faire tourner une clé** sans interrompre le service : une nouvelle clé est
  créée, l'ancienne reste valable un temps de grâce avant d'être coupée.
- **Révoquer / supprimer une clé** si elle n'est plus utilisée ou a été
  compromise.
- **Créer un webhook** : indiquez l'adresse de l'application qui doit recevoir
  la notification et cochez les événements à surveiller.
- **Tester un webhook** : un bouton « Test » envoie une notification factice
  pour vérifier que votre système externe la reçoit bien.
- **Consulter l'historique des envois** (« Livraisons ») et **rejouer** un
  envoi qui a échoué.
- **Consulter la documentation** (bouton Docs) : une page de référence en
  français pour le développeur externe.
- **Essayer un endpoint** (bouton « Essayer », bac à sable) : teste un appel
  d'API directement depuis l'écran, sans écrire de code.
- **Voir le plan d'utilisation** et la consommation du jour et du mois.

### Workflows (circuits de validation)

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Un workflow est un circuit de validation en plusieurs étapes
(par exemple : « clôture d'une non-conformité » = vérification, puis approbation
du responsable, puis clôture). L'écran permet d'installer des modèles de
circuits déjà préparés et de suivre les circuits en cours.

**Où la trouver.** Menu **WORKFLOW → Workflows** (`/workflow`).

**Comment l'utiliser.**
1. Onglet **Modèles** : la liste des circuits prêts à l'emploi (relance devis,
   accueil chantier, rappel garantie…). Cliquez sur **Installer** en face du
   modèle voulu — il est activé pour votre société.
2. Onglet **Instances en cours** : suivez les circuits déjà lancés. Chaque étape
   en attente affiche son échéance ; un retard est signalé visuellement.
3. Sur une étape qui vous attend, cliquez sur **Approuver** ou **Rejeter** pour
   faire avancer le circuit. Ces étapes apparaissent aussi dans la boîte
   d'approbations centralisée (chapitre « Rapports & Tableaux de bord »).

### Tâches planifiées

*Réservé aux profils Responsable et Administrateur.*

**Ce que ça fait.** Affiche la liste des tâches automatiques du système
(sauvegardes, relances, nettoyages…) avec leur cadence, et permet de lancer une
tâche manuellement sans attendre son horaire.

**Où la trouver.** Menu **WORKFLOW → Tâches planifiées**
(`/workflow/taches-planifiees`).

**Comment l'utiliser.**
1. Consultez le tableau : nom de la tâche, cadence (par ex. « tous les jours à
   3 h ») et si elle est active.
2. Pour forcer une exécution immédiate (réservé aux administrateurs), utilisez
   le bouton d'exécution en face de la tâche. Si le système de traitement est
   momentanément indisponible, un message clair vous l'indique — aucune donnée
   n'est perdue.

### Santé du compte

*Réservé au rôle Administrateur.*

**Ce que ça fait.** Donne un score global sur 100 de la « santé » de votre
espace ERP, calculé à partir de 3 critères : la complétude de votre
configuration (profil société, rôles personnalisés, modèles de message), le
niveau d'usage récent de l'équipe, et le volume de données réelles. Des
recommandations concrètes s'affichent pour améliorer le score.

**Où la trouver.** Menu **Administration avancée → Santé du compte**
(`/admin/sante`).

**Comment l'utiliser.**
1. Le score global s'affiche en grand, avec le détail des 3 sous-scores.
2. Consultez la liste de recommandations à droite pour savoir quoi améliorer en
   priorité.
3. Le score est recalculé automatiquement chaque jour ; revenez régulièrement
   pour suivre son évolution.

### Environnements de test (sandbox)

*Réservé au rôle Administrateur.*

**Ce que ça fait.** Crée une copie de test isolée de votre société (identité +
réglages), pour essayer des changements sans risque sur vos vraies données.
L'environnement expire automatiquement après une durée définie et peut être
prolongé deux fois.

**Où la trouver.** Menu **Administration avancée → Sandbox** (`/admin/sandbox`).

**Comment l'utiliser.**
1. Cliquez sur **Créer un environnement de test** (disponible sous quelques
   minutes).
2. Le statut s'affiche (« En création », « Prêt », « Expiré » ou « Échec »)
   avec sa date d'expiration.
3. Une fois « Prêt », vous pouvez cliquer sur **Prolonger (+14 j)** jusqu'à deux
   fois avant l'expiration.
4. Un seul environnement de test actif est autorisé à la fois par société.

### Packages de configuration (export/import de réglages)

*Réservé au rôle Administrateur.*

**Ce que ça fait.** Exporte votre configuration (rôles personnalisés, champs
personnalisés, modèles de message — **jamais** vos données clients) dans un
fichier, pour la réutiliser sur une autre société ou la sauvegarder. À l'import,
un aperçu détaillé des changements est toujours affiché avant toute application.

**Où la trouver.** Menu **Administration avancée → Packages config**
(`/admin/config-packages`).

**Comment l'utiliser.**
1. Pour exporter : cliquez sur **Exporter la config actuelle**, donnez un nom au
   package, confirmez.
2. Pour importer un package reçu : cliquez sur **Importer…** et sélectionnez le
   fichier. Un encart affiche l'aperçu des changements (ajouts, modifications,
   suppressions par catégorie).
3. Vérifiez l'aperçu, puis cliquez sur **Appliquer** (confirmation demandée) ou
   **Annuler**.

### Diagnostic & pack support

*Réservé au rôle Administrateur.*

**Ce que ça fait.** Affiche un instantané non sensible de votre espace (nombre
d'utilisateurs, environnements de test actifs, packages exportés, dernière
connexion) et permet de générer un fichier ZIP à joindre à une demande de
support technique — sans jamais inclure de donnée client.

**Où la trouver.** Menu **Administration avancée → Diagnostic**
(`/admin/diagnostic`).

**Comment l'utiliser.**
1. Consultez le tableau d'informations générales de votre espace.
2. En cas de besoin d'assistance, cliquez sur **Exporter le support bundle
   (.zip)** : le fichier se télécharge — joignez-le à votre demande de support.

### Réglages Administration

*Réservé au rôle Administrateur.*

**Ce que ça fait.** Centralise les réglages transverses du module
Administration : durée par défaut d'un environnement de test, délai de grâce
avant purge, seuil d'alerte sur le nombre de sièges, durée de conservation des
statistiques d'usage, et autorisation (ou non) de créer des environnements de
test.

**Où la trouver.** Menu **Administration avancée → Réglages admin**
(`/admin/reglages-admin`).

**Comment l'utiliser.**
1. Ajustez la durée par défaut d'un environnement de test (7 à 30 jours), le
   délai de grâce avant sa suppression définitive, le seuil d'alerte sièges (%)
   et la durée de rétention des statistiques d'usage.
2. Utilisez l'interrupteur pour autoriser ou bloquer la création de nouveaux
   environnements de test.
3. Cliquez sur **Enregistrer**.

### Console des sociétés (réservée au fondateur)

**Ce que ça fait.** Vue d'administration globale de toutes les sociétés de la
plateforme : statut (actif / suspendu / fermeture), compteurs d'usage et notes
internes. C'est un outil de pilotage de la plateforme, accessible uniquement au
super-administrateur (le serveur refuse tout autre compte).

**Où la trouver.** Menu **Administration → Tenants** (`/admin/tenants`).

**Comment l'utiliser.**
1. Ouvrez la console : la liste des sociétés s'affiche avec leur statut et leur
   usage.
2. Pour changer un statut (par ex. suspendre une société), utilisez le contrôle
   de statut sur sa ligne.
3. Pour annoter une société, ajoutez un commentaire libre dans le champ prévu.

---

## Annexe : couverture du guide

Ce guide couvre l'ensemble des fonctionnalités de TAQINOR OS vérifiées comme
pleinement opérationnelles à la date du 18 juillet 2026, à l'issue d'un audit
complet, module par module, de l'application. Les fonctionnalités encore en
cours de construction — ou construites mais pas encore accessibles depuis un
écran — en sont volontairement exclues : elles seront ajoutées au guide au fur
et à mesure de leur mise à disposition. Si un écran décrit ici a évolué depuis
cette date, fiez-vous à l'interface, et n'hésitez pas à envoyer un retour via le
bouton flottant de l'application.

