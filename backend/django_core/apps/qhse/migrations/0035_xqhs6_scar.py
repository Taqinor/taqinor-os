import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0034_xqhs5_campagne_rappel'),
        ('stock', '0040_fournisseur_custom_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeActionFournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description_defaut', models.TextField(blank=True, default='', verbose_name='Description du défaut')),
                ('echeance_reponse', models.DateField(blank=True, null=True, verbose_name='Échéance de réponse')),
                ('cause_racine_fournisseur', models.TextField(blank=True, default='', verbose_name='Cause racine (fournisseur)')),
                ('action_fournisseur', models.TextField(blank=True, default='', verbose_name='Action corrective (fournisseur)')),
                ('preuve_attachment_ids', models.JSONField(blank=True, default=list, verbose_name='IDs pièces jointes preuve')),
                ('statut', models.CharField(choices=[('emise', 'Émise'), ('repondue', 'Répondue'), ('verifiee', 'Vérifiée'), ('close', 'Close')], default='emise', max_length=10, verbose_name='Statut')),
                ('date_reponse', models.DateTimeField(blank=True, null=True, verbose_name='Répondue le')),
                ('efficace', models.BooleanField(blank=True, null=True, verbose_name='Efficace (vérification)')),
                ('date_verification', models.DateTimeField(blank=True, null=True, verbose_name='Vérifiée le')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_scar', to='authentication.company', verbose_name='Société')),
                ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_scar', to='stock.fournisseur', verbose_name='Fournisseur')),
                ('ncr_source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scar', to='qhse.nonconformite', verbose_name='NCR source')),
                ('verifiee_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_scar_verifiees', to=settings.AUTH_USER_MODEL, verbose_name='Vérifiée par')),
            ],
            options={
                'verbose_name': "Demande d'action corrective fournisseur (SCAR)",
                'verbose_name_plural': "Demandes d'action corrective fournisseur (SCAR)",
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='demandeactionfournisseur',
            index=models.Index(fields=['company', 'fournisseur', 'statut'], name='qhse_scar_co_fourn_statut'),
        ),
    ]
