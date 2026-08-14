# NTRET7 — cycle physique du transfert en deux temps (demande → expédié → reçu).
# Additive : `statut` naît à RECU, donc TOUT transfert direct historique (N15)
# est déjà terminé et son comportement reste strictement inchangé.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0115_ntdst14_stock_vehicule'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='transfertstock',
            name='statut',
            field=models.CharField(choices=[('demande', 'Demandé'), ('expedie', 'Expédié'), ('recu', 'Reçu'), ('annule', 'Annulé')], default='recu', max_length=20),
        ),
        migrations.AddField(
            model_name='transfertstock',
            name='reference',
            field=models.CharField(blank=True, default='', help_text='Référence du bon de transfert (cycle en deux temps).', max_length=50),
        ),
        migrations.AddField(
            model_name='transfertstock',
            name='quantite_recue',
            field=models.PositiveIntegerField(blank=True, help_text="Quantité réellement comptée à la réception (vide tant qu'elle n'a pas eu lieu).", null=True),
        ),
        migrations.AddField(
            model_name='transfertstock',
            name='date_expedition',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transfertstock',
            name='date_reception',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transfertstock',
            name='expedie_par',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transferts_expedies', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='transfertstock',
            name='recu_par',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transferts_recus', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='transfertstock',
            constraint=models.UniqueConstraint(condition=models.Q(('reference', ''), _negated=True), fields=('company', 'reference'), name='stock_transfertstock_company_reference_uniq'),
        ),
    ]
