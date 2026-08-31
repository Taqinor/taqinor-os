"""NTDATA40 — journal de diffusion des rapports (``EnvoiRapport``).

Nouvelle table PUREMENT ADDITIVE : une ligne par tentative d'envoi
(email/WhatsApp), réussie ou non, avec son motif d'échec. Aucun modèle
existant n'est modifié. Le modèle hérite du socle multi-tenant
``core.models.TenantModel`` (ARC1/SCA4) — d'où ``created_at``/``updated_at``
en plus de l'horodatage métier ``envoye_le``.

CHAÎNE : enchaîne explicitement sur la migration NTDATA39, et ne dépend
d'``authentication`` que par la migration qui CRÉE ``Company`` — d'autres
lanes ajoutent des migrations à ``authentication`` en parallèle, et une
dépendance sur sa tête entrerait en collision.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
        ('reporting', '0015_ntdata39_canal_whatsapp'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnvoiRapport',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('canal', models.CharField(
                    choices=[('email', 'Email'), ('whatsapp', 'WhatsApp')],
                    default='email', max_length=10, verbose_name='Canal')),
                ('destinataires', models.TextField(
                    blank=True, default='',
                    help_text='Adresses/numéros visés par cette tentative.',
                    verbose_name='Destinataires')),
                ('statut', models.CharField(
                    choices=[('envoye', 'Envoyé'), ('echec', 'Échec'),
                             ('non_configure', 'Canal non configuré'),
                             ('sans_destinataire', 'Aucun destinataire')],
                    default='envoye', max_length=20, verbose_name='Statut')),
                ('erreur', models.TextField(
                    blank=True, default='',
                    help_text="Motif lisible quand l'envoi n'a pas abouti.",
                    verbose_name='Motif')),
                ('envoye_le', models.DateTimeField(
                    auto_now_add=True, verbose_name='Horodatage')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='envois_rapports',
                    to='authentication.company', verbose_name='Société')),
                ('saved_report', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='envois', to='reporting.savedreport',
                    verbose_name='Rapport')),
            ],
            options={
                'verbose_name': 'Envoi de rapport',
                'verbose_name_plural': 'Envois de rapport',
                'ordering': ['-envoye_le', '-id'],
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='envoirapport',
            index=models.Index(fields=['company', 'saved_report'],
                               name='reporting_envoi_co_rap_idx'),
        ),
        migrations.AddIndex(
            model_name='envoirapport',
            index=models.Index(fields=['company', 'statut'],
                               name='reporting_envoi_co_stat_idx'),
        ),
    ]
