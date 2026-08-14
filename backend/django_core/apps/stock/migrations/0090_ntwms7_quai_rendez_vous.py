"""NTWMS7 — quais de réception/expédition et créneaux transporteur.

Deux NOUVEAUX modèles, purement additifs. L'invariant « deux rendez-vous ne se
chevauchent jamais sur le même quai » est appliqué côté serveur dans
``RendezVousTransporteur.save()`` (un simple ``clean()`` n'aurait PAS protégé
un ``objects.create()``), doublé ici d'une contrainte de base ``fin > début``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('installations', '0034_binlocation_binaffectation_and_more'),
        ('stock', '0089_ntwms6_unite_logistique'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quai',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=80)),
                ('type_quai', models.CharField(
                    choices=[('reception', 'Réception'),
                             ('expedition', 'Expédition'),
                             ('mixte', 'Mixte')],
                    default='mixte', max_length=20)),
                ('actif', models.BooleanField(default=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('emplacement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='quais', to='stock.emplacementstock')),
            ],
            options={
                'verbose_name': 'Quai',
                'verbose_name_plural': 'Quais',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='RendezVousTransporteur',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_heure_debut', models.DateTimeField()),
                ('date_heure_fin', models.DateTimeField()),
                ('statut', models.CharField(
                    choices=[('planifie', 'Planifié'), ('arrive', 'Arrivé'),
                             ('en_cours', 'En cours'), ('termine', 'Terminé'),
                             ('no_show', 'Non présenté'),
                             ('annule', 'Annulé')],
                    default='planifie', max_length=20)),
                ('chauffeur_nom', models.CharField(
                    blank=True, default='', max_length=120)),
                ('immatriculation', models.CharField(
                    blank=True, default='', max_length=30)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_arrivee', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('quai', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rendez_vous', to='stock.quai')),
                ('reference_livraison', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rendez_vous_quai',
                    to='installations.livraison')),
                ('transporteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rendez_vous_quai',
                    to='installations.transporteur')),
            ],
            options={
                'verbose_name': 'Rendez-vous transporteur',
                'verbose_name_plural': 'Rendez-vous transporteur',
                'ordering': ['date_heure_debut', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='quai',
            constraint=models.UniqueConstraint(
                fields=('company', 'nom'), name='stock_quai_company_nom_uniq'),
        ),
        migrations.AddIndex(
            model_name='rendezvoustransporteur',
            index=models.Index(
                fields=['company', 'quai', 'date_heure_debut'],
                name='idx_rdvquai_co_quai_debut'),
        ),
        migrations.AddConstraint(
            model_name='rendezvoustransporteur',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    date_heure_fin__gt=models.F('date_heure_debut')),
                name='stock_rdvtransporteur_fin_apres_debut'),
        ),
    ]
