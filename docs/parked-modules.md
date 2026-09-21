# Modules parqués — sortie physique du périmètre MVP solaire

> Registre machine : [`backend/django_core/core/parked.py`](../backend/django_core/core/parked.py)
> (`APPS_PARQUEES`, `GROUPES`, `PHASE2`, `ARCHIVE_REF`). Ce fichier-ci est la version
> humaine : **la liste des labels n'existe qu'une fois, dans `core/parked.py`** — ne
> jamais en recopier une seconde ailleurs.
>
> Source visible dans le dépôt (SOLMVP37) : [`backend/parked/README.md`](../backend/parked/README.md)
> — le miroir, rafraîchissable, du code d'AVANT coquillage des 47 apps (hors `migrations/`),
> le pendant backend de `frontend/parked/`.

## 1. Pourquoi

Décision fondateur du **20/09/2026** (tranchée, à ne jamais re-demander) : l'ERP vendu est un
**MVP solaire**. Le produit garde CRM, Visites, Calepinage, Ventes (+Facturation), Stock
(+Achats), Chantiers (cœur + suivi GPS), Après-vente (+Monitoring, Outillage, Documents
terrain), Portail client, Publicité (vendue aux clients aussi), Analyse, Paramètres,
Administration — plus la fondation invisible (core, authentication, roles, records,
notifications, audit, customfields, dataimport, tiers, trash, uxviews, onboarding,
offlinesync, agent, automation, publicapi, entites, adminops, semantic, identity,
accessreview, contact).

**49 apps sortent.** Reda a dit « fully out » : pas de toggle, le code et les tests
PARTENT. Et « whenever I want one back » : chaque module doit pouvoir revenir par une
recette écrite, **sans perte de données**. C'est ce double engagement que ce document tient.

Ce parcage **supersède** le mécanisme d'édition/toggle du Groupe SOL (supprimé par SOLMVP3).

### L'archive — la seule source de restauration

