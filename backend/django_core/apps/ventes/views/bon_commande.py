from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework import status, filters
from . import openapi_docs as D
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.stock.services import (
    mouvement_type_sortie, record_stock_movement, verrouiller_produit,
    check_negative_stock_guard,
)
from ..models import BonCommande, Facture
from ..serializers_facturation import BonCommandeSerializer, FactureSerializer
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from apps.roles.permissions import DroitDeLaGrille  # ASEC50
from core.viewsets import CompanyScopedModelViewSet  # noqa: ARC5 — exception documentée (D-ENF22)
from core.pagination import OrdreTotalMixin  # ERR-FACTURES-LISTE-ORDRE-INSTABLE
from ..domain.facturation_ops import StockInsuffisantError
import logging

logger = logging.getLogger(__name__)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


def _reserver_stock_bc_actif(company):
    """YDOCF7 — état du toggle société `reserver_stock_bc` (défaut OFF).

    Lecture robuste : société absente/config absente ⇒ False (comportement
    actuel intact), jamais d'exception."""
    if company is None:
        return False
    try:
        from apps.parametres.models import CompanyProfile
        return bool(CompanyProfile.get(company=company).reserver_stock_bc)
    except Exception:  # pragma: no cover - défensif
        logger.warning("bon_commande._reserver_stock_bc_actif : erreur ignorée (mode dégradé)", exc_info=True)
        return False


def _sortir_reliquat_bc(bc, user):
    """AFAC15 (C-AFAC-001) — sortie de stock de « Livrer » (toggle OFF).

    ASTK244 — ne sort que le RELIQUAT du panier VENDU pas encore sorti
    (``lignes_reliquat_vente``) : livraisons partielles, facture directe,
    livraison directe chantier, F11 ou « Installé » déjà joués — « une vente
    = une sortie ». Même décompteur unique (AUD116) et même solde de
    réservation chantier (ASTK135). À appeler dans la transaction (BC
    verrouillé) de l'appelant ; lève ``StockInsuffisantError``."""
    from ..domain.facturation_ops import (
        decompter_stock_lignes, lignes_reliquat_vente,
        solder_reservations_chantier_vente,
    )

    sorties = {}
    decompter_stock_lignes(
        lignes=lignes_reliquat_vente(bc.devis, bc.company),
        company=bc.company, user=user,
        reference=bc.reference, note=f'Livraison BC {bc.reference}',
        multiplicateur=1, sorties=sorties)
    solder_reservations_chantier_vente(
        devis=bc.devis, company=bc.company, sorties=sorties,
        reference=bc.reference, user=user)
    return sorties


def _notifier_chantier_materiel_confirme(bc):
    """CHT15 — notifie (best-effort, ne lève jamais) le responsable du
    chantier né du même devis que ce BC désormais CONFIRMÉ.

    NOTIFICATION SEULEMENT — jamais de transition automatique de statut
    chantier (gates YSERV1/DUERP imprévisibles depuis un signal, pas de user
    légitime, cascade d'effets inadaptée). Lecture cross-app via
    ``installations.selectors`` uniquement (jamais son modèle)."""
    if bc.devis_id is None:
        return
    try:
        from apps.installations.selectors import installation_for_devis
        installation = installation_for_devis(bc.devis, company=bc.company)
        if installation is None:
            return
        responsable = installation.technicien_responsable
        if responsable is None:
            return
        from apps.notifications.services import notify
        from apps.notifications.types_evenements import EventType
        notify(
            responsable, EventType.CHANTIER_MATERIEL_CONFIRME,
            f'Matériel confirmé — chantier {installation.reference}',
            body=f'Le bon de commande {bc.reference} est confirmé.',
            link=f'/chantiers?id={installation.id}',
            company=bc.company)
    except Exception:  # pragma: no cover - défensif, best-effort
        logger.warning(
            "bon_commande._notifier_chantier_materiel_confirme : erreur ignorée (mode dégradé)", exc_info=True)

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


