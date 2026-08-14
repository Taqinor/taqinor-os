from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OptionProduitViewSet, ContrainteCompatibiliteViewSet,
    RegleProduitCPQViewSet, OffreGroupeeViewSet, PrixContractuelViewSet,
    QuestionConfigurateurViewSet, ConfigurateurDemarrerView,
    ConfigurateurRepondreView, ConfigurateurResultatView,
    ConfigurateurGenererDevisView, ValiderCompatibiliteView,
    SeuilMargeFamilleViewSet, RegleApprobationRemiseViewSet,
    ClauseCGVViewSet, ProduitEquivalentViewSet, DevisVariantesView,
    SuggestionsProduitView, FeuilleConfigurationView, MargeSousSeuilView,
    RapportConformiteView, ParametresCPQViewSet, RapportApprobationsView,
    ComparaisonVariantesView, ImportPrixContractuelsCsvView,
    CatalogueReglesCompatibiliteView, RelancerApprobationView,
)

router = DefaultRouter()
router.register(r'options-produit', OptionProduitViewSet)
router.register(r'contraintes-compatibilite', ContrainteCompatibiliteViewSet)
router.register(r'regles', RegleProduitCPQViewSet)
router.register(r'offres-groupees', OffreGroupeeViewSet)
router.register(r'prix-contractuels', PrixContractuelViewSet)
router.register(r'configurateur-questions', QuestionConfigurateurViewSet)
# WIR105 — CRUD Paramètres CPQ (plus de dépendance au Django admin).
router.register(r'seuils-marge', SeuilMargeFamilleViewSet)
router.register(r'regles-approbation-remise', RegleApprobationRemiseViewSet)
# NTCPQ12 — bibliothèque de clauses/CGV (écran Paramètres).
router.register(r'clauses-cgv', ClauseCGVViewSet)
# NTCPQ16 — règles de substitution produit (moteur de variantes).
router.register(r'produits-equivalents', ProduitEquivalentViewSet)
# NTCPQ30 — réglages CPQ par société (singleton).
router.register(r'parametres-cpq', ParametresCPQViewSet)

urlpatterns = [
    path('valider-compatibilite/', ValiderCompatibiliteView.as_view(),
         name='cpq-valider-compatibilite'),
    # NTCPQ41 — import CSV en masse de PrixContractuel (avant le routeur, un
    # sous-chemin de 'prix-contractuels/' doit être déclaré AVANT le
    # ViewSet du même préfixe pour ne jamais être capturé par son
    # <pk>/ générique).
    path('prix-contractuels/import-csv/',
         ImportPrixContractuelsCsvView.as_view(),
         name='cpq-prix-contractuels-import-csv'),
    # NTCPQ24 — rapport interne « taux de conformité des configurations ».
    path('rapports/conformite/', RapportConformiteView.as_view(),
         name='cpq-rapport-conformite'),
    # NTCPQ25 — rapport interne « historique des approbations de remise ».
    path('rapports/approbations/', RapportApprobationsView.as_view(),
         name='cpq-rapport-approbations'),
    # NTCPQ42 — export lecture seule du catalogue de règles de compatibilité.
    path('rapports/catalogue-regles/',
         CatalogueReglesCompatibiliteView.as_view(),
         name='cpq-catalogue-regles-compatibilite'),
    # NTCPQ23 — tableau de bord interne « marge sous seuil » (staff).
    path('marge-sous-seuil/', MargeSousSeuilView.as_view(),
         name='cpq-marge-sous-seuil'),
    # NTCPQ19 — suggestions de vente croisée / montée en gamme.
    path('suggestions/', SuggestionsProduitView.as_view(),
         name='cpq-suggestions'),
    # NTCPQ16 — moteur de génération des variantes d'un devis.
    path('devis/<int:pk>/variantes/', DevisVariantesView.as_view(),
         name='cpq-devis-variantes'),
    # NTCPQ22 — feuille de configuration technique INTERNE (jamais client).
    path('devis/<int:pk>/feuille-configuration/',
         FeuilleConfigurationView.as_view(),
         name='cpq-feuille-configuration'),
    # NTCPQ26 — feuille de comparaison de variantes INTERNE (jamais client).
    path('devis/<int:pk>/comparaison-variantes/',
         ComparaisonVariantesView.as_view(),
         name='cpq-comparaison-variantes'),
    # NTCPQ28 — relance manuelle (côté demandeur) d'une approbation en attente.
    path('devis/<int:pk>/relancer-approbation/',
         RelancerApprobationView.as_view(),
         name='cpq-relancer-approbation'),
    path('configurateur/demarrer/', ConfigurateurDemarrerView.as_view(),
         name='cpq-configurateur-demarrer'),
    path('configurateur/<uuid:token>/repondre/',
         ConfigurateurRepondreView.as_view(),
         name='cpq-configurateur-repondre'),
    path('configurateur/<uuid:token>/resultat/',
         ConfigurateurResultatView.as_view(),
         name='cpq-configurateur-resultat'),
    path('configurateur/<uuid:token>/generer-devis/',
         ConfigurateurGenererDevisView.as_view(),
         name='cpq-configurateur-generer-devis'),
    path('', include(router.urls)),
]
