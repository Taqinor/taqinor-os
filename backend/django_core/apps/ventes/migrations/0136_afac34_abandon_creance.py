"""AFAC34 (D-AFAC-C6) — ``AbandonCreance`` : l'abandon de créance devient un
enregistrement daté, cumulable et réversible.

ADDITIF : un modèle neuf ; les champs ``Facture.abandon_*`` restent (aucune
suppression). Données : chaque facture dont ``abandon_montant > 0`` reçoit UN
enregistrement qui le recopie (motif, auto, auteur, date). Réversible : le
reverse recopie la somme des abandons ACTIFS dans ``abandon_montant`` puis le
modèle disparaît (revenir à ventes 0135).
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def recopier_abandons(apps, schema_editor):
    Facture = apps.get_model('facturation', 'Facture')
    AbandonCreance = apps.get_model('ventes', 'AbandonCreance')
    now = django.utils.timezone.now()
    for f in Facture.objects.filter(abandon_montant__gt=0).iterator():
        AbandonCreance.objects.create(
            company_id=f.company_id, facture_id=f.pk,
            montant=f.abandon_montant, motif=f.abandon_motif or '',
            auto=bool(f.abandon_auto), created_by_id=f.abandon_par_id,
            date_abandon=f.abandon_date or now)


def remettre_somme(apps, schema_editor):
    from decimal import Decimal
    Facture = apps.get_model('facturation', 'Facture')
    AbandonCreance = apps.get_model('ventes', 'AbandonCreance')
    sommes = {}
    for a in AbandonCreance.objects.filter(annule_le__isnull=True):
        sommes[a.facture_id] = sommes.get(a.facture_id, Decimal('0')) + a.montant
    for fid in set(AbandonCreance.objects.values_list('facture_id', flat=True)):
        Facture.objects.filter(pk=fid).update(
            abandon_montant=sommes.get(fid, Decimal('0')))


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('facturation', '0014_atot6_avoir_ventilation_tva'),
        ('ventes', '0135_merge_adev33_atot12'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AbandonCreance',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('montant', models.DecimalField(
                    decimal_places=2, max_digits=12)),
                ('motif', models.CharField(
                    blank=True, default='', max_length=20)),
                ('auto', models.BooleanField(default=False)),
                ('date_abandon', models.DateTimeField(
                    default=django.utils.timezone.now)),
                ('annule_le', models.DateTimeField(blank=True, null=True)),
                ('motif_reprise', models.TextField(blank=True, default='')),
                ('annule_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='abandons_creance_repris',
                    to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='abandons_creance',
                    to='authentication.company')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='abandons_creance_crees',
                    to=settings.AUTH_USER_MODEL)),
                ('facture', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='abandons_creance',
                    to='facturation.facture')),
            ],
            options={
                'verbose_name': 'Abandon de créance',
                'verbose_name_plural': 'Abandons de créance',
                'ordering': ['date_abandon', 'id'],
            },
        ),
        migrations.RunPython(recopier_abandons, remettre_somme),
    ]