def _erreur_lignes_livraison(lignes, date_livraison):
    """ENF11 — message FR de la première anomalie d'un corps de livraison
    partielle (``lignes`` + ``date_livraison``), ``None`` si le corps est sain."""
    from datetime import date
    from decimal import Decimal, InvalidOperation
    if not isinstance(lignes, list):
        return 'lignes doit être une liste de {ligne_devis, quantite}.'
    for entree in lignes:
        if not isinstance(entree, dict):
            return 'Chaque ligne doit être un objet {ligne_devis, quantite}.'
        if entree.get('ligne_devis') is None or entree.get('quantite') is None:
            return 'Chaque ligne requiert ligne_devis et quantite.'
        try:
            int(entree['ligne_devis'])
        except (TypeError, ValueError):
            return 'ligne_devis doit être un entier.'
        try:
            quantite = Decimal(str(entree['quantite']))
        except (InvalidOperation, ValueError):
            return 'quantite doit être un nombre.'
        if not quantite.is_finite():
            return 'quantite doit être un nombre fini.'
        # CI #997 fuzz (24/10) — la règle publiée au schéma (``LigneLivraison``) :
        # strictement positive, 2 décimales au plus, 10 chiffres entiers au plus.
        # Une chaîne suit ``MOTIF_MONTANT_SAISI`` mot pour mot ; un nombre JSON
        # est jugé sur sa valeur.
        from .openapi_docs import MOTIF_MONTANT_SAISI
        import re
        brut = entree['quantite']
        if isinstance(brut, bool):
            return 'quantite doit être un nombre.'
        if isinstance(brut, str) and not re.fullmatch(
                MOTIF_MONTANT_SAISI, brut):
            return ('quantite doit être strictement positive, avec au plus '
                    '2 décimales.')
        if not isinstance(brut, str) and not (
                Decimal('0.01') <= quantite <= Decimal('9999999999.99')):
            return 'quantite doit être strictement positive.'
    if date_livraison not in (None, ''):
        try:
            date.fromisoformat(str(date_livraison))
        except ValueError:
            return 'date_livraison invalide (attendu AAAA-MM-JJ).'
    return None


