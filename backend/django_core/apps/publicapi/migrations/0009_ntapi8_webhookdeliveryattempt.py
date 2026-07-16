"""NTAPI8 — reprises programmées à backoff long (1m/5m/30m/2h/6h, max 6).

Additif : nouveau statut `en_echec` sur `WebhookDelivery.status` (choices
Python seulement — pas de nouvelle colonne) + nouveau modèle
`WebhookDeliveryAttempt`. Aucune ligne existante affectée."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0008_ntapi5_apikey_api_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='webhookdelivery',
            name='status',
            field=models.CharField(
                choices=[
                    ('success', 'Succès'), ('failed', 'Échec'),
                    ('en_echec', 'Échec définitif'),
                ],
                default='failed', max_length=10),
        ),
        migrations.CreateModel(
            name='WebhookDeliveryAttempt',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('numero_tentative', models.PositiveSmallIntegerField()),
                ('prochain_essai_at', models.DateTimeField(
                    blank=True, db_index=True, null=True)),
                ('statut', models.CharField(
                    choices=[
                        ('en_attente', 'En attente'),
                        ('succes', 'Succès'),
                        ('echec', 'Échec'),
                    ],
                    default='en_attente', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webhook_delivery_attempts',
                    to='authentication.company')),
                ('delivery', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attempts', to='publicapi.webhookdelivery')),
            ],
            options={
                'verbose_name': 'Reprise programmée de livraison webhook',
                'verbose_name_plural':
                    'Reprises programmées de livraison webhook',
                'ordering': ['numero_tentative'],
            },
        ),
        migrations.AddIndex(
            model_name='webhookdeliveryattempt',
            index=models.Index(
                fields=['statut', 'prochain_essai_at'],
                name='publicapi_wda_due_idx'),
        ),
    ]
