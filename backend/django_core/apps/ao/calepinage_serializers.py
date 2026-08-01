"""AOF61/AOF62 — sérialiseurs de l'API de calepinage.

Ces sérialiseurs ne portent AUCUNE règle métier : ils valident la FORME d'une
demande et nomment le champ fautif. Un payload invalide doit produire un 400
qui dit LEQUEL des champs est en cause — « 400 Bad Request » nu oblige à
deviner, et c'est ce qui transforme une erreur de saisie en ticket.

``company`` n'apparaît dans AUCUN champ d'entrée : elle est toujours résolue
côté serveur depuis ``request.user.company`` (règle multi-tenant du dépôt).
"""
from __future__ import annotations

from rest_framework import serializers

__all__ = [
    'DemandeCalepinageSerializer', 'DemandeJobCalepinageSerializer',
    'ResultatCalepinageSerializer', 'JobCalepinageSerializer',
    'ComparaisonVariantesSerializer', 'PreuveCalepinageSerializer',
]


class DemandeCalepinageSerializer(serializers.Serializer):
    """Une demande de calcul : PAR TOITURE, ou par document d'entrée brut.

    Les deux portes existent parce qu'elles servent deux usages réels :
    ``toiture`` est le chemin produit (l'atelier recalcule la toiture ouverte)
    ; ``entree`` est le chemin expert (rejouer un document du contrat AOF57
    tel quel, par exemple un golden). Elles s'excluent : accepter les deux à
    la fois obligerait à choisir en silence laquelle gagne.
    """

    toiture = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="Identifiant de la toiture à calepiner.")
    params = serializers.JSONField(
        required=False,
        help_text="Paramètres de calepinage (défaut : ceux de la toiture).")
    entree = serializers.JSONField(
        required=False,
        help_text="Document d'entrée du contrat de calepinage (mode expert).")

    def validate(self, attrs):
        toiture = attrs.get('toiture')
        entree = attrs.get('entree')
        if toiture is None and entree is None:
            raise serializers.ValidationError({'toiture': (
                "Indiquez une toiture à calepiner, ou fournissez un document "
                "d'entrée complet dans « entree »."
            )})
        if toiture is not None and entree is not None:
            raise serializers.ValidationError({'entree': (
                "« toiture » et « entree » s'excluent : fournissez l'un OU "
                "l'autre, jamais les deux."
            )})
        if entree is not None and not isinstance(entree, dict):
            raise serializers.ValidationError({'entree': (
                "Le document d'entrée doit être un objet JSON."
            )})
        if attrs.get('params') is not None and \
                not isinstance(attrs['params'], dict):
            raise serializers.ValidationError({'params': (
                "Les paramètres de calepinage doivent être un objet JSON."
            )})
        return attrs


class DemandeJobCalepinageSerializer(DemandeCalepinageSerializer):
    """Même demande, lancée en TÂCHE DE FOND (``core.jobs``)."""

    persister = serializers.BooleanField(
        default=False,
        help_text="Écrire le résultat dans une variante de calepinage.")
    nom = serializers.CharField(required=False, allow_blank=True,
                                max_length=255)
    role = serializers.CharField(required=False, allow_blank=True,
                                 max_length=12)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('persister') and attrs.get('toiture') is None:
            raise serializers.ValidationError({'persister': (
                "Persister un résultat exige une toiture : un document brut "
                "n'appartient à aucune toiture."
            )})
        return attrs


class PreuveCalepinageSerializer(serializers.Serializer):
    """La PREUVE publiée — vocabulaire verrouillé d'AOF44."""

    total_retenu = serializers.IntegerField(read_only=True)
    total_optimal = serializers.IntegerField(read_only=True, allow_null=True)
    methode = serializers.CharField(read_only=True)
    methode_exacte = serializers.BooleanField(read_only=True)
    optimal = serializers.BooleanField(read_only=True)
    libelle = serializers.CharField(read_only=True)
    pas_cm = serializers.FloatField(read_only=True)
    nb_optima = serializers.IntegerField(read_only=True, allow_null=True)
    borne_superieure = serializers.IntegerField(read_only=True,
                                                allow_null=True)
    marge_troncon_min = serializers.FloatField(read_only=True,
                                               allow_null=True)
    marge_bande_min = serializers.FloatField(read_only=True, allow_null=True)
    rangee_critique = serializers.CharField(read_only=True)
    obstacle_critique = serializers.CharField(read_only=True)
    controles = serializers.ListField(child=serializers.CharField(),
                                      read_only=True)
    version_moteur = serializers.CharField(read_only=True)


class ResultatCalepinageSerializer(serializers.Serializer):
    """Le résultat d'un calepinage — il porte TOUJOURS (hash, version)."""

    repere = serializers.CharField(read_only=True)
    hash_entree = serializers.CharField(read_only=True)
    version_moteur = serializers.CharField(read_only=True)
    schema_version = serializers.IntegerField(read_only=True)
    total_modules = serializers.IntegerField(read_only=True)
    kwc = serializers.FloatField(read_only=True)
    engageable = serializers.BooleanField(read_only=True)
    motifs_non_engageable = serializers.ListField(
        child=serializers.CharField(), read_only=True)
    engagement_modules = serializers.IntegerField(read_only=True,
                                                  allow_null=True)
    plans = serializers.ListField(child=serializers.JSONField(),
                                  read_only=True)
    rangees = serializers.ListField(child=serializers.JSONField(),
                                    read_only=True)
    preuve = PreuveCalepinageSerializer(read_only=True)
    depuis_cache = serializers.BooleanField(read_only=True, required=False)


class JobCalepinageSerializer(serializers.Serializer):
    """L'état d'un calcul de fond + son résultat quand il est là."""

    id = serializers.IntegerField(read_only=True)
    kind = serializers.CharField(read_only=True)
    statut = serializers.CharField(read_only=True)
    progress_pct = serializers.IntegerField(read_only=True)
    message_erreur = serializers.CharField(read_only=True)
    resultat = ResultatCalepinageSerializer(read_only=True,
                                            required=False,
                                            allow_null=True)
    variante = serializers.IntegerField(read_only=True, allow_null=True,
                                        required=False)


class ComparaisonVariantesSerializer(serializers.Serializer):
    """AOF62 — comparaison de N variantes en UN appel."""

    ids = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Identifiants de variantes séparés par des virgules.")

    def validate_ids(self, valeur):
        identifiants = []
        for brut in (valeur or '').replace(';', ',').split(','):
            brut = brut.strip()
            if not brut:
                continue
            if not brut.isdigit():
                raise serializers.ValidationError(
                    "« %s » n'est pas un identifiant de variante." % brut)
            identifiants.append(int(brut))
        if not identifiants:
            raise serializers.ValidationError(
                "Indiquez au moins un identifiant de variante à comparer.")
        return identifiants
