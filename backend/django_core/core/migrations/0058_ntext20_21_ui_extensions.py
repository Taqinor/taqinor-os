"""NTEXT20/NTEXT21 — points d'extension UI déclaratifs (boutons + onglets
custom). Purement ADDITIF : deux nouvelles tables, aucun impact sur
l'existant tant qu'un admin n'en pose aucune ligne.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('core', '0057_ntapi2_apideprecation'),
    ]

    operations = [
        migrations.CreateModel(
            name='UiActionBouton',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('cible', models.CharField(
                    help_text='Nom de fiche visé, ex. « crm.lead », '
                              '« ventes.devis ».',
                    max_length=80, verbose_name='Cible')),
                ('libelle', models.CharField(
                    max_length=120, verbose_name='Libellé')),
                ('icone', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Icône')),
                ('type_action', models.CharField(
                    choices=[('automation', 'Automatisation'),
                             ('webhook', 'Webhook'),
                             ('server_action', 'Action serveur')],
                    max_length=20)),
                ('ref', models.PositiveIntegerField(
                    help_text="Id de la règle d'automatisation / de "
                              "l'abonnement webhook / de l'action serveur "
                              "lié(e).",
                    verbose_name='Référence')),
                ('role_tier', models.CharField(
                    blank=True, default='',
                    help_text='Vide = visible de tous les paliers.',
                    max_length=40, verbose_name='Palier de rôle')),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ui_action_boutons',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Bouton personnalisé',
                'verbose_name_plural': 'Boutons personnalisés',
                'ordering': ['cible', 'ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='uiactionbouton',
            index=models.Index(
                fields=['company', 'cible', 'actif'],
                name='core_uiactionbouton_idx'),
        ),
        migrations.CreateModel(
            name='UiOngletCustom',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('cible', models.CharField(
                    max_length=80, verbose_name='Cible')),
                ('titre', models.CharField(
                    max_length=120, verbose_name='Titre')),
                ('type_contenu', models.CharField(
                    choices=[('objet_custom_lie', 'Objet personnalisé lié'),
                             ('rapport', 'Rapport'), ('html', 'HTML')],
                    max_length=20)),
                ('ref', models.CharField(
                    blank=True, default='',
                    help_text="Code de l'objet personnalisé lié / id du "
                              "rapport / contenu HTML selon type_contenu.",
                    max_length=120, verbose_name='Référence')),
                ('condition', models.JSONField(blank=True, null=True)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('role_tier', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Palier de rôle')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ui_onglets_custom',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Onglet personnalisé',
                'verbose_name_plural': 'Onglets personnalisés',
                'ordering': ['cible', 'ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='uiongletcustom',
            index=models.Index(
                fields=['company', 'cible', 'actif'],
                name='core_uiongletcustom_idx'),
        ),
    ]
