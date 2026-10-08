# Audit X6 « performance » — dossier d'évaluation (L2, 08/10/2026)

*Dossier partiel (phase 1 — charte). Claim : branche `audit-X6`.*


SHA lu : origin/main (branche audit-X6). Pile locale : checkout `C:\dev\taqinor-os` sur un origin/main récent (dire son SHA).

## Système et frontière
X6 est une PISTE : il ne possède aucun fichier ; chaque tâche va chez le propriétaire des fichiers qu'elle édite
(`python scripts/check_ownership.py --owner-of`). Points chauds du registre : `crm/services.py`, `apps/web/src/pages/proposition/
[...token].astro`, `installations/services.py`, `DevisGenerator.jsx` ; plus les listes et exports des apps conservées
(ventes, crm, installations, stock, sav, ged, reporting). Apps parquées hors périmètre.

## Critère unique : C14 (performance), avec PREUVE MESURÉE
Un constat C14 n'existe que s'il est MESURÉ : nombre de requêtes SQL qui croît avec N (N+1) — mesuré par
`django.test.utils.CaptureQueriesContext` sur la pile locale, à deux tailles de données (données démo, puis N objets
supplémentaires créés DANS une transaction annulée) ; export/liste non paginé (taille de réponse qui croît sans borne) ; boucle
O(n²) prouvée (temps ou compte d'opérations à deux tailles) ; travail lourd refait à chaque requête de lecture (ex. le moteur de
devis appelé par ligne dans une liste — déjà relevé : C-AMOT LBUILD2-1, AMOT13 ; citer). Pas de micro-optimisation, pas
d'« on pourrait mettre un index » sans mesure.

Seuils de décision : S2 = une liste/écran utilisateur dont le nombre de requêtes croît linéairement avec les lignes (N+1) ou
un export sans borne sur une table qui grossit avec l'activité ; S3 = travail redondant mesuré (> 2× le nécessaire) sur un
chemin fréquent ; S4 = le reste (OPTIONNEL).

## NE PAS REFAIRE
Tâches ouvertes de performance déjà déposées (grep « N+1 », « select_related », « prefetch », « pagination », « assertNumQueries »
dans docs/plans/*, PLAN*.md, ERROR_PLAN.md, new_tasks_plan.md) : CITER. La chaîne SPL déplace le code : nommer le SYMBOLE.

## Étapes (identifiants stables)
- P1 listes API : P1.1 ventes (devis, factures, BC), P1.2 crm (leads, clients, cockpit, relances du jour), P1.3 installations /
  stock / sav / ged.
- P2 détails lourds : P2.1 fiche lead, P2.2 devis (overrides, historique, offres-tailles), P2.3 chantier.
- P3 exports et rapports : P3.1 xlsx/csv, P3.2 reporting/pilotage, P3.3 tâches Celery périodiques.
- P4 front : P4.1 DevisGenerator (recalculs à chaque frappe), P4.2 page publique proposition (charge, scripts), P4.3 listes
  qui lisent toutes les pages.

## Détecteurs (scout)
grep `pagination_class = None` et ViewSets sans pagination dans les apps conservées ; grep des SerializerMethodField qui
appellent un service/sélecteur (requête par ligne) ; liste des `@action(detail=False)` qui renvoient `Response(serializer(qs,
many=True).data)` sans pagination ; grep `fetchAllPages(` côté front ; grep `.objects.all()` dans les tâches périodiques ;
taille de `[...token].astro` et du bundle (`ls -la C:\dev\taqinor-os\frontend\dist\assets` si présent) ;
`python scripts/check_parked_apps.py`.
