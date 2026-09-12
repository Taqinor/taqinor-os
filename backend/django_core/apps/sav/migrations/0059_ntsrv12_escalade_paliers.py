"""NTSRV12 - Paliers d'escalade SLA configurables (additif).

Nouveau referentiel `EscaladeSlaNiveau` (vide par defaut -> comportement XSAV6
binaire inchange) + memoire d'idempotence par palier sur le ticket. Le booleen
`sla_escalade_notifiee` (XSAV6) est CONSERVE tel quel.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('sav', '0058_ntsrv11_horaires_ouvres'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='sla_escalade_paliers_notifies',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name="Paliers d'escalade déjà notifiés"),
        ),
        migrations.CreateModel(
            name='EscaladeSlaNiveau',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(
                    blank=True, default='', max_length=120,
                    verbose_name='Libellé')),
                ('ordre', models.PositiveIntegerField(
                    default=0,
                    help_text='Ordre de parcours des paliers (croissant).',
                    verbose_name='Ordre')),
                ('seuil_jours_apres_echeance', models.PositiveIntegerField(
                    default=0,
                    help_text='0 = le jour de l’échéance (J+0), 1 = le '
                              'lendemain (J+1)…',
                    verbose_name='Seuil (jours après échéance)')),
                ('notifier_role', models.CharField(
                    blank=True, default='',
                    help_text='Palier de rôle à notifier (ex. « responsable », '
                              '« admin »). Ignoré si un utilisateur est '
                              'désigné.',
                    max_length=30, verbose_name='Notifier le rôle')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='escalades_sla_sav',
                    to='authentication.company', verbose_name='Société')),
                ('notifier_utilisateur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='escalades_sla_sav',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Notifier l’utilisateur')),
            ],
            options={
                'verbose_name': 'Palier d’escalade SLA',
                'verbose_name_plural': 'Paliers d’escalade SLA',
                'ordering': ['ordre', 'seuil_jours_apres_echeance', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='escaladeslaniveau',
            constraint=models.UniqueConstraint(
                fields=('company', 'ordre'),
                name='sav_escaladeslaniveau_ordre_uniq'),
        ),
    ]
