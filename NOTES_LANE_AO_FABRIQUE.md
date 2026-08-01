# NOTES — lane `backend/ao-fabrique` A (socle, bordereau, cascade de prix)

19 tâches livrées, une par commit : **AOF111, 112, 113, 114, 117, 119, 121,
122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132** + **AOF158** (la
cascade de prix inverse, désignée « cœur de la lane » dans le brief et dont les
trois `Files:` sont dans le périmètre exclusif de cette lane).

**Contrainte de co-activité respectée à la lettre.** La lane n'a créé QUE
`backend/django_core/apps/ao/fabrique/**`, ses tests dans
`backend/django_core/apps/ao/tests/**` et ses gabarits dans
`backend/django_core/templates/ao/**`. Vérifié par `git diff --name-only <base>
HEAD` : aucun fichier de `apps/ao/{models,serializers,views,services,
selectors}.py`, aucune migration, ni `docs/PLAN.md`, ni `docs/CODEMAP.md`.

**Tests : 349 verts, sans base de données, sans docker.** Tous les modules sont
PURS (aucun import Django hors gabarits, aucune E/S, aucun accès ORM) et
reçoivent leurs données en PARAMÈTRE.

    cd backend/django_core
    python -m unittest discover -s apps/ao/tests -p "test_aof_*.py" -t .
    python -m unittest apps.ao.tests.test_approvisionnement \
        apps.ao.tests.test_report_quantites \
        apps.ao.tests.test_bibliotheque_prix \
        apps.ao.tests.test_duplication_affaire

Gates passés sur chaque fichier touché : `python -m py_compile` +
`flake8 --max-line-length=120 --extend-ignore=E501`.

## À CÂBLER au fold (le besoin est écrit ici, le câblage ne l'est pas)

Chaque point est une fonction PURE déjà écrite et testée ; il ne reste qu'à
l'appeler depuis la couche Django, qui appartient à l'autre lane.

1. **`selectors.py` — productible du site (AOF113).** Selector mince déléguant
   à `fabrique.productible.resoudre(ville, override=<CompanyProfile.
   productible_kwh_kwc>)`. Le module lit la table canonique
   `apps/ventes/quote_engine/productible.py` **en AST** (aucun import, aucun
   réseau) — ne PAS le remplacer par un import : le test d'AOF117 le refuse.
