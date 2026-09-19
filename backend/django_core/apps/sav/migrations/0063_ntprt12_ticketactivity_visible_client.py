"""NTPRT12 — visibilité client d'une entrée du chatter ticket.

``TicketActivity.visible_client`` (défaut False) : le chatter reste INTERNE par
construction. Toute entrée existante — note technicien, journal de changement,
e-mail, WhatsApp, appel — garde donc son caractère interne ; seule une note
explicitement marquée visible client peut apparaître dans le fil du portail
« Mes tickets SAV ». ADDITIF STRICT, aucune donnée modifiée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0062_ntsrv34_reponse_type_canaux'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketactivity',
            name='visible_client',
            field=models.BooleanField(
                default=False,
                help_text='Quand actif, cette entrée apparaît dans le fil du '
                          'portail client. Défaut : entrée INTERNE, jamais '
                          'exposée.',
                verbose_name='Visible par le client'),
        ),
    ]
