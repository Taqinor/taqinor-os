from ..openapi_params import ENTITE, qint
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from .facture_cycle import FactureCycleActionsMixin, PEUT_ANNULER, refuser_devis_du_corps
from .facture_rectificatifs import FactureRectificatifsActionsMixin
from .facture_encaissement import FactureEncaissementActionsMixin
from . import openapi_docs as D
from rest_framework.parsers import JSONParser
from rest_framework import serializers as drf_serializers
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from ..models import Facture, RelanceLog, EmailLog
from ..serializers_facturation import (
    FactureSerializer,
    FactureWriteSerializer,
    RelanceLogSerializer,
)
from ..serializers_facturation import FactureActivitySerializer, RelancerFactureSerializer
from ..serializers import EmailLogSerializer
from ..utils.corps import valider_corps
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from core.permissions import declared_action_permissions

# ZFAC11 — `arrondir_au_pas` ré-exporté (déplacé dans domain/encaissements.py).
from ..domain.encaissements import arrondir_au_pas
from authentication.scoping import scope_queryset
from core.viewsets import CompanyScopedModelViewSet
from core.entite_scoping import EntiteScopeMixin
from ..utils.company_settings import create_provisoire
import logging

logger = logging.getLogger(__name__)
__all__ = ['arrondir_au_pas']  # ré-export ZFAC11
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

# ATOT9 (C-ATOT-007, D-ATOT-1) — les champs d'ARGENT d'une facture sont FIGÉS
# dès qu'elle quitte le brouillon, QUEL QUE SOIT `factures_immuables` : une
# facture émise se corrige par avoir (ou `remettre-brouillon`), jamais en
# place. Le flag ne gouverne plus que le reste de FACTURE_CHAMPS_FINANCIERS.
FACTURE_CHAMPS_ARGENT = frozenset([
    'montant_ht', 'montant_tva', 'montant_ttc', 'remise_globale', 'taux_tva',
    'pourcentage', 'arrondi_pas', 'arrondi_unites',
])
MESSAGE_MONTANT_FIGE = (
    'Montant figé après émission : corrigez par un avoir '
    '(ou remettez la facture en brouillon).')


#: AFAC66 — refus nommé de la cinquième porte de facturation d'un devis.
BC_DE_DEVIS_REFUSE = (
    "Cette commande vient d'un devis : créez la facture depuis le bon de "
    "commande — remise, options et sections du devis signé y sont reprises.")

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


@extend_schema_view(list=extend_schema(
    parameters=[ENTITE, qint('client', desc="Filtre optionnel par client.")]),
    # VNT14 — seul un « BROUILLON-<id> » se supprime : 409 sinon (ENF11).
    destroy=extend_schema(
        responses={204: None, 409: D.ErreurSuppressionFacture}))
