from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0023_xsav17_releve_compteur_equipement'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipement',
            name='public_token',
            field=models.CharField(
                blank=True, editable=False, max_length=64, null=True,
                unique=True,
                help_text=(
                    'Jeton public (XSAV19) pour la page de signalement sans '
                    'login. Généré via ensure_public_token().')),
        ),
    ]
