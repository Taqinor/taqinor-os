"""NTP2P11 — délai de soumission + escalade direction sur les notes de frais.

Additif pur, 4 champs nullables/à défaut neutre : sans plafond configuré, la
soumission d'une note de frais reste strictement le cycle FG135 historique
(aucun contrôle de délai, aucune escalade).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frais', '0002_odx15_rename_stale_contenttypes'),
    ]

    operations = [
        migrations.AddField(
            model_name='notefrais',
            name='escalade_direction',
            field=models.BooleanField(default=False, verbose_name='Validation DIRECTION requise (escalade de montant)'),
        ),
        migrations.AddField(
            model_name='notefrais',
            name='warning_delai',
            field=models.TextField(blank=True, default='', verbose_name='Warning de délai (non bloquant, affiché au valideur)'),
        ),
        migrations.AddField(
            model_name='plafondnotefrais',
            name='escalade_direction_au_dela_de',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Au-delà, la note exige une validation DIRECTION (jamais un blocage silencieux). Vide = aucune escalade.', max_digits=14, null=True, verbose_name='Montant au-delà duquel la direction doit valider'),
        ),
        migrations.AddField(
            model_name='plafondnotefrais',
            name='jours_max_apres_depense',
            field=models.PositiveIntegerField(blank=True, help_text='Au-delà, un WARNING non bloquant est journalisé pour le valideur. Vide = aucun contrôle de délai.', null=True, verbose_name='Délai max entre la dépense et sa soumission (jours)'),
        ),
    ]
