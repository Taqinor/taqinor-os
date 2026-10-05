"""ACAL33 — un calepinage par devis (et par société), garanti en BASE.

ADDITIVE et revertable (``AddConstraint`` ↔ ``RemoveConstraint``) : aucune
ligne n'est réécrite. Avant de l'écrire, la production a été lue en lecture
seule le 05/10/2026 : 0 doublon (company, devis) — 4 calepinages, aucun lié à
un devis. Un doublon trouvé plus tard ferait échouer la migration, jamais un
dédoublonnage silencieux.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0016_calx406_responsable'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='calepinage',
            constraint=models.UniqueConstraint(
                condition=models.Q(('devis__isnull', False)),
                fields=('company', 'devis'),
                name='calepinage_un_par_devis'),
        ),
    ]
