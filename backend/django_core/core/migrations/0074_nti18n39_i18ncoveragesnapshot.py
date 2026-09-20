"""NTI18N39 — instantané hebdomadaire de la couverture i18n de l'interface.

Table NEUVE, purement ADDITIVE, écrite À LA MAIN (aucun `makemigrations` sur
cette lane) ; l'état Django est l'équivalent exact de ce que `makemigrations`
produirait pour ``core.models.I18nCoverageSnapshot``. Aucune donnée n'est
écrite : sans ligne, l'écran NTI18N28 continue de lire le rapport JSON committé
comme avant.

``company`` vient de ``core.models.TenantModel`` : son ``related_name`` est le
TEMPLATE ``'%(app_label)s_%(class)s_set'``, écrit ici TEL QUEL (jamais résolu
en ``core_i18ncoveragesnapshot_set``) — sinon le modèle et l'état de migration
divergent et ``makemigrations --check`` rougit en CI. ``created_at`` /
``updated_at`` viennent de ``TimestampedModel``, la PK est un ``BigAutoField``.

Entièrement revertable (suppression d'une table neuve et vide).
"""
import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0073_ntobs25_slasnapshot_recalcul'),
        ('authentication', '0013_customuser_poste_ref'),
    ]

    operations = [
        migrations.CreateModel(
            name='I18nCoverageSnapshot',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('semaine', models.DateField(
                    help_text='Lundi de la semaine ISO couverte par la '
                              'mesure.',
                    verbose_name='Semaine (lundi)')),
                ('calcule_le', models.DateTimeField(
                    default=timezone.now, verbose_name='Calculé le')),
                ('couverture_pct', models.DecimalField(
                    decimal_places=1, max_digits=5,
                    help_text='Part des composants de page migrés vers '
                              'useI18n/useT.',
                    verbose_name='Couverture (%)')),
                ('composants_total', models.PositiveIntegerField(
                    default=0, verbose_name='Composants de page')),
                ('composants_migres', models.PositiveIntegerField(
                    default=0, verbose_name='Composants migrés')),
                ('chaines_en_dur', models.PositiveIntegerField(
                    default=0, verbose_name='Chaînes en dur restantes')),
                ('par_domaine', models.JSONField(
                    blank=True, default=dict,
                    help_text='Rapport par domaine (crm/ventes/stock…) tel '
                              'que produit par '
                              'scripts/extract_i18n_strings.py — jamais '
                              'recalculé ici.',
                    verbose_name='Détail par domaine')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Couverture i18n (instantané)',
                'verbose_name_plural': 'Couverture i18n (instantanés)',
                'ordering': ['-semaine'],
            },
        ),
        migrations.AddConstraint(
            model_name='i18ncoveragesnapshot',
            constraint=models.UniqueConstraint(
                fields=('company', 'semaine'),
                name='core_i18ncoverage_co_semaine'),
        ),
    ]
