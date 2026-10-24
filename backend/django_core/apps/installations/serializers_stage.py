"""CH5 — Sérialiseur de configuration des étapes/gates de chantier (StageModele).

Édition réservée au Directeur (cf. la vue). Le sérialiseur expose l'ordre, le
drapeau bloquant, les exigences (`exige_*`) et le statut hérité mappé ; `cle`
et `protege` sont posés/verrouillés côté serveur pour les étapes système.
"""
from decimal import Decimal

from rest_framework import serializers

from core.champs_stricts import ChampsStrictsMixin
from core.conflit_etat import ConflitEtat
from core.unicite import ConflitUnicite

from .models import StageModele


def valider_unicite_societe(serializer, champ, valeur, message, **portee):
    """ACHT76 — unicité PAR SOCIÉTÉ d'un champ de référentiel (clé, type, nom)
    avant l'écriture : 409 (conflit) en français sous le champ au lieu d'un 500
    (``IntegrityError`` — la société, posée côté serveur, n'est pas parmi les
    champs du sérialiseur, donc DRF ne génère aucun ``UniqueTogetherValidator``).
    Un PATCH qui garde sa propre valeur reste accepté (instance exclue)."""
    request = serializer.context.get('request')
    company = getattr(getattr(request, 'user', None), 'company', None)
    if company is None:
        return valeur
    qs = serializer.Meta.model.objects.filter(
        company=company, **{champ: valeur}, **portee)
    if serializer.instance is not None:
        qs = qs.exclude(pk=serializer.instance.pk)
    if qs.exists():
        # ERR-ENF11 : doublon = CONFLIT (409 unique_conflict), corps toujours
        # rangé sous le champ comme l'était le 400.
        raise ConflitUnicite({champ: [message]}, champs=[champ])
    return valeur


def refus_protege(champ, message):
    """ERR-ENF11 — modifier la clé/le type d'un élément PROTÉGÉ est refusé par
    l'ÉTAT de l'élément (409), corps rangé sous le champ comme le 400 d'avant."""
    return ConflitEtat({champ: [message]})


class StageModeleSerializer(ChampsStrictsMixin, serializers.ModelSerializer):
    statut_legacy_display = serializers.CharField(
        source='get_statut_legacy_display', read_only=True, default=None, allow_null=True)

    class Meta:
        model = StageModele
        fields = [
            'id', 'cle', 'libelle', 'ordre', 'bloquant',
            'exige_checklist', 'exige_photos', 'exige_series', 'exige_tests',
            'exige_materiel', 'exige_dossier', 'exige_pack',
            # CIQ623 — documents de sécurité chantier.
            'exige_hse',
            # CHT23 — exigences de comptage configurables (additif, défauts =
            # comportement historique octet pour octet).
            'photos_min', 'checklist_pct_min',
            'statut_legacy', 'statut_legacy_display', 'actif', 'protege',
        ]
        # `protege` est un verrou système : jamais modifiable via l'API.
        read_only_fields = ['protege']

    def validate_cle(self, value):
        # La clé d'une étape SYSTÈME (protégée) est stable — on ne la renomme
        # pas (elle porte le mapping des effets de bord). Les étapes créées par
        # le Directeur gardent leur clé libre.
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise refus_protege('cle', "La clé d'une étape système ne peut pas être modifiée.")
        return valider_unicite_societe(
            self, 'cle', value, "Cette clé d'étape existe déjà.")


class CautionTotaleMixin:
    """C20 — ``validate`` de ``MaterielConsigneSerializer`` (extrait de ``serializers.py``)."""

    def validate(self, attrs):
        # ENF11 nocturne - caution_totale (= unitaire x quantite) est servie
        # en DecimalField(12, 2) : un produit >= 10**10 faisait lever
        # InvalidOperation a la serialisation (500 sur POST puis sur toute la
        # liste). On le refuse a l'ecriture, en nommant le champ.
        quantite = attrs.get('quantite', getattr(self.instance, 'quantite', 0))
        caution = attrs.get(
            'caution_unitaire', getattr(self.instance, 'caution_unitaire', 0))
        if abs((quantite or 0) * Decimal(caution or 0)) >= Decimal(10) ** 10:
            champ = ('caution_unitaire' if 'caution_unitaire' in attrs
                     else 'quantite')
            # Regle d'ENSEMBLE (produit des deux champs) que le schema ne peut
            # pas exprimer : 409, jamais un 400 sur une requete conforme.
            raise ConflitEtat(
                {champ: ['Caution totale trop elevee '
                         '(quantite x caution unitaire).']})
        return attrs
