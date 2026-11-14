<!-- verifie | groupe: ASUP | pct: 100 | ecarts_s1_s2: 5 -->
# Vérifie ASUP — contre-visite de clôture du parcours PF10 « suppression et archivage », 14/11/2026

Commande `loop audit` (14/11). Le registre compte 27 tâches cochées sur 27 constructibles (100 %) : c'est le `vérifie` de
clôture. La contre-visite du 13/11 (`docs/audits/2026-11-13-suppression-archivage-verifie.md`) avait laissé un S1 résiduel
(C-ASUP-VER2-101, avoirs et notes de débit) et trois S2. Rien n'a été construit ni déployé.

- **Les 100 % ne veulent pas dire « fini ».** Le groupe compte 45 tâches. 27 sont cochées. Les 18 autres sont
  `[BLOCKED: code livré …, preuve en direct due]` et `audit_registre.py` les sort du dénominateur. ASUP57, qui porte le S1
  résiduel, en fait partie : **elle n'est pas cochée**.
- **Les 16 tâches cochées depuis le 13/11** : 16 ok, aucune régression.
- **Le S1 résiduel est fermé dans le code** pour l'avoir et la note de débit, mais pas encore prouvé en direct.
- **Un nouvel écart S2** : les exports comptables listent encore le client vivant anonymisé, sans ICE.

## 0. Préconditions

- **SHA.** Branche de travail = `origin/main` = `a12f40f82` (CI verte sur ce SHA). `origin/main` est passé ensuite à
  `d68328666` : aucun fichier relu ici n'a changé (`git diff --name-only`).
- **Registre.** PF10 `suppression-archivage`, groupe ASUP : 27 cochées sur 27 constructibles. 18 tâches `[BLOCKED: code
  livré, preuve en direct due]` exclues : ASUP4, 5, 6, 12, 13, 14, 17, 18, 44, 45, 48, 56 à 62.
- **Échantillon.** Toutes les tâches cochées depuis le 13/11 au soir, soit ASUP1, 2, 3, 7, 8, 9, 10, 11, 15, 41, 42, 43, 46,
  47, 49 et 52. Elles ont été cochées par `507b1faa82`, `ce59bbee7b` et `8a447794d4`, sur trois enregistrements
  d'acceptation PASS : `2026-11-13-cecbdee80`, `…-c7a04cc01` et `…-3e1eb8c36`. S'y ajoute la relecture du code des
  correctifs ASUP56 à 62, non cochés.
- **Méthode.** Commits, code de la branche et tests nommés, tout lu. Deux sondes hôte jouées (§3, §4). Aucune pile, aucun
  test Django, aucune production consultée.

## 1. Vérificateurs (1 lot, orchestrateur, opus, effort élevé)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **16** | ASUP1, 2, 3, 7, 8, 9, 10, 11, 15, 41, 42, 43, 46, 47, 49, 52 |
| partiel / non-fait / faux / régression / déjà-présent | **0** | — |

Ces 16 tâches avaient été relues « ok » le 13/11 sur `d64fa1e4e`. Depuis, `git diff d64fa1e4e..a12f40f82` sur les
44 fichiers de leurs commits ne montre que des ajouts d'autres tâches :
- `crm/receivers.py` : nouvelle garde de pré-sauvegarde d'ASUP56, qui rejoue la garde d'ASUP9 ;
- `ventes/domain/recouvrement.py` : ASUP58 et AMSG86-87 ;
- `notifications/views.py` : ASUP60 ;
- `stock/services.py` : ASUP61 ;
- `monitoring/views.py` : un droit de plus (ADRG46).

Aucune de ces modifications ne retire le comportement exigé par ces tâches. Le câblage d'ASUP1 à 3 est en place :
- la commande `figer_identite_acheteur` existe ;
- `anonymiser_client` fige les factures avant tout effacement ;
- la garde `pieces_legales_sans_identite_figee` est enregistrée dans `facturation/receivers.py`.

