# NTAI5 — Bibliothèque de prompts éditables par société (+ versions figées).
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur `0005` de cette app.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_governance', '0005_ntai2_llmbudget'),
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PromptTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cle', models.CharField(help_text='Clé de la feature IA surchargée (ex. « ai.rediger.email »).', max_length=120)),
                ('label', models.CharField(blank=True, default='', help_text="Libellé lisible affiché dans l'écran de paramétrage.", max_length=160)),
                ('corps', models.TextField(help_text='Corps du prompt, avec des placeholders {{champ}}.')),
                ('capability', models.CharField(blank=True, default='llm', help_text='Capacité concernée (llm/ocr/stt/vision_qa).', max_length=20)),
                ('actif', models.BooleanField(default=True, help_text="Une surcharge inactive laisse le défaut code s'appliquer.")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Gabarit de prompt',
                'verbose_name_plural': 'Gabarits de prompt',
                'ordering': ['cle'],
                'indexes': [models.Index(fields=['company', 'actif'], name='ai_gov_prompt_co_actif_idx')],
            },
        ),
        migrations.CreateModel(
            name='PromptTemplateVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('numero', models.PositiveIntegerField(default=1)),
                ('corps', models.TextField(blank=True, default='')),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_prompt_versions', to=settings.AUTH_USER_MODEL)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='ai_governance.prompttemplate')),
            ],
            options={
                'verbose_name': 'Version de gabarit de prompt',
                'verbose_name_plural': 'Versions de gabarit de prompt',
                'ordering': ['-numero', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='prompttemplate',
            constraint=models.UniqueConstraint(fields=('company', 'cle'), name='uniq_prompttemplate_co_cle'),
        ),
        migrations.AddConstraint(
            model_name='prompttemplateversion',
            constraint=models.UniqueConstraint(fields=('template', 'numero'), name='uniq_prompttemplateversion_num'),
        ),
    ]
