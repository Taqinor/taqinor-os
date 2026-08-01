# NOTES — lane `backend/ao-fabrique` A (socle, bordereau, cascade de prix)

Contrainte de co-activité respectée : cette lane n'a créé QUE
`backend/django_core/apps/ao/fabrique/**`, ses tests dans
`backend/django_core/apps/ao/tests/**` et ses gabarits dans
`backend/django_core/templates/ao/**`. Aucun fichier de
`apps/ao/{models,serializers,views,services,selectors}.py` ni de
`apps/ao/migrations/**` n'a été touché.

Tous les modules sont PURS (aucun import Django, aucune E/S, aucun accès ORM) et
reçoivent leurs données en PARAMÈTRE. Les tests tournent sans base :

    cd backend/django_core
    python -m unittest discover -s apps/ao/tests -p "test_aof_*.py" -t .

## À CÂBLER au fold (le besoin est écrit ici, le câblage ne l'est pas)

Chaque point ci-dessous est une fonction PURE déjà écrite et testée ; il ne
reste qu'à l'appeler depuis la couche Django, qui appartient à l'autre lane.

1. **`apps/ao/selectors.py` — productible du site (AOF113).** Ajouter un
   selector mince déléguant à `fabrique.productible.resoudre(ville,
   override=<CompanyProfile.productible_kwh_kwc>)`. Le module lit la table
   canonique `apps/ventes/quote_engine/productible.py` en AST (aucun import,
   aucun réseau) — ne PAS le remplacer par un import, le test d'AOF117 le
   refuse.
2. **`apps/ao/services.py` — contexte de dossier (AOF111).** Construire le
   mapping d'entrée depuis les modèles, puis
   `fabrique.contexte.construire_contexte(dossier, productible=…,
   derivations=…)`. Stocker `contexte['empreinte']` sur chaque pièce rendue
   (`fabrique.empreinte.estampiller`) : c'est ce champ qui fait passer une
   pièce en PÉRIMÉ.
3. **Champs de modèle attendus** (aucun n'a été créé par cette lane) :
   - `LigneBordereau.quantite_source` ∈ {calepinage, manuelle, catalogue,
     acheteur} + FK variante + verrou (AOF120, autre lane) — consommés par
     `fabrique.report_quantites` et `fabrique.import_bordereau` sous forme de
     dicts.
   - `SectionBordereau.numero/libelle/batiment` (AOF120) — consommé par
     `fabrique.ordonnancement` et les deux rendus.
   - Clause de réserve paramétrable par société — `fabrique.clauses` la reçoit
     en paramètre (`texte_societe`), avec le texte de référence en repli.
4. **`apps/ao/services.py` — duplication d'affaire (AOF130).**
   `fabrique.duplication.plan_de_duplication(...)` retourne le PLAN (ce qui est
   copié, ce qui est délibérément omis) ; le service exécute le plan et trace
   au chatter `records`.
5. **Jobs (AOF127).** `fabrique.rendus.bordereau_xlsx.doit_passer_en_job(n)`
   dit quand basculer sur `core.jobs.submit` ; le submit lui-même appartient à
   la couche Django.
6. **PDF (AOF128/131/132).** Les modules de rendu produisent le CONTEXTE de
   gabarit et le nom du template ; l'appel `core.pdf.render_pdf` est laissé à
   la couche Django (un seul point d'appel, jamais WeasyPrint en direct).

## EN ATTENTE D'UNE DÉCISION DU FONDATEUR

- **AOF129 — noms du bureau d'études en marque blanche.** Le ratchet
  d'étanchéité sait refuser tout nom de bureau en marque blanche sur une pièce
  client ; la constante `NOMS_MARQUE_BLANCHE` de
  `apps/ao/tests/test_aof_etancheite_pack.py` est volontairement VIDE tant que
  le fondateur n'a pas arrêté la liste (mettre un nom deviné aurait produit un
  faux rouge sur une pièce légitime). Le mécanisme est testé avec un nom
  injecté : il suffit de remplir la constante pour qu'il morde.

## Décisions prises dans la lane

- **Refus du sous-optimum (AOF112) sans échappatoire.** `compte_retenu <
  compte_optimal` est REFUSÉ à l'entrée, sans champ « motif » : un choix
  délibéré d'implanter moins se déclare CÔTÉ MOTEUR (politique de pas), de
  sorte que l'optimum publié soit celui de cette politique. Ajouter un motif
  ici aurait rouvert la porte à la recopie manuelle que le contrat ferme.
- **Productible lu en AST, pas importé (AOF113).** Seule voie qui satisfasse à
  la fois « une seule source de vérité » et « aucun import de quote_engine ».
- **Aucune valeur de repli inventée.** Table illisible → exception explicite.
- **AOF114, écart assumé de 1,9 Wh sur le banc.** Le dossier écrit « 96,48 kWh
  par banc » ; c'est 6 × 16,08, donc un arrondi d'affichage réutilisé comme
  donnée de calcul. Le pack réel (51,2 V × 314 Ah) fait 16,0768 kWh et le banc
  96,4608 kWh. Le registre calcule en pleine précision — les deux s'affichent
  « 96,5 kWh » et « 289,4 kWh installés ». C'est le défaut même que le groupe
  supprime, documenté par un test.
