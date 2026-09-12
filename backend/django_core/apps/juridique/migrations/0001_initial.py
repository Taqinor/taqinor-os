"""NTJUR1 — création du module ``juridique`` : ``DossierJuridique``.

Migration ADDITIVE (nouvelle table, aucune donnée existante touchée).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0030_aud704_identite_employeur'),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierJuridique',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(
                    blank=True, default='', max_length=50,
                    verbose_name='Référence')),
                ('titre', models.CharField(
                    max_length=255, verbose_name='Titre')),
                ('nature', models.CharField(
                    choices=[('contentieux', 'Contentieux'),
                             ('precontentieux', 'Précontentieux'),
                             ('consultatif', 'Consultatif'),
                             ('recouvrement', 'Recouvrement')],
                    default='contentieux', max_length=20,
                    verbose_name='Nature')),
                ('type_procedure', models.CharField(
                    choices=[('civil', 'Civil'), ('commercial', 'Commercial'),
                             ('social', 'Social'), ('penal', 'Pénal'),
                             ('administratif', 'Administratif'),
                             ('arbitrage', 'Arbitrage')],
                    default='civil', max_length=20,
                    verbose_name='Type de procédure')),
                ('juridiction_nom', models.CharField(
                    blank=True, default='', max_length=200,
                    verbose_name='Juridiction')),
                ('juridiction_ville', models.CharField(
                    blank=True, default='', max_length=120,
                    verbose_name='Ville de la juridiction')),
                ('juridiction_degre', models.CharField(
                    choices=[('premiere_instance', 'Première instance'),
                             ('appel', 'Appel'), ('cassation', 'Cassation')],
                    default='premiere_instance', max_length=20,
                    verbose_name='Degré de juridiction')),
                ('montant_en_jeu', models.DecimalField(
                    decimal_places=2, default=0, max_digits=14,
                    verbose_name='Montant en jeu')),
                ('partie_adverse_nom', models.CharField(
                    blank=True, default='', max_length=200,
                    verbose_name='Partie adverse')),
                ('notre_position', models.CharField(
                    choices=[('demandeur', 'Demandeur'),
                             ('defendeur', 'Défendeur')],
                    default='defendeur', max_length=15,
                    verbose_name='Notre position')),
                ('resume_faits', models.TextField(
                    blank=True, default='',
                    verbose_name='Résumé des faits')),
                ('date_ouverture', models.DateField(
                    verbose_name="Date d'ouverture")),
                ('confidentialite', models.CharField(
                    choices=[('public', 'Public'), ('interne', 'Interne'),
                             ('confidentiel', 'Confidentiel')],
                    default='interne', max_length=20,
                    verbose_name='Confidentialité')),
                ('statut', models.CharField(
                    choices=[('ouvert', 'Ouvert'),
                             ('instruction', 'En instruction'),
                             ('audience_programmee', 'Audience programmée'),
                             ('en_delibere', 'En délibéré'),
                             ('jugement_rendu', 'Jugement rendu'),
                             ('appel', 'En appel'),
                             ('execution', 'En exécution'),
                             ('clos_gagne', 'Clos — gagné'),
                             ('clos_perdu', 'Clos — perdu'),
                             ('clos_transaction', 'Clos — transaction'),
                             ('clos_desistement', 'Clos — désistement')],
                    default='ouvert', max_length=25,
                    verbose_name='Statut')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_dossierjuridique_set',
                    to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='dossiers_juridiques_crees',
                    to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
                ('responsable_interne', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='dossiers_juridiques',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Responsable interne')),
            ],
            options={
                'verbose_name': 'Dossier juridique',
                'verbose_name_plural': 'Dossiers juridiques',
                'ordering': ['-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='dossierjuridique',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='juridique_dossier_co_ref_uniq'),
        ),
    ]