Le tag **et** la branche `archive/full-erp-2026-09-20` sont posés sur `main` **avant toute
suppression**, au commit `eb35db39` (PR #699). Ils ne sont **jamais** supprimés : tout le code
parqué s'y trouve verbatim.

```
git ls-remote --tags  origin | grep archive/full-erp-2026-09-20
git ls-remote --heads origin archive/full-erp-2026-09-20
```

## 2. Le contrat de la coquille (« coquille de migrations »)

C'est le **seul** mécanisme de sortie autorisé. Une app parquée :

- ne garde sur le disque que `__init__.py`, `apps.py` (label + manifeste `parked: True`),
  `migrations/` (verbatim **+ une** migration finale
  `SeparateDatabaseAndState(state_operations=[DeleteModel…], database_operations=[])`)
  et un `models.py` **sans aucun modèle** (règle exacte ci-dessous) ;
- **reste dans `INSTALLED_APPS`** — c'est ce qui garde valide le graphe de migrations des
  apps conservées. Donc **jamais de squash** ;
- n'expose **aucune** url, **aucune** tâche Celery / entrée beat, **aucun** test, **aucun**
  écran, **aucun** `contract_samples/`, **aucune** spec e2e ;
- ne perd **aucune table** et **aucune ligne de `django_migrations`** : la migration finale
  ne touche que l'ÉTAT Django (`database_operations=[]`). **Jamais de `DROP TABLE`.**

### Le `models.py` d'une coquille : un TALON, pas forcément un fichier vide

La règle **exacte** — celle que vérifient `core/tests/test_parked_registry.py` et
`python scripts/parquer_app.py --verifier` (source unique : `core.parked.modeles_declares`) —
est : **aucune classe héritant de `models.Model`**. Le cas normal reste le fichier vide
(docstring seul) : 36 des 47 coquilles sont dans ce cas.

Mais les migrations sont **gelées et conservées verbatim**, et certaines référencent un
symbole du `models.py` de leur propre app — typiquement le `default=` callable d'un champ
(`default=apps.pos.models._default_share_token`) que Django a sérialisé par son chemin
d'import. Vider le fichier rend ces migrations **inimportables** : le graphe **entier** casse
sur un `AttributeError`, et — piège — **cela ne se voit que dans un processus neuf** (dans le
processus qui vient de coquiller, le module est déjà importé avec ses modèles).

La coquille garde donc un **talon** : le strict nécessaire, recopié **verbatim** de l'original
— fonctions module-level, énumérations `TextChoices`/`IntegerChoices`, une classe-namespace
simple portant une énumération imbriquée quand une migration écrit `Modele.Enum`, plus les
imports et constantes dont ces symboles dépendent. Rien d'autre : **jamais** un modèle, jamais
un bout de logique métier.

`manage.py parquer_app` fait tout cela mécaniquement : il scanne les migrations de l'app
(`apps.<x>.models.<nom>`, `from apps.<x>.models import …`, alias), extrait ces définitions par
`ast` avec la fermeture de leurs dépendances, écrit le talon — et **vérifie dans un
sous-processus neuf que le graphe de migrations charge encore avant de supprimer le moindre
fichier**. Si la vérification échoue, `models.py`, `apps.py` et la migration-coquille sont
**remis en l'état** et la commande refuse. Elle refuse aussi, sans rien écrire, quand un
symbole réclamé est introuvable au niveau du module ou quand c'est un modèle Django : dans ce
cas le talon s'écrit **à la main** (la commande ne devine pas).

Les 11 talons posés le 21/09/2026 (par SOLMVP30b) :

| App | Symboles gardés dans le talon |
| --- | --- |
| `btp_chantier` | `_default_btp_token`, `lots_types_defaut` (+ `LOTS_TYPES_DEFAUT`) |
| `compta` | `_comptes_frais_defaut` |
| `contrats` | `_default_depot_contrepartie_token` |
| `datarooms` | `_default_acces_token` |
| `douane` | `_defaut_alerte_jours` |
| `gestion_projet` | `_generer_token_portail` |
| `kb` | `_default_partage_token` |
| `pos` | `_default_share_expiry`, `_default_share_token`, `default_code_retrait` |
| `promotions` | `default_carte_cadeau_code`, `default_coupon_code` |
| `qhse` | `_default_qr_token` |
| `rh` | `_default_promesse_expiry`, `_default_promesse_token` |

Deux conséquences à connaître :

- **Les liens FK gardé → parqué partent en `RemoveField`** (destructif-revertable : seule la
  colonne de lien disparaît, jamais la table pointée). Inventaire du 20/09 :

  | App parquée | Lien retiré | Depuis |
  | --- | --- | --- |
  | `flotte` | `ActifFlotte`, `Vehicule` | `stock` (SOLMVP12) |
  | `qhse` | `NonConformite` | `stock` (SOLMVP12) |
  | `rh` | `Departement` | `stock` (SOLMVP12) |
  | `rh` | `Competence` | `sav` (SOLMVP14) |
  | ~~`ged`~~ | ~~`Document`~~ | ~~`portail` (SOLMVP16)~~ — **ANNULÉ par SOLMVP16b** : la GED RESTE dans le MVP, la FK `document_ged` de `DocumentClientPortail` est rétablie et la migration `RemoveField` (jamais appliquée nulle part) supprimée. |

  Le décompte définitif et la note déployeur sont arrêtés par SOLMVP12/14/16 puis
  **SOLMVP53** *(à compléter par SOLMVP53)* — le préambule du Groupe SOLMVP annonce 7 liens,
  l'inventaire par tâche en énumère 5 qui partent vraiment ci-dessus (le 6e, `portail` →
  `ged.Document`, est rétabli par SOLMVP16b).
- **Les appels function-local gardé → parqué sont supprimés avec la fonctionnalité**, jamais
  remplacés par une garde `is_installed` : le code d'une app parquée **n'existe plus**.