class BonCommandeViewSet(OrdreTotalMixin, CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF11/D2 : aucun envoi de fichier
    # ARC5 — sweep TenantMixin : base transverse unique (CompanyScopedModelViewSet
    # = TenantMixin + ModelViewSet). get_queryset/perform_create/get_permissions
    # SURCHARGENT la base : le scoping société et la matrice 401/403/404 restent
    # IDENTIQUES (règle #4 : aucun statut/sérialisation Devis/Facture touché).
    # AUD115 (constat FAC-9) — le N+1 EN SÉRIE de la liste BC. Le queryset ne
    # faisait que `select_related('client','devis')` : `get_has_facture` posait
    # un `.exists()` PAR LIGNE et les trois totaux traversaient TROIS fois la
    # chaîne canonique du devis (chacune rechargeant ses lignes). Le prefetch
    # des lignes + l'annotation d'existence rendent la liste bornée, et le
    # sérialiseur ne calcule plus les totaux qu'UNE fois par BC.
    queryset = (
        BonCommande.objects
        .select_related('client', 'devis')
        .prefetch_related('devis__lignes__produit', 'livraisons__lignes')
        .annotate(
            has_facture_annote=Exists(
                Facture.objects.filter(bon_commande=OuterRef('pk'))),
            # AUD118 — facture VIVANTE (non annulée) : le prédicat qui décide
            # si le bon de commande peut encore être annulé.
            facture_active_annote=Exists(
                Facture.objects
                .filter(bon_commande=OuterRef('pk'))
                .exclude(statut=Facture.Statut.ANNULEE)))
        .all()
    )
    serializer_class = BonCommandeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'client__nom', 'client__email']
    ordering_fields = [
        'date_creation', 'date_livraison_prevue', 'statut'
    ]
    ordering = ['-date_creation', '-id']  # ERR-FACTURES-LISTE-ORDRE-INSTABLE

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['pdf']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'confirmer', 'marquer_livre', 'annuler', 'creer_facture',
            'livrer_partiel',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            # ASEC50 / D-ASEC-4 — supprimer un BC exige ``ventes_supprimer``
            # en plus du palier administrateur (comme le devis).
            return [IsAdminRole(), DroitDeLaGrille('ventes_supprimer')()]
        return [IsAdminRole()]

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.action == 'create' and 'devis' in serializer.fields:
            # AMET5 — « un BC par devis » est jugé par LA porte unique
            # (`creer_bon_commande`, même message que `convertir_en_bc`),
            # pas par le validateur d'unicité générique du OneToOne.
            from rest_framework.validators import UniqueValidator
            champ = serializer.fields['devis']
            champ.validators = [v for v in champ.validators
                                if not isinstance(v, UniqueValidator)]
        return serializer

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        client = serializer.validated_data.get('client')
        devis = serializer.validated_data.get('devis')
        # AUD117 — LA GARDE ERR13 N'EST PLUS CONDITIONNELLE. Elle vivait dans
        # un `if company is not None:` : elle était donc INACTIVE pour le seul
        # profil qui peut voir les objets de tous les tenants (superutilisateur
        # sans société), c'est-à-dire exactement celui contre lequel elle
        # protège. Quand l'utilisateur n'a pas de société, on la DÉRIVE des
        # objets validés (devis d'abord, puis client) au lieu de désactiver le
        # contrôle — et on exige alors que les deux concordent.
        if company is None:
            derivee = (getattr(devis, 'company', None)
                       or getattr(client, 'company', None))
            if derivee is None:
                raise ValidationError({
                    'detail': ('Aucune société ne peut être déterminée pour '
                               'ce bon de commande.')})
            company = derivee
        # ERR13 — client/devis du corps doivent appartenir à la société (refuse
        # de lier un BC au client/devis d'un autre tenant).
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
        if devis is not None and devis.company_id != company.id:
            raise ValidationError({'devis': 'Devis inconnu.'})
        # AMET5 — même porte que `convertir_en_bc` : refus d'un second BC
        # pour le même devis + événement `bon_commande_cree`.
        from ..domain.facturation_ops import (
            BonCommandeExistant, creer_bon_commande)
        try:
            creer_bon_commande(
                devis, company, self.request.user,
                enregistrer=lambda ref: serializer.save(
                    reference=ref, company=company))
        except BonCommandeExistant as exc:
            # CI #997 (2) — corps conforme, c'est l'ÉTAT (BC déjà né) : 409.
            from core.conflit_etat import ConflitEtat
            raise ConflitEtat(exc.message)

    @extend_schema(request=None, responses=BonCommandeSerializer)
    @action(detail=True, methods=['post'], url_path='confirmer',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.EN_ATTENTE:
            # ENF11 — conflit d'ÉTAT (et non entrée invalide) : 409.
            return Response(
                {'detail': 'Seul un BC en attente peut être confirmé.'},
                status=status.HTTP_409_CONFLICT,
            )
        bc.statut = BonCommande.Statut.CONFIRME
        bc.save()
        # YDOCF7 — toggle société (défaut OFF = comportement actuel intact) :
        # réserve le stock des lignes du BC (StockReservation N14, via
        # installations.services — jamais d'import de son modèle ici).
        if _reserver_stock_bc_actif(bc.company):
            from apps.installations.services import reserver_stock_depuis_bc
            reserver_stock_depuis_bc(bc)
        # CHT15 — nudge « Matériel commandé » (notification seulement, jamais
        # de transition de statut chantier).
        _notifier_chantier_materiel_confirme(bc)
        return Response(BonCommandeSerializer(bc).data)

    @extend_schema(request=D.MarquerLivreRequest,
                   responses=BonCommandeSerializer)
    @action(parser_classes=[JSONParser, MultiPartParser, FormParser],
            detail=True, methods=['post'], url_path='marquer-livre',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_livre(self, request, pk=None):
        # ENF11 (nocturne 15/10) — statut du BC et stock insuffisant = refus
        # d'ÉTAT (409) ici et dans livrer-partiel ; la forme reste en 400.
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.CONFIRME:
            return Response(
                {'detail': (
                    'Le BC doit être confirmé avant d\'être livré.'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        # FG51 — capture optionnelle de la preuve de livraison (PV/signature).
        # Le signataire, une note et une pièce jointe (bon signé) peuvent être
        # joints à la livraison. Tout est optionnel : un BC peut être livré sans
        # preuve (la facturation n'est jamais bloquée), mais la preuve lève
        # l'avertissement doux au moment de facturer.
        from django.utils import timezone as _tz
        signataire = (request.data.get('signataire') or '').strip()
        note_pv = (request.data.get('note_pv') or '').strip()
        upload = request.FILES.get('pv') or request.FILES.get('file')
        pv = {}
        if signataire:
            pv['signataire'] = signataire[:150]
        if note_pv:
            pv['note'] = note_pv[:1000]
        if upload is not None:
            from apps.records.storage import store_attachment
            # AUD311 (SCA42) — cle scopee societe : sans `company=`,
            # `store_attachment` retombe en silence sur la cle PLATE
            # `attachments/{uuid}.ext`. La societe vient du BON DE
            # COMMANDE (AUD117), jamais de l'utilisateur.
            meta, err = store_attachment(upload, company=bc.company)
            if err is not None:
                return Response(
                    {'detail': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pv['file_key'] = meta['file_key']
            pv['filename'] = meta['filename']
        if pv:
            pv['signed_at'] = _tz.now().isoformat()
        # YDOCF7 — toggle ON : la réservation créée à `confirmer` est SOLDÉE
        # (consommée) ici au lieu d'un second décrément direct — jamais les
        # deux (double décompte). Toggle OFF : chemin historique inchangé.
        toggle_bc_stock = _reserver_stock_bc_actif(bc.company)
        try:
            with transaction.atomic():
                # AFAC15 — VERROU du BC : deux « Livrer » concurrents (ou un
                # « Livrer » et un « Livrer partiellement ») ne peuvent plus
                # sortir deux fois le même reliquat.
                bc = BonCommande.objects.select_for_update().get(pk=bc.pk)
                if bc.statut != BonCommande.Statut.CONFIRME:
                    return Response(
                        {'detail': (
                            'Le BC doit être confirmé avant d\'être livré.'
                        )},
                        status=status.HTTP_409_CONFLICT,
                    )
                if bc.devis and not toggle_bc_stock:
                    # AFAC15 (C-AFAC-001) — « Livrer » ne sort QUE le
                    # RELIQUAT non encore sorti : les livraisons partielles
                    # ont déjà posé leurs SORTIES (re-sortir tout le panier
                    # comptait deux fois les quantités livrées), et RIEN si
                    # la vente est déjà sortie par la facture directe
                    # (`reserver_stock_devis_facture`, référence = le devis).
                    _sortir_reliquat_bc(bc, request.user)
                bc.statut = BonCommande.Statut.LIVRE
                from django.utils import timezone as _tz2
                bc.date_livraison_reelle = _tz2.now().date()
                if pv:
                    bc.pv_livraison = pv
                bc.save()
        except StockInsuffisantError as exc:
            # Message FR INCHANGÉ : il vit désormais dans le décompteur unique.
            return Response(
                {'detail': exc.message},
                status=status.HTTP_409_CONFLICT,
            )
        if toggle_bc_stock:
            from apps.installations.services import consommer_reservation_bc
            consommer_reservation_bc(bc, request.user)
        return Response(BonCommandeSerializer(bc).data)

    @extend_schema(request=D.LivrerPartielRequest,
                   responses=BonCommandeSerializer)
    @action(detail=True, methods=['post'], url_path='livrer-partiel',
            permission_classes=[IsResponsableOrAdmin])
    def livrer_partiel(self, request, pk=None):
        """XSAL12 — Livraison partielle : décrémente le stock UNIQUEMENT des
        quantités livrées de cette livraison (jamais un second décompte via
        `marquer_livre` — le BC passe à `livre` automatiquement seulement
        quand tout le reliquat est soldé, une seule fois)."""
        from decimal import Decimal, ROUND_HALF_UP

        from ..models import LivraisonBC, LigneLivraisonBC

        bc = self.get_object()
        if bc.devis_id is None:
            return Response(
                {'detail': 'Ce BC ne porte aucun devis : aucune ligne à livrer.'},
                status=status.HTTP_409_CONFLICT,
            )
        lignes_payload = request.data.get('lignes') or []
        if not lignes_payload:
            return Response(
                {'detail': 'lignes est requis (liste de {ligne_devis, quantite}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # ENF11 — entrées validées AVANT toute lecture/écriture : une ligne
        # qui n'est pas un objet, un ``ligne_devis`` non entier, une quantité
        # non numérique/infinie ou une date illisible finissaient en 500
        # (AttributeError, ValueError, InvalidOperation, ValidationError).
        erreur_lignes = _erreur_lignes_livraison(
            lignes_payload, request.data.get('date_livraison'))
        if erreur_lignes:
            return Response({'detail': erreur_lignes},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validation intégrale AVANT toute écriture — un payload invalide ne
        # doit laisser aucune trace (pas de LivraisonBC orpheline). Le stock
        # déjà réservé PAR CETTE MÊME requête est suivi en mémoire (deux
        # lignes de devis du même produit ne doivent pas survaloriser le
        # stock disponible).
        # AUD216 — la VALIDATION (lecture du stock disponible) et l'ÉCRITURE
        # vivent désormais dans UNE SEULE transaction : le verrou de ligne pris
        # ci-dessous ne vaut que s'il tient jusqu'au commit des mouvements.
        # Auparavant la boucle de validation lisait `quantite_stock` HORS
        # transaction (`refresh_from_db()`), puis le bloc atomique écrivait
        # des `qte_avant`/`qte_apres` calculés sur cette valeur déjà morte.
        with transaction.atomic():
            # AFAC15 (C-AFAC-006) — BC VERROUILLÉ et machine à états
            # respectée : seul un BC CONFIRMÉ se livre (ni en attente, ni
            # annulé — un BC annulé ne repasse jamais « livré ») ; le
            # reliquat est relu SOUS le verrou, sur le seul panier VENDU.
            bc = BonCommande.objects.select_for_update().get(pk=bc.pk)
            if bc.statut == BonCommande.Statut.LIVRE:
                return Response(
                    {'detail': 'Ce BC est déjà entièrement livré.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if bc.statut != BonCommande.Statut.CONFIRME:
                return Response(
                    {'detail': (
                        'Le BC doit être confirmé avant d\'être livré.'
                    )},
                    status=status.HTTP_409_CONFLICT,
                )
            reliquats = {r['ligne_devis_id']: r for r in bc.reliquat_par_ligne}
            # ASTK244 — ne SORT que ce que la vente n'a pas déjà sorti
            # (facture directe, livraison directe, F11, « Installé ») : la
            # livraison est enregistrée, sans second mouvement.
            from ..domain.facturation_ops import lignes_reliquat_vente
            reste = {li.produit_id: li.quantite for li in
                     lignes_reliquat_vente(bc.devis, bc.company)}
            stock_reserve = {}
            validated = []
            for entry in lignes_payload:
                ligne_devis_id = entry.get('ligne_devis')
                quantite = entry.get('quantite')
                if ligne_devis_id is None or quantite is None:
                    return Response(
                        {'detail': 'Chaque ligne requiert ligne_devis et quantite.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                reliquat_ligne = reliquats.get(int(ligne_devis_id))
                if reliquat_ligne is None:
                    return Response(
                        {'detail': f'Ligne de devis {ligne_devis_id} inconnue sur ce BC.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                quantite = Decimal(str(quantite))
                if quantite <= 0 or quantite > reliquat_ligne['reliquat']:
                    # ENF11 (nocturne 15/10) — au-delà du reliquat, c'est l'ÉTAT
                    # du BC qui s'oppose (409) ; une quantité <= 0 reste une
                    # entrée invalide (400).
                    return Response(
                        {'detail': (
                            f"Quantité invalide pour « {reliquat_ligne['designation']} » "
                            f"(reliquat disponible : {reliquat_ligne['reliquat']})."
                        )},
                        status=(status.HTTP_400_BAD_REQUEST if quantite <= 0
                                else status.HTTP_409_CONFLICT),
                    )
                ligne_devis = bc.devis.lignes.get(id=ligne_devis_id)
                # AUD216 — VERROU de ligne produit, tenu jusqu'au commit des
                # mouvements (la validation et l'écriture partagent désormais
                # la même transaction).
                produit = verrouiller_produit(ligne_devis.produit_id)
                qte_entiere = min(reste.get(produit.id, 0), int(
                    Decimal(quantite).quantize(
                        Decimal('1'), rounding=ROUND_HALF_UP)))
                reste[produit.id] = reste.get(produit.id, 0) - qte_entiere
                qte_avant = produit.quantite_stock - stock_reserve.get(produit.id, 0)
                qte_apres = qte_avant - qte_entiere
                # AUD228 — la décision passe par le réglage société
                # (`AchatsParametres.stock_negatif_autorise`, défaut False =
                # comportement historique inchangé), jamais un blocage en dur.
                try:
                    check_negative_stock_guard(
                        bc.company, qte_avant, qte_apres if qte_entiere else 0)
                except ValueError:
                    return Response(
                        {'detail': (
                            f'Stock insuffisant pour « {produit.nom} » '
                            f'(disponible : {qte_avant}, requis : {qte_entiere}).'
                        )},
                        status=status.HTTP_409_CONFLICT,
                    )
                stock_reserve[produit.id] = stock_reserve.get(produit.id, 0) + qte_entiere
                validated.append(
                    (ligne_devis, produit, quantite, qte_entiere, qte_avant, qte_apres))

            # Ecritures : MEME transaction que la validation ci-dessus (AUD216).
            livraison = LivraisonBC.objects.create(
                company=bc.company, bon_commande=bc,
                date_livraison=request.data.get('date_livraison') or timezone.now().date(),
                note=(request.data.get('note') or '')[:255],
                created_by=request.user,
            )
            for (ligne_devis, produit, quantite, qte_entiere,
                    qte_avant, qte_apres) in validated:
                LigneLivraisonBC.objects.create(
                    livraison=livraison, ligne_devis=ligne_devis,
                    quantite_livree=quantite)
                if qte_entiere <= 0:
                    continue
                record_stock_movement(
                    company=bc.company,
                    produit=produit,
                    type_mouvement=mouvement_type_sortie(),
                    quantite=qte_entiere,
                    quantite_avant=qte_avant,
                    quantite_apres=qte_apres,
                    reference=bc.reference,
                    note=f'Livraison partielle BC {bc.reference}',
                    created_by=request.user,
                )

            # ERR-BC-LIVRER-PARTIEL-DOUBLE-SORTIE — « une vente = une
            # sortie » : la sortie de CETTE livraison solde (même
            # transaction) la réservation du chantier à hauteur des seules
            # quantités livrées ; « Installé » ne ressort que le reliquat.
            # Référence propre à la livraison : le solde est idempotent par
            # (référence, produit), deux livraisons ne doivent pas s'annuler.
            from ..domain.facturation_ops import (
                solder_reservations_chantier_vente,
            )
            sorties_livraison = {}
            for (_ld, produit, _q, qte_entiere, _qa, _qp) in validated:
                sorties_livraison[produit.id] = (
                    sorties_livraison.get(produit.id, 0) + qte_entiere)
            solder_reservations_chantier_vente(
                devis=bc.devis, company=bc.company,
                sorties=sorties_livraison,
                reference=f'{bc.reference} (livraison {livraison.id})',
                user=request.user)

            # Solde intégral atteint sur toutes les lignes → passage LIVRE
            # (une seule fois — les side-effects existants de `marquer_livre`
            # NE sont PAS ré-exécutés ici : le statut est simplement posé).
            bc.refresh_from_db()
            reliquats_apres = bc.reliquat_par_ligne
            if reliquats_apres and all(r['reliquat'] <= 0 for r in reliquats_apres):
                bc.statut = BonCommande.Statut.LIVRE
                bc.date_livraison_reelle = timezone.now().date()
                bc.save()

        return Response(BonCommandeSerializer(bc).data)

    @extend_schema(request=None, responses=BonCommandeSerializer)
    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        # CI #997 fuzz (24/10) : sans corps, tout refus ci-dessous vient de l'ÉTAT
        # du BC (livré, livraison partielle, facture vivante) : 409, plus 400.
        bc = self.get_object()
        if bc.statut == BonCommande.Statut.LIVRE:
            return Response(
                {'detail': 'Un BC livré ne peut pas être annulé.'},
                status=status.HTTP_409_CONFLICT,
            )
        # AFAC15 (C-AFAC-006) — un BC PARTIELLEMENT livré a déjà sorti du
        # stock : l'annuler laissait des sorties orphelines (aucune extourne).
        if bc.livraisons.exists():
            return Response(
                {'detail': (
                    'Ce BC a déjà été livré partiellement : il ne peut plus '
                    'être annulé (le matériel livré est sorti du stock).'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        # AUD118 — UN BC DÉJÀ FACTURÉ NE S'ANNULE PAS EN SILENCE. Le bouton
        # « Facture » est proposé dès `confirme` et le bouton Annuler restait
        # visible tant que le statut n'était ni `livre` ni `annule` : un BC
        # annulé « par erreur de saisie » laissait en vie une facture ÉMISE que
        # plus aucun écran ne rattachait à son origine (le stepper rendait même
        # un état contradictoire). On dirige vers la voie correcte : annuler
        # d'abord la FACTURE (action `annuler`, qui émet `facture_annulee` et
        # déclenche l'extourne), puis le bon de commande.
        facture = (Facture.objects
                   .filter(bon_commande=bc)
                   .exclude(statut=Facture.Statut.ANNULEE)
                   .first())
        if facture is not None:
            return Response(
                {'detail': (
                    f'La facture {facture.reference} est encore vivante sur '
                    'ce bon de commande : annulez-la d\'abord, puis annulez '
                    'le bon de commande.'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        bc.statut = BonCommande.Statut.ANNULE
        bc.save()
        # YDOCF7 — toggle ON : libère la réservation posée à `confirmer`
        # (no-op si le BC n'avait pas encore été confirmé/réservé).
        if _reserver_stock_bc_actif(bc.company):
            from apps.installations.services import liberer_reservation_bc
            liberer_reservation_bc(bc)
        return Response(BonCommandeSerializer(bc).data)

    @extend_schema(request=None,
                   responses={201: D.FactureCreeeDepuisBc})
    @action(detail=True, methods=['post'], url_path='creer-facture',
            permission_classes=[IsResponsableOrAdmin])
    def creer_facture(self, request, pk=None):
        bc = self.get_object()
        # CI #997 fuzz — sans corps, chaque refus ci-dessous vient de l'ÉTAT
        # du BC (statut, facture existante, vente déjà facturée, société) :
        # 409, comme les trois autres portes de facturation, plus 400.
        if bc.statut not in [
            BonCommande.Statut.CONFIRME, BonCommande.Statut.LIVRE
        ]:
            return Response(
                {'detail': 'Le BC doit être confirmé ou livré.'},
                status=status.HTTP_409_CONFLICT,
            )
        if Facture.objects.filter(bon_commande=bc).exists():
            return Response(
                {'detail': 'Une facture existe déjà pour ce BC.'},
                status=status.HTTP_409_CONFLICT,
            )
        # AUD112 — LES DEUX PORTES SE VOIENT ENFIN. La garde ci-dessus ne
        # regardait que la chaîne BC : un devis déjà facturé par l'échéancier
        # (acompte/tranche) passait ici sans obstacle, et le client recevait
        # deux fois la même vente. Prédicat partagé, une seule définition de
        # « déjà facturé » pour les deux portes.
        # ATOT2 — LA garde unique des quatre portes (échéancier, complète,
        # consolidée) : le refus nomme la facture existante.
        from ..selectors_facturation import (
            DevisDejaFacture, exiger_devis_facturable,
        )
        if bc.devis_id:
            try:
                exiger_devis_facturable(bc.devis, 'bc')
            except DevisDejaFacture as exc:
                return Response({'detail': exc.motif},
                                status=status.HTTP_409_CONFLICT)
        # AUD117 — LA SOCIÉTÉ VIENT DU BON DE COMMANDE, PAS DE L'UTILISATEUR.
        # La règle maison est « company forcée côté serveur, jamais issue de la
        # requête » : elle venait bien du serveur, mais du MAUVAIS objet
        # serveur. Un superutilisateur sans société (`company_qs` laisse
        # passer TOUS les BC dans ce cas) facturait le BC de la société A et la
        # facture naissait dans SA société — ou sans société : invisible pour
        # son propriétaire légitime, et comptée dans le CA d'un autre tenant.
        # Le BC est déjà scopé par `get_object` : c'est LA source de vérité.
        if bc.company_id is None:
            return Response(
                {'detail': (
                    'Ce bon de commande n\'appartient à aucune société : '
                    'impossible d\'émettre une facture.'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        company = bc.company

        def _create_facture(ref):
            # AUD113 — le taux de TÊTE suit le devis (repli des lignes sans
            # taux) : `entete_facture_depuis_devis`. QX1/ERR16/ARRONDI-100/
            # ×N villas — le panier du devis est recopié par LE geste partagé
            # avec `devis/{id}/facturer-complet/` (`copier_devis_sur_facture`).
            from ..domain.facturation_ops import (
                copier_devis_sur_facture, entete_facture_depuis_devis,
            )
            entete = (entete_facture_depuis_devis(bc.devis)
                      if bc.devis_id else {})
            facture = Facture.objects.create(
                reference=ref,
                bon_commande=bc,
                # AUD112 — corollaire minimal : la facture PORTE son devis.
                # Sans lui, `solde_devis`, `devis_a_facturer` et le suivi
                # client ne voyaient tout simplement pas ce document (FK
                # nullable, SET_NULL : rien ne casse si le devis disparaît).
                devis=bc.devis,
                client=bc.client,
                statut=Facture.Statut.BROUILLON,
                created_by=request.user,
                company=company,
                # CIQ216/ATOT4 — référence de commande du client et retenue
                # de garantie du devis : portées par `entete` (geste partagé
                # des quatre portes).
                **entete,
            )
            if bc.devis:
                copier_devis_sur_facture(facture, bc.devis)
            return facture

        # ATOT27 (D-ATOT-5) — brouillon hors série « BROUILLON-<id> » (numéro
        # légal à l'émission) ; facture + lignes recopiées restent atomiques.
        from ..utils.company_settings import create_provisoire
        with transaction.atomic():
            # ERR-FACT-ACOMPTE-PLUS-BC-DOUBLE — la facture de BC est une
            # facture COMPLÈTE (même panier) : comme ``facturer-complet``
            # (VNT65), les brouillons de la vente (acompte auto VNT62) sont
            # ANNULÉS, jamais additionnés au prix convenu.
            if bc.devis_id:
                from ..domain.annulation_facture import (
                    retirer_brouillons_de_la_vente)
                retirer_brouillons_de_la_vente(
                    bc.devis, user=request.user,
                    motif='Remplacé par la facture du bon de commande')
            facture = create_provisoire(_create_facture)
        data = FactureSerializer(facture).data
        # FG51 — avertissement DOUX (jamais bloquant) : on facture la livraison
        # de matériel sans preuve de livraison (PV/signature). Le facturier voit
        # le message mais la facture est bien créée (201).
        if not bc.has_proof_of_delivery:
            data['warnings'] = [
                'Aucune preuve de livraison (PV / signature) n\'est attachée '
                'à ce bon de commande. Vous facturez sans bon de livraison '
                'signé.'
            ]
        return Response(
            data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses=D.PdfBinaire)
    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """ZSAL8 — PDF imprimable du bon de commande client (layout legacy
        WeasyPrint, jamais le moteur devis premium — règle #4). Rendu à la
        volée, non stocké."""
        bc = self.get_object()
        from ..utils.pdf import generate_bon_commande_pdf
        pdf_bytes = generate_bon_commande_pdf(bc.id)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        from ..utils.filenames import document_filename
        filename = document_filename(
            'BonCommande', bc.reference,
            client=bc.client if bc.client_id else None,
            company=bc.company)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
