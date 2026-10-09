# AFAC17 (C-AFAC-013, D-AFAC-C2 a) — annulation d'une saisie de paiement
# erronée : nouveau choix de statut `annule_saisie` + trace datée (annule_le,
# annule_par, motif_annulation). Additif et revertable (choix + champs
# nullables / à défaut vide).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('facturation', '0019_merge_afac_enf13'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paiement',
            name='statut',
            field=models.CharField(
                choices=[('encaisse', 'Encaissé'), ('rejete', 'Rejeté'),
                         ('annule_saisie', 'Annulé (erreur de saisie)')],
                default='encaisse', max_length=20),
        ),
        migrations.AddField(
            model_name='paiement',
            name='annule_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='paiement',
            name='annule_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='paiements_annules_saisie',
                to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='paiement',
            name='motif_annulation',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
