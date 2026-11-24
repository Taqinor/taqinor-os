"""Sérialiseurs du dossier contractuel : corps reçus (validés) et formes
servies (déclarées au schéma OpenAPI, telles que contract_samples/*.json).

Les formes servies sont construites par ``contrats/selectors.py`` ; ces
classes les DÉCRIVENT (schéma, fuzz de la CI). Le ``contenu`` d'un acte est un
objet dont la forme dépend du type d'acte : voir acte_contractuel.json.
"""
from rest_framework import serializers

from .contrats import types as T


class ErreurActeSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()


class ChantierDossierSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference = serializers.CharField()
    annule = serializers.BooleanField()
    devis_id = serializers.IntegerField(allow_null=True)
    devis_reference = serializers.CharField(allow_blank=True)


class ProchaineActionSerializer(serializers.Serializer):
    acte_id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=T.TYPES)
    libelle = serializers.CharField()


class ResumeActeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=T.TYPES)
    variante = serializers.CharField(allow_blank=True)
    rang = serializers.IntegerField()
    titre = serializers.CharField()
    reference = serializers.CharField()
    statut = serializers.ChoiceField(
        choices=(T.BROUILLON, T.EMIS, T.SIGNE, T.ANNULE))
    version = serializers.IntegerField()
    personnalise = serializers.BooleanField()
    ecarte = serializers.BooleanField()
    emis_le = serializers.DateTimeField(allow_null=True)
    signe_le = serializers.DateTimeField(allow_null=True)
    signataire_nom = serializers.CharField(allow_blank=True)
    mode_signature = serializers.CharField(allow_blank=True)
    avertissements = serializers.ListField(child=serializers.CharField())
    peut_modifier = serializers.BooleanField()
    peut_emettre = serializers.BooleanField()
    peut_signer = serializers.BooleanField()
    peut_rouvrir = serializers.BooleanField()
    document_ged_id = serializers.IntegerField(allow_null=True)


class DossierContractuelSerializer(serializers.Serializer):
    chantier = ChantierDossierSerializer()
    client = serializers.CharField(allow_blank=True)
    prix_ttc = serializers.CharField(allow_null=True)
    regle_ttc = serializers.CharField(allow_null=True)
    reste_ttc = serializers.CharField(allow_null=True)
    prochaine_action = ProchaineActionSerializer(allow_null=True)
    actes = ResumeActeSerializer(many=True)


class ChantierActeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference = serializers.CharField()


class ContenuActeSerializer(serializers.Serializer):
    """Les clés communes du contenu ; les sections propres à chaque type
    d'acte (échéancier, articles, garanties, constats…) suivent
    acte_contractuel.json."""
    schema = serializers.IntegerField()
    langue = serializers.ChoiceField(choices=T.LANGUES)
    version = serializers.IntegerField()
    titre = serializers.CharField(allow_blank=True)
    lieu = serializers.CharField(allow_blank=True)
    date_document = serializers.DateField(allow_null=True)
    societe = serializers.DictField()
    client = serializers.DictField()
    chantier = serializers.DictField()
    systeme = serializers.DictField()
    prix = serializers.DictField()
    conditions_particulieres = serializers.CharField(allow_blank=True)
    signatures = serializers.DictField()
    options = serializers.DictField()
    type = serializers.ChoiceField(choices=T.TYPES)
    variante = serializers.CharField(allow_blank=True)
    reference = serializers.CharField()
    echeancier = serializers.ListField(child=serializers.DictField())
    articles = serializers.ListField(child=serializers.DictField())


class DetailActeSerializer(ResumeActeSerializer):
    chantier = ChantierActeSerializer()
    langue = serializers.ChoiceField(choices=T.LANGUES)
    langues = serializers.ListField(child=serializers.CharField())
    sections_personnalisees = serializers.ListField(
        child=serializers.CharField())
    sections_modifiables = serializers.ListField(
        child=serializers.CharField())
    contenu = ContenuActeSerializer()


class ModeleActeReponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


# ── Corps reçus ─────────────────────────────────────────────────────────────

class CorpsPatchSerializer(serializers.Serializer):
    """``{langue, surcharges}`` : chaque section remplace la sienne, ``null``
    la remet au défaut (sections : ``sections_modifiables`` du détail)."""
    langue = serializers.ChoiceField(choices=T.LANGUES, required=False,
                                     default=T.LANGUE_DEFAUT)
    surcharges = serializers.DictField(child=serializers.JSONField(
        allow_null=True))


class CorpsSignerSerializer(serializers.Serializer):
    signature_client = serializers.CharField(max_length=3_000_000)
    signataire_nom = serializers.CharField(max_length=150)
    lieu = serializers.CharField(max_length=120, required=False,
                                 allow_blank=True, default='')


class CorpsMarquerSigneSerializer(serializers.Serializer):
    signataire_nom = serializers.CharField(max_length=150)
    signe_le = serializers.DateField(required=False, allow_null=True)
