# ENF13 — backstop DB (CheckConstraint). Additive, reversible; prod relu le 09/10/2026 : 0 ligne en violation.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0168_astk192_rdv_fournisseur_bcf'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='mouvementstock',
            constraint=models.CheckConstraint(condition=models.Q(('quantite__gte', 0)), name='mouvementstock_quantite_non_negative'),
        ),
    ]
