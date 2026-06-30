# FG376 — Connecteur Zapier / Make : abonnements webhook sortants (REST hooks).
#
# Ajoute ``WebhookSubscription`` : un outil no-code s'abonne à un nom
# d'événement (texte libre) en enregistrant une URL cible. GÉNÉRIQUE — AUCUN
# import d'app métier (contrat import-linter
# ``core-foundation-is-a-base-layer``). Migration ADDITIVE et réversible.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('core', '0005_calendarsyncmapping'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebhookSubscription',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.CharField(
                    help_text='Nom d\'événement, ex. « devis_accepted ».',
                    max_length=80, verbose_name='Événement')),
                ('target_url', models.URLField(
                    max_length=500, verbose_name='URL cible')),
                ('secret', models.CharField(
                    blank=True, default='',
                    help_text='Optionnel : clé HMAC pour signer le payload '
                              '(en-tête X-Taqinor-Signature).',
                    max_length=120, verbose_name='Secret de signature')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('last_delivery_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Dernière livraison')),
                ('last_status', models.IntegerField(
                    blank=True, null=True, verbose_name='Dernier statut HTTP')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webhook_subscriptions',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Abonnement webhook',
                'verbose_name_plural': 'Abonnements webhook',
                'ordering': ['event', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='webhooksubscription',
            constraint=models.UniqueConstraint(
                fields=('company', 'event', 'target_url'),
                name='core_webhook_co_evt_url'),
        ),
        migrations.AddIndex(
            model_name='webhooksubscription',
            index=models.Index(
                fields=['company', 'event', 'actif'],
                name='core_webhook_co_evt_idx'),
        ),
    ]
