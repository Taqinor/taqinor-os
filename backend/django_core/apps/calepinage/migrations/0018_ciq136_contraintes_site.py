# CIQ136 (Groupe CIQ) — contraintes de site PAR PROJET sur ``Calepinage``.
# Additive : une colonne JSON à objet vide (= calepinage d'aujourd'hui).
# Réversible : RemoveField sans perte (colonne neuve).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0017_ciq112_mode_pose_bac_acier'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='contraintes_site',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name='Contraintes de site'),
        ),
    ]
