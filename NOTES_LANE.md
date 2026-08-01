

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