Ordre obligatoire du parcage : archive → détacher les apps gardées → coquiller → frontend →
config/docs → gate.

## 3. Les 49 apps parquées

Une ligne par app = ce qu'elle était (résumé de son manifeste `apps.py`). Les familles sont
celles de `GROUPES` dans `core/parked.py`, et chaque famille est une lane de coquillage.
*La colonne « coquillée » est renseignée par SOLMVP30-36 au fur et à mesure.*

### Finance & conformité — 9 apps *(coquillées par SOLMVP30)*

| App | Ce qu'elle était |
| --- | --- |
| `frais` | Notes de frais, rapports, plafonds de politique, barèmes kilométriques / per-diem chantier. |
| `fpa` | FP&A : cycles budgétaires, prévisions glissantes, scénarios what-if, analyse des écarts. |
| `assurances` | Polices d'entreprise (RC pro, décennale, multirisque, cyber), primes, sinistres, attestations. |
| `einvoice` | Facturation électronique au schéma DGI marocain, signature, file de transmission Simpl. |
| `fiscal` | Calendrier fiscal marocain (TVA/IS/IR/CNSS/taxe pro), attestations tenant, registre UBO, veille. |
| `juridique` | Dossiers juridiques : parties, audiences, prescriptions, cabinets, honoraires, provisions. |
| `litiges` | Réclamations clients et litiges. |
| `credit` | Limite de crédit, credit hold, scoring et assurance-crédit client. |
| `compta` | Comptabilité générale CGNC et fiscalité. |

### RH — 3 apps *(coquillées par SOLMVP31)*

| App | Ce qu'elle était |
| --- | --- |
| `paie` | Paramètres CNSS/AMO/IR et bulletins de paie. |
| `flotte` | Véhicules, engins et maintenance interne. |
| `rh` | Dossier employé, congés et présences. |

### Commercial avancé — 9 apps *(coquillées par SOLMVP32)*

| App | Ce qu'elle était |
| --- | --- |
| `veille_ao` | Sas de veille : avis de marché collectés/importés, triés à la main avant de devenir des AO. |
| `btp_chantier` | Vertical BTP/EPC : réserves géolocalisées sur plan, RFI, visas de documents, journal, avenants, DGD. |
| `ao` | Appels d'offres publics/privés : BOQ, cautions, dossier administratif, échéancier, gagné/perdu. |
| `cpq` | Configuration, prix et devis (CPQ enterprise). |
| `marketing` | Email/SMS marketing, séquences de relance, enquêtes/NPS, événements, fidélité. |
| `contacts` | Organigramme d'achat multi-rôles par client. |
| `territoires` | Règles d'affectation et rotation des leads par territoire. |
| `voip` | Softphone intégré (SIP/WebRTC) : appel navigateur, call-pop, journal automatique. |
| `conversation_ai` | Enregistrements d'appels commerciaux : transcription asynchrone et analyse du transcript. |

### Opérations & services — 9 apps *(coquillées par SOLMVP33)*

| App | Ce qu'elle était |
| --- | --- |
| `datarooms` | Salles de données sécurisées : collections GED, liens et expirations par viewer, filigrane, journal. |
| ~~`ged`~~ | **RESTE (décision fondateur 21/09 : Documents/GED dans le MVP)** : la gestion électronique documentaire est un module vendu du MVP solaire (lanceur « Documents ») — PV de réception, attestations, contrats client, dépôts publics, signatures. Elle sort donc du registre : 47 apps sortent, pas 48. `apps/ged` est détaché des apps parquées par SOLMVP16b (liens `kb`/`rh` retirés) et ses liens depuis les apps gardées (portail, calepinage, notifications, reporting, customfields, core) sont rétablis. |
| `esg` | Reporting ESG/RSE consolidé (périodes figées, catalogue GRI-lite, rapports, trajectoires). |
| `qhse` | Qualité, hygiène, sécurité, environnement. |
| `gestion_projet` | Projets multi-chantiers et ressources. |
| `contrats` | Gestion des contrats (CLM). |
| `innovation` | Boîte à idées interne, campagnes d'innovation, canal de feedback produit in-app. |
| `kb` | Base de connaissances : articles et procédures internes. |
| `chat` | Messagerie interne d'équipe (Discuss). |

