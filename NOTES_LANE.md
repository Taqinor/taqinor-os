

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