Les 16 tâches sont couvertes par les trois enregistrements d'acceptation. Seule ASUP44 y figure « avec écart », et elle
n'est pas cochée.

## 2. Tests nommés

- Les tests des 16 tâches existent et sont comportementaux (relus le 13/11). Leurs fichiers n'ont pas bougé depuis.
- Le test d'ASUP57 est `ventes/tests/test_facture_apar61_identite_vendeur.py::IdentiteVendeurFigeeTests`
  `::test_avoir_et_note_debit_impriment_l_acheteur_fige_apres_anonymisation`. Il est comportemental : vraies routes
  `anonymize`, `creer-avoir`, `avoirs/<id>/annuler/` et `creer-note-debit`. Il lit le texte du PDF stocké puis d'un
  nouveau rendu : nom, ICE, IF, RC et adresse d'origine présents, « Client anonymisé » absent.
- Aucun test n'a été lancé ici. La seule preuve d'un vert est la CI de `main` sur `a12f40f82`.

## 3. Le S1 est-il fermé ?

**ASUP57 n'est pas cochée.** Ligne 608 de `docs/plans/PLAN_AUDIT_FACTURATION.md` : `[BLOCKED: code livré cloud-1311b
(13/11/2026), preuve en direct due]`. Les 100 % du registre viennent de ce que les tâches BLOCKED sortent du
dénominateur.

**Dans le code, le défaut est fermé pour l'avoir et la note de débit.**
- **Commits.** `173c3d0612` (13/11), puis `6b839fbc04` (correctif de CI).
- **Générateurs.** `ventes/utils/pdf.py::generate_avoir_pdf` et `::generate_note_debit_pdf` posent
  `context['acheteur'] = acheteur_de_la_facture(<pièce>.facture)`.
- **Gabarits.** `avoir.html` et `note_debit.html` lisent `acheteur.*`, avec le repli `acheteur or <pièce>.client`.
  `grep "client\."` sur ces deux gabarits ne trouve plus rien.
- **Lien à la facture.** `Avoir.facture` et `NoteDebit.facture` sont obligatoires (PROTECT, non nuls).
- **Appelants.** Les sept appelants passent tous par ces deux générateurs : `creer-avoir`, `retour-client`,
  `creer-note-debit`, les deux `annuler` et les deux `telecharger_pdf`.

**La sonde VER2-101 est périmée.** Rejouée aujourd'hui, elle sort `repro: False`, mais pour une mauvaise raison :
- elle conclut sur la seule présence de la clé `acheteur` dans le contexte ;
- or elle rend les gabarits SANS cette clé, donc par le repli ;
- son HTML porte donc encore « Client anonymisé #12 » sans ICE.

Une vérification à part, hors dépôt, a rendu les vrais gabarits avec le contexte de `generate_*_pdf` : vrais corps
d'`anonymiser_client`, `figer_a_l_emission` et `acheteur_de_la_facture`. Pour l'avoir comme pour la note de débit, le PDF
imprime nom, ICE, IF, RC et adresse d'origine, jamais « Client anonymisé ».

**Le défaut est-il fermé pour TOUS les documents dérivés ?**

| Document | Après « Anonymiser (RGPD) » | Verdict |
|---|---|---|
| Facture, acompte | acheteur figé (ASUP1-3) | fermé |
| Avoir, note de débit (PDF) | acheteur figé de la facture d'origine (ASUP57) | fermé dans le code, non coché |
| Export DGI / UBL, validateur DGI | `acheteur_de_la_facture` (avoir : facture d'origine) | fermé |
| Journal des ventes, export comptable, grand livre, IIF | client vivant : « Client anonymisé », ICE vide | **ouvert, C-ASUP-VER3-100 (S2)** |
| Quittance de paiement | nom du client vivant, sans ICE | non déposé (§5) |
| BC client, BL, PV de réception | nom du client vivant, sans ICE | non déposé (§5) |
| Lettre de relance, dossier contentieux | client vivant | question au fondateur (§5) |
| Journal d'audit | caviardé (ASUP13, D-ASUP-1), plancher de 10 ans (ASUP17-18, D-ASUP-5) | code livré, non coché |
| GED | aucun fournisseur d'effacement ne touche la GED ; `client_nom` reste une métadonnée | conforme |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASUP-VER3-100 | ASUP1, ASUP2, ASUP57 | S2 | Exports comptables d'une facture, d'un avoir ou d'une note de débit émis, après « Anonymiser (RGPD) » du client : « Client anonymisé #N », ICE vide, alors que la pièce garde son acheteur (`backend/django_core/apps/ventes/exports.py::_compta_rows`) | `docs/audits/sondes/ASUP/C-ASUP-VER3-100.py` (`repro: True`) | ASUP63 |
| C-ASUP-VER2-101 | ASUP1-3 | S1 | Rappel du 13/11 : avoir et note de débit. Fermé dans le code, ASUP57 non cochée | sonde VER2-101 périmée (§3) | ASUP57 |
| C-ASUP-VER2-102 | ASUP45 | S2 | Rappel du 13/11 : « Mes activités » et le résumé d'attention. Code relu et conforme ; ASUP59 et ASUP60 non cochées | STATIQUE | ASUP59, ASUP60 |
| C-ASUP-VER2-104 | ASUP12 | S2 | Rappel du 13/11 : leads du client en corbeille. Code relu et conforme (`Lead.all_objects.filter(client=client)`) ; ASUP62 non cochée | STATIQUE | ASUP62 |
| C-ASUP-VER2-105 | ASUP42 | S2 | Rappel du 13/11 : relance d'un lead en corbeille. Code relu et conforme (`avec_corbeille=True`, `is_deleted`) ; ASUP58 non cochée | STATIQUE | ASUP58 |

**C-ASUP-VER3-100, ce qui se passe.** Quatre fonctions de `backend/django_core/apps/ventes/exports.py` lisent
`getattr(<pièce>.client, 'nom' / 'ice')` :
- `export_journal_ventes` ;
- `_compta_rows` (export comptable xlsx et csv) ;
- `lignes_rectificatives` (avoirs et notes de débit, dans le journal comme dans l'export comptable) ;
- `_grand_livre_rows_reconstitues` (grand livre xlsx et csv, export QuickBooks).

**La sonde hôte.** Elle exécute les vrais corps de `_compta_rows`, `lignes_rectificatives` et `pieces_rectificatives` sur
un ORM bouchonné, après le vrai `anonymiser_client`.
- **Avant l'anonymisation**, les trois lignes portent `SARL Exemple` et son ICE.
- **Après**, la facture, l'avoir et la note de débit portent `Client anonymisé #12` et un ICE vide, alors que
  `acheteur_de_la_facture` rend encore `SARL Exemple` et son ICE.

