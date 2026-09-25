"""WIR66 — sérialiseurs des référentiels société (TVA / conditions / unités).

Les trois modèles maîtres (``models_taxes``/``models_payment_terms``/
``models_units``) sont seedés à la création de société mais n'avaient aucune
API. Ces sérialiseurs les exposent en CRUD ; ``company`` est TOUJOURS forcée
côté serveur (jamais lue du corps), la clé technique (``code``) d'une entrée
existante ne peut pas migrer.
"""
from rest_framework import serializers

from .models_payment_terms import ConditionPaiement
from .models_relance import CadenceRelanceEtape
from .models_taxes import TauxTVA
from .models_units import UniteMesure


class TauxTVASerializer(serializers.ModelSerializer):
    class Meta:
        model = TauxTVA
        fields = ['id', 'code', 'libelle', 'taux', 'defaut', 'actif']

    def validate_code(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le code est requis.')
        return value

    def validate(self, attrs):
        # La clé technique ancre le seed/miroir : elle ne migre pas une fois
        # posée (on modifie un taux existant, on n'en renomme jamais le code).
        if self.instance is not None:
            new_code = attrs.get('code')
            if new_code and new_code != self.instance.code:
                raise serializers.ValidationError(
                    {'code': "Le code d'un taux existant ne peut pas changer."})
        return attrs


class ConditionPaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionPaiement
        fields = [
            'id', 'libelle', 'delai_jours', 'fin_de_mois', 'escompte_pct',
            'actif',
        ]

    def validate_libelle(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le libellé est requis.')
        return value


class UniteMesureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UniteMesure
        fields = ['id', 'code', 'libelle', 'actif']

    def validate_code(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le code est requis.')
        return value

    def validate(self, attrs):
        # Le code = valeur portée par ``Produit.unite_stock`` (clé de miroir) :
        # on ne le renomme jamais sur une unité existante.
        if self.instance is not None:
            new_code = attrs.get('code')
            if new_code and new_code != self.instance.code:
                raise serializers.ValidationError(
                    {'code': "Le code d'une unité existante ne peut pas "
                             'changer.'})
        return attrs


class CadenceRelanceEtapeSerializer(serializers.ModelSerializer):
    """RELANCE FOUNDATION — gabarit de cadence de relance (Paramètres → CRM).

    Purement un ordonnancement de rappels internes (délai + canal + libellé),
    jamais un chiffre affiché au client."""

    class Meta:
        model = CadenceRelanceEtape
        # MRY4 — forme `cadence_relance_v2` (contrat MRY25).
        # CAD43 — `samedi_ok` s'AJOUTE en fin de forme (contrat
        # `cadence_relance_v2`) : aucun champ retiré ni déplacé.
        # PARAM-CADENCE (25/09/2026) — `cle` s'AJOUTE en fin de forme, en
        # LECTURE SEULE : c'est la clé stable par laquelle le moteur retrouve
        # un barreau des cadences `apres_contact`/`visite` ; l'écran ne la
        # pose jamais (vide sur un barreau ajouté à la main).
        fields = ['id', 'cadence', 'ordre', 'delai_jours', 'delai_minutes',
                  'heure_cible', 'canal', 'libelle', 'template_cle',
                  'dimanche_ok', 'actif', 'samedi_ok', 'cle']
        read_only_fields = ['cle']

    def validate(self, attrs):
        # PARAM-CADENCE — un barreau à clé moteur appartient à SA cadence : le
        # déplacer dans une autre ferait disparaître une étape de la chaîne
        # (le moteur le cherche dans la sienne) et en créerait une orpheline
        # ailleurs. Le supprimer reste permis — le moteur retombe alors sur le
        # défaut de la plateforme (pilier) ou saute la marche (palier).
        instance = getattr(self, 'instance', None)
        cadence = attrs.get('cadence')
        if (instance is not None and (instance.cle or '')
                and cadence is not None and cadence != instance.cadence):
            raise serializers.ValidationError({'cadence': (
                '« Cadence » : ce barreau est une étape du moteur (clé '
                f'« {instance.cle} ») — il reste dans sa cadence. Modifiez '
                'son libellé, son délai, son canal ou son heure, ou '
                'désactivez-le.')})
        return attrs

    def validate_libelle(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le libellé est requis.')
        return value

    def validate_delai_minutes(self, value):
        # MRY4 — au-delà de 1439, l'appelant voulait dire « un jour de plus » :
        # on refuse plutôt que d'absorber silencieusement un décalage d'un
        # jour dans un champ nommé « minutes ».
        if value is not None and value >= 1440:
            raise serializers.ValidationError(
                'Le délai en minutes doit rester sous 1440 (24 h) — '
                'au-delà, utiliser le délai en jours.')
        # CAD29 — la borne BASSE, elle, ne tenait que par le type de la
        # colonne (`PositiveIntegerField`) : selon le moteur de base, un -1
        # ressortait en erreur d'intégrité (500) au lieu d'un refus nommé.
        # L'aide du champ annonce « 0 à 1439 » : le serveur le dit désormais
        # aussi, en français, sur LE champ fautif (règle fondateur 08/09).
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le délai en minutes ne peut pas être négatif — il va de 0 '
                'à 1439.')
        return value
