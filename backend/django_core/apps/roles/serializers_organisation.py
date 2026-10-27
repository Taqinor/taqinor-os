"""Organigramme (fondateur, 27/10/2026) — sérialiseurs des départements, des
fonctions (postes) et des équipes génériques. Société posée côté serveur
(jamais lue du corps) ; toute FK écrite est bornée à la société (AUD601)."""
from rest_framework import serializers

from core.champs_stricts import (
    ChampsStrictsEntiersMixin, IdInconnu404Mixin)
from core.conflit_etat import ConflitEtat
from core.mixins import SameCompanyFKSerializerMixin
from core.unicite import ConflitUnicite

from .models import Departement, EquipeOrg, Poste


def _nom(user):
    if user is None:
        return None
    return (user.get_full_name() or '').strip() or user.username


def _unique_societe(serializer, champ, valeur, message):
    """Unicité (société, champ) AVANT l'écriture : 409 sous le champ au lieu
    d'un 500 (la société, posée côté serveur, n'est pas un champ du
    sérialiseur : DRF ne génère aucun ``UniqueTogetherValidator``)."""
    request = serializer.context.get('request')
    company = getattr(getattr(request, 'user', None), 'company', None)
    if company is None:
        return valeur
    qs = serializer.Meta.model.objects.filter(company=company, **{champ: valeur})
    if serializer.instance is not None:
        qs = qs.exclude(pk=serializer.instance.pk)
    if qs.exists():
        raise ConflitUnicite({champ: [message]}, champs=[champ])
    return valeur


class DepartementSerializer(IdInconnu404Mixin, SameCompanyFKSerializerMixin,
                            ChampsStrictsEntiersMixin,
                            serializers.ModelSerializer):
    same_company_fields = ('responsable',)
    responsable_nom = serializers.SerializerMethodField()

    class Meta:
        model = Departement
        fields = ['id', 'nom', 'responsable', 'responsable_nom',
                  'est_direction', 'ordre', 'actif']

    def get_responsable_nom(self, obj) -> str | None:
        return _nom(obj.responsable)

    def validate_nom(self, value):
        return _unique_societe(
            self, 'nom', value, 'Un département porte déjà ce nom.')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inst = self.instance
        direction = attrs.get(
            'est_direction', inst.est_direction if inst else False)
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if direction and company is not None:
            autres = Departement.objects.filter(
                company=company, est_direction=True)
            if inst is not None:
                autres = autres.exclude(pk=inst.pk)
            if autres.exists():
                # ENF11 — refus d'ÉTAT (le corps est conforme) : 409.
                raise ConflitEtat({'est_direction': [
                    'La société a déjà un département Direction.']})
        return attrs


class PosteSerializer(IdInconnu404Mixin, SameCompanyFKSerializerMixin,
                      ChampsStrictsEntiersMixin, serializers.ModelSerializer):
    same_company_fields = ('departement', 'role')
    departement_nom = serializers.CharField(
        source='departement.nom', read_only=True, allow_null=True)
    role_nom = serializers.CharField(
        source='role.nom', read_only=True, allow_null=True)
    nb_titulaires = serializers.IntegerField(
        source='titulaires.count', read_only=True)

    class Meta:
        model = Poste
        fields = ['id', 'intitule', 'departement', 'departement_nom',
                  'role', 'role_nom', 'actif', 'nb_titulaires']

    def validate_intitule(self, value):
        return _unique_societe(
            self, 'intitule', value, 'Une fonction porte déjà cet intitulé.')


class EquipeOrgSerializer(IdInconnu404Mixin, SameCompanyFKSerializerMixin,
                          ChampsStrictsEntiersMixin,
                          serializers.ModelSerializer):
    same_company_fields = ('departement', 'chef', 'membres')
    departement_nom = serializers.CharField(
        source='departement.nom', read_only=True, allow_null=True)
    chef_nom = serializers.SerializerMethodField()
    nb_membres = serializers.IntegerField(source='membres.count', read_only=True)

    class Meta:
        model = EquipeOrg
        fields = ['id', 'nom', 'departement', 'departement_nom', 'chef',
                  'chef_nom', 'membres', 'nb_membres', 'actif',
                  'date_creation']
        read_only_fields = ['date_creation']

    def get_chef_nom(self, obj) -> str | None:
        return _nom(obj.chef)

    def validate_nom(self, value):
        return _unique_societe(
            self, 'nom', value, 'Une équipe porte déjà ce nom.')

    def to_internal_value(self, data):
        # ``membres`` = ``{}`` passerait pour une liste vide (le
        # ``ManyRelatedField`` accepte tout itérable) : 400 nommé.
        if (hasattr(data, 'get') and data.get('membres') is not None
                and not isinstance(data.get('membres'), list)):
            raise serializers.ValidationError(
                {'membres': "Une liste d'identifiants est attendue."})
        return super().to_internal_value(data)
