"""VNT98 — gestes d'encaissement de la facture (paiements, arrondi de caisse,
enregistrer un paiement, abandon et reprise de solde, libération de retenue,
lien de paiement, encaissement groupé) : actions de ``FactureViewSet`` portées
par ``FactureEncaissementActionsMixin``, déplacées telles quelles depuis
``views/facture.py``. Aucune route dans ``urls.py`` : le routeur les découvre
sur le viewset.
"""
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import (
    IsAnyRole, IsResponsableOrAdmin,
)
from . import openapi_docs as D
from .facture_gardes import PeutEncaisser
from ..domain.encaissements import proposer_arrondi_caisse
from ..models import Facture, Paiement
from ..openapi_params import qstr
from ..serializers_facturation import FactureSerializer, PaiementSerializer

#: Plus grand identifiant d'une clé ``integer`` PostgreSQL (publié en borne).
_ENTIER_MAX = 2 ** 31 - 1


class FactureEncaissementActionsMixin:
    """Les gestes d'argent entrant d'une facture (garde ``PeutEncaisser``,
    ASEC29)."""

    @extend_schema(responses=PaiementSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='paiements',
            permission_classes=[IsAnyRole])
    def paiements(self, request, pk=None):
        """Liste les paiements enregistrés sur cette facture."""
        facture = self.get_object()
        return Response(
            PaiementSerializer(
                facture.paiements.all(), many=True
            ).data
        )

    @extend_schema(parameters=[qstr('mode')],
                   responses=D.ArrondiCaisseResponse)
    @action(detail=True, methods=['get'], url_path='arrondi-caisse',
            permission_classes=[IsAnyRole])
    def arrondi_caisse(self, request, pk=None):
        """ZFAC11 — propose le reste à payer ARRONDI au pas de caisse société
        pour un règlement EN ESPÈCES (``?mode=especes``, défaut espèces).

        Renvoie ``{applicable, montant_du, montant_arrondi, ecart, pas}`` :
        l'écran d'encaissement pré-remplit ``montant_arrondi`` pour un paiement
        espèces et affiche l'écart qui sera tracé. Hors espèces ou pas société
        nul → ``applicable=false`` et ``montant_arrondi`` = reste à payer (aucun
        arrondi, comportement inchangé)."""
        from decimal import Decimal
        facture = self.get_object()
        mode = request.query_params.get('mode', Paiement.Mode.ESPECES)
        prop = proposer_arrondi_caisse(facture, mode)
        return Response({
            'applicable': prop['applicable'],
            'montant_du': str(facture.montant_du),
            'montant_arrondi': str(prop['montant_arrondi']),
            'ecart': str(prop['ecart']),
            'pas': str(prop['pas'] or Decimal('0')),
        })

    @extend_schema(request=PaiementSerializer,
                   responses={201: FactureSerializer},
                   extensions=D.CORPS_MONTANT_POSITIF)
    @action(detail=True, methods=['post'], url_path='enregistrer-paiement',
            permission_classes=[PeutEncaisser])
    def enregistrer_paiement(self, request, pk=None):
        """Enregistre MANUELLEMENT un paiement (montant + date + mode).

        Réduit le reste à payer de la facture et le solde du devis. Quand la
        facture est intégralement réglée, elle passe automatiquement « Payée ».
        Disponible à la Commerciale (création) ; l'annulation reste admin.
        """
        facture = self.get_object()
        serializer = PaiementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ENF11 — le montant (publié strictement positif) est une règle
        # d'ENTRÉE : 400 ; les refus qui suivent tiennent à l'ÉTAT de la
        # facture (annulée, brouillon, soldée, reste dû dépassé) : 409.
        montant = serializer.validated_data.get('montant')
        if montant is None or montant <= 0:
            return Response(
                {'detail': 'Le montant du paiement doit être positif.'},
                status=status.HTTP_400_BAD_REQUEST)
        if facture.statut == Facture.Statut.ANNULEE:
            return Response(
                {'detail': 'Impossible d\'encaisser sur une facture annulée.'},
                status=status.HTTP_409_CONFLICT,
            )
        # Le corps (verrou ERR72, garde sur-paiement, escompte XFAC12, chatter,
        # événement, bascule « Payée » AUD102, arrondi ZFAC11, tolérance
        # XFAC13) vit dans LE service d'encaissement, partagé avec
        # `devis/{id}/facturer-complet/` — un seul chemin pour l'argent reçu.
        from ..domain.encaissements import (
            EncaissementRefuse, encaisser_sur_facture,
        )
        try:
            facture, _paiement = encaisser_sur_facture(
                facture=facture, donnees=dict(serializer.validated_data),
                user=request.user)
        except EncaissementRefuse as exc:
            return Response({'detail': exc.motif},
                            status=status.HTTP_409_CONFLICT)
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=D.AbandonnerSoldeRequest,
                   responses=D.FactureAbandonnee)
    @action(detail=True, methods=['post'], url_path='abandonner-solde',
            permission_classes=[PeutEncaisser])
    def abandonner_solde(self, request, pk=None):
        """XFAC13 — abandon manuel du résiduel (write-off).

        Motif obligatoire (irrécouvrable / geste commercial / écart de
        règlement / liquidation). Solde la facture (« payée »), passe
        l'écriture d'abandon (6585/créance, reprise de provision FG152 le cas
        échéant) et sort la facture des impayés/balance âgée. Réservé
        responsable/admin.
        """
        facture = self.get_object()
        corps = request.data if isinstance(request.data, dict) else {}
        motif = corps.get('motif')
        motifs_valides = dict(Facture.MotifAbandon.choices)
        if not isinstance(motif, str) or motif not in motifs_valides:
            return Response(
                {'detail': (
                    'Motif obligatoire (irrecouvrable / geste_commercial / '
                    'ecart_reglement / liquidation).'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if facture.statut == Facture.Statut.ANNULEE:
            return Response(
                {'detail':
                 'Impossible d\'abandonner le solde d\'une facture annulée.'},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            locked = Facture.objects.select_for_update().get(pk=facture.pk)
            if locked.statut == Facture.Statut.PAYEE or locked.montant_du <= 0:
                return Response(
                    {'detail': 'Cette facture n\'a aucun résiduel à '
                               'abandonner.'},
                    status=status.HTTP_409_CONFLICT,
                )
            from ..services import abandonner_solde_facture
            from ..domain.encaissements import FactureNonEncaissable
            try:
                montant = abandonner_solde_facture(
                    locked, motif=motif, user=request.user, auto=False,
                )
            except FactureNonEncaissable as exc:
                return Response({'detail': exc.motif},
                                status=status.HTTP_409_CONFLICT)
            locked.refresh_from_db()
        return Response(
            {**FactureSerializer(locked).data, 'montant_abandonne': montant},
        )

    @extend_schema(request=D.ReprendreAbandonRequest,
                   responses={200: D.FactureAbandonRepris,
                              400: D.ErreurRetenue, 409: D.ErreurRetenue})
    @action(detail=True, methods=['post'], url_path='reprendre-abandon',
            permission_classes=[PeutEncaisser])
    def reprendre_abandon(self, request, pk=None):
        """AFAC34 (D-AFAC-C6) — REPRISE MANUELLE d'un abandon de créance
        (corps ``{motif, abandon?}`` ; sans ``abandon``, le plus récent actif).
        L'abandon garde sa trace (``annule_le``) ; la facture revient au
        recouvrement, un paiement tardif s'encaisse ensuite normalement."""
        facture = self.get_object()
        from ..domain.recouvrement import (
            RepriseAbandonRefusee, reprendre_abandon_creance,
        )
        # ENF11 — corps illisible (liste, texte, motif non texte, identifiant
        # d'abandon non entier) : 400 qui nomme le champ, jamais 500.
        corps = request.data
        if not isinstance(corps, dict):
            return Response(
                {'detail': 'Corps JSON objet attendu : {motif, abandon?}.'},
                status=status.HTTP_400_BAD_REQUEST)
        erreur = None
        motif = corps.get('motif')
        if motif is not None and not isinstance(motif, str):
            erreur = {'detail': 'motif : texte attendu.', 'champ': 'motif'}
        abandon_id = corps.get('abandon')
        if abandon_id in ('', None):
            abandon_id = None
        elif isinstance(abandon_id, bool) or not (
                isinstance(abandon_id, int)
                or (isinstance(abandon_id, str) and abandon_id.strip().isdigit())):
            erreur = erreur or {
                'detail': 'abandon : entier attendu.', 'champ': 'abandon'}
        else:
            abandon_id = int(abandon_id)
        # ENF11 — motif (publié non blanc) et identifiant d'abandon (publié
        # 1..2^31-1) sont des règles d'ENTRÉE : 400. Le refus du domaine qui
        # reste (facture annulée, aucun abandon actif à reprendre) tient à
        # l'ÉTAT : 409.
        if not erreur and not (motif or '').strip():
            erreur = {'detail': 'Motif obligatoire pour reprendre un abandon '
                                'de créance.', 'champ': 'motif'}
        if not erreur and abandon_id is not None and not (
                1 <= abandon_id <= _ENTIER_MAX):
            erreur = {'detail': 'abandon : identifiant hors plage.',
                      'champ': 'abandon'}
        if erreur:
            return Response(erreur, status=status.HTTP_400_BAD_REQUEST)
        try:
            abandon = reprendre_abandon_creance(
                facture, user=request.user, motif=motif,
                abandon_id=abandon_id)
        except RepriseAbandonRefusee as exc:
            return Response({'detail': exc.motif},
                            status=status.HTTP_409_CONFLICT)
        facture.refresh_from_db()
        return Response({**FactureSerializer(facture).data,
                         'abandon_repris': abandon.id,
                         'montant_repris': str(abandon.montant)})

    @extend_schema(request=D.LibererRetenueRequest,
                   responses={200: FactureSerializer,
                              400: D.ErreurRetenue, 409: D.ErreurRetenue})
    @action(detail=True, methods=['post'], url_path='liberer-retenue',
            permission_classes=[IsResponsableOrAdmin])
    def liberer_retenue(self, request, pk=None):
        """CIQ214 — libère la retenue de garantie CLIENT d'une facture de
        tranche (D-CIQ-14), à la date SAISIE (``date`` AAAA-MM-JJ, la
        réception définitive du chantier) : ``montant_exigible`` remonte alors
        à ``montant_du``. Aucune écriture comptable, aucun statut changé hors
        de la date ; idempotent sur une retenue déjà libérée (400). La
        réception définitive servie par le contrat CIQ6 la pré-remplira côté
        écran dès que l'app chantier l'expose (lecture via selectors)."""
        import datetime as _dt
        facture = self.get_object()
        # ENF11 — sans retenue ou retenue déjà libérée : l'ÉTAT de la facture
        # s'oppose au geste (409) ; la date illisible reste un 400.
        if facture.retenue_garantie_mad is None:
            return Response(
                {'detail': 'Aucune retenue de garantie sur cette facture.',
                 'champ': 'retenue_garantie_mad'},
                status=status.HTTP_409_CONFLICT)
        if facture.retenue_liberee_le:
            return Response(
                {'detail': 'La retenue de garantie est déjà libérée '
                           f'(le {facture.retenue_liberee_le:%d/%m/%Y}).',
                 'champ': 'retenue_liberee_le'},
                status=status.HTTP_409_CONFLICT)
        brut = (request.data or {}).get('date')
        try:
            date = _dt.date.fromisoformat(str(brut or '').strip())
        except ValueError:
            return Response(
                {'detail': 'Date de libération (réception définitive) '
                           'obligatoire, au format AAAA-MM-JJ.',
                 'champ': 'date'},
                status=status.HTTP_400_BAD_REQUEST)
        facture.retenue_liberee_le = date
        facture.save(update_fields=['retenue_liberee_le'])
        return Response(FactureSerializer(facture).data)

    @extend_schema(request=D.LienPaiementRequest, responses={201: D.LienPaiementResponse})
    @action(detail=True, methods=['post'], url_path='lien-paiement',
            permission_classes=[IsResponsableOrAdmin])
    def lien_paiement(self, request, pk=None):
        """FG53 — crée (ou réutilise) un lien « Payer en ligne » pour la facture.

        Le fournisseur par défaut est NoOp (page de paiement interne, aucun coût
        ni dépendance ; passerelle live gatée). Société forcée depuis la
        facture ; n'envoie rien au client (pas d'email/SMS).

        AUD136 — les gardes de CRÉATION (facture annulée / payée / soldée) sont
        descendues dans `create_payment_link` : elles ne protégeaient que CE
        chemin, alors que tout autre appelant du service pouvait créer un lien
        sur une facture close. La réponse porte désormais `montant_a_payer`
        (reste dû à l'instant T, ce que le client paiera réellement) à côté de
        `montant` (la trace figée à la création)."""
        if not isinstance(request.data, dict):
            return Response(
                {'detail': 'Corps illisible : un objet JSON est attendu.'},
                status=status.HTTP_400_BAD_REQUEST)
        facture = self.get_object()
        from ..services import LinkError, create_payment_link
        from ..domain.encaissements import url_page_paiement
        from ..payments.providers import get_provider, providers_lien_actifs
        # ENF11 — ``provider`` ABSENT = « noop » ; présent, c'est une clé de
        # la liste blanche (``{}``, ``""`` ou ``null`` retombaient en silence
        # sur « noop » alors que le schéma les déclare invalides).
        provider_key = request.data.get('provider', 'noop')
        # AFAC21 (C-AFAC-020) — clé validée contre la LISTE BLANCHE des
        # fournisseurs de lien activés AVANT toute écriture : une clé
        # inconnue créait un lien (201), un fournisseur sans session un 500
        # avec lien orphelin, une clé trop longue un 500 ``DataError``.
        if (not isinstance(provider_key, str)
                or provider_key not in providers_lien_actifs()):
            return Response(
                {'detail': 'Fournisseur de paiement inconnu ou inactif.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            link = create_payment_link(facture=facture, provider=provider_key)
        except LinkError as exc:
            # ENF11 — facture annulée / payée / soldée : refus d'ÉTAT, 409.
            return Response({'detail': exc.message},
                            status=status.HTTP_409_CONFLICT)
        session = get_provider(link.provider).create_session(link)
        # AFAC21 — URL ABSOLUE de la page client : le réglage d'abord, sinon
        # l'hôte de CETTE requête (jamais un chemin ``/api/…`` relatif).
        pay_url = session.get('pay_url') or ''
        if link.provider == 'noop' or not pay_url.startswith('http'):
            pay_url = url_page_paiement(link.token, request)
        return Response({
            'token': link.token,
            'statut': link.statut,
            'montant': str(link.montant),
            'montant_a_payer': str(link.montant_a_payer),
            'provider': link.provider,
            'pay_url': pay_url,
            'expires_at': link.expires_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=D.RevoquerLienPaiementResponse)
    @action(detail=True, methods=['post'], url_path='revoquer-lien-paiement',
            permission_classes=[IsResponsableOrAdmin])
    def revoquer_lien_paiement(self, request, pk=None):
        """AUD136 — révoque le lien « Payer en ligne » actif de la facture.

        Le cycle de vie du lien n'avait aucune SORTIE : un lien créé avec un
        montant erroné ne pouvait être ni corrigé ni fermé, et restait payable
        jusqu'à son expiration. Idempotent : sans lien actif, 200 et rien à
        faire — jamais une erreur pour un état déjà atteint.

        NB : `get_permissions` ci-dessus SURCHARGE les `permission_classes` du
        décorateur ; l'action doit donc être nommée dans sa liste
        `IsResponsableOrAdmin` (comme `lien_paiement`), sans quoi elle retombe
        sur le `IsAdminRole()` terminal et rend 403 au responsable."""
        from ..services import revoquer_lien_paiement
        facture = self.get_object()
        lien = revoquer_lien_paiement(facture=facture, user=request.user)
        if lien is None:
            return Response({
                'detail': 'Aucun lien de paiement actif sur cette facture.',
                'revoque': False,
            })
        return Response({
            'detail': 'Lien de paiement révoqué.',
            'revoque': True,
            'token': lien.token,
            'statut': lien.statut,
        })

    @extend_schema(request=D.EncaissementGroupeRequest,
                   responses={201: PaiementSerializer(many=True)})
    @action(pagination_class=None, detail=False, methods=['post'], url_path='encaissement-groupe',
            permission_classes=[PeutEncaisser])
    def encaissement_groupe(self, request):
        """ZFAC6 — un seul règlement client réparti sur PLUSIEURS factures
        (virement global, chèque unique). Body : ``{client, montant, mode,
        date, reference, factures:[ids]}`` — répartition FIFO par échéance
        (la plus ancienne d'abord) sur les factures listées.

        AUD120 — comportement RÉEL des deux branches (l'ancien docstring
        affirmait un refus qui n'existait pas) :
          - ``repartition`` explicite : refusée en 400 si la somme des parts
            dépasse le ``montant`` encaissé, ou si une part dépasse le reste
            dû de sa facture (tolérance d'un centime) ;
          - FIFO : ce que les factures listées n'absorbent pas devient une
            avance XFAC1 explicite (Paiement sans facture, non affecté),
            renvoyée dans la réponse — jamais abandonnée en silence.
        """
        from decimal import Decimal

        from apps.crm.selectors import get_company_client

        from ..utils.corps import valider_corps

        company = request.user.company
        # CI #997 fuzz — le corps est validé par le sérialiseur PUBLIÉ (il
        # était relu à la main, plus souplement : ``"client": "5"``,
        # ``"reference": 0``, ``"montant": "1.234"`` passaient) → 400 nommé.
        corps = valider_corps(request, D.EncaissementGroupeRequest)
        client = get_company_client(company, corps['client'])
        if client is None:
            return Response(
                {'detail': 'Client introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        montant = Decimal(corps['montant'])
        mode = corps.get('mode') or 'virement'
        date_paiement = corps.get('date') or timezone.now().date()
        reference = corps.get('reference', '').strip()
        facture_ids = corps['factures']

        # AFAC55 — portée du rôle (`get_queryset`) en plus de la société.
        factures = list(self.get_queryset().filter(id__in=facture_ids))
        if len(factures) != len(set(facture_ids)):
            return Response(
                {'detail': 'Une ou plusieurs factures sont introuvables '
                           'pour cette société.'},
                status=status.HTTP_404_NOT_FOUND)
        autres_clients = [f for f in factures if f.client_id != client.id]
        if autres_clients:
            return Response(
                {'detail': (
                    f"La facture {autres_clients[0].reference} "
                    "n'appartient pas à ce client."
                )},
                # ENF11 — ids valides, mais les DONNÉES (client de la
                # facture) s'opposent au rapprochement : 409.
                status=status.HTTP_409_CONFLICT)

        repartition = corps.get('repartition')
        ids_lot = {f.id for f in factures}
        hors_lot = next((cle for cle in (repartition or {}) if not (
            cle.isascii() and cle.isdigit() and int(cle) in ids_lot)), None)
        if hors_lot is not None:
            # CI #997 fuzz — une clé de répartition qui ne nomme aucune facture
            # du lot : règle entre champs que le schéma ne porte pas → 409.
            return Response(
                {'detail': f'Facture {hors_lot} inconnue dans ce lot.'},
                status=status.HTTP_409_CONFLICT)

        from ..services import affecter_encaissement_groupe

        try:
            paiements = affecter_encaissement_groupe(
                company=company, client=client, montant=montant, mode=mode,
                date_paiement=date_paiement, user=request.user,
                factures=factures, reference=reference,
                repartition=repartition,
            )
        except ValueError as exc:
            # CI #997 fuzz — corps valide : facture non encaissable, Σ des
            # parts au-delà du montant, part au-delà du reste dû sont des
            # refus d'ÉTAT ou d'ensemble (409), plus 400.
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)

        return Response(
            PaiementSerializer(paiements, many=True).data,
            status=status.HTTP_201_CREATED)
