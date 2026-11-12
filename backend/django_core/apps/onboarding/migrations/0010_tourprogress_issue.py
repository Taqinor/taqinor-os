"""Follow-up NTDMO42 — ``TourProgress.issue`` : tour terminé vs fermé avant la
fin. Additive ; les lignes existantes restent vides (« vu ou fermé »)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0009_enf15_cle_bornee_a_la_societe'),
    ]

    operations = [
        migrations.AddField(
            model_name='tourprogress',
            name='issue',
            field=models.CharField(
                blank=True, default='', max_length=10,
                choices=[('termine', 'Terminé'),
                         ('ferme', 'Fermé avant la fin')]),
        ),
    ]
