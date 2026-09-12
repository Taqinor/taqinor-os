# NTAI1 — Journal d'usage & coût LLM par tenant.
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur `0003` de cette app, et ne
# dépend d'`authentication` que par la migration qui CRÉE `Company` (d'autres
# lanes ajoutent des migrations à cette app en parallèle).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_governance', '0003_ntai18_extractioncorrection'),
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LlmUsageRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('capability', models.CharField(choices=[('ocr', 'OCR (document)'), ('stt', 'Transcription audio'), ('vision_qa', 'Contrôle vision'), ('llm', 'Génération de texte')], help_text='Capacité IA appelée.', max_length=20)),
                ('provider', models.CharField(help_text="Clé du fournisseur ayant servi l'appel.", max_length=60)),
                ('feature_key', models.CharField(blank=True, default='', help_text='Feature appelante (ex. « ai.rediger ») — texte libre posé par la couche appelante, jamais par le client.', max_length=120)),
                ('prompt_tokens', models.PositiveIntegerField(default=0)),
                ('completion_tokens', models.PositiveIntegerField(default=0)),
                ('cost_estimated_micro_mad', models.PositiveBigIntegerField(default=0, help_text='Coût estimé en micro-MAD (10⁻⁶ MAD) — significatif UNIQUEMENT si « cout_tarife » est vrai.')),
                ('cout_tarife', models.BooleanField(default=False, help_text="Un tarif était configuré pour ce fournisseur au moment de l'appel ; sinon le coût est inconnu (et non nul).")),
                ('latency_ms', models.PositiveIntegerField(default=0)),
                ('success', models.BooleanField(default=True)),
                ('message', models.CharField(blank=True, default='', help_text="Message d'erreur du fournisseur (jamais le contenu du prompt).", max_length=255)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Usage d'une capacité IA",
                'verbose_name_plural': 'Usages des capacités IA',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['company', '-created_at'], name='ai_gov_usage_co_date_idx'), models.Index(fields=['company', 'feature_key'], name='ai_gov_usage_co_feat_idx')],
            },
        ),
    ]
