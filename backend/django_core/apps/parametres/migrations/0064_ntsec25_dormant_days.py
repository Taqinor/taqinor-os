from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0063_ntsec28_login_banner_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="dormant_days",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Jours d'inactivité au-delà desquels un compte est "
                          "désactivé automatiquement (0 = jamais)."),
        ),
    ]
