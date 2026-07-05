# ZSAV9 — Suiveurs de ticket (followers) + « suivre tous les tickets ».
# `TicketFollower` + `SavSlaSettings.suivre_tous_tickets_sav` (M2M, additifs).
import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
        ('sav', '0044_zsav3_ticket_activite_a_faire'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='suivre_tous_tickets_sav',
            field=models.ManyToManyField(
                blank=True, related_name='sav_suit_tous_tickets',
                to=django.conf.settings.AUTH_USER_MODEL,
                verbose_name='Suivre tous les tickets (utilisateurs)'),
        ),
        migrations.CreateModel(
            name='TicketFollower',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ticket_followers',
                    to='authentication.company')),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='followers', to='sav.ticket')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tickets_suivis',
                    to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Suiveur de ticket',
                'verbose_name_plural': 'Suiveurs de ticket',
            },
        ),
        migrations.AlterUniqueTogether(
            name='ticketfollower',
            unique_together={('ticket', 'user')},
        ),
        migrations.AddIndex(
            model_name='ticketfollower',
            index=models.Index(
                fields=['company', 'ticket'],
                name='sav_follower_company_tkt_idx'),
        ),
    ]
