"""Routes du module Portail client (``apps.portail``) — ODX12.

Préfixe ``/api/django/portail/…``. PACT26 — le double montage historique qui
re-servait ces mêmes ViewSets sous ``apps.compta.urls``
(``/api/django/compta/…``) a été retiré : aucun appelant frontend ne
l'utilisait (vérifié). Les vues publiques tokenisées ``portail/<token>/…``
(relevé, contestation facture) restent servies par ``apps.compta.urls`` —
elles n'ont JAMAIS été dupliquées ici, donc hors périmètre de ce retrait. Les
ViewSets gardent le scoping ``request.user.company`` + l'assignation forcée de
``company`` (hérité de ``_ComptaBaseViewSet`` = ``TenantMixin``).

Basenames explicitement préfixés ``portail-…`` (héritage de l'époque où le
routeur compta enregistrait les mêmes ViewSets) : conservé pour ne pas
risquer de collision ailleurs.
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
    MesDemandesSavPortailViewSet,
    MesDevisPortailViewSet,
    MesFacturesPortailViewSet,
    MesLivraisonsPortailViewSet,
    SatisfactionPortailViewSet,
)
from .views_externes import (
    MesBcfPortailFournisseurViewSet,
    MesCommissionsPortailPartenaireViewSet,
    MesSoumissionsPortailPartenaireViewSet,
    candidature_fournisseur,
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
# refusé à tout rôle portail). Porte aussi la déflection KB (XSAV22), qui
# n'était donc jamais exercée par un vrai client.
router.register(r'mes-demandes-sav', MesDemandesSavPortailViewSet,
                basename='portail-mes-demandes-sav')
# NTPRT21 — surface self-service du FOURNISSEUR connecté : ses bons de
# commande, et la confirmation de date d'arrivée (le même effet que le chemin
# tokenisé XPUR22, simplement authentifié).
# NTPRT35 — widget « Satisfaction » : le déclencheur d'INTERFACE qui manquait
# à FG238/FG239 (l'enquête était créée à la réception d'un chantier, sans
# aucun écran client pour y répondre).
router.register(r'satisfaction', SatisfactionPortailViewSet,
                basename='portail-satisfaction')
router.register(r'mes-bons-commande', MesBcfPortailFournisseurViewSet,
                basename='portail-mes-bons-commande')
# NTPRT28 — deal registration : le PARTENAIRE connecté enregistre ses affaires
# (anti-doublon 30 jours) et suit leur avancement.
router.register(r'mes-soumissions', MesSoumissionsPortailPartenaireViewSet,
                basename='portail-mes-soumissions')
# NTPRT30 — « Mes commissions » : relevé (écran) + export PDF, lecture seule.
router.register(r'mes-commissions', MesCommissionsPortailPartenaireViewSet,
                basename='portail-mes-commissions')

urlpatterns = [
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
    # NTPRT25 — auto-inscription fournisseur : PUBLIC (AllowAny) et
    # rate-limité. Volontairement déclaré AVANT le routeur pour qu'aucun
    # ViewSet ne puisse l'ombrer.
    # headless: auto-inscription publique d'un fournisseur, aucun ecran ERP
    path('fournisseurs/candidature/', candidature_fournisseur,
         name='portail-candidature-fournisseur'),
    path('', include(router.urls)),
]
