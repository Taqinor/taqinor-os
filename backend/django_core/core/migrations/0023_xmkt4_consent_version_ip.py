# XMKT4 - champs additifs sur ConsentRecord : version du texte de
# consentement presente + IP de confirmation (preuve de double opt-in,
# loi 09-08/CNDP). Les deux sont optionnels (vide/None) : aucun comportement
# existant n'est modifie.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_yopsb10_retentionrun'),
    ]

    operations = [
        migrations.AddField(
            model_name='consentrecord',
            name='version_texte',
            field=models.CharField(
                blank=True, default='', max_length=40,
                verbose_name='Version du texte de consentement',
                help_text=(
                    'Version du texte présenté à la personne '
                    '(ex. « v1-2026-07 »).'),
            ),
        ),
        migrations.AddField(
            model_name='consentrecord',
            name='ip_confirmation',
            field=models.GenericIPAddressField(
                blank=True, null=True, verbose_name='IP de confirmation',
                help_text=(
                    'IP du clic de confirmation (double opt-in), preuve '
                    'loi 09-08.'),
            ),
        ),
    ]
