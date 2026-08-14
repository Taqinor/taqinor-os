# NTRET3 — Multi-caissiers avec PIN de session (verrouillage rapide sans
# re-login complet). Nouveau modèle additif, ne touche aucune table existante.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0014_customuser_account_lockout"),
        ("pos", "0004_ntret2_numero_rapport_z"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CodePinCaissier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("pin_hash", models.CharField(max_length=128)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="codes_pin_caissier", to="authentication.company")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="codes_pin_caissier", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Code PIN caissier",
                "verbose_name_plural": "Codes PIN caissier",
                "unique_together": {("company", "user")},
            },
        ),
    ]
