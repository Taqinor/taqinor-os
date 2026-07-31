"""WIR95 — Remplace les références opaques ``*_id`` du module portail par de
vraies FK string-référencées (même patron que
``pos.CommandeRetrait.devis = ForeignKey('ventes.Devis', on_delete=SET_NULL)``).

8 champs convertis (5 modèles) :
  AcceptationDevisPortail.devis_id      -> devis    (FK ventes.Devis)
  PaiementFacturePortail.facture_id     -> facture  (FK facturation.Facture)
  DocumentClientPortail.client_id       -> client   (FK crm.Client)
  DocumentClientPortail.lead_id         -> lead     (FK crm.Lead)
  JalonChantierPortail.chantier_id      -> chantier (FK installations.Installation)
  DemandeTicketPortail.client_id        -> client   (FK crm.Client)
  DemandeTicketPortail.chantier_id      -> chantier (FK installations.Installation)
  DemandeTicketPortail.ticket_id        -> ticket   (FK sav.Ticket)

Toutes SET_NULL + db_constraint=False : la contrainte d'intégrité référentielle
vit dans l'ORM Django (le collector de suppression met la FK à NULL pour CHAQUE
ligne qui la référence, que la contrainte FK existe ou non côté base), jamais au
niveau base — ``portail`` reste un consommateur des 5 apps domaine, jamais
couplé à leur schéma physique (elles restent mutuellement décorrélées, cf.
contrat import-linter ``core-domain-models-decoupled``). db_constraint=False
évite aussi qu'un id déjà orphelin (données de test/existantes) ne bloque la
migration de données ci-dessous.

Technique standard (sans SQL brut) pour chaque champ : on ajoute un champ FK
temporaire (nom distinct — un ``ForeignKey`` nommé comme l'ancien champ entier
créerait un conflit d'attribut Python avec son propre attname ``<nom>_id``), on
copie les valeurs entières existantes en masse, on retire l'ancien champ
entier, puis on renomme le champ temporaire vers son nom final — la colonne
physique finale s'appelle de nouveau ``<champ>_id`` (attname standard d'un
ForeignKey nommé ``<champ>``), donc tout code qui lisait ``obj.devis_id`` /
``obj.client_id`` / etc. continue de fonctionner À L'IDENTIQUE (attname
Django), y compris les ``.filter(...)`` / ``.create(...)`` /
``.update(update_fields=[...])`` existants.

────────────────────────────────────────────────────────────────────────────
REVUE HUMAINE DE SÛRETÉ — verdict et justification, en clair
────────────────────────────────────────────────────────────────────────────
Cette migration déclenche ``scripts/check_safe_migrations.py`` (8 RemoveField,
8 RenameField, un RunPython ``.update()`` non batché). Chaque signalement a été
audité opération par opération ; voici la décision.

1. SENS AVANT (``migrate``) — SANS PERTE, ordre vérifié. Les 8 colonnes
   ``*_tmp_id`` sont créées (passe 2), la donnée y est COPIÉE (passe 3) AVANT
   que le moindre ``RemoveField`` ne s'exécute (passe 4), puis le renommage
   (passe 5) ramène chaque colonne physique à son nom d'origine ``<champ>_id``.
   Aucun ``RemoveField`` ne supprime une colonne dont la donnée n'a pas déjà
   été recopiée, et aucune passe ne lit une colonne qu'une passe antérieure
   aurait retirée. L'état final est identique aux modèles : le
   ``MigrationAutodetector`` exécuté sur l'état migré ne détecte AUCUN écart
   pour l'app ``portail``.

2. SENS ARRIÈRE (rollback) — DÉFAUT RÉEL TROUVÉ EN REVUE, CORRIGÉ ICI. La
   première version posait un reverse ``pass`` en affirmant que « la donnée vit
   déjà dans la même colonne physique tout du long » : c'était FAUX. Au
   rollback, Django renomme ``<champ>_id`` en ``<champ>_tmp_id`` (la donnée
   suit la colonne), PUIS recrée les anciennes colonnes entières ``<champ>_id``
   VIDES, PUIS — reverse de la passe 2 — supprime les colonnes ``*_tmp_id`` qui
   portaient TOUTE la donnée. Avec un reverse ``pass``, un simple
   ``migrate portail 0002`` détruisait donc silencieusement les 8 références
   sur toutes les lignes (et, sur les 5 colonnes historiquement NOT NULL,
   échouait à mi-parcours car un ``ADD COLUMN ... NOT NULL`` sans défaut est
   refusé sur une table peuplée). Deux correctifs appliqués :
     a. passe 1 — les 5 anciens entiers NOT NULL passent ``null=True``, ce qui
        rend leur recréation possible au rollback sur une table peuplée ;
     b. ``_copier_ids_depuis_fk`` RECOPIE réellement ``*_tmp_id -> *_id``.
   Séquence de rollback effective désormais : renommage inverse (la donnée suit
   la colonne) -> recréation des entiers, vides et nullables -> RECOPIE ->
   suppression des ``*_tmp_id`` devenues redondantes -> retour à NOT NULL. Sans
   perte. Le retour à NOT NULL échoue BRUYAMMENT (et la transaction annule
   tout) si une ligne créée entre-temps porte une référence NULL — comportement
   voulu : on refuse de deviner une valeur, jamais de corruption silencieuse.

3. ``.update()`` non batché : les 5 tables ``compta_*portail`` sont des tables
   de portail self-service à faible volume (module créé par ODX12, étendu par
   WIR94 — aucun historique de masse) ; un UPDATE global y coûte quelques
   millisecondes. Risque de verrou long assumé et négligeable.

4. Changement de sémantique assumé (voulu par WIR95, pas un effet de bord) :
   5 des 8 champs étaient NOT NULL et deviennent nullables — ``SET_NULL``
   l'exige. La base ne garantit donc plus leur présence ; c'est la contrepartie
   explicite du passage d'un id opaque à une vraie FK décorrélée.

À ce titre — et pour cette raison seulement — le chemin de ce fichier figure
dans ``scripts/safe_migrations_allow.txt``.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F


def _copier_ids_vers_fk_tmp(apps, schema_editor):
    """Passe 3 (avant) — copie les entiers bruts vers les FK temporaires.

    S'exécute AVANT tout ``RemoveField`` : à ce stade les deux jeux de colonnes
    (``<champ>_id`` entier et ``<champ>_tmp_id`` FK) coexistent. Aucune
    validation FK côté base n'est déclenchée (``db_constraint=False``), donc un
    id déjà orphelin est recopié tel quel au lieu de bloquer la migration.
    """
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
    """Reverse de la passe 3 — RESTITUE les entiers bruts depuis les FK.

    Indispensable : à ce point du rollback Django a déjà (a) renommé
    ``<champ>_id`` en ``<champ>_tmp_id`` — la donnée a suivi la colonne — et
    (b) recréé les anciennes colonnes entières ``<champ>_id``, VIDES. La
    suppression des champs ``*_tmp`` qui suit détruirait donc TOUTE la donnée
    si l'on ne la recopiait pas ici (c'était le bug de la première version de
    cette migration, cf. point 2 de la revue en tête de fichier).

    ``apps`` est l'état AVEC la passe 3 appliquée
    (``RunPython.database_backwards`` passe ``from_state.apps``), donc les deux
    jeux de champs y coexistent bien et les deux colonnes existent en base.
    """
    AcceptationDevisPortail = apps.get_model('portail', 'AcceptationDevisPortail')
    PaiementFacturePortail = apps.get_model('portail', 'PaiementFacturePortail')
    DocumentClientPortail = apps.get_model('portail', 'DocumentClientPortail')
    JalonChantierPortail = apps.get_model('portail', 'JalonChantierPortail')
    DemandeTicketPortail = apps.get_model('portail', 'DemandeTicketPortail')

    AcceptationDevisPortail.objects.update(devis_id=F('devis_tmp_id'))
    PaiementFacturePortail.objects.update(facture_id=F('facture_tmp_id'))
    DocumentClientPortail.objects.update(
        client_id=F('client_tmp_id'), lead_id=F('lead_tmp_id'))
    JalonChantierPortail.objects.update(chantier_id=F('chantier_tmp_id'))
    DemandeTicketPortail.objects.update(
        client_id=F('client_tmp_id'), chantier_id=F('chantier_tmp_id'),
        ticket_id=F('ticket_tmp_id'))


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
        # ── Passe 1 — les 5 anciens entiers NOT NULL deviennent nullables ────
        #    Aller : simple ``DROP NOT NULL`` (métadonnée, aucune donnée
        #    touchée). Sa RAISON D'ÊTRE est le RETOUR : sans elle, le reverse
        #    du ``RemoveField`` correspondant émettrait un
        #    ``ADD COLUMN ... NOT NULL`` sans défaut, refusé sur une table
        #    peuplée — le rollback serait impossible. Les 3 autres champs
        #    (lead_id, DemandeTicketPortail.chantier_id, ticket_id) sont déjà
        #    nullables depuis 0001 et n'ont donc pas besoin de cette passe.
        migrations.AlterField(
            model_name='acceptationdevisportail',
            name='devis_id',
            field=models.PositiveIntegerField(
                null=True, verbose_name='Id du devis'),
        ),
        migrations.AlterField(
            model_name='paiementfactureportail',
            name='facture_id',
            field=models.PositiveIntegerField(
                null=True, verbose_name='Id de la facture'),
        ),
        migrations.AlterField(
            model_name='documentclientportail',
            name='client_id',
            field=models.PositiveIntegerField(
                null=True, verbose_name='Id du client'),
        ),
        migrations.AlterField(
            model_name='jalonchantierportail',
            name='chantier_id',
            field=models.PositiveIntegerField(
                null=True, verbose_name='Id du chantier'),
        ),
        migrations.AlterField(
            model_name='demandeticketportail',
            name='client_id',
            field=models.PositiveIntegerField(
                null=True, verbose_name='Id du client'),
        ),

        # ── Passe 2 — champs FK temporaires (noms distincts, aucun conflit) ──
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

        # ── Passe 3 — copie en masse des ids existants (aucune validation FK
        #    au niveau base, db_constraint=False ci-dessus). Le reverse
        #    RECOPIE en sens inverse : sans lui, le rollback perdrait tout. ──
        migrations.RunPython(
            _copier_ids_vers_fk_tmp, _copier_ids_depuis_fk),

        # ── Passe 4 — retrait des anciens champs entiers bruts (leur donnée
        #    est déjà dans les colonnes ``*_tmp_id`` depuis la passe 3) ───────
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

        # ── Passe 5 — renommage vers le nom final (colonne redevient
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

        # ── Passe 6 — related_name final (posé plus haut sur les champs
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
