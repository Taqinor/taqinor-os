"""Serializers du module Portail client (``apps.portail``).

SOLMVP16 — le corps de ces serializers vivait encore, par ré-export
transitoire ODX12, dans le module compta (interleavé avec les serializers
comptables) ; il est désormais relogé ICI, seul point d'accès stable pour les
ViewSets portail et les routes ``/api/django/portail/…``.

``DocumentClientPortailSerializer`` ne dépose plus de miroir GED (module
sorti du produit, WIR94 retiré) : le champ ``document_ged``/``lien_ged`` a
disparu, le document déposé reste servi tel quel depuis son stockage MinIO
natif (``fichier_key`` via ``records.storage``).
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.records.storage import AttachmentSerializerMixin

from .models import (
    AcceptationDevisPortail,
    ComptePortailClient,
    DemandeTicketPortail,
    DocumentClientPortail,
    JalonChantierPortail,
    PaiementFacturePortail,
)

# ── AUD142 — Résolution cross-app des id envoyés par le portail ────────────
#
# ``devis_id``, ``facture_id``, ``client_id``, ``lead_id`` et ``chantier_id``
# étaient de simples ``IntegerField(min_value=0)`` — aucun ``validate_*``,
# aucun queryset borné. Chaque id est résolu par le SELECTOR de l'app cible,
# borné à la société de l'appelant (jamais un import de ses ``models`` —
# frontière cross-app CLAUDE.md).


def _valider_id_cross_app(serializer, valeur, resolveur, libelle):
    """Résout ``valeur`` dans la société de l'appelant, ou lève une 400 FR.

    ``None``/vide/0 traversent (champs optionnels). Hors contexte API (aucune
    ``request`` : usage programmatique interne), on ne bloque pas — la porte
    réellement exposée est le ViewSet, et un service interne a déjà résolu ses
    objets.
    """
    if valeur in (None, '', 0):
        return valeur
    request = serializer.context.get('request')
    if request is None:
        return valeur
    company = getattr(getattr(request, 'user', None), 'company', None)
    if company is None or resolveur(company, valeur) is None:
        raise serializers.ValidationError(
            f'{libelle} inconnu(e) pour cette société.')
    return valeur


def _resoudre_client(company, client_id):
    from apps.crm.selectors import get_company_client
    return get_company_client(company, client_id)


def _resoudre_lead(company, lead_id):
    from apps.crm.selectors import get_company_lead
    return get_company_lead(company, lead_id)


def _resoudre_facture(company, facture_id):
    from apps.ventes.selectors import get_facture_scoped
    return get_facture_scoped(company, facture_id)


def _resoudre_devis(company, devis_id):
    # ``apps.ventes.selectors`` n'expose pas (encore) de résolveur de devis
    # scopé société : on réutilise son point d'entrée par pk et on borne ici,
    # plutôt que d'ajouter une fonction dans une app qui ne nous appartient
    # pas.
    from apps.ventes.selectors import get_devis_by_pk
    devis = get_devis_by_pk(devis_id)
    if devis is None:
        return None
    return devis if devis.company_id == getattr(company, 'id', None) else None


def _resoudre_chantier(company, chantier_id):
    from apps.installations.selectors import installation_scoped
    return installation_scoped(company, chantier_id)


# ── FG228 — Comptes portail client ─────────────────────────────────────────

class ComptePortailClientSerializer(serializers.ModelSerializer):
    # DC32 — l'email est lu depuis le client (source unique), jamais stocké.
    email = serializers.EmailField(source='client.email', read_only=True)
    # AUD141 — le jeton n'est PLUS servi en clair. Il authentifie à lui seul le
    # relevé de compte, son PDF, la contestation de facture et les vues
    # publiques contrats : un export CSV de cette liste, envoyé par email ou
    # déposé sur un partage, donnait un accès permanent aux relevés financiers
    # de TOUS les clients de la société. La liste ne porte donc qu'un aperçu
    # non réutilisable ; le lien complet ne s'obtient que par l'action dédiée
    # et tracée ``lien-acces``, et ``regenerer-jeton`` invalide l'ancien.
    token_apercu = serializers.SerializerMethodField()

    class Meta:
        model = ComptePortailClient
        fields = [
            'id', 'client', 'email', 'token_apercu', 'actif',
            'derniere_connexion', 'date_creation',
        ]
        read_only_fields = [
            'token_apercu', 'derniere_connexion', 'date_creation',
        ]

    @extend_schema_field(serializers.CharField())
    def get_token_apercu(self, obj):
        """4 derniers caractères du jeton — assez pour l'identifier dans une
        liste, jamais assez pour s'en servir."""
        token = getattr(obj, 'token_acces', '') or ''
        return f'••••{token[-4:]}' if token else ''


