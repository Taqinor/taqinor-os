"""NTI18N18 — plan comptable OHADA / SYSCOHADA révisé (pack pays SN_CI).

Table NEUVE, purement ADDITIVE, écrite À LA MAIN. Aucune écriture du grand
livre n'est touchée : ``EcritureComptable`` et ``LigneEcriture`` gardent leur
FK vers ``CompteComptable``/``PlanComptable`` (CGNC) à l'identique, et aucune
donnée n'est écrite par cette migration. Une société sans ligne dans cette
table se comporte EXACTEMENT comme avant — c'est le cas de toutes les
sociétés existantes (marocaines).

``actif`` vaut False par défaut : activer le plan OHADA est une décision
d'expansion (règle DECISION de la tâche), jamais un effet de bord d'une
migration. La correspondance compte CGNC ↔ compte OHADA n'est PAS semée ici :
elle attend la validation fondateur (voir ``docs/ohada-mapping.md``).

``company`` vient de ``core.models.TenantModel`` (socle ARC1/SCA4 — un modèle
NEUF n'a plus le droit de ré-écrire la paire multi-société à la main, garde
``scripts/check_platform.py``) : son ``related_name`` est le TEMPLATE
``'%(app_label)s_%(class)s_set'``, écrit ici TEL QUEL (jamais résolu en
``compta_plancomptableohada_set``) — sinon le modèle et l'état de migration
divergent et ``makemigrations --check`` rougit en CI. ``created_at`` /
``updated_at`` viennent de ``TimestampedModel``.

Entièrement revertable (suppression d'une table neuve et vide).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0127_piecejustificative_fichier_filename_and_more'),
        ('authentication', '0013_customuser_poste_ref'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanComptableOHADA',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('numero', models.CharField(
                    max_length=20, verbose_name='Numéro de compte')),
                ('intitule', models.CharField(
                    max_length=200, verbose_name='Intitulé')),
                ('classe', models.IntegerField(
                    choices=[
                        (1, '1 — Ressources durables'),
                        (2, '2 — Actif immobilisé'),
                        (3, '3 — Stocks'),
                        (4, '4 — Tiers'),
                        (5, '5 — Trésorerie'),
                        (6, '6 — Charges des activités ordinaires'),
                        (7, '7 — Produits des activités ordinaires'),
                        (8, '8 — Autres charges et autres produits'),
                    ],
                    verbose_name='Classe SYSCOHADA')),
                ('compte_cgnc_equivalent', models.CharField(
                    blank=True, default='', max_length=20,
                    help_text='Vide = correspondance NON validée par le '
                              'fondateur (voir docs/ohada-mapping.md). '
                              'Jamais une équivalence supposée.',
                    verbose_name='Compte CGNC équivalent')),
                ('est_tiers', models.BooleanField(
                    default=False, verbose_name='Compte de tiers')),
                ('lettrable', models.BooleanField(
                    default=False, verbose_name='Lettrable')),
                ('actif', models.BooleanField(
                    default=False,
                    help_text="Défaut False : activer le plan OHADA est une "
                              "décision d'expansion, jamais un effet de bord "
                              "d'une migration.",
                    verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Compte du plan OHADA',
                'verbose_name_plural': 'Plan comptable OHADA',
                'ordering': ['numero'],
            },
        ),
        migrations.AddConstraint(
            model_name='plancomptableohada',
            constraint=models.UniqueConstraint(
                fields=('company', 'numero'),
                name='uniq_compte_ohada_par_societe'),
        ),
    ]
