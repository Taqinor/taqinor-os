# Generated manually — ZRH14 badges de reconnaissance interne (gamification).
# Additif, deux nouveaux modèles.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH14 — BadgeReconnaissance + AttributionBadge (additif)."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("rh", "0075_zrh16_localisation_hebdo"),
    ]

    operations = [
        migrations.CreateModel(
            name="BadgeReconnaissance",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=80, verbose_name="Nom")),
                ("description", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Description")),
                ("icone", models.CharField(
                    blank=True, default="🏅", max_length=8,
                    verbose_name="Icône/emoji")),
                ("actif", models.BooleanField(
                    default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_badges_reconnaissance",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Badge de reconnaissance",
                "verbose_name_plural": "Badges de reconnaissance",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="AttributionBadge",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("message", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Message")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("attribue_par", models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rh_badges_attribues",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Attribué par")),
                ("badge", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="attributions",
                    to="rh.badgereconnaissance", verbose_name="Badge")),
                ("beneficiaire", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="badges_recus",
                    to="rh.dossieremploye", verbose_name="Bénéficiaire")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_attributions_badge",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Attribution de badge",
                "verbose_name_plural": "Attributions de badge",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="attributionbadge",
            index=models.Index(
                fields=["company", "beneficiaire"],
                name="rh_attrib_badge_benef_idx"),
        ),
    ]
