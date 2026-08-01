

# NOTES — lane `backend/core-calepinage` (Groupe AOF)

Tâches livrées : AOF34 → AOF57, AOF162, AOF183, AOF184, AOF185 (28 tâches).
Le paquet `core/calepinage/` reste PUR (stdlib seule ; le test AST de pureté
d'AOF33 est vert) et s'importe SANS Django : `python -m unittest discover -s
core/tests -p "test_calepinage*.py"` → **483 tests verts, sans base de données**.

## Réconciliation FRDISI : les chiffres RÉELS des scripts témoins

Les scripts témoins de `docs/ao-frdisi/releve-2026-07-27/` ont été rejoués
verbatim (partie comptage seule, sans matplotlib) par
`scripts/reconcilier_calepinage_frdisi.py`, qui refuse d'écrire un golden tant
que le témoin et le moteur neuf ne disent pas le MÊME nombre. Résultat :

| bâtiment | script témoin | compte du témoin | moteur neuf |
|---|---|---|---|
| A — aile en L (polygone) | `vue_bat_A_v2.py` | **148** | **148** ✅ (42/46/8/14/12/8/10/8) |
| B — arc 3 segments | `vue_bat_B_v2.py` | **120** | **120** ✅ (S1 48 · S2 34 · S3 38) |
| C — école (rectangle) | `vue_bat_C.py` | **314** | **314** ✅ (86/86/60/82) |

Corroborations obtenues sans les chercher : l'échelle de l'arc redonne
A = 112, B = 108, C = 100, D = 104, E = 114, F = 120, G = 126, H = 126 ; les
marges de l'arc redonnent 4,15 cm (tronçon) et 4,90 cm (bande) ; la
contre-épreuve de kit redonne S2 paysage 34 contre portrait 24 et S3 paysage 44
contre portrait 42 ; l'arbitrage de GRECT vaut +8 modules et celui de PAN +4,
exactement ce que le docstring du script témoin annonce.

## Divergences assumées avec le TEXTE du plan (et pourquoi)

1. **« L'aile L redonne 178 » (AOF44) / « kits mixtes : 148 → 178, +30 »
   (AOF54).** Le script témoin publie **148** (rangées explicites, kit portrait
   unique) et le DP exact au centimètre, kits mixtes autorisés, allée 0,60,
   rives 0,35, trouve **172** (+24), `optimal=True`. Aucun réglage testé (rive
   de l'aile appliquée ou non, emprises 4,70/2,25 exactes, pas de recherche
   1 cm, contour avec ou sans rive re-entrante) ne produit 178. AOF183 tranche
   explicitement ce cas — « si l'extraction introduit une erreur silencieuse,
   le golden VERROUILLE l'erreur pour toujours » : le témoin fait foi, les
   tests verrouillent 148 (témoin) et 172 (DP mixte), jamais un 178 non
   reproductible.
2. **« 178 / 126 / 314 » (AOF183).** 314 est exact ; 148 remplace 178 (ci-
   dessus) ; **126 est le compte de l'arc SANS les 3 éléments non cotés**
   (marches G et H de l'échelle), le compte RETENU et publié étant 120 — les
   deux sont testés, chacun sous son nom.
3. **« Bâtiment C : allée gratuite de 0,60 à 1,94 »(AOF50).** Le DP tient le
   compte de 314 jusqu'à **2,04 m** (au-delà, la 4ᵉ rangée ne tient plus :
   0,35 + 4×4,70 + 3×2,04 = 25,27 pour 25,62 relevés). La valeur PUBLIABLE
   proposée reste **1,90 m**, obtenue par la règle « borne haute − 10 cm de
   marge de sécurité, arrondie au multiple de 10 cm inférieur » — le chiffre
   du dossier, atteint par une règle explicable au maître d'ouvrage plutôt que
   par un littéral.
4. **Souches écartées du bâtiment C (AOF183).** Les 4 souches provisoires
   figurent au golden en provenance `ECARTE` avec leur motif, mais **avec une
   emprise nulle** : leur géométrie n'a jamais été relevée et le script témoin
   ne la conserve pas. Elles ne sont donc pas absentes (la traçabilité est
   tenue) et aucune géométrie n'a été inventée.

## Correctif porté sur AOF35 pendant AOF44

`obstacles.intervalles_bloques` comparait `o.y1 + c <= y0` SANS tolérance :
`20.35 + 0.30` vaut `20.650000000000002` en binaire, si bien qu'un obstacle
dont le dégagement AFFLEURE une rangée bloquait une bande entière. Coût mesuré
sur l'aile L : 148 → 142 (6 modules perdus, sans qu'aucune cote ne bouge). Le
moteur historique portait déjà ce `1e-9` ; `units.TOL_LONGUEUR_M` le porte
maintenant, des DEUX côtés (compteur et poseur).

## Écarts de contrat mineurs, documentés

