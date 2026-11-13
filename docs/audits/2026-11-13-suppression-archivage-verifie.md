# Vérifie ASUP — contre-visite du parcours PF10 « suppression et archivage », 13/11/2026 (deux passes)

Commande `loop audit` (13/11). L'audit de parcours PF10 (11/11, PR #1366) avait déposé ASUP1-55. Le groupe a été relu deux
fois le même jour ; ce compte rendu remplace celui de l'après-midi (git garde la première version). Rien n'a été construit ni
déployé.

- **Après-midi (mi-parcours).** Les 11 tâches cochées : 11 ok, aucun écart. Le S1 n'était porté par aucune tâche cochée.
- **Soir.** Les 19 tâches livrées le 12/11 (run 99392c, vague 13), encore en attente de leur preuve en direct sur `main`, dont
  ASUP1-3, qui portent le S1. 19 ok. Le S1 est fermé pour les factures, mais **pas pour les avoirs et les notes de débit** :
  c'est un résiduel S1. Quatre jumeaux restent non filtrés (3 S2, 1 S3).

## 0. Préconditions

- **SHA.** Après-midi : `origin/main` = `bbe833192`. Soir : `origin/main` = `d64fa1e4e` (après `git fetch`). Le code backend de
  la branche de travail est identique à celui de `d64fa1e4e`.
- **Registre.** PF10 `suppression-archivage`, groupe ASUP, 11 tâches cochées sur 12 constructibles (91 %, première passe, non
  recalculé).
- **Échantillon.** Après-midi : toutes les tâches cochées, soit ASUP16, 19, 20, 21, 22, 23, 50, 51, 53, 54, 55. Soir : toutes les
  tâches marquées « code livré, preuve en direct due », soit ASUP1, 2, 3, 7, 8, 9, 10, 11, 12, 15, 41, 42, 43, 44, 45, 46, 47, 49
  et 52. ASUP1-3 portent le S1.
- **Méthode.** Commits, code sur `origin/main` et tests nommés, tout lu. Une sonde hôte écrite et jouée (§3). Aucune pile, aucun
  test Django, aucune production consultée.

## 1. Vérificateurs (2 lots, opus, effort élevé, frais)

| Passe | Verdict | Nombre | Tâches |
|---|---|---|---|
| Après-midi | ok | **11** | ASUP16, 19, 20, 21, 22, 23, 50, 51, 53, 54, 55 |
| Soir | ok | **19** | ASUP1, 2, 3, 7 (test déplacé), 8, 9, 10, 11, 12, 15, 41, 42, 43, 44, 45 (jumeaux hors tâche), 46, 47 (jumeau hors tâche), 49, 52 |
| Les deux | partiel / non-fait / faux / régression / déjà-présent | **0** | — |

Commits relus le soir : ASUP1 `1ddb98b196` et `b2e17271f1`, ASUP2 `f69656afdf`, ASUP3 `055c47479c`, ASUP7 `aae61b81a9`, ASUP8
`971cf78e6e`, ASUP9 `7e45661a95` et `84c23bcfea`, ASUP10 `7b9de73102`, ASUP11 `1904a892dc`, ASUP12 `80f3700846` et `2d419ee968`,
ASUP15 `9c0056d164` et `ca1ac7be1f`, ASUP41 `5c360bd49c`, ASUP42 `80fd724b58`, ASUP43 `cc75d6e558`, ASUP44 `941b6f2e64`, ASUP45
`6f52f2b9a2`, ASUP46 `4f456c6352`, ASUP47 `c5551fda48`, ASUP49 `22abbc32fd`, ASUP52 `7a4fe7e9d9`. Ceux de l'après-midi sont
inchangés.

Les verdicts « ok » portent sur le texte de chaque tâche. Les jumeaux trouvés en dehors de ce texte sont des écarts (§4).

## 2. Tests nommés

- **Les tests nommés des 30 tâches existent** et sont comportementaux : appel HTTP ou vrai service, rôles réels, état relu en base.
- Le test d'ASUP7 est dans `monitoring/test_ciq646_garantie_non_validee.py` et non dans `monitoring/tests.py`, comme le dit le
  plan. Le commit l'explique : `tests.py` fait 1 999 lignes. Ce n'est pas un défaut (§5).
- Les tests d'ASUP2 et d'ASUP12 tuent leur mutant principal. Pour ASUP15, l'appel de purge depuis
  `trash/services.py::purger_expires` n'est couvert par aucun test (§5).
- Les corps des tests d'ASUP10, 43, 45, 47, 49 et 46 (côté rappels) n'ont pas été relus en détail : leur existence et le code
  qu'ils couvrent l'ont été.
- Aucun test n'a été lancé ici. La seule preuve d'un vert est la CI de `main`.

## 3. Le S1 est-il fermé ?

Le S1 du dossier PF10 : « Anonymiser (RGPD) » d'un client facturé efface l'identité légale de l'acheteur.

**Pour les factures, acomptes compris : oui, dans le code.**
- `is_anonymized = True` n'est posé qu'à un seul endroit : `crm/dsr_provider.py::anonymiser_client`. Cette fonction commence par
  figer l'acheteur des factures non brouillon, avant tout effacement (ASUP2).
