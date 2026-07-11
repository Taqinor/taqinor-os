from django.core.exceptions import ValidationError as DjangoValidationError  # noqa: F401,E501
from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.exceptions import ValidationError  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, mouvement_type_entree, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, FollowupLevel, RelanceLog, EmailLog,
    NoteDebit, LigneNoteDebit,
)
from ..serializers import (  # noqa: F401
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AvoirSerializer,
    NoteDebitSerializer,
    RelanceLogSerializer,
    DevisActivitySerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
    HasPermissionOrLegacy,
)
from core.viewsets import CompanyScopedModelViewSet  # noqa: F401  ARC5
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# XFAC24 — champs FINANCIERS d'une facture, verrouillés en écriture quand
# CompanyProfile.factures_immuables est ON et que la facture n'est plus
# brouillon (correction par avoir + nouvelle facture uniquement). Le client
# est inclus (changer le tiers facturé revient à réécrire le document).
FACTURE_CHAMPS_FINANCIERS = frozenset([
    'client', 'montant_ht', 'montant_tva', 'montant_ttc', 'remise_globale',
    'taux_tva', 'escompte_pct', 'escompte_jours', 'pourcentage',
    'type_facture',
])


def arrondir_au_pas(montant, pas):
    """ZFAC11 — arrondit ``montant`` au multiple le plus proche de ``pas``.

    Pur (aucune I/O). ``pas <= 0`` (arrondi désactivé) renvoie ``montant``
    inchangé — comportement actuel strictement préservé. Arrondi « half-up »
    (0,025 monte à 0,05 pour un pas de 0,05). Renvoie un ``Decimal`` quantifié
    à 2 décimales.
    """
    from decimal import Decimal, ROUND_HALF_UP
    montant = Decimal(str(montant))
    pas = Decimal(str(pas or 0))
    if pas <= 0:
        return montant.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    nb_pas = (montant / pas).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return (nb_pas * pas).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def proposer_arrondi_caisse(facture, mode, reste=None):
    """ZFAC11 — propose le reste à payer ARRONDI au pas de caisse société.

    Ne s'applique QU'aux règlements en espèces et seulement si la société a
    configuré un pas (> 0). Renvoie un dict
    ``{montant_arrondi, ecart, pas, applicable}`` où ``ecart`` = résiduel non
    perçu (montant_du − montant_arrondi, jamais négatif) qui sera tracé comme
    un abandon « Arrondi espèces ». Hors espèces ou pas nul → ``applicable`` est
    ``False`` et ``montant_arrondi`` = reste à payer (aucun arrondi).

    ``reste`` : résiduel de référence explicite. Indispensable au moment de
    l'encaissement, où ``facture.montant_du`` (propriété vivante) inclut DÉJÀ
    le paiement tout juste enregistré — la proposition doit se calculer sur le
    reste AVANT paiement, sinon elle ne correspond jamais au montant réglé.
    """
    from decimal import Decimal
    from apps.parametres.models import CompanyProfile
    reste = facture.montant_du if reste is None else reste
    profile = CompanyProfile.get(company=facture.company)
    pas = getattr(profile, 'arrondi_caisse', None) or Decimal('0')
    if mode != Paiement.Mode.ESPECES or pas <= 0 or reste <= 0:
        return {
            'montant_arrondi': reste, 'ecart': Decimal('0'),
            'pas': pas, 'applicable': False,
        }
    montant_arrondi = arrondir_au_pas(reste, pas)
    # On ne perçoit jamais plus que le dû : si l'arrondi monte au-dessus du
    # reste, on redescend au pas inférieur (l'écart reste ≥ 0, jamais un
    # trop-perçu à gérer).
    if montant_arrondi > reste:
        montant_arrondi = montant_arrondi - pas
    if montant_arrondi < 0:
        montant_arrondi = Decimal('0')
    ecart = reste - montant_arrondi
    return {
        'montant_arrondi': montant_arrondi, 'ecart': ecart,
        'pas': pas, 'applicable': ecart > 0,
    }


from authentication.scoping import scope_queryset  # noqa: E402,F401


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


