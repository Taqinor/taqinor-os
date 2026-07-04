# ZSAL3 — Équipes commerciales (« Mes équipes ») : modèle additif
# EquipeCommerciale + M2M membres. Aucune modification d'un modèle existant.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0005_alter_customuser_role"),
        ("crm", "0040_zsal2_plan_activite"),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipeCommerciale",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=120)),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="equipes_commerciales", to="authentication.company")),
                ("responsable", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="equipes_dirigees", to=settings.AUTH_USER_MODEL)),
                ("membres", models.ManyToManyField(
                    blank=True, related_name="equipes_commerciales",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Équipe commerciale",
                "verbose_name_plural": "Équipes commerciales",
                "ordering": ["nom"],
            },
        ),
    ]