Les quatre lecteurs sont confirmés par lecture de l'AST.

**Comment on y arrive.** Le geste est ordinaire : « Journal des ventes » ou « Export comptable » depuis la liste des
factures (`frontend/src/pages/ventes/factureList/useFactureCompta.js`).

**Gravité S2, et pourquoi.**
- Ce n'est pas un S1 : l'identité n'est pas perdue (elle est figée sur la facture), aucun montant n'est faux, et l'export ne
  part pas chez le client.
- C'est un S2 : le document remis au cabinet comptable contredit les pièces émises (colonne « ICE client » vide pour un
  acheteur B2B), et on ne peut le corriger qu'en recopiant chaque PDF.

**Routage.** `python scripts/check_ownership.py --owner-of backend/django_core/apps/ventes/exports.py` → facturation.
ASUP63 va donc dans `docs/plans/PLAN_AUDIT_FACTURATION.md`.

**Réfuté ou requalifié.** Aucun écart du 13/11 n'est réfuté. Les quatre restent comptés tant que leur tâche n'est pas
cochée (§C.4.6), même si leur code est livré.

## 5. Optionnel (non déposé)

- **Quittance.** `ventes/utils/pdf.py::generate_recu_pdf`, rendu à la volée, imprime `paiement.facture.client.nom` (client
  vivant). Après anonymisation, la quittance porte « Client anonymisé ». Il n'y a ni ICE ni mention fiscale ;
  `acheteur_de_la_facture(paiement.facture).nom` suffirait si le fondateur veut le nom d'origine.