- Côté demande d'effacement, une garde répond 409 tant qu'une facture émise n'a pas d'acheteur figé (ASUP3).
- La commande `figer_identite_acheteur` fige les factures anciennes (ASUP1). Elle tourne à blanc par défaut et n'écrit qu'avec
  `--appliquer`.
- Les acomptes sont des lignes `Facture`. Le PDF, l'export DGI/UBL et le validateur DGI lisent tous
  `acheteur_de_la_facture`.

La sonde 001 du dossier PF10 ne tourne plus sur l'hôte : son bouchon n'a pas `apps.facturation`. Le rejeu en direct la remplace.
Deux enregistrements d'acceptation PASS du 13/11 existent sur la branche de travail, pas encore sur `main` :
`docs/audits/acceptation/ASUP/2026-11-13-cecbdee80.md` et `…-3e1eb8c36.md`. Ils couvrent les 19 tâches, ASUP1-3 comprises,
avec un écart accepté sur ASUP44. Sur `main`, ASUP1-3 restent marquées « preuve en direct due ».

**Pour les avoirs et les notes de débit : non. C'est un résiduel S1 (C-ASUP-VER2-101).**
- **Ce qui se passe.** `Avoir` et `NoteDebit` n'ont aucune copie figée de l'acheteur. `ventes/utils/pdf.py::generate_avoir_pdf`
  et `::generate_note_debit_pdf` ne mettent dans le contexte que la pièce elle-même. Les gabarits `templates/pdf/avoir.html` et
  `note_debit.html` impriment `avoir.client.*` et `note_debit.client.*`, c'est-à-dire le client vivant.
- **Sonde hôte jouée.** `docs/audits/sondes/ASUP/C-ASUP-VER2-101.py` exécute le vrai `anonymiser_client`, le vrai
  `figer_a_l_emission` et le vrai `acheteur_de_la_facture`. Elle rend les vrais gabarits avec le vrai environnement Jinja2.
  Sortie : `repro: True`.
  - Témoin avant anonymisation : l'ICE est imprimé.
  - Après anonymisation, la facture d'origine garde `SARL Exemple` et son ICE.
  - L'avoir et la note de débit impriment « Client anonymisé #12 », sans ICE, sans IF, sans RC.
  - Le contexte des deux générateurs se réduit à `['avoir']` et `['note_debit']`.
- **Gestes qui déclenchent un rendu.** Trois gestes d'écran ordinaires :
  - créer un avoir ou une note de débit sur une facture émise du client (`creer-avoir`, `creer-note-debit`, `retour-client`) ;
  - annuler un avoir ou une note de débit : le PDF stocké est alors ré-écrit ;
  - télécharger une pièce dont le PDF manque.

  Aucune garde `is_anonymized` n'existe dans `facturation` ni dans `ventes`. L'export DGI d'un avoir est sûr, car il lit la
  facture d'origine.
- **Gravité S1, et pourquoi.** Le défaut est exploitable aujourd'hui, par deux gestes d'écran ordinaires d'un administrateur
  (« Anonymiser (RGPD) », puis « Créer un avoir » ou « Annuler »). Il touche une pièce légale émise : la ré-annulation
  ré-écrit même le PDF stocké d'un avoir déjà remis. L'acheteur d'une pièce B2B y perd son ICE. C'est la même perte que le S1
  d'origine (seuil S1 « perte »). Le déclencheur est plus étroit, mais ce n'est pas un critère de gravité.
- **Tâche :** ASUP57, dans `docs/plans/PLAN_AUDIT_FACTURATION.md`. Elle imprime l'acheteur figé de la facture d'origine via
  `acheteur_de_la_facture(<pièce>.facture)`, sans champ ni migration.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASUP-VER2-101 | ASUP1, ASUP2, ASUP3 | S1 | Avoir et note de débit rendus après « Anonymiser (RGPD) » : « Client anonymisé », sans ICE, IF, RC ni adresse (`backend/django_core/apps/ventes/utils/pdf.py::generate_avoir_pdf`) | `docs/audits/sondes/ASUP/C-ASUP-VER2-101.py` (`repro: True`) | ASUP57 |
