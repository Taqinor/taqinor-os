# AMON24 — auteur du classement manuel d'un drapeau de sous-performance.
# Additive : une colonne NULL (NULL = fermeture automatique, historique).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('monitoring', '0011_asav71_credentials_chiffres'),
    ]

    operations = [
        migrations.AddField(
            model_name='underperformanceflag',
            name='cloture_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