- **BC client, BL, PV de réception** (`bon_commande.html`, `document_bon_livraison.html`, `document_pv_reception.html`).
  Ils impriment le client vivant, sans ICE, et ne sont pas des pièces fiscales. Un nom effacé y est cohérent avec
  l'effacement. Leur stockage (PV signé) n'a pas été relu.
- **Question au fondateur, non posée ici.** Une seule garde d'effacement existe (`pieces_legales_sans_identite_figee`).
  Aucune ne refuse l'anonymisation d'un client qui a des factures impayées ou un dossier contentieux ouvert. Après
  l'effacement, `lettre_relance.html` et `dossier_contentieux.html` imprimeraient « Client anonymisé », sans adresse.
  Faut-il refuser l'effacement tant qu'une créance est ouverte (intérêt légitime au recouvrement) ? À ouvrir dans
  `decisions.yml` par un audit, pas par cette contre-visite.
- **Brouillons.** Une facture BROUILLON n'est pas figée à l'anonymisation. Émise ensuite, elle fige l'identité effacée.
  Pour un client entreprise, l'émission est refusée faute d'ICE (`ventes/domain/facturation_ops.py`, CIQ217). Pour un
  particulier, elle sort au nom « anonymisé ». Le risque est faible.
- **ASUP12 et ASUP45** sont couvertes par un enregistrement PASS mais restent BLOCKED : la relecture adverse les a refusées.
  Le motif n'a pas été relu ici.
- **Reliquats du 13/11** (ASUP7, ASUP9, ASUP15, ASUP2 / ASUP12 sans verrou, `CLAUDE.md` sur les coffrets) : inchangés.

## 6. Couverture et sortie de cycle

- **Couvert.**
  - Les 16 tâches cochées depuis le 13/11 : commits, diff depuis la base du 13/11, câblage, enregistrements d'acceptation.
  - Le code des correctifs ASUP56 à 62 : diffs relus.
  - L'inventaire des documents dérivés : 34 gabarits PDF, exports de `ventes/exports.py` et du reporting, fournisseurs et
    gardes d'effacement.
- **Non couvert, faute de pile.**
  - Aucun test Django lancé, aucun rejeu navigateur.
  - La preuve en direct d'ASUP57 (étape PF10.4) n'est pas jouée.
  - Les sondes de VER3-100 et de vérification d'ASUP57 tournent sur ORM bouchonné, pas sur une base.
  - Non vérifiés : le widget d'activités du tableau de bord (ASUP59) et les motifs de refus d'ASUP12 et ASUP45.
- **Statut.** Le groupe reste « construit », pas « vérifié » : un S1 et trois S2 du 13/11 ont leur tâche non cochée, et un
  S2 est nouveau. Les écarts S1-S2 comptés sont : 1 nouveau, plus 4 d'origine.
- **Suite.**
  - Jouer en direct ASUP56 à 62 (pile locale ou runner GitHub, §C.4.7), puis les cocher.
  - Construire ASUP63.
  - Contre-visite des correctifs une fois ASUP57 à 63 cochées.

## 7. Coût

- 1 orchestrateur (opus, effort élevé), aucun sous-agent. Jetons non mesurés ici.
- Aucun appel Fable.
