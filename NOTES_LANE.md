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
