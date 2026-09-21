"""SOLMVP14 — Détacher sav des apps parquées (contrats/pos/rh/kb/litiges/grc).

Seul changement de SCHÉMA du détachement : `CategorieTicket.competences_
requises` était un ManyToMany string-FK vers `rh.Competence` (NTSRV6) — la
feature « compétences RH exigées par catégorie » (NTSRV6/NTSRV7/NTSRV43) est
retirée avec elle, donc `niveau_competence_min` (qui n'avait plus de sens
sans compétence à comparer) part aussi. `SavSlaSettings.affectation_par_
competence` pilotait UNIQUEMENT ce filtrage par compétence RH (NTSRV7) et
devient orpheline sans lui.

Destructif-revertable (règle CLAUDE.md : seules les colonnes de LIEN/du
feature retiré partent) : aucune table métier SAV n'est supprimée, aucune
ligne `django_migrations` touchée. Les appels function-local vers
apps.contrats/pos/rh/kb/litiges/grc (facturation de contrat, capture de
série côté vente comptoir, escalade en réclamation, suggestions KB, rétention
GRC) sont retirés côté code — voir services.py/views.py/maintenance.py/
receivers.py/selectors.py — sans migration associée. `Ticket.reclamation_id_
ext` (loose FK entier, AUD529) est CONSERVÉ (pas une colonne de lien
cross-app) ; seul son `help_text` est réécrit (l'action qui l'écrivait a été
retirée), d'où l'AlterField ci-dessous."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0063_ntprt12_ticketactivity_visible_client'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='categorieticket',
            name='competences_requises',
        ),
        migrations.RemoveField(
            model_name='categorieticket',
            name='niveau_competence_min',
        ),
        migrations.RemoveField(
            model_name='savslasettings',
            name='affectation_par_competence',
        ),
        migrations.AlterField(
            model_name='ticket',
            name='reclamation_id_ext',
            field=models.IntegerField(
                blank=True, null=True,
                help_text="ID d'une réclamation externe ouverte depuis ce "
                          "ticket (champ historique — action d'escalade "
                          'retirée).'),
        ),
    ]
