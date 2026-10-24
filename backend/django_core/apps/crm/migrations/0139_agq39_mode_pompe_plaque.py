"""AGQ39 (D-AGQ-10) — le mode de pompe du lead (neuve / existante conservée)
et la plaque de la pompe ACTUELLE (kW, tension, phases), lus par le devis
automatique agricole. Quatre colonnes nullables SANS défaut (vide = question
pas encore posée). Additive, revertable.

Écrite à la main (aucune base disponible dans la lane) : miroir exact des
champs de ``apps/crm/models.py::Lead`` — ``test_aucune_migration_en_attente``
le confirme en CI.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0138_agq10_jours_irrigation_semaine'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='mode_pompe',
            field=models.CharField(blank=True, choices=[('neuve', 'Pompe neuve'), ('existante', 'Pompe actuelle conservée')], help_text="Question à l'appel : « On installe une pompe neuve, ou on garde votre pompe actuelle et on la passe au solaire ? » (neuve ou existante conservée, vide = pas encore posée).", max_length=10, null=True, verbose_name='Mode de pompe'),
        ),
        migrations.AddField(
            model_name='lead',
            name='pompe_actuelle_kw',
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Question à l'appel : « Quelle puissance en kW est écrite sur la plaque de votre pompe actuelle ? » (kW, vide = pas encore posée).", max_digits=6, null=True, verbose_name='Pompe actuelle — puissance plaque (kW)'),
        ),
        migrations.AddField(
            model_name='lead',
            name='pompe_actuelle_tension_v',
            field=models.PositiveSmallIntegerField(blank=True, help_text="Question à l'appel : « Quelle tension est écrite sur la plaque : 220 V ou 380 V ? » (volts, vide = pas encore posée).", null=True, verbose_name='Pompe actuelle — tension plaque (V)'),
        ),
        migrations.AddField(
            model_name='lead',
            name='pompe_actuelle_phases',
            field=models.CharField(blank=True, choices=[('mono', 'Monophasé'), ('tri', 'Triphasé')], help_text="Question à l'appel : « Sur la plaque, la pompe est-elle monophasée ou triphasée ? » (vide = pas encore posée).", max_length=4, null=True, verbose_name='Pompe actuelle — phases plaque'),
        ),
    ]
