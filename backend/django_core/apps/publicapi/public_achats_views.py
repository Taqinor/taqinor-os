"""NTP2P39 — objets Procure-to-Pay LISIBLES par clé d'API (scope
``lecture_achats``).

Deux ressources en LECTURE SEULE, sur la base commune
``public_views.PublicReadOnlyViewSet`` (auth par clé, société TOUJOURS prise sur
la clé, throttle par clé, filtres en liste blanche, ``?updated_since=``) — aucun
nouveau mécanisme d'accès. L'usage visé est l'intégration d'un donneur d'ordre
ou d'un outil d'achat tiers qui suit l'avancement des réquisitions sans entrer
dans l'ERP.

CE QUI N'EST JAMAIS EXPOSÉ — et pourquoi, ligne par ligne :

* les LIGNES d'une demande d'achat. ``DemandeAchatLigne.prix_estime``
  est un prix d'ACHAT interne (règle transverse du dépôt : aucun prix d'achat
  client-facing). Sans les lignes, ``montant_estime`` — le seul agrégat que le
  plan demande d'exposer — ne permet de reconstituer AUCUN prix unitaire :
  ni la quantité ni le nombre de lignes ne sortent.
* le MONTANT d'une offre fournisseur. ``RFQOffre.montant_ht`` est documenté
  « Montants INTERNES » dans son propre modèle : c'est ce qu'un fournisseur nous
  facturerait, donc exactement le prix d'achat que la règle transverse interdit.
  L'offre retenue est donc exposée par son IDENTITÉ (qui, en combien de jours),
  jamais par son prix — c'est l'information dont un donneur d'ordre a besoin
  (« l'adjudication est faite, chez qui ») sans que notre coût d'achat sorte.
* le ``token`` d'une ``RFQConsultation``. C'est un JETON PUBLIC qui ouvre la
  page de réponse SANS LOGIN (XPUR21) : le publier reviendrait à laisser
  n'importe quel porteur de clé répondre à la place d'un fournisseur.
* ``fournisseur_suggere`` sur une demande d'achat : un arbitrage de sourcing
  interne, hors du périmètre demandé.
"""
from rest_framework import serializers

from apps.installations.models_demande_achat import DemandeAchat
from apps.installations.models_rfq import RFQ

from .constants import SCOPE_READ_ACHATS
from .public_views import PublicReadOnlyViewSet


class PublicDemandeAchatSerializer(serializers.ModelSerializer):
    """FG310 — réquisition d'achat : où elle en est, pour combien.

    ``montant_estime`` est la property INTERNE Σ(quantité × prix estimé) de
    l'app cible : un ORDRE DE GRANDEUR d'engagement, le seul chiffre que
    NTP2P39 demande d'exposer. Les lignes qui le composent restent absentes
    (voir la docstring du module)."""
    chantier = serializers.PrimaryKeyRelatedField(read_only=True)
    programme = serializers.PrimaryKeyRelatedField(read_only=True)
    montant_estime = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = DemandeAchat
        fields = [
            'id', 'reference', 'objet', 'statut', 'priorite', 'date_besoin',
            'chantier', 'programme', 'montant_estime',
            'date_creation', 'date_modification',
        ]
        read_only_fields = fields


class PublicRFQSerializer(serializers.ModelSerializer):
    """FG311 — demande de prix : où elle en est, qui a été consulté, qui a été
    retenu. Jamais un montant d'offre (voir la docstring du module)."""
    demande = serializers.PrimaryKeyRelatedField(read_only=True)
    fournisseurs_consultes = serializers.SerializerMethodField()
    offre_retenue = serializers.SerializerMethodField()

    class Meta:
        model = RFQ
        fields = [
            'id', 'reference', 'objet', 'statut', 'date_limite_reponse',
            'demande', 'fournisseurs_consultes', 'offre_retenue',
            'date_creation', 'date_modification',
        ]
        read_only_fields = fields

    def get_fournisseurs_consultes(self, obj):
        """Fournisseurs INVITÉS à répondre (``RFQConsultation``), et s'ils ont
        répondu. Le ``token`` de consultation n'est JAMAIS servi : il ouvre la
        page de réponse sans login."""
        return [
            {
                'fournisseur': consultation.fournisseur_id,
                'nom': getattr(consultation.fournisseur, 'nom', '') or '',
                'a_repondu': consultation.a_repondu,
                'revoque': consultation.revoque,
            }
            for consultation in obj.consultations.select_related(
                'fournisseur').all()
        ]

    def get_offre_retenue(self, obj):
        """L'offre choisie, par son IDENTITÉ seule — jamais son ``montant_ht``
        (le prix d'achat que la règle transverse interdit d'exposer).
        ``None`` tant qu'aucune adjudication n'a eu lieu."""
        offre = obj.offres.select_related('fournisseur').filter(
            retenue=True).first()
        if offre is None:
            return None
        return {
            'id': offre.id,
            'fournisseur': offre.fournisseur_id,
            'nom': (getattr(offre.fournisseur, 'nom', '')
                    or offre.fournisseur_nom_libre or ''),
            'delai_jours': offre.delai_jours,
        }


class PublicDemandeAchatViewSet(PublicReadOnlyViewSet):
    """FG310 — demandes d'achat de la société de la clé, lecture seule."""
    required_scope = SCOPE_READ_ACHATS
    serializer_class = PublicDemandeAchatSerializer
    # `prefetch_related('lignes')` : `montant_estime` somme les lignes — sans
    # lui, une page de 50 demandes coûterait 50 requêtes de plus (les lignes ne
    # sont PAS exposées, seule leur somme l'est).
    queryset = DemandeAchat.objects.select_related(
        'chantier', 'programme').prefetch_related('lignes').order_by('-id')
    filter_whitelist = ('statut', 'priorite', 'chantier', 'programme',
                        'reference')
    ordering_fields = ('date_creation', 'date_modification', 'id')
    sync_field = 'date_modification'


class PublicRFQViewSet(PublicReadOnlyViewSet):
    """FG311 — demandes de prix de la société de la clé, lecture seule."""
    required_scope = SCOPE_READ_ACHATS
    serializer_class = PublicRFQSerializer
    queryset = RFQ.objects.select_related('demande').prefetch_related(
        'consultations__fournisseur', 'offres__fournisseur').order_by('-id')
    filter_whitelist = ('statut', 'demande', 'reference')
    ordering_fields = ('date_creation', 'date_modification', 'id')
    sync_field = 'date_modification'
