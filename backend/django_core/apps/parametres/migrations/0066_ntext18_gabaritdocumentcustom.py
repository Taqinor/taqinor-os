"""NTEXT18 — gabarits de document custom (additif, réversible).

Aucun lien avec ``parametres.DocumentTemplates`` (singleton PRÉEXISTANT des
textes du devis premium) : nouvelle table indépendante.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('parametres', '0065_wir24_comptabilite_auto_ecritures'),
    ]

    operations = [
        migrations.CreateModel(
            name='GabaritDocumentCustom',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.SlugField(
                    help_text='Identifiant stable, ex. '
                              '« fiche_visite_chantier ».',
                    max_length=60, verbose_name='Code')),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('cible', models.CharField(
                    choices=[('chantier', 'Chantier'), ('client', 'Client'),
                             ('ticket', 'Ticket SAV'),
                             ('objet_custom', 'Objet personnalisé')],
                    help_text="Type d'objet documenté. La cible « devis » est "
                              'interdite (règle #4 : le devis client passe par '
                              '/proposal).',
                    max_length=20, verbose_name='Cible')),
                ('corps', models.TextField(
                    blank=True, default='',
                    help_text='HTML avec placeholders ``{{ variable }}``.',
                    verbose_name='Corps HTML')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Gabarit de document',
                'verbose_name_plural': 'Gabarits de document',
                'ordering': ['cible', 'code', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='gabaritdocumentcustom',
            index=models.Index(
                fields=['company', 'cible', 'actif'],
                name='param_gabaritdoc_idx'),
        ),
        migrations.AddConstraint(
            model_name='gabaritdocumentcustom',
            constraint=models.UniqueConstraint(
                fields=('company', 'code'),
                name='parametres_gabaritdoc_co_code'),
        ),
    ]
