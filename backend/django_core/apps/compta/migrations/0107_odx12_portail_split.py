# ODX12 — sortie du portail self-service client (FG228–233) de compta vers
# ``apps.portail`` en STATE-ONLY : compta retire les modèles de l'état
# (SeparateDatabaseAndState, zéro SQL) AVANT que portail 0001 ne les recrée dans
# l'état sur les MÊMES tables (db_table='compta_<model>'). Aucune donnée
# déplacée ; aucun élargissement d'accès (surface AUTH conservée à l'identique).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0106_odx11_ao_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # 1) Retirer d'abord toutes les FK (company + client crm).
                migrations.RemoveField(
                    model_name='compteportailclient',
                    name='client',
                ),
                migrations.RemoveField(
                    model_name='compteportailclient',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='acceptationdevisportail',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='paiementfactureportail',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='documentclientportail',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='jalonchantierportail',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='demandeticketportail',
                    name='company',
                ),
                # 2) Puis supprimer les modèles de l'état compta.
                migrations.DeleteModel(
                    name='DemandeTicketPortail',
                ),
                migrations.DeleteModel(
                    name='JalonChantierPortail',
                ),
                migrations.DeleteModel(
                    name='DocumentClientPortail',
                ),
                migrations.DeleteModel(
                    name='PaiementFacturePortail',
                ),
                migrations.DeleteModel(
                    name='AcceptationDevisPortail',
                ),
                migrations.DeleteModel(
                    name='ComptePortailClient',
                ),
            ],
            database_operations=[],
        ),
    ]
