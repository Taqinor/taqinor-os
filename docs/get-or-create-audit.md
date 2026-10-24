# Audit get_or_create / update_or_create (YDATA15)

Généré par `python scripts/check_get_or_create.py`. Chaque appel listé n'est adossé à AUCUNE garantie d'unicité connue du modèle cible (`unique=True`, `OneToOneField`, `unique_together`, `UniqueConstraint`, héritées comprises — lues en AST) : ses clés de lookup (hors `defaults`) devraient correspondre à une `UniqueConstraint`/`unique_together` company-scopée pour être course-safe. Les appels déjà adossés ne sont plus listés (ENF18). Advisory : ce sweep ne corrige rien (correctifs = ERROR_PLAN).

Clé de CONTENU `fichier::fonction::Modèle` (jamais un numéro de ligne : une insertion en amont ne fait plus remonter les voisins comme nouveaux). Régénéré par `python scripts/check_get_or_create.py --write`.

| Clé | Appel | Récepteur | Clés de lookup |
|---|---|---|---|
| `backend/django_core/apps/adsengine/reconciliation.py::run_daily_reconciliation::RS` | update_or_create | RS.objects | campaign, company, date |
| `backend/django_core/apps/crm/management/commands/snapshot_forecast_hebdo.py::snapshot_forecast_hebdo::ForecastSnapshot` | update_or_create | ForecastSnapshot.objects | categorie, company, owner_id, semaine_iso |
| `backend/django_core/apps/customfields/blueprint.py::importer_blueprint::modele` | update_or_create | modele.objects |  |
| `backend/django_core/apps/installations/services.py::_publier_jalon_statut::JalonProjet` | get_or_create | JalonProjet.objects | installation, phase |
| `backend/django_core/apps/installations/services.py::ensure_default_template::ChecklistEtapeModele` | get_or_create | ChecklistEtapeModele.objects | cle, company, template |
| `backend/django_core/apps/installations/services.py::notifier_reception_solde_a_facturer::JalonProjet` | get_or_create | JalonProjet.objects | installation, phase |
| `backend/django_core/apps/installations/views/program.py::ProjetViewSet._attach::link_model` | get_or_create | link_model.objects | projet |
| `backend/django_core/apps/portail/services.py::upsert_jalon_chantier::JalonChantierPortail` | update_or_create | JalonChantierPortail.objects | chantier_id, cle_phase, company |
| `backend/django_core/apps/portail/views_client.py::MesDevisPortailViewSet.accepter::AcceptationDevisPortail` | get_or_create | AcceptationDevisPortail.objects | company, devis |
| `backend/django_core/apps/portail/views_client.py::MesFacturesPortailViewSet.payer::PaiementFacturePortail` | get_or_create | PaiementFacturePortail.objects | company, facture, statut |
| `backend/django_core/apps/statuspage/tasks.py::_accumuler_uptime_jour::UptimeDayBucket` | get_or_create | UptimeDayBucket.objects | company, composant, date, region |
| `backend/django_core/apps/stock/services.py::consommer_et_produire_assemblage::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::consommer_et_produire_assemblage::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::demonter_composite::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::demonter_composite::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::get_or_create_produit::Produit` | get_or_create | Produit.objects | company |
| `backend/django_core/apps/stock/services.py::rebuter_produit::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::record_stock_movement::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::transfer_stock::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services.py::transfer_stock::StockEmplacement` | get_or_create | StockEmplacement.objects | emplacement, produit |
| `backend/django_core/apps/stock/services_transfert_deux_temps.py::expedier_transfert::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
| `backend/django_core/apps/stock/services_transfert_deux_temps.py::receptionner_transfert::StockEmplacement` | get_or_create | StockEmplacement.objects.select_for_update() | emplacement, produit |