class AcceptationDevisPortailSerializer(serializers.ModelSerializer):
    # WIR95 — ``devis_id`` n'est plus un champ modèle littéral (c'est
    # désormais l'attname de la FK ``devis``) : DRF ``ModelSerializer`` ne le
    # résout pas automatiquement depuis une string dans ``Meta.fields``, donc
    # on le déclare explicitement (même format JSON qu'avant — aucun
    # changement d'API). Lecture/écriture via l'attname reste supportée par
    # Django (``obj.devis_id``, ``.filter(devis_id=…)``, ``.create(devis_id=…)``).
    devis_id = serializers.IntegerField(min_value=0)

    class Meta:
        model = AcceptationDevisPortail
        fields = [
            'id', 'devis_id', 'option_choisie', 'nom_signataire',
            'signature_ip', 'accepte', 'signe_le', 'date_creation',
        ]
        read_only_fields = [
            'signature_ip', 'accepte', 'signe_le', 'date_creation',
        ]

    def validate_devis_id(self, value):
        """AUD142 — le devis DOIT appartenir à la société de l'appelant."""
        return _valider_id_cross_app(self, value, _resoudre_devis, 'Devis')


class PaiementFacturePortailSerializer(serializers.ModelSerializer):
    # WIR95 — voir ``AcceptationDevisPortailSerializer.devis_id`` ci-dessus.
    facture_id = serializers.IntegerField(min_value=0)

    class Meta:
        model = PaiementFacturePortail
        fields = [
            'id', 'facture_id', 'montant', 'methode', 'statut', 'reference',
            'paye_le', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'reference', 'paye_le', 'date_creation',
        ]

    def validate_facture_id(self, value):
        """AUD142 — la facture DOIT appartenir à la société de l'appelant."""
        return _valider_id_cross_app(
            self, value, _resoudre_facture, 'Facture')


class DocumentClientPortailSerializer(AttachmentSerializerMixin,
                                      serializers.ModelSerializer):
    # AUD835 — l'upload part dans MinIO (``records.storage``) au lieu du
    # ``FileField`` irrécupérable. Le champ reste ÉCRIVABLE et jamais rendu :
    # on n'expose toujours aucune URL brute.
    attachment_fields = ('fichier',)

    # WIR95 — voir ``AcceptationDevisPortailSerializer.devis_id`` ci-dessus.
    client_id = serializers.IntegerField(min_value=0)
    lead_id = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    # AUD148 (b) — le ``FileField`` était sérialisé tel quel et rendu en lien
    # DIRECT par l'écran, alors que ``settings/base.py`` ne définit NI
    # ``MEDIA_URL`` NI ``MEDIA_ROOT`` (seules des constantes MinIO), qu'aucune
    # route ne sert ``/media/`` et que ``frontend/nginx.conf`` n'a aucune
    # ``location /media/`` : le lien était mort par construction. Le champ
    # reste ÉCRIVABLE mais n'est plus RENDU — on n'expose jamais une URL de
    # média statique.
    fichier = serializers.FileField(
        write_only=True, required=False, allow_null=True)
    fichier_present = serializers.SerializerMethodField()

    class Meta:
        model = DocumentClientPortail
        fields = [
            'id', 'client_id', 'lead_id', 'type_document', 'libelle',
            'fichier', 'fichier_present', 'traite', 'date_depot',
        ]
        read_only_fields = [
            'fichier_present', 'traite', 'date_depot',
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_fichier_present(self, obj):
        """Y a-t-il un binaire déposé ? (sans jamais publier son URL brute)

        AUD835 — une clé MinIO compte autant que l'ancien ``FileField`` : un
        document déposé après la bascule n'a plus que la clé.
        """
        return bool(getattr(obj, 'fichier_key', '')
                    or getattr(obj, 'fichier', None))

    def validate_client_id(self, value):
        """AUD142 — le client DOIT appartenir à la société de l'appelant."""
        return _valider_id_cross_app(self, value, _resoudre_client, 'Client')

    def validate_lead_id(self, value):
        """AUD142 — le lead DOIT appartenir à la société de l'appelant."""
        return _valider_id_cross_app(self, value, _resoudre_lead, 'Lead')


class JalonChantierPortailSerializer(serializers.ModelSerializer):
    # WIR95 — voir ``AcceptationDevisPortailSerializer.devis_id`` ci-dessus.
    chantier_id = serializers.IntegerField(min_value=0)

    class Meta:
        model = JalonChantierPortail
        fields = [
            'id', 'chantier_id', 'libelle', 'ordre', 'atteint', 'date_jalon',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_chantier_id(self, value):
        """AUD142 — le chantier DOIT appartenir à la société de l'appelant."""
        return _valider_id_cross_app(
            self, value, _resoudre_chantier, 'Chantier')


class DemandeTicketPortailSerializer(serializers.ModelSerializer):
    # WIR95 — voir ``AcceptationDevisPortailSerializer.devis_id`` ci-dessus.
    client_id = serializers.IntegerField(min_value=0)
    chantier_id = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    ticket_id = serializers.IntegerField(
        min_value=0, required=False, allow_null=True, read_only=True)

    class Meta:
        model = DemandeTicketPortail
        fields = [
            'id', 'client_id', 'chantier_id', 'sujet', 'description',
            'statut', 'ticket_id', 'date_creation',
        ]
        read_only_fields = ['statut', 'date_creation']

    def validate_client_id(self, value):
        """AUD142 — le client DOIT appartenir à la société de l'appelant."""
        return _valider_id_cross_app(self, value, _resoudre_client, 'Client')

    def validate_chantier_id(self, value):
        """AUD142 — le chantier DOIT appartenir à la société de l'appelant."""
        return _valider_id_cross_app(
            self, value, _resoudre_chantier, 'Chantier')
