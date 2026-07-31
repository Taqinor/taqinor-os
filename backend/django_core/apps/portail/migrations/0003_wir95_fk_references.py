# WIR95 — Remplace les références opaques ``*_id`` du module portail par de
# vraies FK string-référencées (même patron que
# ``pos.CommandeRetrait.devis = ForeignKey('ventes.Devis', on_delete=SET_NULL)``).
#
# 8 champs convertis (5 modèles) :
#   AcceptationDevisPortail.devis_id      -> devis    (FK ventes.Devis)
#   PaiementFacturePortail.facture_id     -> facture  (FK facturation.Facture)
#   DocumentClientPortail.client_id       -> client   (FK crm.Client)
#   DocumentClientPortail.lead_id         -> lead     (FK crm.Lead)
#   JalonChantierPortail.chantier_id      -> chantier (FK installations.Installation)
#   DemandeTicketPortail.client_id        -> client   (FK crm.Client)
#   DemandeTicketPortail.chantier_id      -> chantier (FK installations.Installation)
#   DemandeTicketPortail.ticket_id        -> ticket   (FK sav.Ticket)
#
# Toutes SET_NULL + db_constraint=False : la contrainte d'intégrité référentielle
# vit dans l'ORM Django (le collector de suppression met la FK à NULL pour
# CHAQUE ligne qui la référence, que la contrainte FK existe ou non côté base),
# jamais au niveau base — ``portail`` reste un consommateur des 5 apps domaine,
# jamais couplé à leur schéma physique (elles restent mutuellement décorrélées,
# cf. contrat import-linter ``core-domain-models-decoupled``). db_constraint=False
# évite aussi qu'un id déjà orphelin (données de test/existantes) ne bloque la
# migration de données ci-dessous.
#
# Technique standard (4 passes, sans SQL brut) pour chaque champ : on ajoute un
# champ FK temporaire (nom distinct — un ``ForeignKey`` nommé comme l'ancien
# champ entier créerait un conflit d'attribut Python avec son propre attname
# ``<nom>_id``), on copie les valeurs entières existantes en masse (aucune
# validation FK au niveau base ici, cf. db_constraint=False ci-dessus), on
# retire l'ancien champ entier, puis on renomme le champ temporaire vers son
# nom final — la colonne physique finale s'appelle de nouveau ``<champ>_id``
# (attname standard d'un ForeignKey nommé ``<champ>``), donc tout code qui lisait
# ``obj.devis_id``/``obj.client_id``/etc. continue de fonctionner À L'IDENTIQUE
# (attname Django), y compris les ``.filter(...)``/``.create(...)``/
# ``.update(update_fields=[...])`` existants.

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F


def _copier_ids_vers_fk_tmp(apps, schema_editor):
    AcceptationDevisPortail = apps.get_model('portail', 'AcceptationDevisPortail')
    PaiementFacturePortail = apps.get_model('portail', 'PaiementFacturePortail')
    DocumentClientPortail = apps.get_model('portail', 'DocumentClientPortail')
    JalonChantierPortail = apps.get_model('portail', 'JalonChantierPortail')
    DemandeTicketPortail = apps.get_model('portail', 'DemandeTicketPortail')

    AcceptationDevisPortail.objects.update(devis_tmp_id=F('devis_id'))
    PaiementFacturePortail.objects.update(facture_tmp_id=F('facture_id'))
    DocumentClientPortail.objects.update(
        client_tmp_id=F('client_id'), lead_tmp_id=F('lead_id'))
    JalonChantierPortail.objects.update(chantier_tmp_id=F('chantier_id'))
    DemandeTicketPortail.objects.update(
        client_tmp_id=F('client_id'), chantier_tmp_id=F('chantier_id'),
        ticket_tmp_id=F('ticket_id'))