### Supply & retail — 5 apps *(coquillées par SOLMVP34)*

| App | Ce qu'elle était |
| --- | --- |
| `promotions` | Moteur de promotions panier, coupons à code unique, cartes cadeaux. |
| `pos` | Point de vente comptoir (accessoires). |
| `transport` | Ordres de transport, étapes, affrètement, preuve de livraison, coûts de fret, CO2 estimé. |
| `douane` | Dossiers d'export (incoterm, ports, pièces, statut douanier). |
| `scm` | Planification supply chain : prévision de demande, ABC, politiques de stock, réappro, S&OP. |

> **Note fondateur (SOL8, 02/09/2026) :** TAQINOR utilisait `douane` et `scm`. Tables et
> données **conservées** ; les modules reviennent par la recette du §5.

### Technique — 7 apps *(coquillées par SOLMVP35)*

| App | Ce qu'elle était |
| --- | --- |
| `grc` | Gouvernance, risques et conformité : registre des risques, contrôles, RGPD/09-08, rétention. |
| `dataquality` | Règles de validation, complétude et dédoublonnage. |
| `mlops` | Versionne par société les paramètres des scorers prédictifs et matérialise leurs signaux. |
| `ai_governance` | Copilotes IA contextuels et surveillance des modèles. |
| `extensions` | Catalogue global (lecture seule) de packages d'extension no-code. |
| `migration` | Projets de migration ERP sortants (Odoo/Sage/Excel) avec rapport de réconciliation. |
| ~~`statuspage`~~ | **RESTE (fondation, décision orchestrateur 21/09)** : `core` lit ses modèles (`sla.py`, `tasks.py`, registre de fiabilité, 6 modules de tests) par `get_model('statuspage', …)` ; la sortir aurait rendu un uptime de 100 % non dérivé. 48 apps sortent, pas 49. |

### Verticaux — 7 apps *(coquillées par SOLMVP36)*

| App | Ce qu'elle était |
| --- | --- |
| `agriculture` | Exploitations, parcelles, campagnes culturales, intrants, traçabilité phytosanitaire. |
| `education` | Année/niveau/classe, dossier famille/élève, inscriptions, scolarité, présences, matières. |
| `hospitality` | Plan des chambres, réservations, check-in/out, folio client, housekeeping. |
| `immobilier` | Patrimoine, baux, quittancement et GMAO bâtiment. |
| `mrp` | Production : postes de charge, gammes, ordres de fabrication, MRP, ordonnancement, coût standard. |
| `sante` | Agenda multi-praticiens, admission, nomenclature des actes, facturation patient/tiers payant. |
| `ecommerce_connect` | Synchronisation catalogue/stock/commandes Shopify et WooCommerce. |

Ces 7 verticaux étaient déjà hors édition : ils passent par la même coquille et
`INSTALLED_APPS` les reprend, le filtre d'édition n'existant plus (SOLMVP3).

## 4. PHASE 2 — les premiers à revenir

Ordre décidé le 20/09/2026 (à retenir, **jamais à re-décider**) — `PHASE2` dans
`core/parked.py` :

