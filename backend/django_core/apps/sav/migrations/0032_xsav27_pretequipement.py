# XSAV27 — Prêt / échange anticipé d'équipement (loaner) : unité sortie du
# stock vers le client pendant qu'un onduleur/une pompe part en réparation
# fournisseur, avec mouvements de stock SORTIE/ENTRÉE et alerte dépassement.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('stock', '0001_initial'),
        ('sav', '0031_xfsm15_recidive'),
    ]

    operations = [
        migrations.CreateModel(
            name='PretEquipement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('numero_serie', models.CharField(
                    blank=True, default='', max_length=120)),
                ('statut', models.CharField(
                    choices=[('en_cours', 'En cours'),
                             ('retourne', 'Retourné')],
                    default='en_cours', max_length=15)),
                ('date_sortie', models.DateField(blank=True, null=True)),
                ('date_retour_prevue', models.DateField(blank=True, null=True)),
                ('date_retour_reelle', models.DateField(blank=True, null=True)),
                ('stock_sorti', models.BooleanField(default=False)),
                ('stock_reintegre', models.BooleanField(default=False)),
                ('alerte_depassement_notifiee', models.BooleanField(default=False)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='prets_equipement', to='authentication.company')),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='prets_equipement', to='sav.ticket')),
                ('produit', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='prets_equipement_sav', to='stock.produit')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Prêt équipement',
                'verbose_name_plural': 'Prêts équipement',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='pretequipement',
            index=models.Index(
                fields=['company', 'ticket'],
                name='sav_pret_equip_co_tick_idx'),
        ),
        migrations.AddIndex(
            model_name='pretequipement',
            index=models.Index(
                fields=['company', 'statut'],
                name='sav_pret_equip_co_statut_idx'),
        ),
    ]
