# ODX17 — Facture a déménagé de ``apps.ventes`` vers ``apps.facturation``
# (même table physique ``ventes_facture``, zéro SQL). Re-pointe la FK
# ``VenteComptoir.facture`` en state-only (SeparateDatabaseAndState,
# database_operations=[]) — aucune colonne ni contrainte ne change.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0001_initial'),
        ('facturation', '0001_odx17_facturation_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='ventecomptoir',
                    name='facture',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='ventes_comptoir', to='facturation.facture'),
                ),
            ],
            database_operations=[],
        ),
    ]