class _DatedDocument:
    """YLEDG3 — adaptateur minimal (company, date_emission) pour réutiliser
    ``apps.compta.services.verifier_facture_modifiable`` sur une date qui
    n'est pas ``Facture.date_emission`` (ex. la date d'un paiement)."""

    def __init__(self, company, une_date):
        self.company = company
        self.date_emission = une_date

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class FactureViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique (CompanyScopedModelViewSet
    # = TenantMixin + ModelViewSet). get_queryset/perform_create/perform_update/
    # get_permissions SURCHARGENT la base : scoping société et matrice 401/403/404
    # IDENTIQUES (règle #4 : aucun statut/sérialisation Facture touché ; la facture
    # garde son PDF légacy séparé, hors périmètre du moteur devis).
    queryset = Facture.objects.select_related(
        'client', 'created_by', 'bon_commande'
    ).prefetch_related('lignes').all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'client__nom', 'client__prenom', 'client__email'
    ]
    ordering_fields = [
        'date_emission', 'date_echeance', 'statut', 'reference'
    ]
    ordering = ['-date_emission']

    def get_queryset(self):
        qs = _company_qs(super().get_queryset(), self.request.user)
        # Portée de visibilité (Feature F) — factures créées par soi / l'équipe.
        return scope_queryset(qs, self.request.user, ['created_by'])

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return FactureWriteSerializer
        return FactureSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + [
            'paiements', 'relances', 'emails', 'arrondi_caisse',
        ]:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'emettre', 'marquer_payee', 'enregistrer_paiement',
            'generer_pdf', 'telecharger_pdf', 'envoyer_email',
            'relancer', 'exclure_relance', 'whatsapp', 'ubl',
            'dgi_export', 'dgi_conformite', 'dgi_transmettre',
            'bulk', 'lien_paiement', 'retour_client',
            'facturer_penalites', 'consolider', 'abandonner_solde',
            'remettre_brouillon', 'encaissement_groupe',
        ]:
            return [IsResponsableOrAdmin()]
        # Annuler une facture = réservé à l'admin/propriétaire (geste comptable).
        elif self.action in ['destroy', 'annuler']:
            return [IsAdminRole()]
        # creer_avoir tombe ici → IsAdminRole (création d'avoir = admin).
        return [IsAdminRole()]

    @staticmethod
    def _guard_periode_verrouillee(document):
        """YLEDG3 — refuse (400) une mutation d'un document ventes daté dans
        une période comptable CLÔTURÉE (FG115). Society/app compta absente ou
        aucune période verrouillée = garde silencieuse (comportement actuel
        inchangé). Import function-local de ``apps.compta.services`` — cross-
        app services autorisé, jamais un import de ``apps.compta.models``."""
        try:
            from apps.compta.services import verifier_facture_modifiable
        except Exception:  # noqa: BLE001 — compta absent = no-op
            return
        try:
            verifier_facture_modifiable(document)
        except DjangoValidationError as exc:
            raise ValidationError({'detail': exc.messages[0]
                                   if exc.messages else str(exc)})

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        # ERR14 — client/bon_commande/devis du corps doivent appartenir à la
        # société (refuse de lier une facture aux enregistrements d'un autre
        # tenant).
        if company is not None:
            client = serializer.validated_data.get('client')
            bon_commande = serializer.validated_data.get('bon_commande')
            devis = serializer.validated_data.get('devis')
            if client is not None and client.company_id != company.id:
                raise ValidationError({'client': 'Client inconnu.'})
            if bon_commande is not None and \
                    bon_commande.company_id != company.id:
                raise ValidationError(
                    {'bon_commande': 'Bon de commande inconnu.'})
            if devis is not None and devis.company_id != company.id:
                raise ValidationError({'devis': 'Devis inconnu.'})
        # FG52 — devise : si le corps n'en fournit pas, appliquer la devise par
        # défaut de la société (CompanyProfile.devise_defaut), repli MAD.
        save_kwargs = dict(
            created_by=self.request.user,
            company=company,
        )
        if 'devise' not in serializer.validated_data:
            from apps.parametres.models import CompanyProfile
            save_kwargs['devise'] = (
                getattr(CompanyProfile.get(company=company), 'devise_defaut', '')
                or 'MAD')

        # XFAC12 — escompte : si le corps n'en fournit pas, proposer les
        # défauts société (surchargeables — un devis explicite dans le corps
        # reste prioritaire). NULL/absent des deux côtés = comportement actuel
        # inchangé (aucun escompte).
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=company)
        if 'escompte_pct' not in serializer.validated_data and \
                getattr(profile, 'escompte_pct_defaut', None) is not None:
            save_kwargs['escompte_pct'] = profile.escompte_pct_defaut
        if 'escompte_jours' not in serializer.validated_data and \
                getattr(profile, 'escompte_jours_defaut', None) is not None:
            save_kwargs['escompte_jours'] = profile.escompte_jours_defaut

        # XFAC18 — workflow de revue : flag OFF (défaut) → rien ne change
        # (revue_statut reste vide). ON et créateur du tier LIMITÉ (menu_tier
        # 'normal' — ex. un rôle Commercial avec seulement ventes_creer, qui
        # passe IsResponsableOrAdmin via ses permissions d'écriture fines mais
        # n'est PAS du palier responsable/admin) → démarre « à valider ». Un
        # responsable/admin qui crée directement n'a pas besoin d'être
        # re-validé.
        from authentication.models import CustomUser
        if getattr(profile, 'revue_factures_active', False) and \
                self.request.user.menu_tier not in (
                    CustomUser.ROLE_ADMIN, CustomUser.ROLE_RESPONSABLE):
            save_kwargs['revue_statut'] = Facture.RevueStatut.A_VALIDER

        create_numbered(
            Facture, company, 'facture',
            lambda ref: serializer.save(reference=ref, **save_kwargs),
        )

    def perform_update(self, serializer):
        # YLEDG3 — un document daté dans une période comptable CLÔTURÉE ne
        # doit plus pouvoir être modifié. Import function-local de
        # apps.compta.services (cross-app services autorisé) ; société sans
        # compta/périodes = garde silencieuse (comportement actuel inchangé).
        self._guard_periode_verrouillee(self.get_object())
        # XFAC24 — immutabilité de la facture émise (opt-in). Flag OFF
        # (défaut) → comportement actuel byte-identique. Flag ON et facture
        # non-brouillon : tout champ FINANCIER dans le corps est refusé (la
        # correction passe par un avoir + une nouvelle facture) ; les champs
        # non financiers (conditions, notes, dates de livraison…) restent
        # modifiables.
        facture = self.get_object()
        if facture.statut != Facture.Statut.BROUILLON:
            from apps.parametres.models import CompanyProfile
            profile = CompanyProfile.get(company=facture.company)
            if getattr(profile, 'factures_immuables', False):
                champs_touches = (
                    set(serializer.validated_data.keys())
                    & FACTURE_CHAMPS_FINANCIERS)
                if champs_touches:
                    from rest_framework.exceptions import ValidationError
                    raise ValidationError({
                        'detail': (
                            "Facture immuable : les champs financiers d'une "
                            "facture émise ne peuvent plus être modifiés. "
                            "Corrigez par un avoir puis une nouvelle "
                            "facture."
                        ),
                        'champs_refuses': sorted(champs_touches),
                    })
        # VX98 — dernier auteur de modification (server-side, jamais du corps) :
        # alimente la puce de fraîcheur. Pattern created_by.
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='emettre')
    def emettre(self, request, pk=None):
        facture = self.get_object()
        if facture.statut != Facture.Statut.BROUILLON:
            return Response(
                {'detail': 'Seule une facture brouillon peut être émise.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not facture.lignes.exists():
            return Response(
                {'detail': (
                    'La facture doit contenir au moins une ligne.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # XFAC18 — workflow de revue (ségrégation des tâches). Flag OFF
        # (défaut) → comportement inchangé, aucun contrôle supplémentaire.
        # Flag ON et facture « à valider » → le valideur doit être un
        # responsable/admin DIFFÉRENT du créateur.
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=facture.company)
        anomalies = []
        if getattr(profile, 'revue_factures_active', False) and \
                facture.revue_statut == Facture.RevueStatut.A_VALIDER:
            if facture.created_by_id == request.user.id:
                return Response(
                    {'detail': (
                        'Cette facture doit être validée par un '
                        'responsable/admin différent du créateur.'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from ..services import anomalies_emission_facture
            anomalies = anomalies_emission_facture(facture)
            facture.revue_statut = Facture.RevueStatut.VALIDEE
        facture.statut = Facture.Statut.EMISE
        # XFAC23 — dérive l'échéance depuis les conditions de paiement du
        # client à l'émission, SAUF si une échéance a déjà été saisie
        # manuellement (jamais écrasée — input freedom) ; sans réglage
        # client, l'échéancier FG46/FG220 ou le repli +30 j (scheduled.py)
        # gardent la priorité, comportement inchangé.
        if not facture.date_echeance:
            from ..services import calculer_date_echeance
            derivee = calculer_date_echeance(
                client=facture.client, date_emission=facture.date_emission)
            if derivee is not None:
                facture.date_echeance = derivee
        # XFAC18 — save complet (persiste statut + revue_statut + échéance
        # dérivée), puis surface les anomalies de revue dans la réponse.
        facture.save()
        # YEVNT6 — événement documentaire (best-effort, ne change rien au
        # statut déjà posé ci-dessus).
        from core.events import facture_emise
        facture_emise.send(
            sender=Facture, instance=facture, company=facture.company)
        data = FactureSerializer(facture).data
        if anomalies:
            data['anomalies'] = anomalies
        return Response(data)

    @action(detail=True, methods=['post'], url_path='remettre-brouillon',
            permission_classes=[IsResponsableOrAdmin])
    def remettre_brouillon(self, request, pk=None):
        """ZFAC1 — Reset to Draft (opt-in période ouverte).

        Repasse une facture ÉMISE en brouillon UNIQUEMENT si elle n'a AUCUN
        paiement ni avoir actif et que la période comptable de sa date
        d'émission n'est pas verrouillée (YLEDG3) ni que XFAC24
        (immutabilité) est activée pour la société. Le numéro/référence est
        CONSERVÉ (pas de renumérotation) — seul le statut change."""
        facture = self.get_object()
        if facture.statut != Facture.Statut.EMISE:
            return Response(
                {'detail': (
                    'Seule une facture émise (sans paiement ni avoir) peut '
                    'être remise en brouillon.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if facture.paiements.exists():
            return Response(
                {'detail': (
                    'Impossible : cette facture a déjà au moins un '
                    'paiement enregistré.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if facture.avoirs.exclude(statut=Avoir.Statut.ANNULEE).exists():
            return Response(
                {'detail': (
                    'Impossible : cette facture a un avoir actif.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=facture.company)
        if getattr(profile, 'factures_immuables', False):
            return Response(
                {'detail': (
                    "Facture immuable : l'immutabilité (XFAC24) est activée "
                    "pour cette société — corrigez par un avoir puis une "
                    "nouvelle facture."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # YLEDG3 — refuse si la période comptable de la facture est verrouillée.
        self._guard_periode_verrouillee(facture)
        ancien = facture.statut
        facture.statut = Facture.Statut.BROUILLON
        facture.save(update_fields=['statut'])
        from .. import activity
        activity.log_facture_remise_brouillon(facture, request.user, ancien)
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='marquer-payee',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_payee(self, request, pk=None):
        facture = self.get_object()
        if facture.statut not in [
            Facture.Statut.EMISE, Facture.Statut.EN_RETARD
        ]:
            return Response(
                {'detail': (
                    'Seule une facture émise ou en retard '
                    'peut être marquée payée.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facture.statut = Facture.Statut.PAYEE
        facture.save()
        # YDOCF4 — facture_paid, exactement une fois. Un passage manuel
        # « marquer payée » ne porte pas de montant de paiement propre : on
        # transmet le résiduel qui vient d'être annulé (montant_du AVANT ce
        # passage, ici recalculé à 0 côté document — le montant informatif
        # posé est donc le solde figé de la facture, cohérent avec les autres
        # sites d'émission qui portent le montant réglé).
        from core.events import facture_paid, facture_payee
        facture_paid.send(
            sender=Facture, facture=facture, montant=facture.total_ttc,
            company=facture.company)
        # YEVNT6 — événement documentaire générique (même transition).
        facture_payee.send(
            sender=Facture, instance=facture, company=facture.company)
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsAdminRole])
    def annuler(self, request, pk=None):
        """Annule une facture — admin only.

        FG50 — sort l'acompte de la facture morte. Le corps peut porter une
        directive ``acompte`` traitant les paiements (acompte) restés sur la
        facture annulée :

          - ``{"acompte": {"action": "transferer", "facture_cible": <id>}}``
            re-pointe TOUS les paiements de la facture annulée vers une AUTRE
            facture (active) du MÊME devis (mêmes société + devis) ; les soldes
            des deux factures se redérivent automatiquement (``montant_paye`` /
            ``montant_du`` sont calculés depuis les lignes Paiement).
          - ``{"acompte": {"action": "rembourser"}}`` écrit un Paiement NÉGATIF
            de contre-passation sur la facture annulée : son ``montant_paye``
            net retombe à 0 et l'écriture négative matérialise l'obligation de
            remboursement (l'acompte n'est plus « coincé » sur une facture
            morte).

        Sans directive (ou sur une facture sans acompte) : comportement
        historique strictement inchangé — on bascule seulement le statut.
        """
        from decimal import Decimal
        facture = self.get_object()
        self._guard_periode_verrouillee(facture)
        if facture.statut == Facture.Statut.PAYEE:
            return Response(
                {'detail': 'Une facture payée ne peut pas être annulée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if facture.statut == Facture.Statut.ANNULEE:
            return Response(
                {'detail': 'Cette facture est déjà annulée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        directive = request.data.get('acompte') or {}
        if not isinstance(directive, dict):
            return Response(
                {'detail': 'Directive « acompte » invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        acompte_action = (directive.get('action') or '').strip()

        # Paiements « bloqués » sur la facture morte (l'acompte versé). On ne
        # déplace/contre-passe que le NET : si la facture porte déjà des
        # écritures négatives (remboursement partiel antérieur), elles entrent
        # dans le total.
        from .. import activity
        with transaction.atomic():
            locked = Facture.objects.select_for_update().get(pk=facture.pk)
            if locked.statut in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE):
                return Response(
                    {'detail': 'Cette facture ne peut plus être annulée.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            paiements = list(locked.paiements.all())
            net_acompte = sum((p.montant for p in paiements), Decimal('0'))

            if acompte_action == 'transferer':
                if net_acompte <= 0:
                    return Response(
                        {'detail': (
                            'Aucun acompte à transférer sur cette facture.'
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                cible_id = directive.get('facture_cible')
                if not cible_id:
                    return Response(
                        {'detail': 'La facture cible est requise.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    cible_id = int(cible_id)
                except (TypeError, ValueError):
                    return Response(
                        {'detail': 'Facture cible invalide.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if cible_id == locked.pk:
                    return Response(
                        {'detail': (
                            "La facture cible doit être différente de celle "
                            "annulée."
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Le devis source doit exister pour relier les deux factures.
                if locked.devis_id is None:
                    return Response(
                        {'detail': (
                            "Transfert impossible : la facture n'est pas liée "
                            "à un devis."
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                cible = Facture.objects.select_for_update().filter(
                    pk=cible_id).first()
                # Validation multi-tenant + même devis + cible vivante.
                if cible is None or cible.company_id != locked.company_id:
                    return Response(
                        {'detail': 'Facture cible inconnue.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if cible.devis_id != locked.devis_id:
                    return Response(
                        {'detail': (
                            "La facture cible doit appartenir au même devis."
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if cible.statut == Facture.Statut.ANNULEE:
                    return Response(
                        {'detail': (
                            "Impossible de transférer vers une facture "
                            "annulée."
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Re-pointe les paiements vers la cible : les soldes des deux
                # factures se redérivent (propriétés calculées).
                nb = len(paiements)
                for p in paiements:
                    p.facture = cible
                    p.save(update_fields=['facture'])
                locked.statut = Facture.Statut.ANNULEE
                locked.save(update_fields=['statut'])
                activity.log_facture_acompte_transfere_sortie(
                    locked, request.user, cible, net_acompte, nb)
                activity.log_facture_acompte_transfere_entree(
                    cible, request.user, locked, net_acompte, nb)
                facture = locked

            elif acompte_action == 'rembourser':
                if net_acompte <= 0:
                    return Response(
                        {'detail': (
                            'Aucun acompte à rembourser sur cette facture.'
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Contre-passation : un Paiement négatif soldant l'acompte. Le
                # net retombe à 0 → l'acompte n'est plus « coincé » ; la ligne
                # négative porte l'obligation de remboursement.
                from django.utils import timezone as _tz
                Paiement.objects.create(
                    facture=locked, company=locked.company,
                    montant=-net_acompte, date_paiement=_tz.now().date(),
                    mode=Paiement.Mode.AUTRE,
                    note='Remboursement acompte (annulation facture)',
                    created_by=request.user,
                )
                locked.statut = Facture.Statut.ANNULEE
                locked.save(update_fields=['statut'])
                activity.log_facture_acompte_rembourse(
                    locked, request.user, net_acompte)
                facture = locked

            elif acompte_action:
                return Response(
                    {'detail': (
                        "Action acompte invalide. Valeurs : « transferer », "
                        "« rembourser »."
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                # Comportement historique : simple bascule de statut.
                locked.statut = Facture.Statut.ANNULEE
                locked.save(update_fields=['statut'])
                facture = locked

        # YEVNT6 — événement documentaire (best-effort), une fois pour les
        # trois branches ci-dessus (toutes convergent vers ANNULEE).
        from core.events import facture_annulee
        facture_annulee.send(
            sender=Facture, instance=facture, company=facture.company)
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['get'], url_path='paiements',
            permission_classes=[IsAnyRole])
    def paiements(self, request, pk=None):
        """Liste les paiements enregistrés sur cette facture."""
        facture = self.get_object()
        return Response(
            PaiementSerializer(
                facture.paiements.all(), many=True
            ).data
        )

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

    @action(detail=True, methods=['post'], url_path='enregistrer-paiement',
            permission_classes=[IsResponsableOrAdmin])
    def enregistrer_paiement(self, request, pk=None):
        """Enregistre MANUELLEMENT un paiement (montant + date + mode).

        Réduit le reste à payer de la facture et le solde du devis. Quand la
        facture est intégralement réglée, elle passe automatiquement « Payée ».
        Disponible à la Commerciale (création) ; l'annulation reste admin.
        """
        from decimal import Decimal
        facture = self.get_object()
        if facture.statut == Facture.Statut.ANNULEE:
            return Response(
                {'detail': 'Impossible d\'encaisser sur une facture annulée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PaiementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        montant = serializer.validated_data.get('montant')
        if montant is None or montant <= 0:
            return Response(
                {'detail': 'Le montant du paiement doit être positif.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # YLEDG3 — un paiement DATÉ dans une période comptable clôturée est
        # refusé (la date du paiement, pas celle de la facture, est ce qui
        # tombe dans la période comptable concernée).
        paiement_date = serializer.validated_data.get('date_paiement')
        if paiement_date is not None:
            self._guard_periode_verrouillee(
                _DatedDocument(facture.company, paiement_date))
        # ERR72 — la garde sur-paiement et l'écriture du paiement doivent être
        # sérialisées : on verrouille la ligne facture (select_for_update) puis
        # on lit le reste à payer, on contrôle, et on enregistre — le tout dans
        # une seule transaction. Sans le verrou, deux paiements concurrents
        # lisaient chacun l'ancien reste et passaient tous deux la garde.
        with transaction.atomic():
            locked = Facture.objects.select_for_update().get(pk=facture.pk)
            if locked.statut == Facture.Statut.ANNULEE:
                return Response(
                    {'detail':
                     'Impossible d\'encaisser sur une facture annulée.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Garde sur-paiement : refuser un encaissement qui dépasse le reste
            # à payer (TTC − déjà payé − avoirs). Tolérance d'un centime pour
            # les arrondis ; un montant égal au reste passe (solde la facture).
            reste = locked.montant_du
            # XFAC12 — escompte pour règlement anticipé : si la fenêtre est
            # atteinte (date_paiement <= émission + escompte_jours) ET que le
            # montant réglé correspond au NET après escompte (reste − escompte,
            # tolérance 1 centime), l'escompte se calcule automatiquement et
            # SOLDE la facture avec le règlement — jamais hors fenêtre (plein
            # tarif reste dû, comportement actuel inchangé).
            date_paiement = serializer.validated_data.get('date_paiement')
            escompte_montant = Decimal('0')
            if locked.escompte_applicable(date_paiement):
                escompte_potentiel = locked.calcul_escompte(reste, date_paiement)
                net_attendu = reste - escompte_potentiel
                if abs(montant - net_attendu) <= Decimal('0.01'):
                    escompte_montant = escompte_potentiel
                    reste = net_attendu
            if montant - reste > Decimal('0.01'):
                return Response(
                    {'detail': (
                        f'Le paiement dépasse le reste à payer '
                        f'({reste:.2f} MAD).'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            paiement = serializer.save(
                facture=locked,
                company=locked.company,
                created_by=request.user,
                escompte_montant=escompte_montant,
            )
            # Chatter facture : trace l'encaissement (acteur côté serveur,
            # jamais lu du corps de la requête).
            from .. import activity
            activity.log_facture_paiement(locked, request.user, paiement)
            # YLEDG1 — événement documentaire générique (pose du seam pour
            # compta.ecriture_pour_paiement, jamais d'import de son service ici).
            from core.events import paiement_enregistre
            paiement_enregistre.send(
                sender=Paiement, instance=paiement, company=locked.company)
            # Statut auto : intégralement réglée → « Payée ».
            locked.refresh_from_db()
            if locked.montant_du <= Decimal('0') and \
                    locked.statut != Facture.Statut.ANNULEE:
                locked.statut = Facture.Statut.PAYEE
                locked.save(update_fields=['statut'])
                # U10 — facture soldée : on arrête l'escalade de relance
                # (efface la prochaine relance et neutralise le compteur de
                # niveau) pour qu'une facture payée cesse d'afficher un retard.
                from ..services import reset_relance_escalation
                reset_relance_escalation(locked)
                # YDOCF4 — facture_paid, exactement une fois au passage
                # résiduel→0 (jamais à un règlement partiel).
                from core.events import facture_paid, facture_payee
                facture_paid.send(
                    sender=Facture, facture=locked, montant=montant,
                    company=locked.company)
                # YEVNT6 — événement documentaire générique (même transition).
                facture_payee.send(
                    sender=Facture, instance=locked, company=locked.company)
            elif locked.statut != Facture.Statut.ANNULEE:
                # ZFAC11 — arrondi de caisse : un règlement EN ESPÈCES égal au
                # reste à payer arrondi au pas société (défaut 0 = désactivé,
                # comportement inchangé) solde la facture, l'écart d'arrondi
                # étant tracé comme un abandon « Arrondi espèces » (jamais
                # silencieux). Ne s'applique qu'aux espèces ; virement/chèque
                # l'ignorent. Passe AVANT la tolérance XFAC13 (motif dédié).
                mode = serializer.validated_data.get('mode', Paiement.Mode.VIREMENT)
                # ``reste`` = résiduel AVANT ce paiement (capturé plus haut) —
                # montant_du est déjà retombé après serializer.save().
                prop = proposer_arrondi_caisse(locked, mode, reste=reste)
                if (prop['applicable']
                        and abs(montant - prop['montant_arrondi']) <= Decimal('0.01')
                        and Decimal('0') < locked.montant_du <= prop['pas']):
                    from ..services import abandonner_solde_facture
                    abandonner_solde_facture(
                        locked, motif=Facture.MotifAbandon.ARRONDI_CAISSE,
                        user=request.user, auto=True,
                    )
                    locked.refresh_from_db()
                else:
                    # XFAC13 — tolérance société : un résiduel sous le seuil
                    # (défaut 0 = désactivé, comportement inchangé) est abandonné
                    # automatiquement à l'encaissement plutôt que de laisser la
                    # facture « en retard » pour quelques centimes.
                    from apps.parametres.models import CompanyProfile
                    profile = CompanyProfile.get(company=locked.company)
                    tolerance = getattr(
                        profile, 'tolerance_ecart_reglement', None) or Decimal('0')
                    if tolerance > 0 and locked.montant_du <= tolerance:
                        from ..services import abandonner_solde_facture
                        abandonner_solde_facture(
                            locked, motif=Facture.MotifAbandon.ECART_REGLEMENT,
                            user=request.user, auto=True,
                        )
                        locked.refresh_from_db()
            facture = locked
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='abandonner-solde',
            permission_classes=[IsResponsableOrAdmin])
    def abandonner_solde(self, request, pk=None):
        """XFAC13 — abandon manuel du résiduel (write-off).

        Motif obligatoire (irrécouvrable / geste commercial / écart de
        règlement / liquidation). Solde la facture (« payée »), passe
        l'écriture d'abandon (6585/créance, reprise de provision FG152 le cas
        échéant) et sort la facture des impayés/balance âgée. Réservé
        responsable/admin.
        """
        facture = self.get_object()
        motif = (request.data or {}).get('motif')
        motifs_valides = dict(Facture.MotifAbandon.choices)
        if motif not in motifs_valides:
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
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            locked = Facture.objects.select_for_update().get(pk=facture.pk)
            if locked.statut == Facture.Statut.PAYEE or locked.montant_du <= 0:
                return Response(
                    {'detail': 'Cette facture n\'a aucun résiduel à '
                               'abandonner.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from ..services import abandonner_solde_facture
            montant = abandonner_solde_facture(
                locked, motif=motif, user=request.user, auto=False,
            )
            locked.refresh_from_db()
        return Response(
            {**FactureSerializer(locked).data, 'montant_abandonne': montant},
        )

    @action(detail=True, methods=['post'], url_path='generer-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def generer_pdf(self, request, pk=None):
        facture = self.get_object()
        from ..tasks import task_generate_facture_pdf
        task = task_generate_facture_pdf.delay(facture.id)
        # M4 — événement découplé : ventes émet, le satellite audit journalise
        # (AuditLog.Action.PDF). ventes n'importe plus apps.audit ; le signal
        # est synchrone (même requête), donc l'acteur/société restent identiques.
        from core.events import document_pdf_generated
        document_pdf_generated.send(
            sender=Facture, instance=facture, kind='facture')
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'], url_path='telecharger-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def telecharger_pdf(self, request, pk=None):
        facture = self.get_object()
        if not facture.fichier_pdf:
            return Response(
                {'detail': (
                    'PDF non disponible. '
                    'Cliquez d\'abord sur « Générer PDF ».'
                )},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from ..utils.pdf import download_pdf
            pdf_bytes = download_pdf(facture.fichier_pdf)
        except Exception:
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from ..utils.filenames import document_filename
        filename = document_filename(
            'Facture', facture.reference,
            client=facture.client if facture.client_id else None,
            company=facture.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @action(detail=True, methods=['get'], url_path='ubl',
            permission_classes=[IsResponsableOrAdmin])
    def ubl(self, request, pk=None):
        """N38 — aperçu BROUILLON UBL 2.1 de la facture (XML téléchargeable).

        Génère le XML à la volée, le dépose en local (MinIO, best-effort) et le
        renvoie. Aucun appel externe, aucune transmission DGI."""
        facture = self.get_object()
        from apps.parametres.models import CompanyProfile
        from ..utils.ubl import build_ubl_xml, store_ubl_xml
        profile = CompanyProfile.get(company=facture.company)
        xml_str = build_ubl_xml(facture, profile)
        key = store_ubl_xml(facture, xml_str)
        if key and facture.fichier_ubl != key:
            facture.fichier_ubl = key
            facture.save(update_fields=['fichier_ubl'])
        response = HttpResponse(xml_str, content_type='application/xml')
        response['Content-Disposition'] = (
            f'attachment; filename="{facture.reference}-ubl.xml"'
        )
        return response

    @action(detail=True, methods=['get'], url_path='dgi-export',
            permission_classes=[IsResponsableOrAdmin])
    def dgi_export(self, request, pk=None):
        """N105 — Export DGI local (UBL 2.1) de la facture, à la demande.

        GARDÉ par l'interrupteur maître ``dgi_export_actif`` (défaut OFF) : tant
        qu'il est OFF pour la société, cet endpoint se comporte comme
        introuvable (404) → la capacité reste invisible. Aucun statut n'est
        modifié, rien n'est transmis."""
        facture = self.get_object()
        from apps.ventes.dgi import build_ubl_xml, is_dgi_enabled
        if not is_dgi_enabled(facture.company):
            return Response(
                {'detail': 'Introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        xml_str = build_ubl_xml(facture)
        response = HttpResponse(xml_str, content_type='application/xml')
        response['Content-Disposition'] = (
            f'attachment; filename="{facture.reference}-dgi.xml"'
        )
        return response

    @action(detail=True, methods=['get'], url_path='dgi-conformite',
            permission_classes=[IsResponsableOrAdmin])
    def dgi_conformite(self, request, pk=None):
        """N105 — Contrôle de conformité DGI de la facture, à la demande.

        Même garde que ``dgi_export`` : 404 tant que l'interrupteur maître est
        OFF. Renvoie la liste des problèmes (vide = conforme) ; ne modifie
        aucun statut."""
        facture = self.get_object()
        from apps.ventes.dgi import validate_dgi_conformity, is_dgi_enabled
        if not is_dgi_enabled(facture.company):
            return Response(
                {'detail': 'Introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        problemes = validate_dgi_conformity(facture)
        return Response(
            {'conforme': not problemes, 'problemes': problemes})

    @action(detail=True, methods=['post'], url_path='dgi-transmettre',
            permission_classes=[IsResponsableOrAdmin])
    def dgi_transmettre(self, request, pk=None):
        """XFAC29 — Transmet (ou retransmet) la facture à la plateforme DGI
        agréée configurée. GARDÉ par l'interrupteur maître
        ``dgi_transmission_actif`` (défaut OFF) : tant qu'il est OFF pour la
        société, cet endpoint se comporte comme introuvable (404) — la
        capacité reste invisible, symétrique de `dgi_export`/`dgi_conformite`.
        Un rejet peut être rejoué (nouvelle tentative) ; une facture déjà
        ACCEPTÉE n'est jamais retransmise (idempotence)."""
        facture = self.get_object()
        from apps.ventes.dgi.transmission import (
            is_dgi_transmission_enabled, transmettre_facture,
        )
        if not is_dgi_transmission_enabled(facture.company):
            return Response(
                {'detail': 'Introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        facture = transmettre_facture(facture)
        return Response({
            'dgi_statut': facture.dgi_statut,
            'dgi_reference': facture.dgi_reference,
            'dgi_motif_rejet': facture.dgi_motif_rejet,
        })

    @action(detail=True, methods=['post'], url_path='whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp(self, request, pk=None):
        """Lien wa.me prêt à envoyer pour une facture (ou un rappel).

        N'envoie RIEN : ouvre WhatsApp avec le message pré-rempli. Le {lien} est
        un lien public tokenisé (30 j) vers le PDF CLIENT de la facture.
        Body : `modele` ∈ {'facture','relance'}, `langue` ∈ {'fr','darija'}.
        """
        from ..utils.phone import normalize_ma_phone
        from ..utils.whatsapp import build_facture_whatsapp, build_wa_url
        facture = self.get_object()
        phone = facture.client.telephone if facture.client_id else ''
        if not normalize_ma_phone(phone):
            return Response(
                {'detail': 'Aucun numéro de téléphone.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        modele = request.data.get('modele', 'facture')
        langue = request.data.get('langue', 'fr')
        message, link = build_facture_whatsapp(request, facture, modele, langue)
        # L856 — trace l'action dans le chatter de la facture (Historique).
        # Acteur et société posés côté serveur, jamais lus du corps de requête.
        from ..activity import log_facture_whatsapp
        log_facture_whatsapp(facture, request.user, modele)
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
        })

    @action(detail=True, methods=['post'], url_path='lien-paiement',
            permission_classes=[IsResponsableOrAdmin])
    def lien_paiement(self, request, pk=None):
        """FG53 — crée (ou réutilise) un lien « Payer en ligne » pour la facture.

        Le fournisseur par défaut est NoOp (page de paiement interne, aucun coût
        ni dépendance ; passerelle live gatée). Renvoie le jeton, l'URL de la
        page de paiement, le montant figé (reste à payer) et l'échéance. Société
        forcée depuis la facture ; n'envoie rien au client (pas d'email/SMS)."""
        facture = self.get_object()
        if facture.statut == Facture.Statut.ANNULEE:
            return Response(
                {'detail': 'Facture annulée : aucun lien de paiement.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from decimal import Decimal
        if facture.montant_du <= Decimal('0'):
            return Response(
                {'detail': 'Cette facture est déjà soldée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from ..services import create_payment_link
        from ..payments.providers import get_provider
        provider_key = request.data.get('provider') or 'noop'
        link = create_payment_link(facture=facture, provider=provider_key)
        session = get_provider(link.provider).create_session(link)
        return Response({
            'token': link.token,
            'statut': link.statut,
            'montant': str(link.montant),
            'provider': link.provider,
            'pay_url': session.get('pay_url'),
            'expires_at': link.expires_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='envoyer-email',
            permission_classes=[IsResponsableOrAdmin])
    def envoyer_email(self, request, pk=None):
        """N87 — Envoie la facture au client par email (PDF en pièce jointe).

        Route par l'intégration email configurable : NO-OP réseau sans clé
        (backend console), envoi réel via Brevo/SMTP quand configuré. L'envoi
        est consigné sur le fil (EmailLog). Le corps/sujet/destinataire peuvent
        être surchargés dans le body de la requête."""
        from ..email_service import send_document_email
        facture = self.get_object()
        log = send_document_email(
            facture,
            to_email=(request.data.get('to_email') or '').strip() or None,
            sujet=(request.data.get('sujet') or '').strip() or None,
            corps=(request.data.get('corps') or '').strip() or None,
            user=request.user,
            attach_pdf=request.data.get('attach_pdf', True),
        )
        if log.statut == EmailLog.Statut.ECHEC:
            return Response(
                {'detail': log.erreur or 'Envoi impossible.',
                 'email_log_id': log.id},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'detail': 'Email envoyé.', 'email_log_id': log.id,
             'to_email': log.to_email},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['post'], url_path='creer-avoir')
    def creer_avoir(self, request, pk=None):
        """Crée un Avoir (note de crédit) depuis une facture ÉMISE — admin only
        (get_permissions par défaut). Total ou partiel : si `lignes` est fourni
        on crédite ces lignes ; sinon on crédite toute la facture. Lié à la
        facture d'origine ; le PDF reprend le style facture.

        ZFAC5 — ``mode`` ∈ {``correction`` (défaut, comportement ci-dessus
        inchangé), ``contre_passation``} : en ``contre_passation`` l'avoir
        reprend TOUTES les lignes de la facture à l'identique (les `lignes`
        du corps sont ignorées) et, à son émission, la facture d'origine
        passe ``annulee`` avec un ``FactureActivity`` liant les deux pièces.
        Refusé (400) si la facture a déjà des paiements (dû négatif évité)."""
        facture = self.get_object()
        self._guard_periode_verrouillee(facture)
        if facture.statut not in ('emise', 'payee', 'en_retard'):
            return Response(
                {'detail': 'Un avoir ne peut être créé que depuis une '
                           'facture émise (ou payée/en retard).'},
                status=status.HTTP_400_BAD_REQUEST)
        mode = (request.data.get('mode') or 'correction').strip()
        if mode not in ('correction', 'contre_passation'):
            return Response(
                {'detail': "mode doit être 'correction' ou 'contre_passation'."},
                status=status.HTTP_400_BAD_REQUEST)
        if mode == 'contre_passation' and facture.montant_paye > 0:
            return Response(
                {'detail': ("Contre-passation refusée : cette facture a déjà "
                            "des paiements enregistrés.")},
                status=status.HTTP_400_BAD_REQUEST)
        company = facture.company
        motif = (request.data.get('motif') or '').strip()
        lignes = None if mode == 'contre_passation' \
            else request.data.get('lignes')
        # Plafond : un avoir ne peut pas dépasser le reste créditable de la
        # facture (TTC − avoirs actifs déjà émis). Mesuré AVANT création.
        from decimal import Decimal, InvalidOperation
        reste_creditable = facture.total_ttc - facture.avoirs_total

        # ERR34 — valider les lignes fournies AVANT toute création, et échouer
        # bruyamment (400) au lieu de les avaler en silence (l'ancien
        # `except Exception: continue` créait un avoir amputé de son montant,
        # sans erreur). On vérifie désignation / quantité / prix_unitaire de
        # chaque ligne et on renvoie une erreur 400 claire si l'une est
        # invalide.
        clean_lignes = None
        if isinstance(lignes, list) and lignes:
            clean_lignes = []
            for i, ligne in enumerate(lignes, start=1):
                if not isinstance(ligne, dict):
                    return Response(
                        {'detail': f'Ligne {i} invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)
                designation = (ligne.get('designation') or '').strip()
                if not designation:
                    return Response(
                        {'detail': f'Ligne {i} : désignation requise.'},
                        status=status.HTTP_400_BAD_REQUEST)
                try:
                    qte = Decimal(str(ligne.get('quantite')))
                    pu = Decimal(str(ligne.get('prix_unitaire')))
                except (InvalidOperation, TypeError, ValueError):
                    return Response(
                        {'detail': (f'Ligne {i} : quantité et prix unitaire '
                                    'numériques requis.')},
                        status=status.HTTP_400_BAD_REQUEST)
                if qte <= 0 or pu < 0:
                    return Response(
                        {'detail': (f'Ligne {i} : quantité > 0 et prix '
                                    'unitaire ≥ 0 requis.')},
                        status=status.HTTP_400_BAD_REQUEST)
                try:
                    remise = Decimal(str(ligne.get('remise') or 0))
                except (InvalidOperation, TypeError, ValueError):
                    return Response(
                        {'detail': f'Ligne {i} : remise invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)
                taux_tva = ligne.get('taux_tva')
                if taux_tva not in (None, ''):
                    try:
                        taux_tva = Decimal(str(taux_tva))
                    except (InvalidOperation, TypeError, ValueError):
                        return Response(
                            {'detail': f'Ligne {i} : taux TVA invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
                else:
                    taux_tva = None
                # DC10 — produit REQUIS sur une nouvelle ligne d'avoir (lien
                # snapshot fort). Le FK reste nullable en base pour l'historique,
                # mais toute ligne saisie ici doit désigner un produit de la
                # société.
                produit_id = ligne.get('produit') or None
                if produit_id is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit requis.'},
                        status=status.HTTP_400_BAD_REQUEST)
                from apps.stock.selectors import get_produit_scoped
                if get_produit_scoped(company, produit_id) is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit inconnu.'},
                        status=status.HTTP_400_BAD_REQUEST)
                clean_lignes.append({
                    'produit_id': produit_id,
                    'designation': designation[:255],
                    'quantite': qte, 'prix_unitaire': pu,
                    'remise': remise, 'taux_tva': taux_tva,
                })

        def _create(ref):
            avoir = Avoir.objects.create(
                company=company, reference=ref, facture=facture,
                client=facture.client, statut=Avoir.Statut.EMISE,
                motif=motif, taux_tva=facture.taux_tva,
                created_by=request.user)
            if clean_lignes:
                for ligne in clean_lignes:
                    LigneAvoir.objects.create(avoir=avoir, **ligne)
            else:
                f_lignes = list(facture.lignes.all())
                if f_lignes:
                    for ligne in f_lignes:
                        LigneAvoir.objects.create(
                            avoir=avoir, produit=ligne.produit,
                            designation=ligne.designation,
                            quantite=ligne.quantite,
                            prix_unitaire=ligne.prix_unitaire,
                            remise=ligne.remise, taux_tva=ligne.taux_tva)
                else:
                    # Facture de tranche sans lignes : montants figés.
                    avoir.montant_ht = facture.total_ht
                    avoir.montant_tva = facture.total_tva
                    avoir.montant_ttc = facture.total_ttc
                    avoir.save(update_fields=[
                        'montant_ht', 'montant_tva', 'montant_ttc'])
            return avoir

        avoir = create_numbered(
            Avoir, company, 'avoir', _create)
        # Garde plafond : si l'avoir créé dépasse le reste créditable, on le
        # supprime (avec ses lignes) et on refuse — un avoir partiel correct
        # passe inchangé. Tolérance d'un centime pour les arrondis.
        if avoir.total_ttc - reste_creditable > Decimal('0.01'):
            avoir.lignes.all().delete()
            avoir.delete()
            return Response(
                {'detail': "L'avoir dépasse le montant restant de la facture "
                           f"({reste_creditable:.2f} MAD)."},
                status=status.HTTP_400_BAD_REQUEST)
        # Chatter facture : trace la création de l'avoir (acteur côté serveur,
        # jamais lu du corps de la requête).
        from .. import activity
        activity.log_facture_avoir(facture, request.user, avoir)
        if mode == 'contre_passation':
            # ZFAC5 — annulation NETTE : la facture d'origine passe annulee,
            # avec un FactureActivity liant les deux pièces (avoir miroir).
            from ..models import FactureActivity
            ancien_statut = facture.statut
            facture.statut = Facture.Statut.ANNULEE
            facture.save(update_fields=['statut'])
            FactureActivity.objects.create(
                company=company, facture=facture, user=request.user,
                kind=FactureActivity.Kind.MODIFICATION,
                field='statut', field_label='Statut',
                old_value=ancien_statut, new_value=Facture.Statut.ANNULEE,
                body=(f"Facture annulée par contre-passation — avoir miroir "
                      f"{avoir.reference}."),
            )
        # YLEDG1 — événement documentaire générique (pose du seam pour
        # compta.ecriture_pour_avoir, jamais d'import de son service ici).
        from core.events import avoir_cree
        avoir_cree.send(sender=Avoir, instance=avoir, company=company)
        try:
            from ..utils.pdf import generate_avoir_pdf
            generate_avoir_pdf(avoir.id)
            avoir.refresh_from_db()
        except Exception:
            pass
        return Response(AvoirSerializer(avoir).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='creer-note-debit')
    def creer_note_debit(self, request, pk=None):
        """ZFAC4 — crée une NoteDebit (majoration d'une facture déjà émise) —
        pendant de l'avoir. Total (copie des lignes de la facture) ou
        personnalisé (`lignes` fourni) ; augmente ``Facture.montant_du``."""
        facture = self.get_object()
        self._guard_periode_verrouillee(facture)
        if facture.statut not in ('emise', 'payee', 'en_retard'):
            return Response(
                {'detail': 'Une note de débit ne peut être créée que depuis '
                           'une facture émise (ou payée/en retard).'},
                status=status.HTTP_400_BAD_REQUEST)
        company = facture.company
        motif = (request.data.get('motif') or '').strip()
        lignes = request.data.get('lignes')

        from decimal import Decimal, InvalidOperation
        clean_lignes = None
        if isinstance(lignes, list) and lignes:
            clean_lignes = []
            for i, ligne in enumerate(lignes, start=1):
                if not isinstance(ligne, dict):
                    return Response(
                        {'detail': f'Ligne {i} invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)
                designation = (ligne.get('designation') or '').strip()
                if not designation:
                    return Response(
                        {'detail': f'Ligne {i} : désignation requise.'},
                        status=status.HTTP_400_BAD_REQUEST)
                try:
                    qte = Decimal(str(ligne.get('quantite')))
                    pu = Decimal(str(ligne.get('prix_unitaire')))
                except (InvalidOperation, TypeError, ValueError):
                    return Response(
                        {'detail': (f'Ligne {i} : quantité et prix unitaire '
                                    'numériques requis.')},
                        status=status.HTTP_400_BAD_REQUEST)
                if qte <= 0 or pu < 0:
                    return Response(
                        {'detail': (f'Ligne {i} : quantité > 0 et prix '
                                    'unitaire ≥ 0 requis.')},
                        status=status.HTTP_400_BAD_REQUEST)
                try:
                    remise = Decimal(str(ligne.get('remise') or 0))
                except (InvalidOperation, TypeError, ValueError):
                    return Response(
                        {'detail': f'Ligne {i} : remise invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)
                taux_tva = ligne.get('taux_tva')
                if taux_tva not in (None, ''):
                    try:
                        taux_tva = Decimal(str(taux_tva))
                    except (InvalidOperation, TypeError, ValueError):
                        return Response(
                            {'detail': f'Ligne {i} : taux TVA invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
                else:
                    taux_tva = None
                produit_id = ligne.get('produit') or None
                if produit_id is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit requis.'},
                        status=status.HTTP_400_BAD_REQUEST)
                from apps.stock.selectors import get_produit_scoped
                if get_produit_scoped(company, produit_id) is None:
                    return Response(
                        {'detail': f'Ligne {i} : produit inconnu.'},
                        status=status.HTTP_400_BAD_REQUEST)
                clean_lignes.append({
                    'produit_id': produit_id,
                    'designation': designation[:255],
                    'quantite': qte, 'prix_unitaire': pu,
                    'remise': remise, 'taux_tva': taux_tva,
                })

        def _create(ref):
            note_debit = NoteDebit.objects.create(
                company=company, reference=ref, facture=facture,
                client=facture.client, statut=NoteDebit.Statut.EMISE,
                motif=motif, taux_tva=facture.taux_tva,
                created_by=request.user)
            if clean_lignes:
                for ligne in clean_lignes:
                    LigneNoteDebit.objects.create(
                        note_debit=note_debit, **ligne)
            else:
                f_lignes = list(facture.lignes.all())
                if f_lignes:
                    for ligne in f_lignes:
                        LigneNoteDebit.objects.create(
                            note_debit=note_debit, produit=ligne.produit,
                            designation=ligne.designation,
                            quantite=ligne.quantite,
                            prix_unitaire=ligne.prix_unitaire,
                            remise=ligne.remise, taux_tva=ligne.taux_tva)
                else:
                    note_debit.montant_ht = facture.total_ht
                    note_debit.montant_tva = facture.total_tva
                    note_debit.montant_ttc = facture.total_ttc
                    note_debit.save(update_fields=[
                        'montant_ht', 'montant_tva', 'montant_ttc'])
            return note_debit

        note_debit = create_numbered(
            NoteDebit, company, 'note_debit', _create)
        try:
            from ..utils.pdf import generate_note_debit_pdf
            generate_note_debit_pdf(note_debit.id)
            note_debit.refresh_from_db()
        except Exception:
            pass
        return Response(NoteDebitSerializer(note_debit).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='retour-client',
            permission_classes=[IsResponsableOrAdmin])
    def retour_client(self, request, pk=None):
        """XPOS7 — Retour client avec re-stockage (contre ticket/facture
        d'origine). Sélectionne des lignes + quantités retournées → crée
        l'avoir référençant la facture d'origine (même chemin Avoir que
        `creer_avoir`, inchangé) + option « remettre en stock » (MouvementStock
        ENTREE via `stock.services`). Motif de retour OBLIGATOIRE. Une
        quantité retournée supérieure à ce qui a été vendu (moins les retours
        déjà actés) est refusée."""
        facture = self.get_object()
        self._guard_periode_verrouillee(facture)
        if facture.statut not in ('emise', 'payee', 'en_retard'):
            return Response(
                {'detail': 'Un retour ne peut être créé que depuis une '
                           'facture émise (ou payée/en retard).'},
                status=status.HTTP_400_BAD_REQUEST)
        company = facture.company
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'detail': 'Le motif du retour est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        restocker = bool(request.data.get('restocker', False))
        lignes = request.data.get('lignes')
        if not isinstance(lignes, list) or not lignes:
            return Response(
                {'detail': 'Au moins une ligne retournée est requise.'},
                status=status.HTTP_400_BAD_REQUEST)

        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
        reste_creditable = facture.total_ttc - facture.avoirs_total

        # Quantité déjà retournée par produit (avoirs actifs déjà émis sur
        # cette facture) — pour ne jamais accepter un retour au-delà du vendu.
        deja_retourne = {}
        for a in facture.avoirs.filter(statut=Avoir.Statut.EMISE):
            for lig in a.lignes.all():
                if lig.produit_id:
                    deja_retourne[lig.produit_id] = (
                        deja_retourne.get(lig.produit_id, Decimal('0'))
                        + lig.quantite)

        vendu_par_produit = {}
        for lig in facture.lignes.all():
            if lig.produit_id:
                vendu_par_produit[lig.produit_id] = (
                    vendu_par_produit.get(lig.produit_id, Decimal('0'))
                    + lig.quantite)

        clean_lignes = []
        for i, ligne in enumerate(lignes, start=1):
            if not isinstance(ligne, dict):
                return Response(
                    {'detail': f'Ligne {i} invalide.'},
                    status=status.HTTP_400_BAD_REQUEST)
            produit_id = ligne.get('produit') or None
            if produit_id is None:
                return Response(
                    {'detail': f'Ligne {i} : produit requis.'},
                    status=status.HTTP_400_BAD_REQUEST)
            from apps.stock.selectors import get_produit_scoped
            produit = get_produit_scoped(company, produit_id)
            if produit is None:
                return Response(
                    {'detail': f'Ligne {i} : produit inconnu.'},
                    status=status.HTTP_400_BAD_REQUEST)
            try:
                qte = Decimal(str(ligne.get('quantite')))
            except (InvalidOperation, TypeError, ValueError):
                return Response(
                    {'detail': f'Ligne {i} : quantité numérique requise.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if qte <= 0:
                return Response(
                    {'detail': f'Ligne {i} : quantité > 0 requise.'},
                    status=status.HTTP_400_BAD_REQUEST)
            vendu = vendu_par_produit.get(produit_id, Decimal('0'))
            deja = deja_retourne.get(produit_id, Decimal('0'))
            disponible_retour = vendu - deja
            if qte > disponible_retour:
                return Response(
                    {'detail': (
                        f'Ligne {i} : quantité retournée ({qte}) supérieure '
                        f'à la quantité vendue restant retournable '
                        f'({disponible_retour}) pour « {produit.nom} ».')},
                    status=status.HTTP_400_BAD_REQUEST)
            f_ligne = next(
                (lig for lig in facture.lignes.all()
                 if lig.produit_id == produit_id), None)
            prix_unitaire = f_ligne.prix_unitaire if f_ligne else Decimal('0')
            remise = f_ligne.remise if f_ligne else Decimal('0')
            taux_tva = f_ligne.taux_tva if f_ligne else None
            designation = (
                f_ligne.designation if f_ligne else produit.nom)[:255]
            clean_lignes.append({
                'produit': produit, 'produit_id': produit_id,
                'designation': designation, 'quantite': qte,
                'prix_unitaire': prix_unitaire, 'remise': remise,
                'taux_tva': taux_tva,
            })

        def _create(ref):
            avoir = Avoir.objects.create(
                company=company, reference=ref, facture=facture,
                client=facture.client, statut=Avoir.Statut.EMISE,
                motif=motif, motif_retour=motif, restocke=restocker,
                taux_tva=facture.taux_tva, created_by=request.user)
            for ligne in clean_lignes:
                LigneAvoir.objects.create(
                    avoir=avoir, produit=ligne['produit'],
                    designation=ligne['designation'],
                    quantite=ligne['quantite'],
                    prix_unitaire=ligne['prix_unitaire'],
                    remise=ligne['remise'], taux_tva=ligne['taux_tva'])
            return avoir

        avoir = create_numbered(Avoir, company, 'avoir', _create)
        if avoir.total_ttc - reste_creditable > Decimal('0.01'):
            avoir.lignes.all().delete()
            avoir.delete()
            return Response(
                {'detail': "Le retour dépasse le montant restant de la "
                           f"facture ({reste_creditable:.2f} MAD)."},
                status=status.HTTP_400_BAD_REQUEST)

        if restocker:
            for ligne in clean_lignes:
                produit = ligne['produit']
                produit.refresh_from_db()
                qte_entiere = int(Decimal(ligne['quantite']).quantize(
                    Decimal('1'), rounding=ROUND_HALF_UP))
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant + qte_entiere
                record_stock_movement(
                    company=company, produit=produit,
                    type_mouvement=mouvement_type_entree(),
                    quantite=qte_entiere, quantite_avant=qte_avant,
                    quantite_apres=qte_apres, reference=avoir.reference,
                    note=f'Retour client — {motif} (facture {facture.reference})',
                    created_by=request.user,
                )

        from .. import activity
        activity.log_facture_avoir(facture, request.user, avoir)
        try:
            from ..utils.pdf import generate_avoir_pdf
            generate_avoir_pdf(avoir.id)
            avoir.refresh_from_db()
        except Exception:
            pass
        return Response(AvoirSerializer(avoir).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='relancer',
            permission_classes=[IsResponsableOrAdmin])
    def relancer(self, request, pk=None):
        """Consigne une relance et, par défaut, l'envoie par email (N87).

        Journalise une RelanceLog + fixe la prochaine date de relance. L'email
        de relance part via l'intégration configurable : NO-OP réseau sans clé
        (backend console), envoi réel via Brevo/SMTP quand configuré. Passer
        ``envoyer_email=false`` pour seulement consigner sans envoyer (ancien
        comportement). Ouvert à la Commerciale."""
        facture = self.get_object()
        niveau = request.data.get('niveau')
        note = (request.data.get('note') or '').strip()
        niveau_nom = ''
        lvl = None
        if niveau:
            lvl = FollowupLevel.objects.filter(
                company=facture.company, ordre=niveau).first()
            niveau_nom = lvl.nom if lvl else ''
        RelanceLog.objects.create(
            company=facture.company, facture=facture,
            niveau=niveau or None, niveau_nom=niveau_nom, note=note,
            created_by=request.user)
        # Envoi email de relance (par défaut) — NO-OP sans clé configurée.
        email_log_id = None
        if request.data.get('envoyer_email', True):
            from ..email_service import send_relance_email
            email_log = send_relance_email(
                facture, niveau_nom=niveau_nom,
                message=(lvl.message if lvl else ''), user=request.user)
            email_log_id = email_log.id
        # Prochaine relance proposée si fournie, sinon laissée telle quelle.
        prochaine = request.data.get('prochaine_relance')
        if prochaine:
            facture.prochaine_relance = prochaine
            facture.save(update_fields=['prochaine_relance'])
        data = FactureSerializer(facture).data
        data['email_log_id'] = email_log_id
        return Response(data)

    @action(detail=True, methods=['post'], url_path='exclure-relance',
            permission_classes=[IsResponsableOrAdmin])
    def exclure_relance(self, request, pk=None):
        """Bascule l'exclusion de la facture des listes d'impayés."""
        facture = self.get_object()
        facture.exclu_relances = bool(request.data.get('exclu', True))
        facture.save(update_fields=['exclu_relances'])
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='facturer-penalites',
            permission_classes=[IsResponsableOrAdmin])
    def facturer_penalites(self, request, pk=None):
        """XFAC6 — action OPTIONNELLE : crée une facture de frais dédiée pour
        la pénalité de retard calculée au niveau de relance courant. Ne
        modifie JAMAIS ``montant_du`` de la facture d'origine (la pénalité
        reste indicative tant que non facturée — cette action la matérialise
        volontairement en un nouveau document, séparé)."""
        from decimal import Decimal
        from ..utils.company_settings import create_numbered

        facture = self.get_object()
        levels = list(FollowupLevel.objects.filter(
            company=facture.company).order_by('delai_jours', 'ordre'))
        jr = facture.jours_retard
        niveau = None
        for lvl in levels:
            if jr >= lvl.delai_jours:
                niveau = lvl
        if niveau is None:
            return Response(
                {'detail': "Aucun niveau de relance atteint pour "
                           "cette facture."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        penalite = niveau.calcul_penalite(facture.montant_du, jr)
        if penalite <= 0:
            return Response(
                {'detail': "Aucune pénalité à facturer (taux/frais à 0)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        libelle = (
            f"Pénalités de retard — facture {facture.reference} "
            f"({jr} jour(s) de retard, {niveau.nom})")

        def _create(ref):
            return Facture.objects.create(
                reference=ref, company=facture.company,
                client=facture.client, statut=Facture.Statut.EMISE,
                libelle=libelle, montant_ht=penalite,
                montant_tva=Decimal('0'), montant_ttc=penalite,
                taux_tva=Decimal('0'), created_by=request.user,
            )

        facture_penalite = create_numbered(
            Facture, facture.company, 'facture', _create)
        from .. import activity
        activity.log_facture_penalite_facturee(
            facture, request.user, facture_penalite, penalite)
        return Response(
            FactureSerializer(facture_penalite).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='relances',
            permission_classes=[IsAnyRole])
    def relances(self, request, pk=None):
        """Historique des relances consignées sur cette facture."""
        facture = self.get_object()
        return Response(
            RelanceLogSerializer(facture.relances.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='emails',
            permission_classes=[IsAnyRole])
    def emails(self, request, pk=None):
        """Fil des emails (envoyés/reçus) consignés sur cette facture (N87/N88)."""
        from ..serializers import EmailLogSerializer
        facture = self.get_object()
        return Response(
            EmailLogSerializer(facture.email_logs.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter de la facture : avoirs créés + paiements encaissés (qui,
        quand, montant). Lecture seule ; acteur et société posés côté serveur."""
        from ..serializers import FactureActivitySerializer
        facture = self.get_object()
        return Response(
            FactureActivitySerializer(
                facture.activites.all(), many=True).data)

    @action(detail=False, methods=['post'], url_path='consolider',
            permission_classes=[IsResponsableOrAdmin])
    def consolider(self, request):
        """XFAC11 — crée UNE facture consolidée à partir de plusieurs devis
        acceptés du MÊME client. Body : ``{devis_ids: [...]}``."""
        from ..services import consolider_factures

        devis_ids = request.data.get('devis_ids') or []
        try:
            devis_ids = [int(x) for x in devis_ids]
        except (TypeError, ValueError):
            return Response({'detail': 'devis_ids invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            facture = consolider_factures(
                company=request.user.company, devis_ids=devis_ids,
                user=request.user, created_by=request.user,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='encaissement-groupe',
            permission_classes=[IsResponsableOrAdmin])
    def encaissement_groupe(self, request):
        """ZFAC6 — un seul règlement client réparti sur PLUSIEURS factures
        (virement global, chèque unique). Body : ``{client, montant, mode,
        date, reference, factures:[ids]}`` — répartition FIFO par échéance
        (la plus ancienne d'abord) sur les factures listées ; un solde
        éventuel non affecté n'est PAS créé ici (XFAC1 le gère séparément
        s'il est présent — le montant excédentaire est simplement refusé)."""
        from decimal import Decimal, InvalidOperation

        from apps.crm.selectors import get_company_client

        company = request.user.company
        client_id = request.data.get('client')
        client = get_company_client(company, client_id)
        if client is None:
            return Response(
                {'detail': 'Client introuvable.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            montant = Decimal(str(request.data.get('montant')))
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {'detail': 'Montant invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        if montant <= 0:
            return Response(
                {'detail': 'Le montant doit être positif.'},
                status=status.HTTP_400_BAD_REQUEST)
        mode = (request.data.get('mode') or 'virement').strip()
        date_paiement = request.data.get('date') or timezone.now().date()
        reference = (request.data.get('reference') or '').strip()
        facture_ids = request.data.get('factures') or []
        if not isinstance(facture_ids, list) or not facture_ids:
            return Response(
                {'detail': 'factures (liste d\'ids) requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        factures = list(
            Facture.objects.filter(company=company, id__in=facture_ids))
        if len(factures) != len(set(facture_ids)):
            return Response(
                {'detail': 'Une ou plusieurs factures sont introuvables '
                           'pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)
        autres_clients = [f for f in factures if f.client_id != client.id]
        if autres_clients:
            return Response(
                {'detail': (
                    f"La facture {autres_clients[0].reference} "
                    "n'appartient pas à ce client."
                )},
                status=status.HTTP_400_BAD_REQUEST)

        repartition = request.data.get('repartition')
        if repartition is not None and not isinstance(repartition, dict):
            return Response(
                {'detail': 'repartition doit être un objet {facture_id: montant}.'},
                status=status.HTTP_400_BAD_REQUEST)

        from ..services import affecter_encaissement_groupe

        try:
            paiements = affecter_encaissement_groupe(
                company=company, client=client, montant=montant, mode=mode,
                date_paiement=date_paiement, user=request.user,
                factures=factures, reference=reference,
                repartition=repartition,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PaiementSerializer(paiements, many=True).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[IsResponsableOrAdmin])
    def bulk(self, request):
        """FG43 — opérations en masse sur les factures.

        Body :
          - ``action`` ∈ {emettre, relancer, envoyer-email, generer-pdf}
          - ``ids``    : liste d'ids de factures (toutes scopées à la société)

        Renvoie un dict par id : ``{id: {ok: bool, detail: str}}``.
        Les erreurs par facture n'interrompent pas le batch.
        """
        request.user.company
        action_name = (request.data.get('action') or '').strip()
        ids = request.data.get('ids') or []

        VALID_ACTIONS = {'emettre', 'relancer', 'envoyer-email', 'generer-pdf'}
        if action_name not in VALID_ACTIONS:
            return Response(
                {'detail': (
                    f'Action invalide. Valeurs acceptées : '
                    f'{", ".join(sorted(VALID_ACTIONS))}.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not ids or not isinstance(ids, list):
            return Response(
                {'detail': 'La liste `ids` est requise et doit être non vide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Borner aux factures de la société (scoping multi-tenant).
        factures_qs = _company_qs(
            Facture.objects.select_related('client').all(), request.user
        ).filter(id__in=ids)
        factures_by_id = {f.id: f for f in factures_qs}

        results = {}
        for fid in ids:
            try:
                fid_int = int(fid)
            except (ValueError, TypeError):
                results[fid] = {'ok': False, 'detail': 'ID invalide.'}
                continue
            facture = factures_by_id.get(fid_int)
            if facture is None:
                results[fid_int] = {'ok': False, 'detail': 'Introuvable.'}
                continue
            try:
                if action_name == 'emettre':
                    if facture.statut != Facture.Statut.BROUILLON:
                        results[fid_int] = {
                            'ok': False,
                            'detail': (
                                f'Statut {facture.get_statut_display()} : '
                                'seule une facture brouillon peut être émise.'
                            )}
                    elif not facture.lignes.exists() and not facture.libelle:
                        results[fid_int] = {
                            'ok': False,
                            'detail': 'La facture doit avoir au moins une ligne.'}
                    else:
                        facture.statut = Facture.Statut.EMISE
                        facture.save(update_fields=['statut'])
                        results[fid_int] = {
                            'ok': True,
                            'detail': 'Émise.',
                            'reference': facture.reference}

                elif action_name == 'relancer':
                    if facture.statut not in (
                        Facture.Statut.EMISE, Facture.Statut.EN_RETARD,
                    ):
                        results[fid_int] = {
                            'ok': False,
                            'detail': (
                                f'Statut {facture.get_statut_display()} : '
                                'relance uniquement sur facture émise ou en retard.'
                            )}
                    else:
                        from ..models import RelanceLog
                        RelanceLog.objects.create(
                            company=facture.company, facture=facture,
                            note='Relance en masse', created_by=request.user)
                        results[fid_int] = {
                            'ok': True,
                            'detail': 'Relance consignée.',
                            'reference': facture.reference}

                elif action_name == 'envoyer-email':
                    from ..email_service import send_document_email
                    from ..models import EmailLog
                    log = send_document_email(
                        facture, user=request.user, attach_pdf=True)
                    if log.statut == EmailLog.Statut.ECHEC:
                        results[fid_int] = {
                            'ok': False,
                            'detail': log.erreur or 'Envoi impossible.'}
                    else:
                        results[fid_int] = {
                            'ok': True,
                            'detail': f'Email envoyé à {log.to_email}.',
                            'reference': facture.reference}

                elif action_name == 'generer-pdf':
                    from ..tasks import task_generate_facture_pdf
                    task = task_generate_facture_pdf.delay(facture.id)
                    results[fid_int] = {
                        'ok': True,
                        'detail': 'Génération PDF lancée.',
                        'task_id': task.id,
                        'reference': facture.reference}

            except Exception as exc:  # noqa: BLE001 — batch: no single failure kills all
                results[fid_int] = {'ok': False, 'detail': str(exc)}

        return Response(results)