2. **`services.py` — contexte de dossier (AOF111).** Construire le mapping
   d'entrée depuis les modèles puis `fabrique.contexte.construire_contexte(
   dossier, productible=…, derivations=…)`. Stocker `contexte['empreinte']`
   sur chaque pièce rendue (`fabrique.empreinte.estampiller`) : c'est ce champ
   qui fait passer une pièce en PÉRIMÉ.
3. **`services.py` — approvisionnement (AOF119).** Alimenter
   `fabrique.approvisionnement.controler(equipements, catalogue)` depuis
   `stock.selectors`. L'état du catalogue ne doit porter AUCUN champ de coût :
   le module lève sinon (`EtatCatalogueInvalide`).
4. **`services.py` — bordereau.** `fabrique.import_bordereau` (cadre acheteur),
   `fabrique.report_quantites` (report depuis les variantes),
   `fabrique.ordonnancement` (renumérotation, totaux, contrôles),
   `fabrique.cascade` (cascade inverse) travaillent tous sur des **listes de
   dicts** ; il suffit de sérialiser `LigneBordereau` vers ce format et de
   ré-appliquer le résultat.
5. **`services.py` — duplication (AOF130).**
   `fabrique.duplication.dupliquer_affaire()` retourne `(affaire, plan)` ; le
   service crée la référence via `core.numbering` et trace au chatter
   `records` avec `fabrique.duplication.trace_chatter(...)`.
6. **Jobs (AOF127).** `fabrique.rendus.bordereau_xlsx.doit_passer_en_job(n)`
   dit quand basculer sur `core.jobs.submit` ; le submit appartient à la couche
   Django.
7. **PDF (AOF128/131/132).** Les modules de rendu produisent le CONTEXTE de
   gabarit et le nom du template ; l'appel `core.pdf.render_pdf(template=…,
   context=…)` (ARC11) est laissé à la couche Django — un seul point d'appel
   PDF, jamais WeasyPrint en direct.
8. **Champs de modèle attendus** (aucun créé par cette lane) :
   `LigneBordereau.quantite_source` ∈ {calepinage, manuelle, catalogue,
   acheteur} + FK variante + verrou, `SectionBordereau.numero/libelle/batiment`
   (AOF120), et le texte de clause paramétrable par société
   (`fabrique.clauses.texte_clause(texte_societe=…)`, repli sur le texte de
   référence).
9. **Champ INTERDIT en base (AOF125).** Aucun modèle ne doit porter
   `prix_unitaire_lettres` / `montant_lettres` / `arrete_lettres` /
   `total_lettres` / `somme_en_lettres` : les lettres sont RECALCULÉES. Le
   garde `fabrique.montants.verifier_absence_de_stockage(champs)` est prêt à
   être appelé depuis un test de modèle.

## EN ATTENTE D'UNE DÉCISION DU FONDATEUR

- **AOF129 — noms du bureau d'études en marque blanche.** Le ratchet sait
  refuser tout nom de bureau en marque blanche sur une pièce client ; la
  constante `NOMS_MARQUE_BLANCHE` de
  `apps/ao/tests/test_aof_etancheite_pack.py` est volontairement VIDE tant que
  la liste n'est pas arrêtée (mettre un nom deviné aurait produit un faux rouge
  sur une pièce légitime). Le mécanisme est testé avec un nom injecté : il
  suffit de remplir la constante pour qu'il morde.

## Décisions prises dans la lane

1. **Refus du sous-optimum SANS échappatoire (AOF112).** `compte_retenu <
   compte_optimal` est refusé à l'entrée de la fabrique, sans champ « motif » :
   un choix délibéré d'implanter moins se déclare CÔTÉ MOTEUR (politique de
   pas), de sorte que l'optimum publié soit celui de cette politique. Ajouter
   un motif ici aurait rouvert la porte à la recopie manuelle que le contrat
   ferme.
2. **Productible lu en AST, pas importé (AOF113).** Seule voie qui satisfasse à
   la fois « une seule source de vérité » et « aucun import de quote_engine »
   (règle #4 + AOF117). Un test compare la table lue à la table committée :
   elles ne peuvent pas diverger sans faire rougir la CI.
3. **Les lignes du cadre ACHETEUR ne sont pas dupliquées (AOF130).** Un BPU/DQE
   appartient à SA consultation ; le reporter dans une autre affaire y
   importerait des quantités imposées par un autre maître d'ouvrage. Elles sont
   listées comme volontairement écartées, jamais silencieusement reprises.

## Points d'attention pour le fold

- **AOF114, écart assumé de 1,9 Wh sur le banc.** Le dossier écrit « 96,48 kWh
  par banc » : c'est 6 × 16,08, donc un arrondi d'affichage réutilisé comme
  donnée de calcul. Le pack réel (51,2 V × 314 Ah) fait 16,0768 kWh et le banc
  96,4608 kWh. Le registre calcule en pleine précision — les deux s'affichent
  « 96,5 kWh » et « 289,4 kWh installés ». C'est le défaut même que le groupe
  supprime, documenté par un test.
- **Format de cellule XLSX (AOF127).** Le plan demande `# ##0,00 "DH"` ; un
  fichier XLSX stocke les séparateurs en notation neutre. Le format écrit est
  donc `[$-40C]#,##0.00\ "DH"`, qui rend « 4 999 920,00 DH » en français quelle
  que soit la locale du lecteur. Même intention, syntaxe imposée par le format
  de fichier.
- **Pas métier de la cascade (AOF158).** Les quatre pas (50 / 100 / 500 /
  1 000 DH) et leurs seuils sont CALÉS sur les prix réels du bordereau déposé :
  2 950 impose un pas de 50 (il n'est pas multiple de 100), 8 500 et 15 000
  tiennent au pas de 100, 39 500 au pas de 500, tout ce qui dépasse 50 000 est
  rond au millier. Changer un seuil rendrait un prix réel « non crédible ».
- **Jeu d'essai partagé.** `apps/ao/tests/aof_fixtures.py` (non collecté : il
  ne suit pas le motif `test*.py`) porte le bordereau FRDISI réel — A 1 034 100
  + B 744 200 + C 1 511 300 + communes 877 000 = 4 166 600 HT, TVA 833 320,
  TTC 4 999 920 — dans son état AVANT le déplacement des câbles DC du bâtiment
  B, pour que le test d'AOF123 rejoue le déplacement réel. Les lignes de
  câblage y sont chiffrées au mètre linéaire à 50 DH afin que TOUS les PU du
  jeu tombent sur leur pas métier.
- **La lane parallèle a déjà livré des migrations `apps/ao` jusqu'à
  `0006_resultat_ao`** ; le plan annonçait `0006_equipements_bordereau`. À
  arbitrer au fold (renumérotation ou fusion), hors périmètre de cette lane.
