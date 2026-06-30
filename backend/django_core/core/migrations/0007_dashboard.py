# FG381 — Constructeur de graphiques/dashboards sans-code (drag-and-drop).
#
# Ajoute ``Dashboard`` : persiste un dashboard sauvegardé par utilisateur/
# société. ``layout`` est un JSON OPAQUE — AUCUN import d'app métier (contrat
# import-linter ``core-foundation-is-a-base-layer``). Migration ADDITIVE et
# réversible.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('core', '0006_webhooksubscription'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Dashboard',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(
                    max_length=160, verbose_name='Titre')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('layout', models.JSONField(
                    blank=True, default=dict,
                    help_text='Widgets + disposition + specs de données '
                              '(opaque pour core).',
                    verbose_name='Configuration')),
                ('partage', models.BooleanField(
                    default=False,
                    help_text='Visible par toute la société (sinon '
                              'personnel).',
                    verbose_name='Partagé')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dashboards',
                    to='authentication.company', verbose_name='Société')),
                ('owner', models.ForeignKey(
                    blank=True, null=True,
                    help_text='Vide = dashboard de société (non personnel).',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dashboards',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Propriétaire')),
            ],
            options={
                'verbose_name': 'Dashboard',
                'verbose_name_plural': 'Dashboards',
                'ordering': ['titre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='dashboard',
            index=models.Index(
                fields=['company', 'owner'],
                name='core_dashboard_co_owner_idx'),
        ),
        migrations.AddIndex(
            model_name='dashboard',
            index=models.Index(
                fields=['company', 'partage'],
                name='core_dashboard_co_part_idx'),
        ),
    ]
