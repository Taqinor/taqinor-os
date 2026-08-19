"""PVOND-H (fondateur 19/08/2026) — trois variables ONDULEUR que le moteur
électrique (core.electrique.types.SpecOnduleur) sait déjà lire mais qui
n'avaient AUCUN champ dédié sur FicheTechnique :

  * la plage de tension batterie (ond_bat_aucune / ond_bat_v_min /
    ond_bat_v_max) vivait en texte libre dans Produit.description (ligne
    « Plage batterie : … », cf. apps/stock/selectors.py::
    plage_batterie_onduleur) — qui garde son repli sur cette ligne pour une
    fiche pas encore migrée, jamais de régression ;
  * tension de démarrage (ond_v_demarrage_v) et Isc max par MPPT
    (ond_isc_max_mppt_a) n'étaient nulle part, seedées en COMMENTAIRE
    (« NON seedés faute de champ ») faute d'un endroit où les saisir.

Additif pur, tout nullable/blank (ond_bat_aucune excepté, BooleanField
default=False) : aucune fiche existante n'est impactée, aucune donnée
migrée ici — seed_catalogue.py comble les valeurs sourcées au prochain
déploiement (même patron que PV85/PVG4)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0121_dyness_orthographe_marque'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_bat_aucune',
            field=models.BooleanField(default=False, help_text='Déclaration explicite : cet onduleur ne prend AUCUNE batterie (réseau / string on-grid). Prioritaire sur la plage min/max ci-dessous.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_bat_v_max',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Plage de tension batterie compatible — borne haute (V). Onduleur hybride uniquement.', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_bat_v_min',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Plage de tension batterie compatible — borne basse (V). Onduleur hybride uniquement.', max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_isc_max_mppt_a',
            field=models.DecimalField(blank=True, decimal_places=1, help_text="Courant de court-circuit (Isc) maximal admissible par entrée MPPT (A) — borne matérielle, distincte du courant maximal de fonctionnement ci-dessus. À défaut, c'est ce dernier qui fait foi.", max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_v_demarrage_v',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Tension de démarrage (V). À défaut, le bas de la plage MPPT fait foi.', max_digits=6, null=True),
        ),
    ]