| C-ASUP-VER2-102 | ASUP45 | S2 | « Mes activités » et les compteurs du résumé d'attention comptent encore les à-faire d'un lead archivé ou supprimé (`backend/django_core/apps/records/views.py::ActivityViewSet.mine`, `backend/django_core/apps/notifications/views.py::attention_summary`) | STATIQUE (lecture : `sans_cibles_archivees` absent des deux) | ASUP59, ASUP60 |
| C-ASUP-VER2-103 | ASUP47 | S3 | La suggestion de réapprovisionnement propose un fournisseur archivé ; le BCF de réappro sans fournisseur répond alors 409 (`backend/django_core/apps/stock/services.py::produits_a_reapprovisionner`) | STATIQUE (lecture : requête `PrixFournisseur` sans filtre d'archivage) | ASUP61 |
| C-ASUP-VER2-104 | ASUP12 | S2 | « Anonymiser (RGPD) » n'efface un lead du client déjà en corbeille que s'il partage son e-mail ou son téléphone (`backend/django_core/apps/crm/clients_views.py::ClientViewSet.anonymize`) | STATIQUE (lecture : `client.leads`, manager des vivants ; la corbeille ne purge jamais la fiche) | ASUP62 |
| C-ASUP-VER2-105 | ASUP42 | S2 | Le devis d'un lead mis à la corbeille est encore relancé (`backend/django_core/apps/ventes/domain/recouvrement.py::_lead_ecarte`) | STATIQUE (lecture : `get_company_lead` sans `avec_corbeille` ⇒ `None` ⇒ non écarté) | ASUP58 |

**Pourquoi ces gravités.** Les trois S2 portent le même mal qu'un constat d'origine que le dossier PF10 classe S2 :
- à-faire d'un lead archivé encore listés (ASUP45) ;
- leads du client non effacés (ASUP12) ;
- relances vendeur vers un lead écarté (ASUP42).

Ici, c'est un écran jumeau ou un sous-cas. Le vérificateur les proposait en S3 parce qu'ils sortaient du « fini quand » de la
tâche ; c'est une question de périmètre, pas de gravité. C-ASUP-VER2-103 reste S3 : la création du BCF refuse déjà un fournisseur
archivé (409), donc aucune commande ne part chez lui, et on contourne en choisissant le fournisseur à la main.

**Routage.** Chaque tâche a un seul propriétaire (`check_ownership.py --owner-of`) :
- ASUP57 et ASUP58 → facturation ;
- ASUP59 → sécurité (`records`) ;
- ASUP60 → paramètres (`notifications`) ;
- ASUP61 → stock ;
- ASUP62 → lead.

C-ASUP-VER2-102 touche deux propriétaires. Il est donc scindé en deux tâches sœurs, plutôt que porté par une tâche transverse.

**Réfuté ou requalifié.** Aucun des cinq écarts n'est réfuté. Le constat « test d'ASUP7 hors du module nommé » n'est pas un défaut
du produit : il passe en §5.

## 5. Optionnel (non déposé)

- ASUP7 : le plan nomme encore `monitoring/tests.py` alors que le test vit ailleurs (texte du plan seulement). On peut aussi
  repousser `start_year` dans le futur par PATCH puis supprimer. La cascade `Installation` → `ProductionWarranty` ne passe pas par
  la garde.
- ASUP9 : l'« absorbé par fusion » est repéré par une expression régulière sur `lead.note`. Éditer la note, ou un effacement DSR,
  le fait disparaître. Un champ structuré serait plus solide. Le contournement par la corbeille commune est déjà suivi en ASUP56.
- ASUP15 : l'appel de purge depuis `purger_expires` n'est pas testé. Le mutant « retirer l'appel » survivrait.
- ASUP2 / ASUP12 : aucun verrou. Une facture émise pendant l'anonymisation figerait une identité déjà effacée (risque faible).
- ASUP1 : le dry-run imprime nom et statut sur la sortie standard. C'est voulu, mais ce sont des données personnelles.
- Reliquats de l'après-midi :
  - `CLAUDE.md` dit encore que le seeder archive les six coffrets estimés ; c'est périmé depuis ASUP55.
  - D-ASUP-2 liste encore ASUP55.
  - Le test d'ASUP53 ne joue le cas « produit actif » que par le sérialiseur.
  - Le correctif de CI d'ASUP21 a ajouté une quinzaine de lignes au viewset des tickets.
  - Il reste des fonctions d'appel mortes côté écran.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 30 tâches relues : code, commits, tests nommés, jumeaux, avec une sonde hôte sur le S1 résiduel. Les quatre
  jumeaux du soir ont été relus dans le code avant d'être déposés.
- **Non couvert.**
  - Aucun test Django lancé, aucun rejeu navigateur.
  - Les quatre écarts S2-S3 sont statiques : pas de sonde.
  - Non vérifié : tous les chemins d'acceptation d'un devis émettent-ils bien `devis_accepted` (ASUP49) ?
  - Non vérifié : la traduction en 409 de `ConflitEtat` par la vue de la corbeille (ASUP11).
- **Statut.** Le groupe reste « construit », pas « vérifié ». Il garde un S1 ouvert (C-ASUP-VER2-101) et trois S2 nouveaux.
  ASUP1-3 ne sont pas cochées sur `main` ; leurs enregistrements d'acceptation PASS attendent le merge de la branche
  d'acceptation.
- **Suite.** Une contre-visite des correctifs sera due quand ASUP57-62 seront cochées.

## 7. Coût

- Après-midi : 1 vérificateur (opus, effort élevé), environ 0,2 M de jetons.
- Soir : 1 vérificateur (opus, effort élevé) et 1 rédacteur (opus). Leurs jetons ne sont pas mesurés ici.
- Aucun appel Fable.

<!-- verifie | groupe: ASUP | pct: 91 | ecarts_s1_s2: 4 -->
