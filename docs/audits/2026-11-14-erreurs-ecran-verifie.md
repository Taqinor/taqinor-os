<!-- verifie | groupe: AERR | pct: 97 | ecarts_s1_s2: 6 -->
# Vérifie AERR — contre-visite de clôture du parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran », 14/11/2026 (2e passe)

Commande `loop audit` (14/11). Le groupe AERR a passé 95 % de tâches cochées (126 sur 129 constructibles,
`audit_registre.py --du`) : c'est la contre-visite de CLÔTURE. Elle remplace le compte rendu de mi-parcours du matin
(résumé en §6). Rien n'a été construit ni déployé.

- **Bilan.** 77 tâches contrôlées, soit toutes celles cochées depuis le matin : 63 ok, 12 partielles, 2 régressions,
  aucune fausse.
- **Le S1 du dossier PF12 est fermé.** AERR25 et AERR26 sont livrées. Aucun chemin ne fait plus écrire le ticket A sur
  le ticket B.
- **Cinq S2 nouveaux.**
  - Un appel journalisé avalé, avec un succès affiché (AERR103).
  - Une note de débit rejouée sur la mauvaise facture (résidu d'AERR133).
  - Deux sections des Paramètres qui perdent encore leur saisie (AERR134).
  - Des brouillons de la fiche ticket perdus au changement de ticket (AERR25).
  - Des boutons « Fermer » qui passent outre la garde de saisie (AERR38).
- **Un S2 du matin reste ouvert.** Son correctif, AERR132, est livré mais n'est pas coché.

## 0. Préconditions

- **SHA.** HEAD de la branche = `d986bb9bc`, qui contient `origin/main` = `e569da5ce` (`git merge-base --is-ancestor`).
- **Registre.** PF12 `erreurs-ecran`, groupe AERR : 126 tâches cochées sur 129 (97 %), clôture due. Les 3 tâches non
  cochées sont AERR112, AERR131 et AERR155. Neuf tâches attendent leur preuve en direct : AERR1, AERR4, AERR69, AERR100,
  AERR102, AERR114, AERR117, AERR120 et AERR132.
- **Échantillon.** Les 77 tâches cochées depuis le matin (`git show 47f925be1:<plan>` comparé à HEAD). Cela inclut 100 %
  des tâches où une erreur serveur peut perdre une saisie, afficher un succès faux, laisser un état à moitié écrit
  (argent, devis, facture, stock) ou cacher un refus. On y trouve les 62 tâches « code livré, preuve en direct due »
  cochées après les rejeux du 14/11, et les 15 tâches d'écart du matin (AERR133-154).
- **Méthode.** Pour chaque tâche : le texte, les commits, le code de HEAD, le test nommé (lu, avec un mutant raisonné)
  et les jumeaux du même geste. Les 50 sondes hôtes AERR ont été rejouées. Cinq sondes neuves ont été écrites puis
  jouées. Pas de pile, pas de Docker, pas de production, aucun test vitest lancé.

## 1. Vérificateurs (3 lots, opus, frais)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **63** | AERR2, 6, 7, 9, 11, 12, 23, 24, 26, 28, 29, 32, 33, 34, 35, 36, 37, 50, 52, 56, 57, 58, 59, 61, 64, 65, 77, 78, 104, 105, 106, 107, 110, 111, 113, 118, 119, 121, 122, 124, 125, 127, 128, 129, 130, 133, 134, 135, 137, 138, 139, 140, 141, 142, 144, 146, 147, 148, 150, 151, 152, 153, 154 |
| partiel | **12** | AERR3, 5, 25, 27, 38, 101, 103, 108, 109, 116, 143, 145 |
| régression | **2** | AERR136, AERR149 |
| faux / non-fait / déjà-présent | **0** | — |

- **Lot argent.** 25 tâches : devis, factures, générateur, stock, achats, réglages.
- **Lot terrain.** 22 tâches : SAV, chantiers, interventions, GED, sécurité.
- **Lot CRM.** 30 tâches : CRM, briques partagées, notifications, portail, reporting, Paramètres.

Un « ok » porte sur le texte de la tâche. AERR29, AERR61 et AERR65 sont conformes mais laissent un jumeau (§4).
AERR134 est conforme à ses huit sections, mais le constat du matin n'est fermé qu'en partie (§4).

## 2. Tests nommés

- **Présence.** Les tests nommés des 77 tâches existent. Ils sont comportementaux : écran rendu, geste joué, appel ou
  état relu. AERR26 et AERR153 ont leur test côté serveur.
- **Trois tests ne voient pas le cas qui casse.**
  - Le test d'AERR27 reste vert sans `dialogueParDessus(`. Radix fait `preventDefault` sur Échap en phase de capture ;
    c'est lu dans `node_modules`, pas exécuté.
  - Le test d'AERR135 bouchonne `onReassign`. La relance dans `LeadsPage` n'est gardée que par une regex. Le code relu
    est juste.
  - Le test d'AERR103 rejoue la reprise dans la même saisie, jamais après une fermeture.
- **Clauses sans test.**
  - AERR3 : l'avis « Indicateurs pas à jour ».
  - AERR109 : la relecture ratée après un glisser.
  - AERR108 : « Ouvrir le doublon » en création.
  - AERR116 : les 11 champs autres que la surface.
- **Exécution.** Aucun test n'a été lancé ici. La seule preuve d'un vert reste la CI de `main`.

## 3. Sondes rejouées

**Les 50 sondes AERR** ont été rejouées sur l'hôte (`PYTHONIOENCODING=utf-8 python <sonde>`). Huit sortent encore
`repro: true`. Pour six d'entre elles, les vérificateurs ont conclu que la sonde est périmée : son détecteur cherche
l'ancien motif, et le code relu ne montre pas le défaut.
- `C-AERR-002` : la liste est relue sous garde, `loading && devis.length === 0`.
- `C-AERR-005` : la fermeture au clic est voulue (décision du 08/10) ; le reste du défaut est C-AERR-VER2-211.
- `C-AERR-047` : l'étape fautive est maintenant nommée ; le vrai reste est C-AERR-VER2-200.
- `C-AERR-050` : `confirmDelete({` n'est pas reconnu par le détecteur.
- `C-AERR-053` : `setEvents([])` n'est appelé que si le mois change.
- `C-AERR-095` : Achats est désactivé sur un échec de lecture.

Les deux autres (`C-AERR-001` pour AERR1, `C-AERR-044` pour AERR100) visent des tâches non cochées. Elles n'ont pas été
tranchées.

Sondes de la contre-visite du matin, rejouées :
- `C-AERR-VER1-100` : `repro: false` (vrai vert).
- `C-AERR-VER1-140` : `repro: false` (code d'AERR132 livré).
- `C-AERR-VER1-161` : `repro: false`. C'est un vrai vert : les autres chemins de `reassign` n'affichent aucun succès.
- `C-AERR-VER1-160` : `repro: false`, mais c'est un **faux vert**. Sa liste de noms de brouillon ignore `templates` et
  `settings` (voir C-AERR-VER2-202).

**Les cinq sondes neuves** ont été jouées par le rédacteur sur `d986bb9bc`. Elles lisent le vrai source, front et serveur.
Toutes sortent `repro: true` :

| Sonde | Ce qu'elle prouve |
|---|---|
| `docs/audits/sondes/AERR/C-AERR-VER2-200.py` | `appelJournalise` est remis à faux dans `reset` seulement, et `reset` est appelé au succès seulement. Aucun effet sur `leadId`. `reprise` saute `logInteraction` et affiche « Relance planifiée. » |
| `docs/audits/sondes/AERR/C-AERR-VER2-201.py` | Le bloc de remise à zéro ne touche ni la clé, ni le motif, ni le montant, ni l'erreur. La clé serveur est rangée par vue, sans l'id de la facture. `PaiementDialog`, le survivant, remet sa clé. |
| `docs/audits/sondes/AERR/C-AERR-VER2-202.py` | `email` et `monitoring` sont rendues par `tab === … &&`, hors `SectionGardee`. Leur brouillon local attend une sauvegarde explicite. |
| `docs/audits/sondes/AERR/C-AERR-VER2-203.py` | 5 brouillons déclarés dans `TicketDetailCorps`, aucun dans `dirty`, un seul `useDirtyGuard`. `selectionner` est gardé par `isAnyFormDirty`. |
| `docs/audits/sondes/AERR/C-AERR-VER2-204.py` | Échap et le clic extérieur sont gardés, mais « Fermer » appelle `onClose` nu. Vrai dans la recette de pompage et dans la fiche ticket. |

Le rédacteur a aussi relu lui-même chaque S2 dans le code :
- **VER2-200.** Popover sans `key` dans `TimelineTab.jsx`. Fermeture par `setOpen`, qui ne fait que `onOpenChange`.
- **VER2-201.** `_idempotency_endpoint` = module + classe ; empreinte = corps seul. `FactureList.jsx` monte la boîte
  sans `key`.
- **VER2-202.** `setTab` n'est pas gardé. `EmailSection` n'a aucun `useDirtyGuard`.
- **VER2-203.** `isAnyFormDirty` ne compte que les gardes enregistrées. La note est un `Textarea` libre.
- **VER2-204.** `closeDetail` = `setSelected(null)`, sans garde.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-AERR-VER2-200 | AERR103 | S2 | Après une relance ratée, l'appel suivant (fenêtre rouverte ou autre lead) n'est jamais journalisé et « Relance planifiée. » s'affiche (`frontend/src/features/crm/CallLogPopover.jsx::CallLogPopover`) | `docs/audits/sondes/AERR/C-AERR-VER2-200.py` (`repro: true`) | AERR156 |
| C-AERR-VER2-201 | AERR133 (résidu) | S2 | Clé d'envoi, motif et montant de la facture A gardés en ouvrant B. Après un échec sans réponse sur A, « Créer » sur B fait rejouer par le serveur la note de A (`frontend/src/pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog`) | `docs/audits/sondes/AERR/C-AERR-VER2-201.py` (`repro: true`) | ACNC71 (même défaut, déjà déposée par la contre-visite ACNC du 14/11) |
| C-AERR-VER2-202 | AERR134, constat VER1-160 | S2 | « E-mail » (modèles en 3 langues), « Monitoring » et « Clients » encore démontées au changement d'onglet (`frontend/src/pages/parametres/ParametresEntreprise.jsx::ParametresEntreprise`) | `docs/audits/sondes/AERR/C-AERR-VER2-202.py` (`repro: true`) | AERR158 |
| C-AERR-VER2-203 | AERR25 | S2 | Note, compte rendu, pièce, retrait et motif perdus sans demande au changement de ticket (`frontend/src/pages/sav/TicketsPage.jsx::TicketDetailCorps`) | `docs/audits/sondes/AERR/C-AERR-VER2-203.py` (`repro: true`) | AERR159 |
| C-AERR-VER2-204 | AERR38 + jumeau | S2 | « Fermer » perd les mesures de recette et la fiche ticket modifiée sans demande (`frontend/src/pages/installations/RecettePompageDialog.jsx::RecettePompageDialog`) | `docs/audits/sondes/AERR/C-AERR-VER2-204.py` (`repro: true`) | AERR160 |
| C-AERR-VER2-210 | AERR3 | S3 | Tuiles d'argent non relues après une note de débit ou une échéance ; l'avis « pas à jour » n'a pas de test (`frontend/src/pages/ventes/FactureList.jsx::FactureList`) | STATIQUE | AERR161 |
| C-AERR-VER2-211 | AERR5 | S3 | Modale d'acceptation non rouverte sur le 409 « date future », un 5xx ou une coupure (`frontend/src/pages/ventes/DevisList.jsx::DevisList`) | STATIQUE | AERR162 |
| C-AERR-VER2-212 | AERR116 | S3 | Une seule erreur de champ rendue sur 12 (`frontend/src/pages/crm/SiteProfilePage.jsx::SiteProfilePage`) | STATIQUE | AERR163 |
| C-AERR-VER2-213 | AERR149 (régression) | S3 | Deux Entrée créent deux lots (`frontend/src/features/ventes/LotsMultiSites.jsx::LotsMultiSites`) | STATIQUE | AERR164 |
| C-AERR-VER2-214 | AERR101 | S3 | Verdict d'un autre commercial gardé sous le nouveau filtre après une panne (`frontend/src/pages/crm/ControleSuiviPanel.jsx::ControleSuiviPanel`) | STATIQUE | AERR165 |
| C-AERR-VER2-215 | AERR108 | S3 | « Abandonner » ignoré au démontage ; refus de A posé sous B ; clause du doublon non testée (`frontend/src/features/crm/workspace/useLeadDraft.js::useLeadDraft`) | STATIQUE | AERR166 |
| C-AERR-VER2-216 | AERR136 (régression) | S3 | Le corps d'un 404 rendu par `.unwrap()` n'est plus signalé (`frontend/src/lib/mutateWithUndo.js::mutateWithUndo`) | STATIQUE | AERR167 |
| C-AERR-VER2-217 | AERR109 | S3 | La relecture ratée après un glisser n'a pas de test (`frontend/src/pages/CalendarPage.jsx::CalendarPage`) | STATIQUE | AERR168 |
| C-AERR-VER2-218 | AERR143 | S3 | Quatre lectures encore doublées par un toast local (`frontend/src/pages/parametres/NotificationsAdminSection.jsx::RoutingRulesPanel`) | STATIQUE | AERR169 |
| C-AERR-VER2-219 | AERR69 (non cochée) | S3 | « Annuler » de la palette ⌘K envoyé sans `undo: true`, donc refusé en 409 (`frontend/src/providers/CommandPalette.jsx::CommandPalette`) | STATIQUE | AERR69 (à corriger avant de la cocher) |
| C-AERR-VER2-220 | AERR27 | S3 | Entrée volée à un bouton focalisé ; J/K sous une boîte non testés (`frontend/src/pages/sav/TicketsPage.jsx::TicketsPage`) | STATIQUE | AERR170 |
| C-AERR-VER2-221 | AERR145 | S3 | `mes`, `newTicket`, `equip` et deux motifs suivent encore le chantier A ; latent (`frontend/src/pages/installations/InstallationDetail.jsx::InstallationDetail`) | STATIQUE | AERR171 |
| C-AERR-VER2-222 | AERR29 (jumeau) | S3 | La fiche intervention passe à Terminée ou Validée sans confirmation (`frontend/src/pages/interventions/InterventionsPage.jsx::DetailSheet`) | STATIQUE | AERR172 |
| C-AERR-VER2-224 | AERR65 (jumeaux) | S3 | « Lever le hold » et la suppression d'un champ de signature partent d'un clic (`frontend/src/features/ged/advanced/RetentionPage.jsx::RetentionPage`) | STATIQUE | AERR173 |

**Pourquoi ces gravités.**
- **VER2-200 (S2).** Le toast « Relance planifiée. » affiche un succès faux, et l'appel réel manque au journal du lead.
  Il suffit d'une relance ratée puis d'une fermeture.
- **VER2-201 (S2, chemin en chaîne).** Un succès faux sur un document d'argent : « ND-… créée » sous la facture B, alors
  que B ne reçoit rien. Le chemin demande un échec sans réponse sur A, puis l'ouverture de B avec le même corps. Ce corps
  est précisément celui que la boîte a gardé de A.
- **VER2-202, 203, 204 (S2).** Une perte de saisie réelle sans avertissement, sur un geste ordinaire : clic d'onglet,
  clic de ticket, « Fermer ». Même grille que les constats 074 et 075 du dossier PF12 et que VER1-160.
- **Pas de S1.** VER2-221 serait de type S1 (mesures de A envoyées à B) s'il devenait atteignable. Aujourd'hui, aucun
  écran ne change de chantier sans remonter la fiche.

**Routage.** Les propriétaires viennent de `check_ownership.py --owner-of` :
- lead : AERR156, 163, 165, 166, 168 ;
- facturation : ACNC71 (même défaut, déjà déposée par la contre-visite ACNC du 14/11), 161 ;
- paramètres : AERR158, 169 ;
- SAV : AERR159, 170 ;
- devis : AERR162, 164 ;
- deploy : AERR167 ;
- chantiers : AERR171, 172 ;
- documents : AERR173 ;
- transverse, atomique chantiers + SAV : AERR160.

**Réfuté ou déjà porté.**
- AERR69 porte déjà C-AERR-VER2-219. Aucun autre écart n'est porté par une tâche ouverte : AERR112, AERR117, AERR120 et
  AERR155 visent d'autres gestes.
- Deux propositions des vérificateurs sont rétrogradées en §5 : l'en-tête « 0 pièce(s) jointe(s) » affiché sous l'avis
  d'échec (`components/AttachmentsPanel.jsx`, S4), et le doublon de toast à l'annulation.

## 5. Optionnel (non déposé)

- **Pièces jointes.** L'en-tête `AttachmentsPanel` compte 0 sur une lecture ratée, alors que l'avis d'échec est affiché.
- **Annulation.** « Annulation impossible — vérifiez votre connexion » s'affiche en plus du toast global sur un refus
  serveur (`useLeadDraft.js`, `mutateWithUndo.js`).
- **AERR5.** Message doublé : toast plus texte sous le champ.
- **AERR9.** Lien montré dans un toast de 20 s seulement.
- **AERR142.** « La suppression du prix a échoué. » s'affiche si seule la relecture échoue.
- **AERR78 et AERR64.** Une relecture ratée remplace tout le panneau (séries, SoD).
- **AERR28.** `onChangeStatus` avale la raison serveur ; antérieur à la tâche.
- **Annulation d'un ticket.** La boîte se ferme avant le 2xx ; le motif est gardé.
- **AERR108.** L'envoi au démontage contourne la garde de fraîcheur (VX243c).
- **CalendarPage.** Une réponse en retard d'un autre mois n'est pas gardée.
- **Spec d'acceptation.** `frontend/e2e/acceptation/aerr.spec.js` garde une étape AERR25 périmée sous `etapeRouge` ;
  les étapes vivantes sont dans `aerr5.spec.js`.

## 6. Rappel de la passe du matin

La passe de mi-parcours (49 tâches, SHA `47f925be1`) avait retenu 4 S2 et 13 S3. Leur état à `d986bb9bc` :

| Constat du matin | Tâche | État ce soir |
|---|---|---|
| VER1-100 (S2) : notes de A sous B | AERR133 cochée | **fermé** : sonde à `repro: false`, test « A puis B en échec ». Résidu de clé et de saisie : VER2-201 |
| VER1-140 (S2) : fiche produit à stock négatif bloquée | AERR132 non cochée (code livré, preuve en direct due) | code livré, sonde à `repro: false`, **toujours compté** tant que la tâche n'est pas cochée |
| VER1-160 (S2) : sections des Paramètres démontées | AERR134 cochée | **partiellement fermé** : 8 sections gardées, E-mail, Monitoring et Clients restent (VER2-202) |
| VER1-161 (S2) : réassignation refusée annoncée réussie | AERR135 cochée | **fermé** : relance avec `relancer`, aucun autre chemin n'affiche de succès |
| VER1-101, 102, 103 (S3, factures) | AERR137, 138, 139 cochées | fermés |
| VER1-120, 122 (S3, chantiers, outillage) | AERR140, 146 cochées | fermés |
| VER1-121 (S3, brouillons de la fiche chantier) | AERR145 cochée | partiel, VER2-221 |
| VER1-141, 142 (S3, stock, SAV) | AERR142, 144 cochées | fermés |
| VER1-162 (S3, `.unwrap()`) | AERR136 cochée | fermé, avec une régression (VER2-216) |
| VER1-163 (S3, toasts doublés) | AERR143 cochée | écritures fermées, lectures restantes (VER2-218) |
| VER1-164, 165, 180 (S3) | AERR147, 148, 141 cochées | fermés |

Le S1 du dossier PF12 (fiche SAV qui écrivait A sur B) est fermé par AERR25 et AERR26. Il est rejoué en direct dans
`docs/audits/acceptation/AERR/2026-11-14-3d6d2abe8.md`.

## 7. Couverture et sortie de cycle

- **Couvert.**
  - Les 77 tâches cochées depuis le matin : texte, commits, code de HEAD, tests nommés, jumeaux.
  - Les 50 sondes anciennes rejouées.
  - Cinq sondes neuves sur les S2, relues dans le code par le rédacteur.
- **Non couvert.**
  - Aucun test vitest ni Django lancé, aucun rejeu à l'écran ; les S3 sont statiques.
  - Les 6 enregistrements d'acceptation AERR du 14/11 n'ont pas été rejoués.
  - Les 9 tâches « preuve en direct due » n'ont pas été relues, AERR132 comprise.
  - Les sondes `C-AERR-001` et `C-AERR-044` encore à `repro: true` n'ont pas été tranchées.
- **Statut.** Le groupe reste « construit », pas « vérifié ». Il compte 5 S2 nouveaux, plus le S2 du matin dont la
  tâche (AERR132) n'est pas cochée.
- **Suite.** Une contre-visite des correctifs sera due quand AERR156 à AERR160 et AERR132 seront cochées. AERR69 ne se
  coche pas avant d'envoyer `undo: true`.

## 8. Coût

- 3 vérificateurs (opus, frais), environ 0,88 M jetons de sous-agents. 1 rédacteur (opus).
- Aucun appel Fable.
