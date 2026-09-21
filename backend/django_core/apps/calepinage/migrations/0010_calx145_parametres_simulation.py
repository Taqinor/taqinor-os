"""CALX145 — les deux sections « simulation » et « electrique_societe » des
réglages société (clés SAISIES avec leur provenance).

ADDITIVE et SANS DONNÉE : les deux champs naissent à ``{}`` pour toutes les
sociétés. Une section vide veut dire « aucune clé saisie », donc chaque étape
de simulation ou chaque contrôle électrique qui en dépend reste OMIS en
nommant ce qui manque — jamais un forfait, jamais un seuil supposé. C'est
exactement le comportement d'aujourd'hui (aucune de ces valeurs n'existait),
donc aucune société existante ne change de comportement en recevant ces
champs.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0009_cal212_pose_reelle'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrescalepinage',
            name='electrique_societe',
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name='Seuils électriques de la société'),
        ),
        migrations.AddField(
            model_name='parametrescalepinage',
            name='simulation',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name='Réglages de simulation'),
        ),
    ]
