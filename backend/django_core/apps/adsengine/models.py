"""Modèles du moteur publicitaire Meta Ads (Groupe ENG).

ENG1 pose l'app satellite SANS modèle (le scaffold). Les modèles atterrissent
dans les tâches suivantes de la lane ``backend/adsengine`` :

  * ENG2 — ``MetaConnection`` (connexion Meta par société, credentials
    write-only) ;
  * ENG3 — ``GuardrailConfig`` (garde-fous par société ; l'activation d'une
    campagne n'est JAMAIS un champ — interdite en dur au niveau service) ;
  * ENG5 — miroirs ``AdCampaignMirror`` / ``AdSetMirror`` / ``AdMirror`` +
    ``InsightSnapshot`` ;
  * ENG7 — ``EngineAction`` (colonne vertébrale propose→approuve→applique).

Tout nouveau modèle métier hérite de ``core.models.TenantModel`` (FK société +
horodatage) et les ViewSets de ``core.viewsets.CompanyScopedModelViewSet``.
"""