class FactureViewSet(FactureCycleActionsMixin, FactureEncaissementActionsMixin, FactureRectificatifsActionsMixin, EntiteScopeMixin, CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF11/D2 : aucun envoi de fichier
    # ARC5 — sweep TenantMixin : base transverse unique (CompanyScopedModelViewSet
    # = TenantMixin + ModelViewSet). get_queryset/perform_create/perform_update/
    # get_permissions SURCHARGENT la base : scoping société et matrice 401/403/404
    # IDENTIQUES (règle #4 : aucun statut/sérialisation Facture touché ; la facture
    # garde son PDF légacy séparé, hors périmètre du moteur devis).
    # AUD157 (FAC-14) — LE PRÉFETCH DIT CE QUE LE SÉRIALISEUR LIT. Il ne
    # portait que `lignes`, alors que `FactureSerializer` sérialise pour CHAQUE
    # facture les paiements imbriqués, les avoirs, `montant_paye` (→ paiements
    # + affectations_paiement), `montant_du` (→ + notes_debit + retenues_subies)
    # et `mentions_manquantes` — soit ≈6 requêtes par facture. Le viewset Devis
    # avait reçu le correctif équivalent (YOPSB13) ; la liste des factures
    # jamais.
    #
    # AUD157 (résidu) — LE SÉRIALISEUR IMBRIQUÉ COMPTE AUSSI. Le préfetch
    # s'arrêtait à la facture, mais `PaiementSerializer` — imbriqué dans
    # `FactureSerializer` — expose `montant_disponible`, qui interroge
    # `Paiement.affectations` (`.exists()`, puis `montant_affecte`). Une
    # requête PAR PAIEMENT sérialisé : le budget de la liste restait indexé
    # sur le portefeuille (+1 par ligne), le N+1 s'était juste déplacé d'un
    # cran. Le gestionnaire de relation sert `.all()` ET `.exists()` depuis
    # `_prefetched_objects_cache` — préfetcher la relation suffit, aucune
    # propriété modèle n'a à être réécrite.
    #
    # Même raison pour `avoirs__lignes` / `notes_debit__lignes` : `get_avoirs`
    # et `notes_debit_total` lisent le `total_ttc` de chaque document, qui
    # retombe sur SES lignes dès que ses montants ne sont pas figés.
    queryset = Facture.objects.select_related(
        'client', 'created_by', 'bon_commande', 'devis', 'updated_by',
        'company', 'devis__bon_commande',
    ).prefetch_related(
        'lignes', 'paiements', 'paiements__affectations',
        'avoirs', 'avoirs__lignes',
        'notes_debit', 'notes_debit__lignes', 'retenues_subies',
        'affectations_paiement__paiement',
    ).all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'client__nom', 'client__prenom', 'client__email'
    ]
    ordering_fields = [
        'date_emission', 'date_echeance', 'statut', 'reference'
    ]
    ordering = ['-date_emission']

    def get_queryset(self):
        qs = super().get_queryset()
        # AFAC17/ENF — `?client=` (réaffectation d'un paiement : factures du
        # MÊME client) ; une valeur non numérique est ignorée.
        client = self.request.query_params.get('client')
        if self.action == 'list' and client and str(client).isdigit():
            qs = qs.filter(client_id=int(client))
        # Portée de visibilité (Feature F) — factures créées par soi / l'équipe.
        return scope_queryset(qs, self.request.user, ['created_by'])

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return FactureWriteSerializer
        return FactureSerializer

    def get_permissions(self):
        # ASEC29 — la garde DÉCLARÉE par l'@action PRIME (patron AUD421) :
        # sans cette ligne, le ``permission_classes=`` des gestes d'argent
        # était jeté en silence au profit du tiering ci-dessous.
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        if self.action in READ_ACTIONS + [
            'paiements', 'relances', 'emails', 'arrondi_caisse', 'kpis',
        ]:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'emettre', 'enregistrer_paiement',
            'generer_pdf', 'telecharger_pdf', 'envoyer_email',
            'relancer', 'relance_apercu', 'exclure_relance', 'whatsapp', 'ubl',
            'dgi_export', 'dgi_conformite', 'dgi_transmettre',
            'bulk', 'lien_paiement', 'revoquer_lien_paiement',
            'retour_client',
            'facturer_penalites', 'consolider', 'abandonner_solde',
            'remettre_brouillon', 'encaissement_groupe',
            # CIQ214 — libérer la retenue de garantie (date de réception
            # définitive) : édition courante du responsable, pas un geste admin.
            'liberer_retenue',
        ]:
            return [IsResponsableOrAdmin()]
        # VNT13 — supprimer un brouillon : même garde qu'annuler.
        elif self.action == 'destroy':
            return [p() for p in PEUT_ANNULER]
        # AUD124 — `marquer_payee` : geste comptable, palier admin.
        elif self.action == 'marquer_payee':
            return [IsAdminRole()]
        # creer_avoir tombe ici → IsAdminRole (création d'avoir = admin).
        return [IsAdminRole()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        # ERR14 — client/bon_commande du corps : de la société ; VNT89 — un
        # devis jamais (la facture de vente naît par « Facturer la vente »).
        if company is not None:
            client = serializer.validated_data.get('client')
            bon_commande = serializer.validated_data.get('bon_commande')
            if client is not None and client.company_id != company.id:
                raise ValidationError({'client': 'Client inconnu.'})
            if bon_commande is not None and \
                    bon_commande.company_id != company.id:
                raise ValidationError(
                    {'bon_commande': 'Bon de commande inconnu.'})
        refuser_devis_du_corps(serializer.validated_data)
        # AFAC66 (C-AFAC-057) — la cinquième porte est FERMÉE : une facture
        # liée au BC d'un devis ne naît QUE par `bons-commande/<id>/
        # creer-facture/` (copie fidèle du devis signé, garde ATOT2).
        bc_corps = serializer.validated_data.get('bon_commande')
        if bc_corps is not None and bc_corps.devis_id:
            raise ValidationError({'bon_commande': BC_DE_DEVIS_REFUSE, 'code': 'bon_commande_de_devis'})
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

        # ATOT27 (D-ATOT-5) — brouillon hors série : « BROUILLON-<id> ».
        create_provisoire(
            lambda ref: serializer.save(reference=ref, **save_kwargs),
        )

    def perform_destroy(self, instance):
        """AUD103 (FICHE-DEL) — la suppression d'une facture cesse d'emporter
        les encaissements en cascade (DRF appelait ``instance.delete()`` nu :
        une facture émise/payée partait avec ses ``Paiement``, l'écriture au
        grand livre survivait en orphelin).

        Gardes, plus une traduction :
          1. seul un BROUILLON est supprimable (tout le reste s'ANNULE) ;
          1 bis. VNT14 (D-VNT-1) — seul un « BROUILLON-<id> » : une référence
             LÉGALE remise en brouillon s'annule (409 ``reference_legale``),
             sinon « plus-haut-utilisé + 1 » réutiliserait le numéro ;
          2. aucun paiement, même rejeté (piste d'audit) ;
          3. verrou de période comptable ;
          4. ``ProtectedError`` (avoir, note de débit, intention de paiement
             portail) devient un refus français, plus une 500 non traduite.
        Chaque refus dépend de l'ÉTAT de la facture, pas du corps : 409
        ``ConflitEtat`` (ENF11, ``core/conflit_etat.py``), jamais un 400.
        """
        from django.db.models import ProtectedError
        from core.conflit_etat import ConflitEtat
        from core.numbering import est_reference_provisoire

        if instance.statut != Facture.Statut.BROUILLON:
            raise ConflitEtat({'detail': (
                'Seule une facture brouillon peut être supprimée. Une facture '
                'émise, en retard ou payée s\'ANNULE (elle porte un numéro '
                'légal et, le cas échéant, des encaissements).'
            )})
        if not est_reference_provisoire(instance.reference):
            raise ConflitEtat({'code': 'reference_legale', 'detail': (
                f'Cette facture porte le numéro {instance.reference} : '
                'annulez-la (un numéro légal ne se supprime jamais).')})
        if instance.paiements.exists():
            raise ConflitEtat({'detail': (
                'Cette facture porte au moins un paiement : la supprimer '
                'effacerait des encaissements réels. Annulez-la ou rejetez '
                'd\'abord ses paiements.'
            )})
        try:
            instance.delete()
        except ProtectedError:
            raise ConflitEtat({'detail': (
                'Suppression impossible : cette facture est référencée par un '
                'avoir, une note de débit ou un paiement du portail client. '
                'Annulez-la plutôt que de la supprimer.'
            )})

    def perform_update(self, serializer):
        # XFAC24 — immutabilité de la facture émise (opt-in). Flag OFF
        # (défaut) → comportement actuel byte-identique. Flag ON et facture
        # non-brouillon : tout champ FINANCIER dans le corps est refusé (la
        # correction passe par un avoir + une nouvelle facture) ; les champs
        # non financiers (conditions, notes, dates de livraison…) restent
        # modifiables.
        facture = self.get_object()
        # AFAC66 (C-AFAC-057) / VNT89 — mêmes portes fermées en modification :
        # poser le BC d'un devis, ou un devis, sur une facture existante.
        bc_corps = serializer.validated_data.get('bon_commande')
        if bc_corps is not None and bc_corps.devis_id \
                and bc_corps.pk != facture.bon_commande_id:
            raise ValidationError({'bon_commande': BC_DE_DEVIS_REFUSE, 'code': 'bon_commande_de_devis'})
        refuser_devis_du_corps(serializer.validated_data, facture)
        from ..domain.facturation_ops import argent_modifie  # ATOT35
        argent_touche = argent_modifie(
            facture, serializer.validated_data, FACTURE_CHAMPS_ARGENT)
        if facture.statut != Facture.Statut.BROUILLON and argent_touche:
            raise ValidationError({
                'detail': MESSAGE_MONTANT_FIGE,
                'champs_refuses': sorted(argent_touche),
            })
        if facture.statut != Facture.Statut.BROUILLON:
            from apps.parametres.models import CompanyProfile
            profile = CompanyProfile.get(company=facture.company)
            if getattr(profile, 'factures_immuables', False):
                champs_touches = (
                    set(serializer.validated_data.keys())
                    & FACTURE_CHAMPS_FINANCIERS)
                if champs_touches:
                    raise ValidationError({
                        'detail': (
                            "Facture immuable : les champs financiers d'une "
                            "facture émise ne peuvent plus être modifiés. "
                            "Corrigez par un avoir puis une nouvelle "
                            "facture."
                        ),
                        'champs_refuses': sorted(champs_touches),
                    })
        # ATOT9 — toute modification d'argent ACCEPTÉE (brouillon) laisse une
        # trace avant/après dans le chatter de la facture.
        avant = {champ: getattr(facture, champ) for champ in argent_touche}
        # VX98 — dernier auteur de modification (server-side, jamais du corps) :
        # alimente la puce de fraîcheur. Pattern created_by.
        serializer.save(updated_by=self.request.user)
        if argent_touche:
            from ..models import FactureActivity
            instance = serializer.instance
            for champ in sorted(argent_touche):
                apres = getattr(instance, champ)
                if apres == avant[champ]:
                    continue
                FactureActivity.objects.create(
                    company=instance.company, facture=instance,
                    user=self.request.user,
                    kind=FactureActivity.Kind.MODIFICATION,
                    field=champ, field_label=champ,
                    old_value='' if avant[champ] is None else str(avant[champ]),
                    new_value='' if apres is None else str(apres),
                    body=(f'Montant modifié sur le brouillon : {champ} '
                          f'{avant[champ]} -> {apres}.'),
                )

    @extend_schema(request=None, responses={202: D.PdfTaskResponse})
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

    @extend_schema(responses=D.PdfBinaire)
    @action(detail=True, methods=['get'], url_path='telecharger-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def telecharger_pdf(self, request, pk=None):
        facture = self.get_object()
        # AFAC41 (C-AFAC-042) — le téléchargement interne (et l'aperçu inline
        # de la liste) sert le PDF GARANTI à jour par `cle_facture_pdf_a_jour`,
        # exactement comme le lien public : après un paiement, le « Reste à
        # payer » imprimé est le courant ; une facture jamais rendue se rend à
        # la volée. Si le rafraîchissement échoue, le fichier stocké est servi
        # tel quel (même repli que le lien public).
        from ..utils.pdf import cle_facture_pdf_a_jour, download_pdf
        try:
            cle = cle_facture_pdf_a_jour(facture)
        except Exception:  # noqa: BLE001
            logger.warning("facture.FactureViewSet.telecharger_pdf : erreur ignorée (mode dégradé)", exc_info=True)
            cle = facture.fichier_pdf
        if not cle:
            return Response(
                {'detail': 'PDF indisponible pour le moment. Réessayez.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            pdf_bytes = download_pdf(cle)
        except Exception:
            logger.warning("facture.FactureViewSet.telecharger_pdf : erreur ignorée (mode dégradé)", exc_info=True)
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

    @extend_schema(responses=D.UblXml)
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

    @extend_schema(responses=D.UblXml)
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

    @extend_schema(responses=D.DgiConformiteResponse)
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

    @extend_schema(request=None, responses=D.DgiTransmissionResponse)
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

    @extend_schema(request=D.FactureWhatsappRequest, responses=D.FactureWhatsappResponse)
    @action(detail=True, methods=['post'], url_path='whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp(self, request, pk=None):
        """Lien wa.me prêt à envoyer pour une facture (ou un rappel).

        N'envoie RIEN : ouvre WhatsApp avec le message pré-rempli. Le {lien} est
        un lien public tokenisé (30 j) vers le PDF CLIENT de la facture.
        Body : `modele` ∈ {'facture','relance'}, `langue` ∈ {'fr','darija'}.
        """
        from ..utils.phone import normalize_phone_e164
        from ..utils.whatsapp import build_facture_whatsapp, build_wa_url
        facture = self.get_object()
        phone = facture.client.telephone if facture.client_id else ''
        if not normalize_phone_e164(phone):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        saisie = valider_corps(request, D.FactureWhatsappRequest)
        modele, langue = saisie.get('modele', 'facture'), saisie.get('langue', 'fr')
        message, link = build_facture_whatsapp(request, facture, modele, langue)
        # L856 — trace l'action dans le chatter de la facture (Historique).
        # Acteur et société posés côté serveur, jamais lus du corps de requête.
        from ..activity import log_facture_whatsapp
        log_facture_whatsapp(facture, request.user, modele)
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
        })

    @extend_schema(request=D.EnvoyerEmailFactureRequest,
                   responses={202: D.EnvoyerEmailFactureResponse,
                              400: D.ErreurEnvoiEmail})
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
        saisie = valider_corps(request, D.EnvoyerEmailFactureRequest)
        log = send_document_email(
            facture, user=request.user,
            to_email=saisie.get('to_email', '').strip() or None,
            sujet=saisie.get('sujet', '').strip() or None,
            corps=saisie.get('corps', '').strip() or None,
            attach_pdf=saisie.get('attach_pdf', True))
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

    @extend_schema(request=RelancerFactureSerializer,
                   responses=D.FactureRelancee)
    @action(detail=True, methods=['post'], url_path='relancer',
            permission_classes=[IsResponsableOrAdmin])
    def relancer(self, request, pk=None):
        """Consigne une relance — l'envoi d'email est un OPT-IN explicite.

        AUD129 (PAY-4) : l'envoi était le DÉFAUT (``envoyer_email`` non fourni
        ⇒ email parti) alors que la modale annonce « Cette action journalise la
        relance (aucun envoi) » et que le lot poste ``{niveau}`` seul — une
        consignation en lot expédiait donc de vraies mises en demeure. Le
        défaut est désormais FALSE : il faut poster ``envoyer_email=true``
        (case « Envoyer l'email au client ») pour qu'un email parte.

        AUD129 (PAY-19) : le corps de l'email reprend la note saisie quand elle
        est renseignée (``note or lvl.message``) — elle n'était jusqu'ici
        écrite que dans le journal interne et perdue pour le destinataire.

        AUD131 (PAY-18) : l'action ne vérifiait NI ``statut`` NI ``montant_du``,
        alors que le cron exclut payee/annulee/brouillon — une facture déjà
        payée pouvait recevoir une mise en demeure. Elle partage désormais LE
        prédicat ``recouvrement.facture_relancable`` avec la liste des impayés
        et le beat, et son corps est validé par un serializer (un ``niveau``
        inexistant ou une ``prochaine_relance`` non-date ⇒ 400, plus jamais une
        relance consignée à vide ni une erreur base).

        Journalise une RelanceLog + fixe la prochaine date de relance. L'envoi
        passe par l'intégration configurable : NO-OP réseau sans clé (backend
        console), envoi réel via Brevo/SMTP quand configuré."""
        from ..recouvrement import (
            ensure_default_followup_levels, facture_relancable,
        )
        facture = self.get_object()
        # AUD131 — garde d'état AVANT toute écriture.
        ok, motif = facture_relancable(facture)
        if not ok:
            return Response({'detail': motif},
                            status=status.HTTP_400_BAD_REQUEST)
        # Fondateur 05/10/2026 — les 3 niveaux par défaut existent toujours
        # (créés seulement si la société n'en a aucun) : le `niveau` posté
        # (ORDRE, cf. RelancerFactureSerializer) se résout donc toujours.
        ensure_default_followup_levels(facture.company)

        payload = RelancerFactureSerializer(
            data=request.data, context={'company': facture.company})
        payload.is_valid(raise_exception=True)
        donnees = payload.validated_data

        niveau = donnees.get('niveau')
        note = (donnees.get('note') or '').strip()
        lvl = payload.context.get('followup_level')
        if niveau is None and lvl is None:
            # AFAC46 — sans niveau choisi, LE prochain niveau de la cadence
            # (le même que l'aperçu et le beat), jamais une relance hors
            # séquence.
            from ..domain.recouvrement import prochain_niveau
            lvl, _tous = prochain_niveau(facture)
            niveau = lvl.ordre if lvl is not None else None
        niveau_nom = lvl.nom if lvl is not None else ''
        RelanceLog.objects.create(
            company=facture.company, facture=facture,
            niveau=niveau or None, niveau_nom=niveau_nom, note=note,
            created_by=request.user)
        # AUD129 — envoi d'email en OPT-IN explicite (défaut : ne rien envoyer).
        # NO-OP réseau sans clé configurée.
        email_log_id = None
        if donnees.get('envoyer_email'):
            from ..email_service import send_relance_email
            # AUD129 (PAY-19) — la note saisie prime sur le message générique
            # du niveau : sinon la personnalisation n'atteint jamais le client.
            email_log = send_relance_email(
                facture, niveau_nom=niveau_nom,
                message=(note or (lvl.message if lvl is not None else '')),
                user=request.user)
            email_log_id = email_log.id
        # Prochaine relance proposée si fournie, sinon laissée telle quelle.
        prochaine = donnees.get('prochaine_relance')
        if prochaine:
            facture.prochaine_relance = prochaine
            facture.save(update_fields=['prochaine_relance'])
        data = FactureSerializer(facture).data
        data['email_log_id'] = email_log_id
        return Response(data)

    @extend_schema(responses=D.RelanceApercuResponse)
    @action(detail=True, methods=['get'], url_path='relance-apercu',
            permission_classes=[IsResponsableOrAdmin])
    def relance_apercu(self, request, pk=None):
        """Fenêtre « Relancer » (fondateur, 05/10/2026) : niveau qui part
        maintenant (1 → 2 → 3 d'après le journal des relances) + aperçu EXACT
        de l'email (même rendu que l'envoi). Lecture seule — hormis la
        création, si la société n'en a aucun, des 3 niveaux par défaut.
        Contrat : ``contract_samples/facture_relance_apercu.json``."""
        from ..recouvrement import apercu_relance
        facture = self.get_object()
        return Response(apercu_relance(facture))

    @extend_schema(request=D.ExclureRelanceRequest, responses=FactureSerializer)
    @action(detail=True, methods=['post'], url_path='exclure-relance',
            permission_classes=[IsResponsableOrAdmin])
    def exclure_relance(self, request, pk=None):
        """Bascule l'exclusion de la facture des listes d'impayés."""
        facture = self.get_object()
        corps = request.data if isinstance(request.data, dict) else {}
        exclu = corps.get('exclu', True)
        if not isinstance(exclu, bool):
            raise ValidationError({'exclu': ['Booléen attendu.']})
        facture.exclu_relances = exclu
        facture.save(update_fields=['exclu_relances'])
        return Response(FactureSerializer(facture).data)

    @extend_schema(responses=inline_serializer('FacturesKpis', {
        'mois': drf_serializers.CharField(),
        'mois_precedent': drf_serializers.CharField(),
        'encaisse_mois': drf_serializers.CharField(),
        'encaisse_mois_precedent': drf_serializers.CharField(),
        'total_du': drf_serializers.CharField(),
        'nb_impayees': drf_serializers.IntegerField(),
        'total_en_retard': drf_serializers.CharField(),
        'nb_en_retard': drf_serializers.IntegerField(),
        'total_a_echoir_7j': drf_serializers.CharField(),
    }))
    @action(detail=False, methods=['get'], url_path='kpis',
            permission_classes=[IsAnyRole])
    def kpis(self, request):
        """AUD157 (FAC-13) — LES KPI MONÉTAIRES DE L'ÉCRAN FACTURES, calculés
        par le serveur.

        « Encaissé ce mois » était sommé côté écran sur `p.montant` SANS
        filtrer `p.statut` : l'écran comptait des chèques revenus impayés, avec
        une définition différente de `Facture.montant_paye`. Un seul
        propriétaire désormais : `selectors.kpis_factures`, sur le queryset
        DÉJÀ scopé société + portée de visibilité de ce viewset.

        Contrat PACT10 : `apps/ventes/contract_samples/factures_kpis.json`.
        """
        from ..selectors import kpis_factures
        return Response(kpis_factures(self.filter_queryset(
            self.get_queryset())))

    @extend_schema(responses=RelanceLogSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='relances',
            permission_classes=[IsAnyRole])
    def relances(self, request, pk=None):
        """Historique des relances consignées sur cette facture."""
        facture = self.get_object()
        return Response(
            RelanceLogSerializer(facture.relances.all(), many=True).data)

    @extend_schema(responses=EmailLogSerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='emails',
            permission_classes=[IsAnyRole])
    def emails(self, request, pk=None):
        """Fil des emails (envoyés/reçus) consignés sur cette facture (N87/N88)."""
        from ..serializers import EmailLogSerializer
        facture = self.get_object()
        return Response(
            EmailLogSerializer(facture.email_logs.all(), many=True).data)

    @extend_schema(responses=FactureActivitySerializer(many=True))
    @action(pagination_class=None, detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter de la facture : avoirs créés + paiements encaissés (qui,
        quand, montant). Lecture seule ; acteur et société posés côté serveur."""
        from ..serializers_facturation import FactureActivitySerializer
        facture = self.get_object()
        return Response(
            FactureActivitySerializer(
                facture.activites.all(), many=True).data)

    @extend_schema(request=D.ConsoliderRequest,
                   responses={201: FactureSerializer})
    @action(detail=False, methods=['post'], url_path='consolider',
            permission_classes=[IsResponsableOrAdmin])
    def consolider(self, request):
        """XFAC11 — crée UNE facture consolidée à partir de plusieurs devis
        acceptés du MÊME client. Body : ``{devis_ids: [...]}``."""
        from ..services import consolider_factures

        corps = request.data
        devis_ids = (corps.get('devis_ids') if isinstance(corps, dict)
                     else None) or []
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

    @extend_schema(request=D.BulkRequest, responses=D.BulkResponse)
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
        donnees = request.data if isinstance(request.data, dict) else {}
        action_brute = donnees.get('action')
        # ENF11 — une action qui n'est pas un texte est invalide (jamais un 500).
        action_name = action_brute.strip() if isinstance(action_brute, str) else ''
        ids = donnees.get('ids') or []

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
        # Borner aux factures de la société (scoping multi-tenant). AFAC55
        # (C-AFAC-048) — ET à la portée du rôle (`get_queryset` : créées par
        # soi / l'équipe) : un id invisible répond « Introuvable. ».
        # ENF11 — le schéma déclare des ids ENTIERS : tout autre élément
        # (texte, objet, booléen) est refusé en 400 avant toute lecture.
        if any(type(brut) is not int for brut in ids):
            return Response({'detail': "ids : liste d'entiers attendue."},
                            status=status.HTTP_400_BAD_REQUEST)
        factures_by_id = {f.id: f for f in self.get_queryset().filter(
            id__in=[i for i in ids if abs(i) < 2 ** 31])}

        results = {}
        for fid_int in ids:
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
                        # AUD101 — le bulk passe par LE service unique : il
                        # posait EMISE en silence, sans verrou de période,
                        # sans workflow de revue XFAC18, sans dérivation
                        # d'échéance et sans `facture_emise` (donc sans
                        # écriture au grand livre).
                        from ..domain.facturation_ops import emettre_facture
                        emettre_facture(
                            facture, user=request.user, source='bulk')
                        results[fid_int] = {
                            'ok': True,
                            'detail': 'Émise.',
                            'reference': facture.reference}

                elif action_name == 'relancer':
                    # AFAC46 — LE prédicat partagé (`facture_relancable`) et
                    # LE prochain niveau de la cadence (jamais `niveau=NULL`).
                    from ..recouvrement import (
                        ensure_default_followup_levels, facture_relancable,
                    )
                    relancable, motif_refus = facture_relancable(facture)
                    if not relancable:
                        results[fid_int] = {'ok': False, 'detail': motif_refus}
                    else:
                        from ..domain.recouvrement import prochain_niveau
                        from ..models import RelanceLog
                        ensure_default_followup_levels(facture.company)
                        lvl, _tous = prochain_niveau(facture)
                        RelanceLog.objects.create(
                            company=facture.company, facture=facture,
                            niveau=lvl.ordre if lvl is not None else None,
                            niveau_nom=lvl.nom if lvl is not None else '',
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
                logger.warning("facture.FactureViewSet.bulk : erreur ignorée (mode dégradé)", exc_info=True)
                results[fid_int] = {'ok': False, 'detail': str(exc)}

        return Response(results)
