"""R3 (fondateur, 28/10/2026) — fiche C&I : calibre du comptage et nature du
produit de supervision.

ADDITIF : ``lim_calibre_a`` (NULL = non publié) et ``log_type`` (chaîne vide =
non publié) ajoutés ; le choix ``compteur_tc_externe`` rejoint ``lim_mode``
(compteur dont les TC sont fournis à part, sans calibre borné). Aucune donnée
existante n'est réécrite. RÉVERSIBLE : ``RemoveField`` des deux colonnes
neuves, et l'``AlterField`` des choix revient à la liste de CIQ101.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0176_ccat_fiches_client'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fichetechnique', name='lim_mode',
            field=models.CharField(
                blank=True, default='', max_length=24,
                choices=[('compteur_direct', 'compteur_direct'),
                         ('compteur_tc', 'compteur_tc'),
                         ('controleur', 'controleur'),
                         ('compteur_tc_externe', 'compteur_tc_externe')],
                help_text='Limiteur — mode de raccordement (vide = non publié).'),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='lim_calibre_a',
            field=models.FloatField(
                blank=True, null=True,
                help_text="Limiteur — calibre du comptage (A) : courant maxi au "
                          "point d'injection, TC compris (vide = non publié ; "
                          "compteur à TC externes = sans borne)."),
        ),
        migrations.AddField(
            model_name='fichetechnique', name='log_type',
            field=models.CharField(
                blank=True, default='', max_length=16,
                choices=[('dongle', 'dongle'), ('logger', 'logger')],
                help_text='Logger — dongle (clé wifi, une par onduleur) ou '
                          'logger central (vide = non publié).'),
        ),
    ]
