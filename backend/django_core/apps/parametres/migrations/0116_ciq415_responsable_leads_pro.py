# CIQ415 (Groupe CIQ, D-CIQ-20) — réglage société « responsable des leads
# commerciaux et industriels », NULL par défaut. Additive et réversible.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0115_agr606_recette_pompage_ecart'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='responsable_leads_pro',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
