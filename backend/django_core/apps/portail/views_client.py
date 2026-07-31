"""NTPRT10/NTPRT11 — Surface self-service AUTHENTIFIÉE du portail CLIENT.

Ces deux ViewSets sont la version « compte réel » (NTPRT1/2/5) de ce que le
client obtenait jusqu'ici par lien tokenisé. Ils n'ajoutent AUCUNE logique
métier :

* la LECTURE passe par ``apps.ventes.selectors`` (jamais un import de
  ``apps.ventes.models`` — frontière cross-app CLAUDE.md), avec des payloads
  volontairement pauvres : aucun champ de coût/marge, aucune donnée interne ;
* l'ACCEPTATION d'un devis appelle ``apps.ventes.services.accept_devis``, le
  chemin d'acceptation UNIQUE déjà utilisé par la proposition publique
  tokenisée — la chaîne aval (statut accepté → BonCommande/Facture → chantier)
  est donc préservée 1:1 (règle #4), et la trace portail ``AcceptationDevisPortail``
  (FG229) est posée en plus via ``services.signer_acceptation_devis`` ;
* le PAIEMENT réutilise ``services.initier_paiement_facture`` : NO-OP tant que
  ``CMI_ENABLED`` est OFF (aucun appel réseau payant sans clé), avec repli
  virement (RIB de ``CompanyProfile``, lu via ``parametres.selectors``).

Le PDF du devis n'est PAS rendu ici : il reste servi par l'UNIQUE chemin
canonique ``GET /api/django/ventes/devis/<id>/proposal/`` (règle #4), dont la
garde a été ouverte au client PROPRIÉTAIRE (NTPRT10, cf.
``roles.permissions.IsInternalWriterOrPortalClientOwner``).

SÉCURITÉ — chaque endpoint exige ``IsPortalClientUser`` : portée EXACTEMENT
``portail_client`` (un compte fournisseur/partenaire est refusé même s'il est
« portail ») ET un ``portail_client_id`` non nul. Tout accès à un document
passe ensuite par un sélecteur qui exige le triplet (société, client, id) : un
document d'autrui est INTROUVABLE (404), jamais « trouvé puis refusé ».
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.roles.permissions import IsPortalClientUser, portal_scope_id

from . import services

#: Valeurs acceptées comme « oui » pour le consentement e-signature (QX9).
_VRAI = (True, 'true', 'True', '1', 1, 'on')


def _scope(request):
    """(société, client_id) du compte portail appelant."""
    return request.user.company, portal_scope_id(request.user)


def _ip(request):
    return request.META.get('REMOTE_ADDR')


class MesDevisPortailViewSet(viewsets.ViewSet):
    """NTPRT10 — « Mes devis » : liste, détail, acceptation."""

    permission_classes = [IsPortalClientUser]

    def list(self, request):
        from apps.ventes.selectors import devis_du_client_portail
        company, client_id = _scope(request)
        return Response(
            {'results': devis_du_client_portail(company, client_id)})

    def retrieve(self, request, pk=None):
        from apps.ventes.selectors import devis_du_client_portail
        company, client_id = _scope(request)
        for ligne in devis_du_client_portail(company, client_id):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='accepter',
            permission_classes=[IsPortalClientUser])
    def accepter(self, request, pk=None):
        """Accepte le devis via le chemin d'acceptation UNIQUE de ``ventes``.

        Exige un nom signataire ET un consentement EXPLICITE à la signature
        électronique (QX9, loi 43-20) : le consentement ne défaute jamais à
        vrai. Idempotent — un second envoi ne re-signe pas.
        """
        from apps.ventes.selectors import devis_du_client_portail_obj
        from apps.ventes.services import AcceptError, accept_devis

        company, client_id = _scope(request)
        devis = devis_du_client_portail_obj(company, client_id, pk)
        if devis is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        nom = (request.data.get('nom') or '').strip()
        if not nom:
            return Response(
                {'detail': 'Votre nom est requis pour signer le devis.'},
                status=status.HTTP_400_BAD_REQUEST)
        if request.data.get('consent_esign') not in _VRAI:
            return Response(
                {'detail': 'Votre consentement explicite à la signature '
                           'électronique est requis pour accepter le devis.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            accept_devis(
                devis=devis,
                user=request.user,
                nom=nom,
                option=(request.data.get('option') or '').strip(),
                ip=_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
                consentement=True,
            )
        except AcceptError as exc:
            return Response(
                {'detail': exc.message},
                status=(status.HTTP_409_CONFLICT if exc.conflict
                        else status.HTTP_400_BAD_REQUEST))

        # Trace portail (FG229) — posée APRÈS la bascule, jamais à sa place.
        from .models import AcceptationDevisPortail
        acceptation, _ = AcceptationDevisPortail.objects.get_or_create(
            company=company, devis=devis)
        services.signer_acceptation_devis(
            acceptation, nom=nom, ip=_ip(request))

        devis.refresh_from_db(fields=['statut'])
        return Response({
            'detail': 'Devis accepté. Merci !',
            'reference': devis.reference,
            'statut': devis.statut,
        })
