# XPUR20/21 — RFQConsultation : fournisseur consulté (invité) sur une RFQ,
# porteur du jeton public unique (RFQ, fournisseur) utilisé par la réponse
# fournisseur sans login (XPUR21) et la traçabilité d'envoi email/WhatsApp
# (XPUR20). Additive : aucune table existante modifiée.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.installations.models_rfq


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0062_xmfg14_gamme_etapes'),
        ('stock', '0040_fournisseur_custom_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RFQConsultation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=apps.installations.models_rfq._default_rfq_token, editable=False, max_length=64, unique=True)),
                ('revoque', models.BooleanField(default=False)),
                ('email_envoye_le', models.DateTimeField(blank=True, null=True)),
                ('whatsapp_envoye_le', models.DateTimeField(blank=True, null=True)),
                ('derniere_relance_le', models.DateTimeField(blank=True, null=True)),
                ('nb_relances', models.PositiveIntegerField(default=0)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_rfq_consultations', to='authentication.company')),
                ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installations_rfq_consultations', to='stock.fournisseur')),
                ('offre', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consultation_source', to='installations.rfqoffre')),
                ('rfq', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consultations', to='installations.rfq')),
            ],
            options={
                'verbose_name': 'Consultation RFQ',
                'verbose_name_plural': 'Consultations RFQ',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='rfqconsultation',
            index=models.Index(fields=['company', 'rfq'], name='idx_rfqc_co_rfq'),
        ),
        migrations.AddIndex(
            model_name='rfqconsultation',
            index=models.Index(fields=['token'], name='idx_rfqc_token'),
        ),
        migrations.AlterUniqueTogether(
            name='rfqconsultation',
            unique_together={('rfq', 'fournisseur')},
        ),
    ]
