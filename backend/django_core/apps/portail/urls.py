"""Routes du module Portail client (``apps.portail``) — ODX12.

Préfixe ``/api/django/portail/…``. PACT26 — le double montage historique qui
re-servait ces mêmes ViewSets sous les routes compta historiques
(``/api/django/compta/…``) a été retiré : aucun appelant frontend ne
l'utilisait (vérifié). Les vues publiques tokenisées ``portail/<token>/…``
(relevé, contestation facture) restent servies par le module compta —
elles n'ont JAMAIS été dupliquées ici, donc hors périmètre de ce retrait. Les
ViewSets gardent le scoping ``request.user.company`` + l'assignation forcée de
``company`` (``_PortailBaseViewSet`` = ``TenantMixin``).

Basenames explicitement préfixés ``portail-…`` (héritage de l'époque où le
routeur compta enregistrait les mêmes ViewSets) : conservé pour ne pas
risquer de collision ailleurs.

SOLMVP16 — ``satisfaction`` (NTPRT35) a été retiré : marketing est un module
sorti du produit et cette surface n'avait pas d'équivalent sans lui.
``mes-documents`` (NTPRT13) et ``ressources`` (NTPRT31) RESTENT : la GED est
dans le MVP solaire (décision fondateur du 21/09/2026, SOLMVP16b).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcceptationDevisPortailViewSet,
    ComptePortailClientViewSet,
    DemandeTicketPortailViewSet,
    DocumentClientPortailViewSet,
    JalonChantierPortailViewSet,
    PaiementFacturePortailViewSet,
)
from .views_client import (
    MesChantiersPortailViewSet,
    MesContratsMaintenancePortailViewSet,
    MesDemandesSavPortailViewSet,
    MesDevisPortailViewSet,
    MesDocumentsPortailViewSet,
    MesFacturesPortailViewSet,
    MesLivraisonsPortailViewSet,
    MonEquipePortailViewSet,
    exporter_mes_donnees,
    ma_consommation_client,
    recherche_portail_client,
    tableau_de_bord_client,
)
from .views_externes import (
    MesBcfPortailFournisseurViewSet,
    MesCommissionsPortailPartenaireViewSet,
    MesFacturesPortailFournisseurViewSet,
    MesSoumissionsPortailPartenaireViewSet,
    RessourcesPartenairePortailViewSet,
    candidature_fournisseur,
    ma_performance_fournisseur,
    preference_portail,
    tableau_de_bord_fournisseur,
    tableau_de_bord_partenaire,
)

router = DefaultRouter()
router.register(r'comptes-portail', ComptePortailClientViewSet,
                basename='portail-compte')
router.register(r'acceptations-devis-portail', AcceptationDevisPortailViewSet,
                basename='portail-acceptation-devis')
router.register(r'paiements-facture-portail', PaiementFacturePortailViewSet,
                basename='portail-paiement-facture')
router.register(r'documents-client-portail', DocumentClientPortailViewSet,
                basename='portail-document-client')
router.register(r'jalons-chantier-portail', JalonChantierPortailViewSet,
                basename='portail-jalon-chantier')
router.register(r'demandes-ticket-portail', DemandeTicketPortailViewSet,
                basename='portail-demande-ticket')

# NTPRT10/NTPRT11 — surface self-service du CLIENT connecté (compte réel
# NTPRT1/2, garde `IsPortalClientUser`). Les routes ci-dessus restent des
# écrans INTERNES d'administration des comptes portail ; celles-ci sont les
# seules que le client lui-même appelle.
router.register(r'mes-devis', MesDevisPortailViewSet,
                basename='portail-mes-devis')
router.register(r'mes-factures', MesFacturesPortailViewSet,
                basename='portail-mes-factures')
# WIR216 — « Mes livraisons » : lien mort expédié à chaque transition de
# livraison (FG228/XSTK22), la section portail n'existait pas.
router.register(r'mes-livraisons', MesLivraisonsPortailViewSet,
                basename='portail-mes-livraisons')
# AUD525 — « Mes demandes SAV » : la surface CLIENT de FG233, jamais
# atteignable jusqu'ici (son seul ViewSet est gardé IsResponsableOrAdmin,
# refusé à tout rôle portail).
router.register(r'mes-demandes-sav', MesDemandesSavPortailViewSet,
                basename='portail-mes-demandes-sav')
# NTPRT14 — « Mes chantiers » : timeline (jalons portail CHT10/CHT11) +
# galerie photos avant/pendant/après, jamais de donnée financière.
router.register(r'mes-chantiers', MesChantiersPortailViewSet,
                basename='portail-mes-chantiers')
# NTPRT6 — « Mon équipe » : invitation/gestion des utilisateurs du portail
# client par l'admin client lui-même (lecture ouverte à toute l'équipe,
# invitation/révocation réservées à l'admin — services.est_admin_portail_client).
router.register(r'mon-equipe', MonEquipePortailViewSet,
                basename='portail-mon-equipe')
# NTPRT13 — « Mes documents » : documents GED partagés EXPLICITEMENT (ged.AclGed
# .client) + dépôt de justificatifs (réutilise DocumentClientPortail existant).
router.register(r'mes-documents', MesDocumentsPortailViewSet,
                basename='portail-mes-documents')
# NTPRT21 — surface self-service du FOURNISSEUR connecté : ses bons de
# commande, et la confirmation de date d'arrivée (le même effet que le chemin
# tokenisé XPUR22, simplement authentifié).
router.register(r'mes-bons-commande', MesBcfPortailFournisseurViewSet,
                basename='portail-mes-bons-commande')
# NTPRT28 — deal registration : le PARTENAIRE connecté enregistre ses affaires
# (anti-doublon 30 jours) et suit leur avancement.
router.register(r'mes-soumissions', MesSoumissionsPortailPartenaireViewSet,
                basename='portail-mes-soumissions')
# NTPRT30 — « Mes commissions » : relevé (écran) + export PDF, lecture seule.
router.register(r'mes-commissions', MesCommissionsPortailPartenaireViewSet,
                basename='portail-mes-commissions')
# NTPRT31 — « Ressources » : documents GED partagés GLOBALEMENT avec TOUS les
# partenaires (ACL par rôle système « Portail partenaire »), lecture seule.
router.register(r'ressources', RessourcesPartenairePortailViewSet,
                basename='portail-ressources')
# NTPRT23 — « Mes factures & statut de paiement » du portail FOURNISSEUR
# connecté, lecture seule.
router.register(r'mes-factures-fournisseur',
                MesFacturesPortailFournisseurViewSet,
                basename='portail-mes-factures-fournisseur')
# NTPRT16 — « Mes contrats » (maintenance) : liste + demande de
# renouvellement/résiliation, portail CLIENT.
router.register(r'mes-contrats-maintenance',
                MesContratsMaintenancePortailViewSet,
                basename='portail-mes-contrats-maintenance')

urlpatterns = [
    # NTPRT9 — tableau de bord du portail CLIENT (garde de portée EXACTE,
    # symétrique de NTPRT20/NTPRT27 ci-dessous).
    path('client/tableau-de-bord/', tableau_de_bord_client,
         name='portail-client-tableau-de-bord'),
    # NTPRT15 — « Ma consommation » : série de production + alertes de
    # sous-performance ouvertes, lecture seule.
    path('client/ma-consommation/', ma_consommation_client,
         name='portail-client-ma-consommation'),
    # NTPRT36 — export « mes données » (portabilité, loi 09-08) : zip
    # devis/factures/tickets/documents du client connecté.
    path('client/mes-donnees/export/', exporter_mes_donnees,
         name='portail-client-mes-donnees-export'),
    # NTPRT38 — recherche globale, version scopée-portail du client connecté.
    path('client/recherche/', recherche_portail_client,
         name='portail-client-recherche'),
    # NTPRT20/NTPRT27 — tableaux de bord des portails FOURNISSEUR et
    # PARTENAIRE (gardes de portée EXACTE, symétriques du portail client).
    path('fournisseur/tableau-de-bord/', tableau_de_bord_fournisseur,
         name='portail-fournisseur-tableau-de-bord'),
    path('partenaire/tableau-de-bord/', tableau_de_bord_partenaire,
         name='portail-partenaire-tableau-de-bord'),
    # NTPRT34 — préférence d'affichage (langue) du compte portail connecté :
    # la SEULE surface commune aux trois portails, d'où la garde « portail
    # quelconque » plutôt qu'une portée exacte.
    path('ma-preference/', preference_portail,
         name='portail-ma-preference'),
    # NTPRT26 — carte « Ma performance » du portail FOURNISSEUR connecté,
    # lecture seule.
    path('ma-performance/', ma_performance_fournisseur,
         name='portail-ma-performance'),
    # NTPRT25 — auto-inscription fournisseur : PUBLIC (AllowAny) et
    # rate-limité. Volontairement déclaré AVANT le routeur pour qu'aucun
    # ViewSet ne puisse l'ombrer.
    # headless: auto-inscription publique d'un fournisseur, aucun ecran ERP
    path('fournisseurs/candidature/', candidature_fournisseur,
         name='portail-candidature-fournisseur'),
    path('', include(router.urls)),
]
