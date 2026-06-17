# N66 — installateur par défaut des nouveaux chantiers. Additif, nullable :
# NULL = comportement actuel (le créateur du chantier en est le technicien).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0014_companyprofile_commission"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="default_installer",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
