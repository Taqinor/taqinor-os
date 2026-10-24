"""AGQ10 (D-AGQ-6) — jours d'irrigation par semaine sur le lead (colonne
nullable SANS défaut : vide = question pas encore posée), lue par le bloc
économie du devis automatique ; et le ``help_text`` de ``pompe_debit_m3h``
réaligné sur D-AGQ-1 (le débit souhaité devient le débit de conception quand
aucun volume n'est déclaré). Additive, revertable.

Écrite à la main (aucune base disponible dans la lane) : miroir exact des
champs de ``apps/crm/models.py::Lead`` — ``test_aucune_migration_en_attente``
le confirme en CI.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0137_enf15_lead_external_ref_soft_delete'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='jours_irrigation_semaine',
            field=models.DecimalField(blank=True, decimal_places=1, help_text="Question à l'appel : « Vous irriguez combien de jours par semaine en saison ? » (1 à 7, vide = pas encore posée).", max_digits=3, null=True, verbose_name="Jours d'irrigation par semaine"),
        ),
        migrations.AlterField(
            model_name='lead',
            name='pompe_debit_m3h',
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Question à l'appel : « Quel débit voulez-vous, en m³ par heure ? » (débit SOUHAITÉ, vide = pas encore posée). Débit souhaité (m³/h) : devient le débit de conception quand aucun volume n'est déclaré (D-AGQ-1).", max_digits=8, null=True),
        ),
    ]
