"""SOLMVP30b — retrait du dernier lien GARDÉ → PARQUÉ de ``authentication``.

``CustomUser.poste_ref`` était un FK nullable ``SET_NULL`` vers ``'rh.Poste'``
(string-FK, DC17/FG160) : l'écho, côté compte applicatif, du poste canonique
porté par ``rh.DossierEmploye``. ``rh`` sort du MVP solaire (``core.parked``), et
une app parquée ne peut pas rester pointée par une app gardée — sinon le
``DeleteModel`` de sa coquille casserait l'état Django.

Ce qui part : **la seule colonne de lien** ``customuser.poste_ref_id``. Ce qui
reste intact : la table ``rh_poste`` et toutes ses lignes (la coquille de ``rh``
est ``database_operations=[]``), et la colonne texte LIBRE ``CustomUser.poste``,
qui porte l'intitulé lisible — donc aucun intitulé de poste n'est perdu côté
compte.

Revertable sans perte de donnée métier : ``migrate authentication 0032`` recrée
la colonne (vide), et le rattachement se refait par
``authentication.poste_sync.backfill_poste_ref`` — conservé ici EXPRÈS, la
migration gelée ``0013_customuser_poste_ref`` l'importe encore. Recette de
retour du module : ``docs/parked-modules.md`` §5, étape 4 (AddField dans une
NOUVELLE migration, jamais une réécriture de celle-ci).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customuser',
            name='poste_ref',
        ),
    ]