1. **`chat`** — Messages (messagerie interne d'équipe).
2. **`ao` + `veille_ao` + `btp_chantier`** — ensemble, future **édition « Solaire C&I / EPC »**.
3. **Pack Maroc : `paie` + `einvoice` + `fiscal`.**
4. **`compta`** — comptabilité générale.

La GED était le n°2 de cette liste : **décision fondateur du 21/09/2026, elle RESTE dans le
MVP** (module « Documents ») — il n'y a donc plus rien à faire revenir pour elle.

Les sous-fonctions retirées du module Chantiers (sous-traitance, prix négociés,
documents-projet, suivi-projet, consultations fournisseurs, astreintes) restent en base,
modèles et tables conservés, et sont listées ici en PHASE 2 *(à compléter par SOLMVP13)*.

## 5. Recette de retour d'un module

Générique, valable pour les 49 ; `<x>` = le label. Aucune donnée n'est recréée : les tables
n'ont jamais été supprimées, on ne fait que **rendre les modèles à Django**.
*La recette est prouvée de bout en bout sur une app réelle par **SOLMVP51**, qui finalise
cette section et `docs/module-playbook.md` ; l'ordre exact des étapes 2-3 y est verrouillé.*

1. **Restaurer le code backend depuis l'archive** — tout sauf `migrations/`, qui est déjà
   verbatim dans la coquille :
   ```
   git checkout archive/full-erp-2026-09-20 -- backend/django_core/apps/<x>
   git checkout HEAD -- backend/django_core/apps/<x>/migrations
   ```
   Le `models.py` de l'archive **remplace** celui de la coquille, talon compris : un talon
   (§2) n'est qu'un extrait verbatim de ce même fichier, il n'y a donc rien à fusionner et
   rien à recopier. Le vrai `models.py` redéfinit tous les symboles que les migrations gelées
   réclament, plus les modèles.
2. **Renverser la migration d'état** (`<n-1>` = la migration qui précède la coquille) :
   ```
   python manage.py migrate <x> <n-1>
   ```
   Elle est `database_operations=[]` : ce `migrate` ne touche **aucune** table, il rend
   seulement les modèles à l'état Django.
3. **Supprimer le fichier de la migration-coquille** une fois renversée, sinon le prochain
   `migrate` la réapplique. `makemigrations --check` doit alors être vert sans nouvelle
   migration.
4. **Rendre les liens FK** que le parcage avait retirés côté app gardée (tableau du §2) :
   **une NOUVELLE migration** `AddField` dans l'app gardée — jamais une réécriture de la
   migration `RemoveField` déjà partie en prod.
5. **Restaurer le frontend** depuis la même archive :
   `frontend/src/features/<x>/`, `frontend/src/pages/<x>/`, `frontend/src/api/<x>Api.js`,
   puis réinscrire la route dans `router/moduleRoutes.jsx`.
   ⚠️ Le dossier frontend ne porte pas toujours le label de l'app (`chat` → `messaging`,
   `scm` → `logistique`, `pos` → `magasin`…) : l'inventaire exact est celui de SOLMVP40.
6. **Ré-inclure les urls** dans `erp_agentique/urls.py` (et, si le module en avait, ses
   entrées Celery beat, ses `contract_samples/` et ses specs e2e, restaurés de l'archive).
7. **Retirer le label de `APPS_PARQUEES`** dans `core/parked.py` (et de `GROUPES`, et de
   `PHASE2` s'il y figurait).
8. **Re-passer les gardes** : `scripts/check_parked_apps.py`, `scripts/check_platform.py`,
   `python manage.py makemigrations --check`, `flake8`, puis la CI complète.

Ce que la recette ne fait **jamais** : recréer une table, toucher `django_migrations` à la
main, squasher des migrations, ou réécrire une migration déjà appliquée en production.

## 6. Notes déployeur

*(à compléter par SOLMVP53)* — migrations livrées par le parcage (`RemoveField` des liens
gardé → parqué + les 49 migrations d'état), confirmation qu'**aucune table n'est supprimée**,
ordre sûr pour l'auto-deploy, et « rien à faire à la main ». Les chiffres avant/après
(bundle frontend, durée `backend-tests`) y sont consignés au DONE LOG.

La garde CI permanente `scripts/check_parked_apps.py` (job `stage-names`) échoue si un
import, une FK, un include d'urls ou une tâche beat vise un label de `APPS_PARQUEES` hors
`*/migrations/*` — elle est créée par SOLMVP53.
