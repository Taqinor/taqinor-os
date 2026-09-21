"""AOF157 — serializers de l'ÉCONOMIE d'un appel d'offres (DIRECTEUR SEUL).

Module SÉPARÉ, délibérément. Les coûts, la marge et le bénéfice ne doivent
apparaître dans AUCUN serializer AO général : un champ ajouté par distraction
dans ``apps/ao/serializers.py`` sortirait la marge sur toutes les surfaces qui
consomment déjà l'AO. La séparation physique rend la faute visible en revue —
et un test d'introspection (``test_economie_directeur``) la rend impossible en
silence.

Ces serializers ne sont montés QUE par ``apps.ao.views_directeur``, derrière
``ao_rentabilite_voir`` (permission ÉLEVÉE, cf. ``apps.ao.permissions``).
"""
from rest_framework import serializers

from .models import CibleFinanciere, EconomieAO, LigneCoutRevient

__all__ = [
    'CibleFinanciereSerializer',
    'EconomieAOSerializer',
    'LigneCoutRevientSerializer',
]


class LigneCoutRevientSerializer(serializers.ModelSerializer):
    poste_display = serializers.CharField(
        source='get_poste_display', read_only=True)
    regime_tva_display = serializers.CharField(
        source='get_regime_tva_display', read_only=True)
    montant_ht = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = LigneCoutRevient
        fields = [
            'id', 'economie', 'poste', 'poste_display', 'designation',
            'quantite', 'unite', 'prix_unitaire_ht', 'regime_tva',
            'regime_tva_display', 'montant_ht', 'ordre',
        ]


class CibleFinanciereSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = CibleFinanciere
        fields = [
            'id', 'economie', 'version', 'benefice_net_cible_ht',
            'arrondi_psychologique', 'seuil_psychologique',
            'ligne_ajustement', 'active', 'auteur', 'auteur_nom', 'motif',
            'created_at',
        ]
        read_only_fields = ['version', 'auteur', 'created_at']


class EconomieAOSerializer(serializers.ModelSerializer):
    """Tous les agrégats sont DÉRIVÉS — aucun total n'est stocké."""

    lignes = LigneCoutRevientSerializer(many=True, read_only=True)
    cibles = CibleFinanciereSerializer(many=True, read_only=True)
    appel_offre_reference = serializers.CharField(
        source='appel_offre.reference', read_only=True)

    cout_revient_ht = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    cout_regime_reduit_ht = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    cout_regime_standard_ht = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    tva_deductible = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    benefice_net_cible_ht = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    tva_collectee = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    tva_nette_a_reverser = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    marge_pct = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True)
    controle_tresorerie = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    ecart_tresorerie = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    sous_seuil_psychologique = serializers.BooleanField(read_only=True)

    class Meta:
        model = EconomieAO
        fields = [
            'id', 'appel_offre', 'appel_offre_reference', 'taux_tva_vente',
            'taux_tva_achat_reduit', 'taux_tva_achat_standard',
            'verrouillee', 'note_comptable', 'lignes', 'cibles',
            'cout_revient_ht', 'cout_regime_reduit_ht',
            'cout_regime_standard_ht', 'tva_deductible',
            'benefice_net_cible_ht', 'total_ht', 'tva_collectee',
            'total_ttc', 'tva_nette_a_reverser', 'marge_pct',
            'controle_tresorerie', 'ecart_tresorerie',
            'sous_seuil_psychologique', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