* **Repère unifié.** Le plan écrit `bande(x0, largeur) -> (ymin, ymax)`
  (convention de la planche de l'aile L) et `pas_de_pose(kit, y0)` (convention
  de la planche de l'arc) : les deux planches nomment la position de rangée
  avec des lettres OPPOSÉES. Le moteur fixe UNE convention — `x` = abscisse le
  long de la rangée, `y` = coordonnée transversale (celle de `calepinage.py`,
  le moteur historique) — et garde les noms de méthodes du contrat. C'est
  documenté en tête de `surfaces/base.py`.
* **`optimum.optimiser` a gagné un paramètre `positions`** (AOF48) alors que
  `optimum.py` n'est pas dans les `Files:` d'AOF48 : sans lui, le balayage sur
  points de rupture n'a aucun consommateur. Ajout strictement additif, défaut
  inchangé (grille au centimètre), et un test vérifie que les comptes sont
  IDENTIQUES sur les 3 jeux entre les deux chemins.
* **Points de rupture.** Le raccourci n'est adopté que s'il est plus petit que
  la grille : avec deux kits, la fermeture par chaînage coûte plus qu'elle ne
  rapporte, et `perf.positions_utiles` rend alors la grille. Gain mesuré à un
  kit sur l'aile L : 4 639 positions → 591, DP 0,69 s → 0,07 s, compte
  identique.
* **`garde_fous.valider` fait un SAT de TOUTES les paires de tables** (O(n²)).
  Sur un plan réel (~150 tables) c'est quelques dizaines de millisecondes ;
  c'est seulement le fuzz d'AOF185 qui en souffre, d'où ses 120 cas validés sur
  les 500 engendrés (les 500 passent l'invariant compteur == poseur).

# NOTES — lane `backend/core-calepinage-rendu` (AOF63-AOF70)

Lane strictement additive : elle ne crée QUE `core/calepinage/rendu/**` et ses
tests dans `core/tests/`. Aucun fichier existant de `core/calepinage/` n'est
touché (une autre lane y travaille en parallèle).

## BESOINS À ARBITRER AU FOLD (aucune action prise ici)

1. **`core/tests/test_calepinage_purete.py` (AOF33) doit accepter `matplotlib`
   dans le SEUL sous-paquet `rendu/`.** Le test de pureté marche sur TOUS les
   fichiers de `core/calepinage/` et sa liste blanche est « stdlib + numpy ».
   Or AOF63 impose explicitement « matplotlib Agg » dans `rendu/feuille.py`, et
   le docstring de `core/calepinage/__init__.py` prévoit lui-même le rendu
   (« le rendu retourne des OCTETS »). Le fichier n'existe pas dans ce worktree,
   donc rien n'a été modifié.
   *Mitigation déjà faite ici pour réduire le correctif à une ligne :*
   **`rendu/feuille.py` est le SEUL fichier du sous-paquet qui importe
   matplotlib** — les huit autres modules (`cartouche`, `couleurs`, `planche`,
   `bandeau`, `notes`, `arc`, `profils`, `metadata`) ne parlent qu'aux
   primitives de `Feuille`. Le correctif attendu est donc d'autoriser
   `matplotlib` pour `rendu/` (ou de restreindre le walk du test à la racine du
   paquet). Aucun `savefig` n'est appelé (l'API bas niveau `print_figure` du
   canevas est utilisée), donc l'interdiction d'attribut d'AOF33 reste
   satisfaite telle quelle.

2. **`core/calepinage/__init__.py` n'a PAS été créé ni modifié.** Dans ce
   worktree le paquet `core/calepinage/` n'existe pas encore (il arrive avec la
   lane AOF33-57) : `rendu/` s'importe donc via un paquet-espace-de-noms. Au
   fold, le `__init__.py` de `dev-aof` s'ajoute sans conflit. Aucun export n'a
   été demandé au paquet parent : tous les imports internes visent le module
   directement (`from core.calepinage.rendu.feuille import Feuille`).

3. **Contrat import-linter `calepinage-est-un-noyau-pur`** : inchangé et
   satisfait (le sous-paquet n'importe aucun `core.models` / `core.services` /
   `apps.*` / Django).

4. **Adaptateur `Resultat` -> `DonneesPlanche` à écrire côté consommateur.**
   `rendu/planche.py` définit le CONTRAT de projection (`DonneesPlanche` et ses
   structures) mais ne connaît pas `core.calepinage.types` (pas encore sur cette
   base). La fonction qui projette un `Resultat`/`Plan` validé vers une
   `DonneesPlanche` appartient au consommateur (`apps.ao`) ou à une tâche
   ultérieure du paquet ; elle n'a été ni écrite ni devinée ici.

## DÉCISIONS DE CETTE LANE

* **Zéro `pyplot`.** `Feuille` instancie `Figure` + `FigureCanvasAgg` directement.
  C'est ce qui satisfait d'un coup les trois exigences d'AOF63 (pas d'état global,
  deux fils concurrents indépendants, zéro figure fuitée) et c'est aussi ce qui
  évite l'attribut `savefig` interdit par le test de pureté d'AOF33 (l'API
  bas-niveau `canvas.print_figure` est utilisée à la place).
