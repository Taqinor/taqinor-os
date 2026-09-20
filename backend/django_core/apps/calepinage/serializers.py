"""Sérialiseurs du module « calepinage » — CAL16.

RAPPEL multi-tenant : ``company`` n'est JAMAIS exposée en écriture — elle est
toujours forcée côté serveur (``CompanyScopedModelViewSet.perform_create``).
Un ``company`` envoyé dans le corps est donc ignoré, pas « refusé » : il
n'existe simplement pas pour ce sérialiseur.

LE RATTACHEMENT EST UN « OU EXCLUSIF » PORTÉ ET NOMMÉ
-----------------------------------------------------
La base garantit déjà qu'un calepinage a un lead OU un client
(``CheckConstraint`` ``calepinage_lead_ou_client``), mais une contrainte de
base rend une ``IntegrityError`` — un « non enregistré » générique côté écran.
Le sérialiseur refuse donc AVANT, en français, en NOMMANT le champ fautif
(règle fondateur « erreurs → le champ fautif »). Les deux à la fois sont
refusés aussi : un calepinage rattaché à un lead ET à un client d'un autre
dossier serait retrouvé depuis deux fiches qui ne parlent pas du même client.

Les lectures cross-app passent par les ``selectors.py`` des apps cibles
(``apps.crm.selectors``) — jamais un import de leurs modèles.
"""
from __future__ import annotations

from rest_framework import serializers

from core.mixins import SameCompanyFKSerializerMixin

from .models import Calepinage, CalepinageVariante


class CalepinageSerializer(SameCompanyFKSerializerMixin,
                           serializers.ModelSerializer):
    """Le calepinage en liste et en écriture (le DÉTAIL agrégé est CAL17).

    ``lead`` est un identifiant OPAQUE (``PositiveIntegerField``) : il est
    exposé sous le nom ``lead`` côté API — celui que l'écran emploie — et
    VALIDÉ contre ``apps.crm.selectors.get_company_lead`` pour qu'un lead
    d'une autre société soit refusé comme « introuvable » (jamais un 403 qui
    confirmerait son existence).
    """

    lead = serializers.IntegerField(source='lead_id', required=False,
                                    allow_null=True)
    appel_offre = serializers.IntegerField(source='appel_offre_id',
                                           required=False, allow_null=True)
    statut_libelle = serializers.CharField(source='get_statut_display',
                                           read_only=True)

    #: AUD601 — une FK cross-app ne pointe jamais la ligne d'une autre société.
    same_company_fields = ('client', 'devis')

    class Meta:
        model = Calepinage
        fields = [
            'id', 'titre', 'statut', 'statut_libelle',
            'lead', 'client', 'devis', 'appel_offre',
            'layout_hash', 'roof_image', 'version_moteur',
            'cree_par', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'layout_hash', 'roof_image', 'version_moteur', 'cree_par',
            'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        """Lead XOR client, et un lead qui existe VRAIMENT dans la société."""
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        lead_id = attrs.get('lead_id', getattr(instance, 'lead_id', None))
        client = attrs.get('client', getattr(instance, 'client', None))

        if lead_id and client is not None:
            raise serializers.ValidationError({
                'client': (
                    "Un calepinage se rattache à un lead OU à un client, pas "
                    "aux deux : laissez « Client » vide, ou retirez le lead."
                ),
            })
        if not lead_id and client is None:
            raise serializers.ValidationError({
                'client': (
                    "Rattachez ce calepinage à un lead ou à un client : "
                    "renseignez « Client » ou « Lead »."
                ),
            })
        if lead_id and 'lead_id' in attrs:
            self._exiger_lead_de_la_societe(lead_id)
        return attrs

    def _exiger_lead_de_la_societe(self, lead_id):
        """Un lead d'une AUTRE société est « introuvable », jamais « interdit ».

        Lecture cross-app par le sélecteur crm uniquement : ce module
        n'importe jamais ``apps.crm.models``.
        """
        from apps.crm.selectors import get_company_lead

        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return
        if get_company_lead(company, lead_id) is None:
            raise serializers.ValidationError({
                'lead': f"Lead introuvable (#{lead_id}).",
            })


class CalepinageVarianteSerializer(serializers.ModelSerializer):
    """CAL21 — une variante en lecture et en écriture, SAUF ``retenue``.

    ``retenue`` est en LECTURE SEULE ici : elle n'a qu'un seul chemin
    d'écriture (``services.variantes.retenir_variante``, bascule atomique
    gardée par ``garde_retenue``). Un sérialiseur qui l'écrirait ouvrirait la
    seconde porte par laquelle on se retrouve avec deux retenues, ou zéro.
    """

    class Meta:
        model = CalepinageVariante
        fields = ['id', 'nom', 'roof_layout', 'resultat', 'retenue',
                  'layout_hash', 'cree_par', 'created_at', 'updated_at']
        read_only_fields = ['retenue', 'layout_hash', 'cree_par',
                            'created_at', 'updated_at']
