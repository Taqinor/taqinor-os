"""AGR100 — champs structurés pompage sur ``Produit``.

ADDITIF PUR : cinq colonnes (``role_pompage``, ``type_pompe``,
``alimentation`` à chaîne vide ; ``courbe_source`` à ``{}`` ;
``courbe_frequence_hz`` NULL). Aucune donnée existante n'est réécrite.
RÉVERSIBLE : les cinq ``AddField`` se défont par ``RemoveField`` sans perte
(les colonnes sont neuves).
"""
from django.db import migrations, models


ROLES = [
    'pompe', 'variateur_pompage', 'afficheur_variateur', 'structure_sol',
    'cable_dc', 'cable_descente', 'protection_dc', 'sonde_niveau',
    'compteur_eau', 'colonne_refoulement', 'clapet', 'tuyauterie', 'bassin',
    'installation_pompage', 'entretien_pompage', 'antivol', 'cloture',
]


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0159_calx60_fiche_chaine_pertes'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='role_pompage',
            field=models.CharField(
                blank=True, db_index=True, default='',
                choices=[(r, r) for r in ROLES],
                help_text="Rôle DÉCLARÉ dans une composition pompage (pompe, "
                          "variateur_pompage, sonde_niveau…). Vide = non "
                          "déclaré.",
                max_length=32, verbose_name='Rôle pompage'),
        ),
        migrations.AddField(
            model_name='produit',
            name='type_pompe',
            field=models.CharField(
                blank=True, default='',
                choices=[('immergee', 'immergee'), ('surface', 'surface'),
                         ('dc', 'dc')],
                help_text='Pompes seulement : immergee, surface ou dc.',
                max_length=16),
        ),
        migrations.AddField(
            model_name='produit',
            name='alimentation',
            field=models.CharField(
                blank=True, default='',
                choices=[('mono', 'mono'), ('tri', 'tri'), ('dc', 'dc')],
                help_text='Pompes et variateurs : mono, tri ou dc. Vide = '
                          'non publié.',
                max_length=8),
        ),
        migrations.AddField(
            model_name='produit',
            name='courbe_source',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='Provenance de courbe_pompe : {"document": "", '
                          '"date": null, "page": null}. Document vide = '
                          'source non publiée.'),
        ),
        migrations.AddField(
            model_name='produit',
            name='courbe_frequence_hz',
            field=models.FloatField(
                blank=True, null=True,
                help_text='Fréquence (Hz) de publication de la courbe '
                          'constructeur. null = non publié — jamais '
                          'supposé.'),
        ),
    ]
