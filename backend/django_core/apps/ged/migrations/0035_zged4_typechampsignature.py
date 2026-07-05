import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('ged', '0034_zged2_signataire_auth_extra_otp'),
    ]

    operations = [
        migrations.CreateModel(
            name='TypeChampSignature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, verbose_name='code')),
                ('libelle', models.CharField(max_length=100, verbose_name='libellé')),
                ('mode_saisie', models.CharField(choices=[('texte', 'Texte'), ('multiligne', 'Texte multiligne'), ('case', 'Case à cocher'), ('selection', 'Sélection'), ('signature', 'Signature'), ('initiales', 'Initiales'), ('date', 'Date')], default='texte', max_length=12, verbose_name='mode de saisie')),
                ('largeur_defaut', models.DecimalField(decimal_places=2, default=20, max_digits=5, verbose_name='largeur par défaut (%)')),
                ('hauteur_defaut', models.DecimalField(decimal_places=2, default=5, max_digits=5, verbose_name='hauteur par défaut (%)')),
                ('placeholder', models.CharField(blank=True, default='', max_length=200)),
                ('astuce', models.CharField(blank=True, default='', max_length=300, verbose_name='astuce')),
                ('options', models.JSONField(blank=True, default=list, null=True)),
                ('auto_remplir', models.CharField(blank=True, choices=[('', 'Aucun'), ('nom', 'Nom du partenaire'), ('email', 'Email du partenaire'), ('telephone', 'Téléphone du partenaire'), ('societe', 'Société du partenaire')], default='', max_length=10, verbose_name='auto-remplissage partenaire')),
                ('lecture_seule', models.BooleanField(default=False, verbose_name='lecture seule')),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ged_types_champ_signature', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_types_champ_signature_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Type de champ de signature',
                'verbose_name_plural': 'Types de champ de signature',
                'ordering': ['libelle', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='typechampsignature',
            index=models.Index(fields=['company', 'code'], name='ged_typechamp_co_code_idx'),
        ),
        migrations.AddConstraint(
            model_name='typechampsignature',
            constraint=models.UniqueConstraint(fields=('company', 'code'), name='ged_typechamp_co_code_unique'),
        ),
        migrations.AddField(
            model_name='champsignature',
            name='type_champ_ref',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='champs_signature', to='ged.typechampsignature', verbose_name='type de champ personnalisé'),
        ),
    ]
