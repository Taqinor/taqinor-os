"""Sérialiseurs de facturation de ventes — ``BonCommandeSerializer`` + ré-export.

SPL148 a sorti ces classes de ``serializers.py`` ; ODX18 (étape 2) a ensuite
DÉPLACÉ tels quels les sérialiseurs de facture/paiement/avoir/note de
débit/relance/remise/mandat vers ``apps.facturation.serializers``. Seul
``BonCommandeSerializer`` (le bon de commande relève de ventes) vit encore ici.
Les autres noms sont RÉ-EXPORTÉS : ``from apps.ventes.serializers_facturation
import FactureSerializer`` renvoie la MÊME classe (aucune copie).

Ordre d'import : ``apps.facturation.serializers`` ne lit de ventes que
``models``, ``serializers`` et ``domain`` (jamais ce module) : l'import en tête
ci-dessous ne forme aucun cycle, quel que soit le module chargé le premier.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import BonCommande, Facture
from core.champs_stricts import ChampsStrictsSansDecimalMixin, IdInconnu404Mixin
from core.mixins import SameCompanyFKSerializerMixin
from apps.facturation.serializers import (  # noqa: F401 — ré-export ODX18
    AffectationPaiementSerializer,
    AvoirSerializer,
    FactureActivitySerializer,
    FactureListeSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    FollowupLevelSerializer,
    LigneAvoirSerializer,
    LigneFactureSerializer,
    LigneNoteDebitSerializer,
    LigneRemiseEncaissementSerializer,
    MandatPaiementSerializer,
    NoteDebitSerializer,
    PaiementAvecRetenueEntreeSerializer,
    PaiementSerializer,
    ParametrageRelanceClientSerializer,
    PromessePaiementSerializer,
    RelanceLogSerializer,
    RelancerFactureSerializer,
    RemiseEncaissementSerializer,
    RetenueSubieSerializer,
)

__all__ = [
    'BonCommandeSerializer',
    'AffectationPaiementSerializer',
    'AvoirSerializer',
    'FactureActivitySerializer',
    'FactureListeSerializer',
    'FactureSerializer',
    'FactureWriteSerializer',
    'FollowupLevelSerializer',
    'LigneAvoirSerializer',
    'LigneFactureSerializer',
    'LigneNoteDebitSerializer',
    'LigneRemiseEncaissementSerializer',
    'MandatPaiementSerializer',
    'NoteDebitSerializer',
    'PaiementAvecRetenueEntreeSerializer',
    'PaiementSerializer',
    'ParametrageRelanceClientSerializer',
    'PromessePaiementSerializer',
    'RelanceLogSerializer',
    'RelancerFactureSerializer',
    'RemiseEncaissementSerializer',
    'RetenueSubieSerializer',
]


class BonCommandeSerializer(IdInconnu404Mixin, ChampsStrictsSansDecimalMixin,
                            SameCompanyFKSerializerMixin,
                            serializers.ModelSerializer):
    # CI #997 — texte/booléens stricts (``signe_au_domicile: 0`` converti).
    # ASEC28 (C-ASEC-005) — FK inscriptibles bornées à la société de la
    # requête : un id étranger = 400 « objet inexistant », en PATCH comme en
    # création (la garde ERR13 de perform_create ne couvrait que la création).
    same_company_fields = ('client', 'devis', 'lead')
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, allow_null=True)
    has_facture = serializers.SerializerMethodField()
    # ATOT49 — porte de facturation `{ok, motif}` (même fonction que
    # `creer-facture`) : l'écran n'affiche « Facture » que si `ok`.
    facturable = serializers.SerializerMethodField()
    # AUD118 — DISTINCT de `has_facture` : une facture ANNULÉE ne bloque plus
    # rien. `has_facture` reste le prédicat « une facture a déjà été émise »
    # (il gouverne le bouton « Facture », dont la garde serveur ne filtre pas
    # le statut) ; `facture_active` est le prédicat « une facture VIVANTE est
    # attachée », qui gouverne le bouton « Annuler ».
    facture_active = serializers.SerializerMethodField()
    # FG51 — preuve de livraison (lecture seule : capturée par l'action
    # « marquer-livre », jamais par un PUT du corps).
    has_proof_of_delivery = serializers.BooleanField(read_only=True)
    # Totaux du BC dérivés du devis lié (un BC reprend les lignes du devis).
    # Aucun devis → None → l'UI affiche « — ». Affichage seulement.
    total_ht = serializers.SerializerMethodField()
    total_tva = serializers.SerializerMethodField()
    total_ttc = serializers.SerializerMethodField()
    # XSAL12 — état dérivé de livraison partielle (lecture seule, calculé à
    # la demande depuis LigneLivraisonBC ; ne casse pas l'enum de statut).
    reliquat_par_ligne = serializers.ListField(read_only=True)
    est_partiellement_livre = serializers.BooleanField(read_only=True)

    class Meta:
        model = BonCommande
        fields = '__all__'
        # company is force-assigned in perform_create — never accept it from the body.
        # FG51 — pv_livraison/date_livraison_reelle ne se posent QUE via
        # l'action « marquer-livre » (jamais un PUT direct du corps).
        # AUD506 — ``statut`` en lecture seule : BonCommandeViewSet n'a AUCUN
        # perform_update, un PATCH brut faisait donc passer un BC directement
        # en_attente→livre sans réservation stock ni preuve de livraison.
        # CONFIRME/LIVRE/ANNULE passent désormais UNIQUEMENT par leurs actions
        # dédiées (confirmer/marquer-livre/annuler), qui posent le statut
        # directement sur le modèle (hors de ce sérialiseur).
        read_only_fields = ['reference', 'date_creation', 'company',
                            'pv_livraison', 'date_livraison_reelle',
                            'statut']

    @extend_schema_field(serializers.BooleanField())
    def get_has_facture(self, obj):
        # AUD115 — lit l'annotation `Exists` posée par le viewset quand elle
        # est là (un seul aller-retour pour toute la page) ; repli sur la
        # requête historique pour les appelants qui sérialisent une instance
        # nue (détail, tests, autres vues).
        annote = getattr(obj, 'has_facture_annote', None)
        if annote is not None:
            return bool(annote)
        return Facture.objects.filter(bon_commande=obj).exists()

    @extend_schema_field(serializers.DictField())
    def get_facturable(self, obj):
        from .selectors_facturation import porte_facture_bc
        return porte_facture_bc(obj)

    @extend_schema_field(serializers.BooleanField())
    def get_facture_active(self, obj):
        # AUD118 — même annotation servie par le viewset, filtrée sur les
        # factures NON annulées : c'est elle qui décide si l'annulation du BC
        # est encore possible.
        annote = getattr(obj, 'facture_active_annote', None)
        if annote is not None:
            return bool(annote)
        return (Facture.objects
                .filter(bon_commande=obj)
                .exclude(statut=Facture.Statut.ANNULEE)
                .exists())

    def _totaux(self, obj):
        """AUD115 — LES TROIS TOTAUX EN UN SEUL PASSAGE. Chacun des trois
        `get_total_*` traversait la chaîne canonique du devis de bout en bout
        (`_totaux_argent()`), soit trois parcours complets des lignes par bon
        de commande. On mémoïse la chaîne sur l'instance : la SOURCE des
        chiffres ne change pas d'un centime, seul le nombre de parcours."""
        if not obj.devis_id:
            return None
        totaux = getattr(obj, '_aud115_totaux', None)
        if totaux is None:
            from .domain.argent import Vue, totaux as _chaine
            totaux = _chaine(obj.devis, vue=Vue.NET)
            obj._aud115_totaux = totaux
        return totaux

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_total_ht(self, obj):
        totaux = self._totaux(obj)
        return str(totaux.ht_net) if totaux is not None else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_total_tva(self, obj):
        totaux = self._totaux(obj)
        return str(totaux.tva) if totaux is not None else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_total_ttc(self, obj):
        totaux = self._totaux(obj)
        return str(totaux.ttc) if totaux is not None else None
