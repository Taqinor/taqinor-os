"""NTWFL1 — matrice d'approbation d'entreprise unifiée (additive, réversible).

Nouveau modèle ``MatriceApprobation`` : objet × montant × département →
chaîne de paliers ordonnée. Référentiel ADDITIF consulté en premier par
``parametres.ApprovalPolicy.requires_approval`` et
``apps.contrats.services.lancer_workflow_approbation`` avant leur logique
historique (repli inchangé sans ligne correspondante).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0048_aud820_sharingrule_unique'),
    ]

    operations = [
        migrations.CreateModel(
            name='MatriceApprobation',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_objet', models.CharField(
                    help_text=(
                        "Valeur libre alignée par convention sur "
                        "parametres.ApprovalPolicy.ActionType ou sur le "
                        "nom d'un automation.ApprovalRequestType — jamais "
                        "dupliquée ici."),
                    max_length=40, verbose_name="Type d'objet")),
                ('departement', models.CharField(
                    blank=True, default='',
                    help_text='Libellé libre (aligné sur roles.Role/service '
                              "RH). Vide = s'applique à tous les "
                              'départements.',
                    max_length=80, verbose_name='Département')),
                ('montant_min', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    help_text='NULL = borne non fixée (ouverte de ce côté).',
                    verbose_name='Montant minimum')),
                ('montant_max', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    help_text='NULL = borne non fixée (ouverte de ce côté).',
                    verbose_name='Montant maximum')),
                ('chaine_paliers', models.JSONField(
                    blank=True, default=list,
                    help_text='Liste ordonnée de {palier, '
                              'nombre_approbateurs_requis, role_requis}.',
                    verbose_name='Chaîne de paliers')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': "Matrice d'approbation",
                'verbose_name_plural': "Matrices d'approbation",
                'ordering': ['type_objet', 'departement', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='matriceapprobation',
            index=models.Index(
                fields=['company', 'type_objet', 'actif'],
                name='core_matappr_co_typ_act_idx'),
        ),
    ]
