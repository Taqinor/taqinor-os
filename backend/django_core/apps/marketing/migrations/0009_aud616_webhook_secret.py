# AUD616 — secret HMAC PAR SOCIÉTÉ pour les webhooks marketing entrants
# (Brevo, agrégateur SMS), sur le patron AUD212. Additive et fail-closed :
# la valeur par défaut vide signifie « aucun webhook accepté » tant que la
# société n'a pas configuré son secret.
#
# Écrite à la main (la chaîne d'import WeasyPrint bloque makemigrations sur
# cet hôte — voir 0006_ntmkt16_dernier_numero_version.py), calquée sur ce que
# Django autogénère pour un AddField CharField.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0008_ntmkt20_modele_attribution'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametresmarketing',
            name='webhook_secret',
            field=models.CharField(
                blank=True, default='', max_length=128,
                help_text=(
                    "Secret HMAC-SHA256 partagé avec Brevo / l'agrégateur "
                    'SMS. Vide = aucun webhook accepté pour cette société.'),
                verbose_name=(
                    'Secret HMAC des webhooks marketing entrants (AUD616)')),
        ),
    ]
