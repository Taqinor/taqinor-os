# FG22 — politique de mot de passe & verrouillage de compte (CompanyProfile).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0025_fg52_devise_defaut"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="password_min_length",
            field=models.PositiveSmallIntegerField(
                default=8,
                help_text="Longueur minimale du mot de passe (FG22).",
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="password_require_complexity",
            field=models.BooleanField(
                default=False,
                help_text="Exiger maj./min./chiffre/caractère spécial (FG22).",
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="lockout_max_attempts",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Nombre d'échecs consécutifs avant verrouillage "
                          "(0 = off).",
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="lockout_duration_minutes",
            field=models.PositiveSmallIntegerField(
                default=15,
                help_text="Durée du verrouillage temporaire (minutes).",
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="password_expiry_days",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Expiration du mot de passe en jours (0 = jamais).",
            ),
        ),
    ]
