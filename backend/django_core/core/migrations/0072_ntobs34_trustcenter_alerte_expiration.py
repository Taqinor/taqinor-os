# NTOBS34 — marqueur anti-double-alerte d'expiration sur une entrée du trust
# center. Champ ADDITIF à défaut False : aucune entrée existante n'est marquée
# comme déjà alertée, donc la première alerte part bien et le comportement
# actuel (aucune alerte) reste inchangé tant que rien ne la déclenche.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0071_ntobs21_reliabilitysettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='trustcenterentry',
            name='alerte_expiration_envoyee',
            field=models.BooleanField(
                default=False,
                help_text='Faux = jamais alertée ; posé une seule fois.',
                verbose_name="Alerte d'expiration envoyée"),
        ),
    ]
