# Vérifie AERR — contre-visite du parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran », 14/11/2026

Commande `loop audit` (14/11). L'audit de parcours PF12 (11/11, PR #1374) avait déposé AERR1-131. C'est la première
contre-visite du groupe, due à mi-parcours : 49 tâches cochées sur 52 constructibles (94 %). Les 49 ont été relues. Rien n'a
été construit ni déployé.

- **Bilan.** 36 ok, 10 partielles, 2 régressions, 1 fausse. Aucun S1 nouveau.
- **Quatre S2.** Deux régressions introduites par une tâche (AERR21, AERR87), une tâche partielle (AERR72) et un défaut
  antérieur trouvé en relisant AERR71 (réassignation d'un lead refusée annoncée comme réussie).
- **Le S1 du dossier PF12 n'est pas couvert ici.** Il est porté par AERR25, qui n'est pas cochée : son code est livré et
  attend sa preuve en direct (§6).

## 0. Préconditions

- **SHA.** `origin/main` = `47f925be1`. Les 57 commits relus sont tous ancêtres de ce SHA (`git merge-base --is-ancestor`).
- **Registre.** PF12 `erreurs-ecran`, groupe AERR, 49 tâches cochées sur 52 constructibles (94 %), première passe.
  62 autres tâches sont marquées « code livré, preuve en direct due » ; AERR69, AERR112 et AERR131 restent à faire.
- **Échantillon.** Toutes les tâches cochées, soit 49. Le dossier ne classe aucune d'elles P0 ni S1.
- **Méthode.** Texte de chaque tâche, commit(s), code sur `origin/main`, test nommé lu avec un mutant raisonné, jumeaux.
  Quatre sondes hôtes écrites et jouées sur les écarts S2 (§3). Aucune pile, aucun test lancé, aucune production consultée.

## 1. Vérificateurs (5 lots, opus, effort élevé, frais)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **36** | AERR8, 10, 14, 15, 16, 19, 20, 22, 30, 31, 54, 55, 60, 63, 66, 67, 68, 73, 74, 75, 76, 79 (effet de bord), 81, 82, 83, 84, 85, 86, 88, 89, 90, 91, 92, 115, 123, 126 |
| partiel | **10** | AERR13, 17, 18, 51, 53, 62, 70, 72, 80, 93 |
| régression | **2** | AERR21, AERR87 |
| faux | **1** | AERR71 |
| non-fait / déjà-présent | **0** | — |

Commits relus :
- **Factures.** AERR8 `5ef6d56c8e`, AERR10 `bfbe09f8cd`, AERR13 `77ac4009d6`, AERR15 `854cc04ba3`, AERR17 `1a5e7803ae`,
  AERR18 `ed24d1ab0d`, AERR19 `76bab19e8e`, AERR20 `f10b45f52e`, AERR21 `7e5cfaf29d`, plus `aeaa5e9274` (tests réalignés).
- **Devis, chantiers et achats.** AERR14 `b522b0f386`, AERR16 `298e952a0c`, AERR22 `f9c393fe09`, AERR30 `caf7109d2f`, AERR81
  `ef0d187e4b` et `4ef1a04b81`, AERR83 `cc6e57dd4b`, AERR85 `8758532009`, AERR86 `91abf4ff25` et `467d734ce5`, AERR91
  `607b560da5` et `73a9625129`, AERR93 `4716a0f4a0`.
- **Stock et SAV.** AERR67 `674843aaaa`, AERR76 `86f1ebba4e`, AERR80 `151e614ac2`, AERR84 `fea0e956cc`, AERR87 `c3aeaaf6a7`,
  AERR88 `fc23409bac`, AERR89 `608adf310c`, AERR90 `3e0b50a0bf`, AERR31 `02183ad3bd` et `1d5b9f6235`, AERR79 `52c2a33b9a`,
  AERR82 `1e609d65bc` et `37541d1583`, AERR92 `64566e7412`.
- **Briques partagées et Paramètres.** AERR51 `f91857fc9b`, AERR53 `532c16666d`, AERR63 `788c6cb35a`, AERR66 `827b862748`,
  AERR68 `a9ea6d7cbe`, AERR70 `1fcf91037f`, AERR71 `dc3ea98ea2`, AERR72 `c3bc1a4d6a` et `1c76a4c5c2`, AERR74 `922f3fd7b4`,
  AERR75 `173ca15928`, AERR123 `60b79680d5`.
- **Administration, GED, visites, générateur.** AERR54 `ca41aba6d0`, AERR55 `3617e634bb`, AERR60 `c41277cf61`, AERR62
  `882ffbac1a`, AERR73 `9997cc7880`, AERR115 `004068ab09` et `ae607e1c69`, AERR126 `714b847bcb`.

Les verdicts « ok » portent sur le texte de chaque tâche. Un « ok » peut laisser un écart hors de ce texte : AERR79, AERR85 et
AERR91 en portent un (§4).

## 2. Tests nommés

- **Les tests nommés des 49 tâches existent** et sont comportementaux : écran rendu, geste joué, état affiché ou appel relu.
- **Trois tests ne voient pas le cas qui casse.**
  - AERR21 rend la boîte « Notes de débit » une seule fois, sur une seule facture.
  - AERR71 bouchonne `apply` avec une erreur axios à `response` ; aucun des appelants réels ne rejette sous cette forme.
  - AERR70 bouchonne le même type d'erreur ; le seul écran réel (catalogue du stock) rejette avec le corps du refus.
- **Clauses du « fini quand » sans test.** Le retrait d'un prix fournisseur (AERR80). La clause outillage d'AERR85. La
  seconde moitié d'AERR18 (encaissement groupé le lendemain). Deux clauses sur trois d'AERR22. Deux gestes sur trois d'AERR83.
  Le code de ces clauses a été relu et il est juste, sauf AERR18 (§4).
- **Exécution.** Aucun test n'a été lancé ici. Pour AERR54, 55, 60, 62, 73, 115 et 126, un vérificateur a lu la CI des PR de
  merge (#1391, #1389) : tranches vitest et lint verts. Pour les autres, la seule preuve d'un vert est la CI de `main`.

## 3. Sondes rejouées et S2 relus

Les quatre sondes ont été rejouées par le rédacteur sur `47f925be1` (`PYTHONIOENCODING=utf-8 python <sonde>`). Aucune n'affirme
sur son propre bouchon : trois lisent le vrai source de l'écran, une exécute la vraie fonction JS sous node.

| Sonde | Sortie rejouée | Ce qu'elle prouve |
|---|---|---|
| `docs/audits/sondes/AERR/C-AERR-VER1-100.py` | `repro: true` | lecture ratée sans vidage de `notes` ; alerte masquée dès que `notes` n'est pas vide ; boîte montée en permanence, sans `key` ni remise à zéro à l'ouverture |
| `docs/audits/sondes/AERR/C-AERR-VER1-140.py` | `repro: true` | la vraie `erreursEntiersProduit` rend « Saisissez un nombre entier. » pour un stock de -3 ; `validate` l'applique en édition, où le champ est grisé |
| `docs/audits/sondes/AERR/C-AERR-VER1-160.py` | `repro: true` | 4 sections gardées ; 8 sections autonomes à brouillon encore démontées au changement d'onglet |
| `docs/audits/sondes/AERR/C-AERR-VER1-161.py` | `repro: true` | le `catch` de `reassign` ne relance pas ; le kanban la passe comme `apply` à `mutateWithUndo` |

Les quatre défauts ont aussi été relus dans le code par le rédacteur :
- **AERR21.** `NoteDebitDialog.jsx::NoteDebitDialog` remet à zéro `loadedFactureId` à l'ouverture, jamais `notes` ni
  `lectureKo`. `FactureList.jsx` monte la boîte sans `key` et ne change que la prop `facture`. Ouvrir A puis B avec une
  lecture en échec affiche donc les notes de A sous le titre de B, avec leurs boutons « PDF » et « Annuler ».
- **AERR87.** `validationEntiers.js::erreursEntiersProduit` contrôle `quantite_stock` par `^\d+$`. `ProduitForm.jsx::validate`
  l'applique sans exception d'édition. Or le champ est `disabled={isEdit}` et n'est pas envoyé en édition. Une fiche à stock
  négatif ne s'enregistre plus, quel que soit le champ modifié. `Produit.quantite_stock` accepte le négatif.
- **AERR72.** `ParametresEntreprise.jsx::ParametresEntreprise` n'enveloppe que documents, tarification, données et statuts
  dans `SectionGardee`. Les huit autres sections à brouillon sont encore rendues par `{tab === '…' && …}`, dont les modèles
  brandés (corps de modèle en édition) et les traductions.
- **Réassignation.** `LeadsPage.jsx::reassign` attrape le refus et ne fait qu'un `console.warn`. `KanbanView.jsx::reassignAvecUndo`
  la passe comme `apply` à `mutateWithUndo`, qui ne voit donc jamais l'échec. Le toast d'erreur global sort, puis « Responsable
  modifié. » avec « Annuler ». La carte garde l'ancien responsable. Le défaut est antérieur à AERR117 et hors des tâches.
- **AERR71 faux, confirmé.** `mutateWithUndo` ne tait le toast local que si l'erreur porte `response`. Les thunks
  `updateLead`, `archiveLead` et `restoreLead` rejettent avec `err.response?.data ?? err.message` ; `.unwrap()` rend ce corps.
  Le doublon de toast du constat 040 du dossier PF12 reste donc sur la liste des leads.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AERR-VER1-100 | AERR21 | S2 | La boîte « Notes de débit » d'une facture B affiche les notes de la facture A quand la lecture de B échoue (`frontend/src/pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog`) | `docs/audits/sondes/AERR/C-AERR-VER1-100.py` (`repro: true`) | AERR133 |
| C-AERR-VER1-101 | AERR17 | S3 | « Émettre » d'une facture de vente (onglet Devis de la fiche lead, liste des devis) attribue un numéro légal sans confirmation (`frontend/src/features/ventes/vente/LigneFactureVente.jsx::LigneFactureVente`) | STATIQUE | AERR137 |
| C-AERR-VER1-102 | AERR18 | S3 | `today` figé au chargement encore lu par le Kanban des factures et le compteur « à échoir » (`frontend/src/pages/ventes/FactureList.jsx::FactureList`) | STATIQUE | AERR138 |
| C-AERR-VER1-103 | AERR13 | S3 | Refus serveur sur `repartition` de l'encaissement groupé en texte fixe, jamais sous la part de la facture (`frontend/src/pages/ventes/factureList/useFactureGestes.js::useFactureGestes`) | STATIQUE | AERR139 |
| C-AERR-VER1-120 | AERR93 | S3 | Aucun appelant de `ListeEtat` ne passe `onRetry` : « Réessayer » n'apparaît nulle part (`frontend/src/features/installations/ParametrageKits.jsx::NomenclatureTab`) | STATIQUE | AERR140 |
| C-AERR-VER1-121 | AERR91 | S3 | Une note tapée sur la fiche du chantier A part sur le chantier B quand la fiche suit B (`frontend/src/pages/installations/InstallationDetail.jsx::InstallationDetail`) | STATIQUE | AERR145 |
| C-AERR-VER1-122 | AERR85 | S3 | Le refus d'un outil reste affiché à l'ouverture d'un autre outil ; la clause outillage n'a pas de test (`frontend/src/pages/outillage/OutillagePage.jsx::OutillagePage`) | STATIQUE | AERR146 |
| C-AERR-VER1-140 | AERR87 | S2 | Une fiche produit à stock négatif ne peut plus être enregistrée : erreur sous un champ grisé (`frontend/src/pages/stock/validationEntiers.js::erreursEntiersProduit`) | `docs/audits/sondes/AERR/C-AERR-VER1-140.py` (`repro: true`) | AERR132 |
| C-AERR-VER1-141 | AERR80 | S3 | Le retrait d'un prix fournisseur, objet du « fini quand », n'a aucun test (`frontend/src/pages/stock/useRetraitPrixFournisseur.jsx::useRetraitPrixFournisseur`) | STATIQUE | AERR142 |
| C-AERR-VER1-142 | AERR79 | S3 | « Note non enregistrée. » effacé aussitôt par la relecture (`frontend/src/pages/sav/TicketChecklistPanel.jsx::TicketChecklistPanel`) | STATIQUE | AERR144 |
| C-AERR-VER1-160 | AERR72 | S2 | Huit sections des Paramètres perdent encore leur saisie au changement d'onglet (`frontend/src/pages/parametres/ParametresEntreprise.jsx::ParametresEntreprise`) | `docs/audits/sondes/AERR/C-AERR-VER1-160.py` (`repro: true`) | AERR134 |
| C-AERR-VER1-161 | hors tâche (lu avec AERR71) | S2 | Réassignation refusée sur le kanban des leads : toast d'erreur puis « Responsable modifié. » + « Annuler » (`frontend/src/pages/crm/leads/LeadsPage.jsx::LeadsPage`) | `docs/audits/sondes/AERR/C-AERR-VER1-161.py` (`repro: true`) | AERR135 |
| C-AERR-VER1-162 | AERR71, AERR70 | S3 | Un refus rejeté par `.unwrap()` n'est pas reconnu : toast doublé sur la liste des leads, message générique dans la cellule du catalogue (`frontend/src/lib/mutateWithUndo.js::mutateWithUndo`) | STATIQUE | AERR136 |
| C-AERR-VER1-163 | AERR53 | S3 | Toasts locaux encore doublés (champs personnalisés, webhooks, notifications) ; refus 404 devenu muet (`frontend/src/pages/parametres/NotificationsAdminSection.jsx::RoutingRulesPanel`) | STATIQUE | AERR143 |
| C-AERR-VER1-164 | AERR66 (jumeau) | S3 | Règles de routage, jours fériés, annonces et gabarits WhatsApp supprimés d'un clic (`frontend/src/pages/parametres/NotificationsAdminSection.jsx::RoutingRulesPanel`) | STATIQUE | AERR147 |
| C-AERR-VER1-165 | AERR74 (jumeau) | S3 | La boîte « Variante » arrondit le pourcentage de la société (17,5 devient 18) (`frontend/src/pages/ventes/DevisList.jsx::DevisList`) | STATIQUE | AERR148 |
| C-AERR-VER1-180 | AERR62 | S3 | Cinq onglets de Sécurité & identité et l'onglet Campagnes disent « Aucun… » quand la lecture échoue (`frontend/src/pages/admin/SecuriteIdentitePage.jsx::ReseauTab`) | STATIQUE | AERR141 |

**Pourquoi ces gravités.**
- **C-AERR-VER1-100 (S2).** La donnée d'un objet est montrée sous un autre : les notes de débit de A sous le titre de B, avec
  « Annuler » sur un document d'argent. Pas S1 : l'annulation passe par une boîte de confirmation.
- **C-AERR-VER1-140 (S2).** Un écran de travail est bloqué. Toute modification d'une fiche à stock négatif est refusée, sous
  un champ que l'utilisateur ne peut pas corriger. Il ne peut que fermer et perdre sa saisie.
- **C-AERR-VER1-160 (S2, le constat 041 du dossier PF12 était S3).** Le S2 est maintenu. C'est une perte de saisie réelle,
  sans avertissement, sur un clic d'onglet ordinaire. Le dossier PF12 classe S2 le même mécanisme ailleurs : un formulaire long
  fermé sans garde (constats 074 et 075), la fiche lead quittée sans question (constat 052). Les sections restantes portent les
  plus longs textes libres des Paramètres : corps des modèles brandés, traductions. Le S3 d'origine tenait à l'écran, peu
  fréquenté ; la fréquence n'est pas un critère de la grille.
- **C-AERR-VER1-161 (S2).** Une erreur avalée laisse croire à un succès : « Responsable modifié. » s'affiche après le refus. Le
  toast d'erreur global sort aussi, mais l'écran dit les deux. Défaut antérieur à AERR117, hors du texte des tâches.
- **Les S3.** Messages doublés, effacés ou génériques, confirmations manquantes sur des gestes réversibles ou sans argent,
  états latents (la fiche chantier ne change de chantier qu'en cas rare), tests manquants sur une clause du « fini quand ».
  « Émettre » (C-AERR-VER1-101) reste S3, comme le constat 015 du dossier PF12 qu'il double.
  La variante (C-AERR-VER1-165) arrondit une valeur LUE dans la configuration, pas un nombre tapé : la règle du générateur
  n'est pas violée, mais les variantes partent à 18 % au lieu de 17,5 %.

**Routage.** Chaque tâche a un seul propriétaire (`check_ownership.py --owner-of`) :
- AERR132, AERR142 → stock ;
- AERR133, AERR137, AERR138, AERR139 → facturation ;
- AERR134, AERR143, AERR147 → paramètres ;
- AERR135 → lead ;
- AERR136 → deploy (`lib/` et `ui/`) ;
- AERR140, AERR145, AERR146 → chantiers ;
- AERR141 → sécurité ;
- AERR144 → SAV ;
- AERR148 → devis.

AERR70 et AERR71 sont regroupés en une tâche : même brique propriétaire, même cause (la forme du rejet de `.unwrap()`).

**Réfuté ou déjà porté.** Aucun écart proposé n'est réfuté. Aucun n'est porté par une tâche ouverte : greps sur
`docs/plans/*.md` (`LigneFactureVente`, `openVarianteModal`, `NotificationsAdminSection`, `SecuriteIdentitePage`,
`reassignAvecUndo`, `SectionGardee`, `erreursEntiersProduit`, `noteBody`, `useRetraitPrixFournisseur`, `EditableCell`). Les
tâches ouvertes qui citent les mêmes fichiers (ACNC1-10, ADRG115, AERR69) portent d'autres gestes. Deux écarts S3 vont en §5
au lieu d'une tâche : ils ne se produisent que sur un chemin concurrent ou en chaîne.

## 5. Optionnel (non déposé)

- AERR81 : un 404 sur la suppression d'une ligne d'assemblage (ligne déjà supprimée ailleurs) ne dit rien.
  `lib/toast.js::toastErreurNonAffichee` le traiterait.
- AERR51 : la branche « panne du refresh » de `api/axios.js` passe `expirer: emitSessionExpired` sans
  `noterEcritureRefusee`. Une écriture dont le refresh tombe en panne puis est refusée au réessai ne reçoit pas l'avis.
- AERR85 : `clearField` absent dans `DemandesAchatList.jsx::setLigne` ; un second champ de ligne refusé (`prix_estime`)
  n'est rendu nulle part.
- Tests manquants sans défaut : AERR22 (motifs illisibles, toast unique de suppression), AERR83 (`GammeTab`, équipements),
  AERR82 (compatibilité), AERR15 (moitié positive), AERR16 et AERR66 (tests hors `ConfirmProvider`), AERR84 (position du
  message), AERR21 (PDF 404 et consolidation).
- `clearField` non appelé à la frappe : AERR13, AERR54, AERR84.
- AERR31 : l'annulation avale son propre échec. AERR20 : `ConfirmDialog` sans `loading`.
- AERR76 : après un 409, réenregistrer renvoie la version périmée. AERR87 : « -1 » au rebut dit « quantité entière ».
- AERR18 : l'année du journal suit le fuseau du navigateur. AERR126 : jetons de tarif jamais nettoyés.
- AERR72 : les sections masquées restent montées (sondages éventuels en arrière-plan, non vérifié).

## 6. Couverture et sortie de cycle

- **Couvert.** Les 49 tâches cochées : texte, commits, code sur `origin/main`, tests nommés, jumeaux. Quatre sondes hôtes
  sur les S2, rejouées par le rédacteur, et les S2 relus dans le code.
- **Non couvert.**
  - Aucun test vitest ni Django lancé ; aucun rejeu à l'écran ; les écarts S3 sont statiques.
  - Les 62 tâches « code livré, preuve en direct due » n'ont pas été relues. Parmi elles AERR25 et AERR26, qui portent le seul
    S1 du dossier PF12 (fiche SAV qui écrit les champs du ticket A sur le ticket B), et les S2 les plus lourds (AERR7, 27, 28,
    29, 56, 77, 124). Leurs rejeux sur runner sont en cours le 14/11 ; aucun enregistrement d'acceptation AERR n'est encore
    sur `main`.
  - AERR69, AERR112 et AERR131 sont encore à faire.
- **Statut.** Le groupe reste « construit », pas « vérifié » : quatre S2 nouveaux, et le S1 d'origine derrière une tâche non
  cochée.
- **Suite.** La contre-visite de clôture sera due à 95 %. Une contre-visite des correctifs sera due quand AERR132-135 seront
  cochées.

## 7. Coût

- 5 vérificateurs (opus, effort élevé) et 1 rédacteur (opus). Leurs jetons ne sont pas mesurés ici.
- Aucun appel Fable.

<!-- verifie | groupe: AERR | pct: 94 | ecarts_s1_s2: 4 -->