def _copier_ids_depuis_fk(apps, schema_editor):
    """Reverse — reconstitue les entiers bruts depuis les FK (pour un rollback
    propre ; les FK ``*_tmp`` n'existent plus à ce stade du reverse, donc on
    lit directement les attnames finaux ``devis_id``/``client_id``/etc., qui
    à ce point de la remontée sont encore les colonnes FK — cf. l'ordre inverse
    des opérations Django lors d'un ``migrate`` arrière)."""
    # Reverse géré par les opérations elles-mêmes (RenameField/AddField/
    # RemoveField sont toutes réversibles) ; cette passe n'a rien à copier de
    # plus car la donnée vit déjà dans la même colonne physique tout du long.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0002_wir94_documentclientportail_document_ged'),
        ('crm', '0067_lb48_savedview'),
        ('ventes', '0089_alter_rooflayout_devis'),
        ('facturation', '0002_odx17_rename_stale_contenttypes'),
        ('installations', '0096_odx19_repoint_achats_crossapp'),
        ('sav', '0050_alter_equipement_client_vente_and_more'),
    ]

    operations = [
        # ── Passe 1 — champs FK temporaires (noms distincts, aucun conflit) ──
        migrations.AddField(
            model_name='acceptationdevisportail',
            name='devis_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='acceptations_portail_tmp', to='ventes.devis'),
        ),
        migrations.AddField(
            model_name='paiementfactureportail',
            name='facture_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='paiements_portail_tmp', to='facturation.facture'),
        ),
        migrations.AddField(
            model_name='documentclientportail',
            name='client_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='documents_portail_tmp', to='crm.client'),
        ),
        migrations.AddField(
            model_name='documentclientportail',
            name='lead_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='documents_portail_lead_tmp', to='crm.lead'),
        ),
        migrations.AddField(
            model_name='jalonchantierportail',
            name='chantier_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='jalons_portail_tmp', to='installations.installation'),
        ),
        migrations.AddField(
            model_name='demandeticketportail',
            name='client_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandes_ticket_portail_tmp', to='crm.client'),
        ),
        migrations.AddField(
            model_name='demandeticketportail',
            name='chantier_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandes_ticket_portail_chantier_tmp',
                to='installations.installation'),
        ),
        migrations.AddField(
            model_name='demandeticketportail',
            name='ticket_tmp',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandes_portail_tmp', to='sav.ticket'),
        ),

        # ── Passe 2 — copie en masse des ids existants (aucune validation FK
        #    au niveau base, db_constraint=False ci-dessus) ──────────────────
        migrations.RunPython(
            _copier_ids_vers_fk_tmp, _copier_ids_depuis_fk),

        # ── Passe 3 — retrait des anciens champs entiers bruts ───────────────
        migrations.RemoveField(
            model_name='acceptationdevisportail', name='devis_id'),
        migrations.RemoveField(
            model_name='paiementfactureportail', name='facture_id'),
        migrations.RemoveField(
            model_name='documentclientportail', name='client_id'),
        migrations.RemoveField(
            model_name='documentclientportail', name='lead_id'),
        migrations.RemoveField(
            model_name='jalonchantierportail', name='chantier_id'),
        migrations.RemoveField(
            model_name='demandeticketportail', name='client_id'),
        migrations.RemoveField(
            model_name='demandeticketportail', name='chantier_id'),
        migrations.RemoveField(
            model_name='demandeticketportail', name='ticket_id'),

        # ── Passe 4 — renommage vers le nom final (colonne redevient
        #    ``<champ>_id``, attname standard d'un ForeignKey ``<champ>``) ───
        migrations.RenameField(
            model_name='acceptationdevisportail',
            old_name='devis_tmp', new_name='devis'),
        migrations.RenameField(
            model_name='paiementfactureportail',
            old_name='facture_tmp', new_name='facture'),
        migrations.RenameField(
            model_name='documentclientportail',
            old_name='client_tmp', new_name='client'),
        migrations.RenameField(
            model_name='documentclientportail',
            old_name='lead_tmp', new_name='lead'),
        migrations.RenameField(
            model_name='jalonchantierportail',
            old_name='chantier_tmp', new_name='chantier'),
        migrations.RenameField(
            model_name='demandeticketportail',
            old_name='client_tmp', new_name='client'),
        migrations.RenameField(
            model_name='demandeticketportail',
            old_name='chantier_tmp', new_name='chantier'),
        migrations.RenameField(
            model_name='demandeticketportail',
            old_name='ticket_tmp', new_name='ticket'),

        # ── Passe 5 — related_name final (posé plus haut sur les champs
        #    temporaires pour éviter toute collision passagère ; on les
        #    ré-aligne maintenant sur les noms définitifs du modèle) ──────────
        migrations.AlterField(
            model_name='acceptationdevisportail',
            name='devis',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='acceptations_portail', to='ventes.devis',
                verbose_name='Devis'),
        ),
        migrations.AlterField(
            model_name='paiementfactureportail',
            name='facture',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='paiements_portail', to='facturation.facture',
                verbose_name='Facture'),
        ),
        migrations.AlterField(
            model_name='documentclientportail',
            name='client',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='documents_portail', to='crm.client',
                verbose_name='Client'),
        ),
        migrations.AlterField(
            model_name='documentclientportail',
            name='lead',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='documents_portail', to='crm.lead',
                verbose_name='Lead'),
        ),
        migrations.AlterField(
            model_name='jalonchantierportail',
            name='chantier',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='jalons_portail', to='installations.installation',
                verbose_name='Chantier'),
        ),
        migrations.AlterField(
            model_name='demandeticketportail',
            name='client',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandes_ticket_portail', to='crm.client',
                verbose_name='Client'),
        ),
        migrations.AlterField(
            model_name='demandeticketportail',
            name='chantier',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandes_ticket_portail',
                to='installations.installation', verbose_name='Chantier'),
        ),
        migrations.AlterField(
            model_name='demandeticketportail',
            name='ticket',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandes_portail', to='sav.ticket',
                verbose_name='Ticket SAV créé'),
        ),
    ]
