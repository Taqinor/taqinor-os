# FG25 — politiques d'approbation configurables (ApprovalPolicy).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('parametres', '0026_fg22_password_policy'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprovalPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('discount', 'Remise sur devis'), ('quote_amount', 'Montant de devis'), ('purchase_order', 'Bon de commande fournisseur'), ('expense', 'Dépense / frais'), ('contract', 'Contrat'), ('refund', 'Avoir / remboursement')], max_length=20)),
                ('seuil', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('approver_tier', models.CharField(choices=[('responsable', 'Responsable (ou plus)'), ('admin', 'Administrateur uniquement')], default='admin', max_length=20)),
                ('enabled', models.BooleanField(default=True)),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approval_policies', to='authentication.company')),
            ],
            options={
                'verbose_name': "Politique d'approbation",
                'verbose_name_plural': "Politiques d'approbation",
                'ordering': ['action_type', 'id'],
                'unique_together': {('company', 'action_type')},
            },
        ),
        migrations.AddIndex(
            model_name='approvalpolicy',
            index=models.Index(fields=['company', 'action_type', 'enabled'], name='param_apprpol_idx'),
        ),
    ]
