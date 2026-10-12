from ..openapi_params import ENTITE, qint
from drf_spectacular.utils import extend_schema, extend_schema_view
from .facture_cycle import FactureCycleActionsMixin, PEUT_ANNULER, refuser_devis_du_corps
from .facture_lot import FactureLotActionsMixin
from .facture_recouvrement import FactureRecouvrementActionsMixin
from .facture_documents import FactureDocumentsActionsMixin
from .facture_rectificatifs import FactureRectificatifsActionsMixin
from .facture_encaissement import FactureEncaissementActionsMixin
from . import openapi_docs as D
from rest_framework.parsers import JSONParser
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from ..models import Facture
from ..serializers_facturation import FactureSerializer, FactureWriteSerializer
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
class FactureViewSet(
        FactureCycleActionsMixin, FactureEncaissementActionsMixin,
        FactureRectificatifsActionsMixin, FactureDocumentsActionsMixin,
        FactureRecouvrementActionsMixin, FactureLotActionsMixin,
        EntiteScopeMixin, CompanyScopedModelViewSet):
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