* **Une seule tolérance d'arithmétique métier dans `rendu/`** : `bandeau.ecart`
  (AOF67), nommée dans `ARITHMETIQUE_TOLEREE` de
  `core/tests/test_calepinage_planche.py` et dont le corps est vérifié par AST
  dans `core/tests/test_calepinage_bandeau.py`.
* **Le « test de contenu binaire » d'AOF64 est doublé.** matplotlib écrit les
  PDF en polices Type 3 : aucun texte rendu n'y figure littéralement, donc un
  `assertNotIn(b"TAQINOR", pdf)` seul serait vert quoi qu'il arrive. Le contrôle
  porte donc (a) sur les textes rendus relus sur la figure et (b) sur le
  dictionnaire de métadonnées, seul littéral du fichier — avec témoin négatif.


## ARBITRAGE ORCHESTRATEUR (fold batch 2, 2026-08-01)

- **matplotlib dans core/calepinage/rendu/** : exemption ACCORDÉE et posée dans
  test_calepinage_purete.py (SOUS_PAQUET_RENDU + DEPENDANCES_RENDU). Portée : le seul
  sous-paquet rendu/, où matplotlib reste confiné à feuille.py. Le calcul demeure
  stdlib + numpy ; les verrous django/rest_framework/celery/I-O restent globaux.

# NOTES — lane backend/ao — TRONÇON 1 (AOF1-AOF5, AOF12-AOF32)

- AOF1 PARTIEL: la note d'une ligne à ajouter sous ODX22 dans `docs/PLAN.md`
  (« le shim compta↔ao a été INVERSÉ par AOF1 ») n'a PAS été écrite —
  `docs/PLAN.md` est explicitement INTERDIT à cette lane par la consigne du run.
  À faire par l'orchestrateur au moment du fold. Le reste d'AOF1 est livré.
- AOF1 PÉRIMÈTRE: `apps/compta/serializers.py` n'est pas dans les `Files:`
  d'AOF1 ; les 8 serializers AO y restent donc DÉFINIS et deviennent orphelins
  côté compta. AOF3 (dont les `Files:` incluent `apps/ao/serializers.py`)
  reloge leur corps dans `apps/ao/serializers.py`. Le nettoyage des doublons
  résiduels dans `apps/compta/serializers.py` revient à ODX22.
- AOF31 RISQUE CI RÉSIDUEL (à traiter au 1er run CI, ~30 s) :
  `scripts/check_openapi_schema.py` ne peut PAS tourner sur cet hôte Windows
  (WeasyPrint ne charge pas ses DLL GTK). J'ai ajouté à la main la seule
  signature déterministe (`Error|ContratApiAO|unable to guess serializer…`).
  Restent possibles des avertissements NEUFS de collision d'énumération
  drf-spectacular sur les champs de choix ajoutés par ce tronçon : `nature`,
  `axe`, `verdict`, `origine`, `etat`, `portee`, `forme`, `provenance`,
  `type_piece`, `type_exigence`, `type_couverture`, `type_fichier`,
  `orientation_modules` (les homonymes existent déjà dans compta/qhse/rh/
  marketing/kb…). `statut`, `role`, `mode`, `canal`, `type` sont DÉJÀ
  baselinés, donc sans effet. Correctif mécanique si la CI rougit :
  `python scripts/check_openapi_schema.py --write-baseline`, ou ajouter les
  lignes `Warning|<global>|enum naming … "<champ>"` manquantes.
- AOF31 PÉRIMÈTRE: le contrat d'API est publié en endpoint DÉRIVÉ du routeur
  (`GET /api/django/ao/contrat/`) plutôt que recopié dans CODEMAP §4 —
  `docs/CODEMAP.md` est interdit à cette lane. La mise à jour de §4 + le
  re-stamp `codemap_fingerprint.py --write` reviennent à l'orchestrateur.
- Fichiers de gate touchés hors `Files:` (maintenance mécanique de MES propres
  décalages de lignes, jamais un élargissement) : `scripts/on_delete_allowlist.txt`
  (15 entrées `apps/ao/models.py` RETIRÉES au profit de commentaires inline
  `# on_delete:` — la baseline RÉTRÉCIT ; `roles/models.py:419` → `:442`),
  `scripts/check_money_rounding.py` (7 entrées compta/services.py rebasées),
  `scripts/openapi_schema_allow.txt` (1 ajout), et les audits régénérés
  `docs/get-or-create-audit.md`, `docs/on-delete-financial-audit.md`,
  `docs/money-fields-audit.md`.


---

# NOTES — lane `backend/ao-fabrique B` (pièces, sanitisation, cohérence)

Base réelle du worktree : `dev-aof` (34f21ad3). Le worktree avait été créé sur
`main`, 138 commits en arrière — reset sur `dev-aof` avant la première tâche,
sans quoi aucune fondation AO n'était présente.

**Co-activité observée.** Au moment de ce run, `apps/ao/fabrique/` n'existait
PAS sur `dev-aof` : la lane A (AOF111-131 — contexte, empreinte, gabarits,
dérivations, bordereau, cascade, `DossierAO`, `EquipementAO`) tourne EN MÊME
TEMPS et ses fichiers ne sont pas visibles d'ici. Conséquence de conception,
assumée : **tous les modules de cette lane sont des fonctions PURES sur le
`contexte` de dossier passé en argument** — aucun import des fichiers de la
lane A, aucun fichier partagé avec elle. Le contrat consommé est documenté
dans le docstring de chaque module ; au fold, les deux lanes se rejoignent par
le dict de contexte.

## Points à reprendre au fold

- **AOF138 — `python-docx` NON inscrit dans `requirements.txt`.** La tâche
  porte `@blocked: nouvelle dépendance python-docx — accord fondateur` : le
  code est livré et testé sur ses DEUX voies (docx éditable + dégradation PDF
  « pièce à fournir »), mais la ligne de dépendance n'a pas été ajoutée. Une
  seule ligne à poser le jour de l'accord, aucune autre modification. Tant
  qu'elle n'est pas posée c'est la voie dégradée qui s'exécute en CI et en
  production — un état sain, pas une panne.
- **Ratchet AOF129 (`apps/ao/tests/test_aof_etancheite_pack.py`)** appartient à
  la lane A. Chaque pièce livrée ici porte SES propres assertions d'étanchéité
  dans son propre fichier de test ; l'extension du ratchet commun est à faire
  par la lane A au fold, sur les artefacts : note de calcul, checklist
  docx/pdf, page de garde + sommaire, rapport de contrôle, ZIP de dépôt, PDF
  « bon à tirer » (le classeur de rentabilité, lui, est directeur).

### Tâches bloquées par la composition (jamais de substitut local)

- **AOF141 — bascule d'équipement atomique : `[BLOCKED: attend AOF118]`.**
  `basculer_equipement()` opère sur `EquipementAO` (rôle, snapshot catalogue,
  fiche technique, `remplace` self-FK) — modèle livré par AOF118, absent de
  `dev-aof` au moment de ce run. Recréer un équipement local pour « pouvoir
  avancer » serait exactement le poste de dette n°1 du dépôt. Le PLAN de
  bascule (quels emplacements doivent changer, quelles grandeurs dérivées se
  recalculent, quelle fiche s'ajoute et laquelle se retire) est en revanche
  livré et testé dans `apps/ao/fabrique/bascule_rapport.py` (AOF142) : le jour
  où AOF118 est sur la branche, `basculer_equipement` n'a plus qu'à APPLIQUER
  ce plan en une transaction et à journaliser via `records.services.log_activity`.
- **AOF154 — endpoints de la fabrique : `[BLOCKED: attend AOF115]`.** Les six
  routes (génération de pack, rendu d'une pièce, téléchargement du ZIP,
  exécution du contrôle, historique de cascade, bascule) sont des actions SUR
  `DossierAO` — modèle d'AOF115, absent de `dev-aof` au moment de ce run. Il
  n'existe donc aucun queryset à scoper ni aucun `basename` à router. Écrire
  des routes contre un modèle imaginaire aurait produit une matrice de
  permissions non testable. Les briques que ces routes exposeront sont, elles,
  livrées et testées (production du pack, ZIP, bon à tirer, contrôle,
  sanitisation, cascade, propagation).
- **AOF155 — verrou de dossier : `[BLOCKED: attend AOF115]`.** Le verrou est
  un `select_for_update` sur la LIGNE `DossierAO` plus un drapeau persistant
  « opération en cours par X depuis HH:MM » — donc des champs et une migration
  sur un modèle qui n'existe pas encore. Recoder un verrou hors-base
  (fichier, cache) serait un substitut local à une primitive de la plateforme.
  À noter pour le fold : l'idempotence par empreinte livrée en AOF153 règle le
  double-clic d'UN utilisateur, pas l'édition concurrente de DEUX — les deux
  mécanismes sont complémentaires, AOF153 ne dispense pas d'AOF155.
- **AOF156 — approbation humaine avant dépôt : `[BLOCKED: attend AOF115 +
  AOF150]`.** La tâche branche `core.models.WorkflowDefinition` sur la
  transition `pret_a_deposer → depose` de `DossierAO` et fait porter à
  l'approbation l'EMPREINTE DU PACK approuvé (AOF150) — deux objets absents de
  la branche. Le noyau d'approbation existe déjà et sera CONSOMMÉ, jamais
  recodé. Le mécanisme de péremption d'approbation est le même que celui déjà
  livré et testé pour le rapport de contrôle (AOF148,
  `rapport_controle.est_perime`) : approuver un pack puis le régénérer doit
  invalider l'approbation, exactement comme cela périme le rapport.
- **AOF159 — partiellement livrée.** Le REGISTRE des six cibles, la péremption
  en cascade, le refus de « prêt à déposer » et l'historique des deltas sont
  livrés et testés (`apps/ao/fabrique/propagation.py`, deltas réels
  5 413 680 → 5 219 280 → 4 999 920 reproduits). L'EXPOSITION HTTP de cet
  historique (`views.py` + `selectors.py`) attend AOF115/AOF154 : il n'existe
  pas encore de `DossierAO` à interroger. `verifier_registre` est appelable
  telle quelle par le contrôleur de cohérence (AOF146) et par le test du
  gabarit de pack (AOF116).
- **AOF160 — partiellement livrée.** Le classeur directeur est livré et testé :
  coût de revient par poste avec TVA sur achats DIFFÉRENCIÉE (10 % panneaux /
  20 % reste), TVA collectée, TVA nette à reverser, bénéfice net HT, cellule de
  CONTRÔLE DE TRÉSORERIE, variante « panneaux facturés à 10 % », montants
  écrits en NOMBRES (jamais en chaînes), plus la tâche de fond
  `ao.produire_rentabilite_xlsx`. Les quatre chiffres de contrôle du dossier
  réel tombent au dirham (2 666 600 · 1 500 000 · 349 280 · −165 200) et
  l'identité `4 999 920 − 3 150 640 − 349 280 = 1 500 000` est vérifiée par un
  test. L'exclusion du pack est prouvée sur les TROIS assembleurs (sommaire,
  ZIP, bon à tirer). En attente : `views_directeur.py` + `CanViewAoRentabilite`
  + l'URL signée à durée courte, qui appartiennent à AOF157 (`EconomieAO`,
  permission `ao_rentabilite_voir`) — non présent sur la branche.

- **AOF158 livrée DEUX FOIS** (fabrique A hors-liste + fabrique B dans sa liste). Version
  RETENUE : celle de fabrique A (324 lignes, 353 de tests), déjà foldée ET vérifiée par
  l orchestrateur sur le cas réel FRDISI : 2 666 600 + 1 500 000 -> 4 166 600 HT /
  4 999 920 TTC, invariant au centime, marge 36,0 %, residu 8 800 sur la ligne
  d ajustement, aucun cout dans la vue publique. La version de fabrique B (262 lignes)
  est ecartee ; si un apport lui est propre (seuil, residu non soldable), le rattraper
  depuis worktree-wf_0144c3ae-0d5-1.
---

# NOTES — lane `backend/ao` (service moteur + API de calepinage)

Tâches de cette lane : AOF58, AOF59, AOF60, AOF61, AOF62, AOF71.

Contrainte de co-activité : deux autres lanes écrivent dans `apps/ao`. Cette
lane n'a donc modifié AUCUN de `models.py` / `serializers.py` / `views.py` /
`services.py` / `selectors.py`, ni aucune migration : tout son code vit dans
des fichiers NEUFS (`calepinage_io.py`, `calepinage_service.py`,
`calepinage_serializers.py`, `calepinage_views.py`, `calepinage_tasks.py`,
`ingestion_service.py`) et le seul point de couture est un `include()` ajouté
en fin d'`apps/ao/urls.py`.

## AOF58 — `[BLOCKED: nouvelle dépendance ezdxf — accord fondateur]`

Export DXF du calepinage. `ezdxf` est **absent de `requirements.txt`** et la
tâche est explicitement `[GATED]` sur l'accord du fondateur : aucune
dépendance n'a été ajoutée, rien n'a été écrit dans
`core/calepinage/export/dxf.py`. La tâche reste `[ ]`.

Deux points pour le jour du déblocage :

- l'IMPORT DXF (AOF72) partage la même dépendance mais reste un sujet DISTINCT
  (porte d'entrée vs livrable) — ne pas les fusionner sous une seule tâche ;
- la géométrie à exporter est déjà disponible sans recalcul :
  `apps/ao/calepinage_io.plan_vers_json()` rend enveloppe, rangées et tables
  posées, et `core/calepinage/rendu/` porte déjà les calques logiques.

## AOF59 — `[BLOCKED: décision fondateur — portée v1 de l'export bancable]`

Export de la géométrie vers PVsyst (`.SHD` / scène DAE). La tâche n'offre que
deux issues et **les deux sont hors de portée d'un agent** :

1. *livrer l'export* — invérifiable ici : « ouvrable dans PVsyst avec la scène
   attendue » ne peut être prouvé sans PVsyst, et publier un exporteur qui
   AFFIRME une compatibilité jamais constatée est précisément le genre de
   déclaration non vérifiée que ce dépôt refuse (le `.SHD` n'est pas un format
   publiquement spécifié ; une scène DAE resterait une hypothèse) ;
2. *acter le non-objectif v1* — c'est une **décision de portée produit**, donc
   du fondateur, pas de l'agent ; et son support (`docs/moteur-calepinage.md`,
   AOF194) **n'existe pas encore** sur cette base : l'écrire ici créerait le
   fichier d'une autre tâche.

La tâche reste `[ ]`. Rien n'a été écrit dans `core/calepinage/export/`.
Quand la décision tombe, la matière est prête : `calepiner()` rend déjà
enveloppe + obstacles + tables dans un repère métrique unique, donc l'export
sera une pure traduction, sans recalcul de scène.

## Écarts de fichiers assumés (co-activité `apps/ao`)

Les `Files:` d'AOF60/61/62/71 désignent `services.py`, `views.py`,
`serializers.py`, `tasks.py`. Deux autres lanes écrivant ces mêmes fichiers, le
code a été logé dans des modules NEUFS, sans rien réécrire :

| `Files:` déclaré | fichier réellement écrit |
|---|---|
| `apps/ao/services.py` (AOF60/62/71) | `apps/ao/calepinage_service.py`, `apps/ao/ingestion_service.py` |
| `apps/ao/views.py` (AOF61/62) | `apps/ao/calepinage_views.py` |
| `apps/ao/serializers.py` (AOF61) | `apps/ao/calepinage_serializers.py` |
| `apps/ao/tasks.py` (AOF61/71) | `apps/ao/calepinage_tasks.py`, `apps/ao/ingestion_tasks.py` |
| `apps/ao/urls.py` (AOF61) | `apps/ao/calepinage_urls.py` |

Deux seules coutures dans des fichiers partagés, toutes deux en **fin de
fichier** (append pur, conflit trivial) :

- `apps/ao/urls.py` : `urlpatterns += [path('', include('apps.ao.calepinage_urls'))]` ;
- `apps/ao/tasks.py` : deux `from .<module>_tasks import …` — obligatoires,
  l'autodécouverte Celery n'importe QUE `<app>.tasks`.

## À traiter au fold (orchestrateur)

1. **`views.VarianteCalepinageViewSet.retenir` (fichier d'une autre lane) n'a
   ni garde de péremption ni idempotence.** Il appelle directement
   `services.retenir_variante`, donc une variante `PERIME` peut y devenir
   retenue — exactement ce qu'AOF62 interdit. Correctif d'UNE ligne :
   remplacer l'appel par `calepinage_service.retenir_variante(...)` (qui lève
   `VariantePerimee`). Je ne l'ai pas fait : `views.py` est hors de mon
   périmètre de co-activité.
2. **`core/tests/test_action_permissions.py` est ROUGE sur `dev-aof`, avant et
   indépendamment de cette lane.** Le scanner compte **17** `@action` sans
   garde dans `apps/ao/views.py` alors que `UNGUARDED_ACTION_BASELINE` n'a
   aucune entrée `"ao"` (absent = 0 toléré). Cause : les viewsets AO sont
   gardés au niveau CLASSE par `AoBaseViewSet.get_permissions`, mais le
   scanner ne crédite qu'un `get_permissions` déclaré dans le corps de la
   classe elle-même — même situation que `accessreview`/`assurances`/`chat`,
   qui portent une entrée de baseline commentée. Correctif : ajouter
   `"ao": 17` au baseline avec le même commentaire de dette « coarse ».
   Vérifié avec `python -c "from core import action_permission_scan as s;
   print(len(s.unguarded_actions()['ao']))"`. **Mon viewset n'y ajoute rien**
   (`CalepinageVarianteViewSet` déclare son propre `get_permissions`).

## Manques de modèle relevés (aucun champ ajouté — chaîne de migrations mono-écrivain)

- **Aucun modèle de ZONE dans `apps/ao`.** `core/calepinage/zones.py` sait
  traiter 4 natures de contour (`ENVELOPPE`, `INTERDITE`, `RESERVEE`,
  `PREFEREE`) et le contrat JSON porte `zones`, mais rien ne les persiste :
  `calepinage_io.document_entree()` émet donc toujours `zones: []`. Une
  `ZoneToiture(toiture, nature, sommets, retrait_m, hauteur_m)` débloquerait
  les zones réservées (locaux techniques, cheminements) et le bonus de zone
  préférée du départage.
- **`PlanSource` ne stocke pas les dimensions du rendu.** Le contrôle de
  vraisemblance d'AOF71 est bien plus fort avec `largeur_px`/`hauteur_px`
  (« ce plan ferait 3 000 m de large ») ; faute de champ, le job les RETOURNE
  mais elles ne sont pas rejouables, et `calibrer()` doit les recevoir en
  argument. Deux champs `rendu_largeur_px` / `rendu_hauteur_px` suffiraient.
- **`resultat['rangees']` porte `x0` ET `y0` avec la MÊME valeur.** Le contrat
  d'AOF28 nomme `x0` la position d'une rangée ; le moteur, dans son repère
  unifié, la nomme `y0` (`x` court le long de la rangée). Les deux clés sont
  émises depuis la même variable, elles ne peuvent donc pas diverger — mais
  c'est une dette de nommage à trancher une fois pour toutes.

## Constat produit à remonter (vrai, mesuré, hors périmètre de cette lane)

**Le plan DP-optimal est systématiquement « au ras », donc AOF28 refuse de le
publier.** Mesuré sur les goldens FRDISI via `calepiner()` :

| bâtiment | modules | marge tronçon | marge bande | publiable AOF28 ? |
|---|---|---|---|---|
| C — école | 314 (= témoin) | 0,022 m | **0,000 m** (obstacle `LOCAL`) | non (seuil 0,04 m) |
| A — aile L | 148 (= témoin) | 0,010 m | **0,000 m** (obstacle `BAR3`) | non (2 seuils) |
| B — arc | 120 (= témoin) | 0,050 m | 0,00028 m | non (seuil de bande) |

Ce n'est pas un bug : le DP maximise le compte, donc il colle les rangées au
dégagement des obstacles. `core/calepinage/robustesse.py` a déjà la réponse
(`departager` choisit, à compte ÉGAL, le plan aux meilleures marges) mais
`optimum.optimiser` ne rend qu'UN plan optimal, pas les candidats. Sans une
tâche « énumérer les plans optimaux puis départager », **aucune variante ne
deviendra jamais `publiable`** et la garde d'AOF28 se dévaluera. Deux détails
de mise en œuvre déjà réglés de mon côté : une marge NON MESURÉE est persistée
`null` et non `0` (sinon une toiture SANS obstacle serait refusée pour une
marge de bande de zéro), et les marges de N surfaces sont cumulées axe par axe.

## Vérifications faites (et ce qui n'a PAS pu l'être ici)

Verts sur ce poste : `py_compile` + `flake8 --max-line-length=120` sur tous mes
fichiers, `scripts/check_platform.py`, `scripts/check_tenant_isolation.py`,
`scripts/check_celery_tasks.py`, `scripts/check_on_delete.py`,
`scripts/check_company_fk.py`, le scanner de gardes d'`@action` (0 ajout), et
un rejeu RÉEL des 3 goldens FRDISI par le service (`148 / 120 / 314`, hash
d'entrée identiques aux goldens, `optimal=True`).

Non exécutables ici, sans docker ni base : la suite Django (4 fichiers de
tests ajoutés) et `scripts/check_openapi_schema.py` (WeasyPrint ne charge pas
sur Windows, `libgobject-2.0-0` absent). Mitigation openapi : **toutes** mes
vues sont des `GenericAPIView`/`GenericViewSet` avec `serializer_class` ET un
`@extend_schema` explicite (`OpenApiTypes.OBJECT` là où la réponse est un dict
libre) — c'est la forme qui ne produit aucun avertissement drf-spectacular,
mais la baseline n'a pas pu être confrontée en local.

## Le bâtiment B des goldens exige les DEUX kits

`core/calepinage/golden/frdisi_2026_07_27/bat_B_arc.json` déclare deux kits
dans `kits` mais **un seul** (`AO_PORTRAIT`) dans `parametres.kits`, alors que
les segments S2 et S3 sont posés en PAYSAGE. Un service qui respecte le
document rend donc 108, pas 120. En ouvrant les deux kits au DP, le total
retombe **exactement** sur le témoin (48 + 34 + 38 = 120). C'est ce que fait
`apps/ao/tests/test_orchestration_calepinage.py`, et c'est une remarque pour la
lane `core-calepinage` : le `parametres.kits` de ce golden mérite d'être
complété.
---

## NOTES — lane `intégrations + gouvernance` (AOF163-169, 186, 193, 194)

- **AOF165 livrée PARTIELLEMENT (blocage réel, pas un raccourci).** `import_specs`
  (`obstacles`, `chaines`) est déclaré ET prouvé câblé (AOF30 + ARC32). Trois surfaces
  restent VIDES **à dessein**, chacune avec sa raison écrite dans `apps/ao/platform.py`
  et verrouillée par un test de `test_platform_ao.py` :
  * `searchable_models` — `apps/reporting/search.py` n'itère que les clés présentes À LA
    FOIS dans le manifeste ET dans son registre local `_SEARCH_SPECS` ; aucune spec AO n'y
    existe. Déclarer rendrait une recherche VIDE tout en périmant l'entrée de baseline
    `('ao.appeloffre','chatter_sans_recherche')` de `core/platform_coverage.py` → CI rouge
    des deux côtés. Le câblage manquant est dans une app transverse, que la tâche interdit
    explicitement de toucher (« sans toucher aux surfaces transverses »).
  * `record_targets` — ne peut pas s'étendre sans la précédente : une cible chatter non
    cherchable et hors baseline est une dérive NOUVELLE, donc rouge.
  * `customfield_models` — les valeurs sont stockées dans un champ `custom_data`
    (`JSONField`) porté par le MODÈLE CIBLE (patron `contrats.Contrat`, `flotte.Vehicule`).
    Aucun modèle d'`apps/ao/models.py` ne le porte, et ce fichier appartient à une autre
    lane de ce run. Débloquer = `custom_data` + migration additive sur `AppelOffre` et
    `BatimentAO`, puis déclarer DANS LE MÊME COMMIT.
  * `automation_state_fields` — la « date limite » n'est volontairement PAS déclarée : ce
    n'est pas un champ d'ÉTAT (les couperets passent par `EcheanceAO` + le beat
    `ao.rappeler_echeances`). Un test l'interdit explicitement.
- **AOF186 : `seed_ao_demo` sème le bordereau LEGACY.** AOF120 (bordereau v2 :
  `SectionBordereau`, TVA, `quantite_source`, verrou de quantité) n'est pas construit dans
  ce run — le seed crée donc `BordereauPrix` + 3 `LigneBordereau` (une par bâtiment,
  quantité = engagement du golden). Quand AOF120 landera, ajouter les sections au seed est
  additif : les quantités, elles, resteront lues dans les goldens. Le pack documentaire
  (fabrique) n'est pas semé non plus, pour la même raison.
- **AOF169 : le sas `apps/veille_ao` (Groupe VAO) n'existe pas encore.** La note du plan
  demande de le consommer plutôt que de réécrire un parseur ; il n'y a rien à consommer, donc
  l'import passe par la primitive plateforme `apps.dataimport.parsing.iter_rows` (jamais un
  parseur maison) et `services.creer_appel_offre_depuis_avis` est le point de contact UNIQUE
  que VAO30 trouvera déjà en place — à ne pas dupliquer.

# NOTES_LANE — lane `frontend/ao-qualite` (AOF187-192)

- **Base réelle vs base attendue.** Le brief de run annonce un worktree basé sur
  `dev-aof` avec `apps/ao` complet et « tout le frontend AO » déjà livré. En
  réalité ce worktree est basé sur `main` post-insertion du plan (commit
  `2793ee05`) : `backend/django_core/apps/ao` ne contient que ses squelettes
  (models/migrations/tests vides) et `frontend/src/features/ao/` ne contient
  QUE `module.config.jsx` dans son état WIR166 (« reste BACKEND-ONLY »,
  `nav`/`routes` absents). Aucun des prérequis nommés par mes tâches (AOF8
  hooks `data-ao-*`, AOF90/92 studio, AOF102 canvas, AOF176 dossier, AOF186 seed
  de démo) n'est présent dans CE worktree. Les tâches ci-dessous sont donc
  livrées CONTRE LE CONTRAT documenté dans l'en-tête du Groupe AOF et le texte
  intégral d'AOF8/AOF186 (lu dans `docs/PLAN.md`), pas contre du code
  vérifiable localement — aucun `npm`/DB disponible ici de toute façon pour
  exécuter les specs Playwright. À reconcilier par l'orchestrateur au moment du
  fold avec les lanes soeurs (`frontend/ao-socle`, `frontend/ao-studio`,
  `frontend/ao-dossier`, `backend/ao`).

- **Bilan AOF187-192 (aucune tâche marquée BLOQUÉE — 6/6 livrées) — hypothèses
  À VÉRIFIER par l'orchestrateur au fold :**
  - AOF187/188/190 (`ao-parcours.spec.js`, `ao-dossier.spec.js`, `ao-a11y.spec.js`,
    `ao-mobile.spec.js`) supposent des routes `/ao`, `/ao/affaires`, des liens
    accessibles « Toiture »/« Calepinage »/« Dossier »/« Variantes »/« Bordereau »,
    et un marqueur `FRDISI` dans le nom de l'affaire plantée par `seed_ao_demo`
    (AOF186) — à ajuster si `frontend/ao-socle` (AOF7)/`frontend/ao-dossier`/
    `backend/ao` (AOF186) nomment différemment. Les hooks `data-ao-*` utilisés
    reprennent MOT POUR MOT la liste normative d'AOF8 lue dans `docs/PLAN.md`
    (canvas, outil, verdict, compte, tiroir, variante, piece, controle, repere,
    provenance, etat) mais le fichier `E2E_HOOKS.md` lui-même n'existe pas
    encore dans ce worktree pour être diffé.
  - AOF189/190 (`ModeChantier.jsx`/`ModeMobile.jsx`) sont des WRAPPERS qui
    reçoivent l'éditeur réel en `children`/props — ils ne recréent aucun canvas
    ni logique de calepinage (qui n'existent pas encore ici). À brancher par la
    lane qui livre l'atelier réel (`frontend/ao-studio`).
  - AOF192 : le chunk `ao-studio` cible `features/ao/studio/**` (mes deux
    fichiers AOF189/190 seulement, pour l'instant) — AUCUNE mesure
    avant/après réelle prise (pas de `node_modules`/build ici) ; la logique de
    `check_bundle_budget.mjs` a été validée par exécution `node` directe contre
    un `dist/` synthétique (chunk `ao-studio` correctement détecté et flaggé
    au `modulepreload` de boot), mais jamais contre un VRAI build.
  - AOF191 (`fileReleve.js`) est autonome (zéro import cross-feature) et ses
    10 tests sont RÉELLEMENT exécutés en vert via `node --test` (pas seulement
    grep-vérifiés) — le seul livrable de cette lane avec une preuve d'exécution
    complète.
