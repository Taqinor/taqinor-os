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
