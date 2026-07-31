"""DC32 — le compte portail client se lie à ``crm.Client`` PAR FK et réutilise
l'email du client (fin de la 2ᵉ copie d'identité).

L'ancien champ ``client_id`` (PositiveIntegerField) contenait déjà la PK du
client : on le renomme temporairement, on ajoute la vraie FK ``client``, on
recopie la valeur (même PK), puis on retire la colonne temporaire et l'ancien
champ ``email`` dupliqué. Réversible.

────────────────────────────────────────────────────────────────────────────
REVUE HUMAINE DE SÛRETÉ — correctif de rollback appliqué après coup
────────────────────────────────────────────────────────────────────────────
CE QUI A CHANGÉ DANS CE FICHIER (et pourquoi il a été modifié alors qu'il
était DÉJÀ APPLIQUÉ) — même défaut, même correctif que
``apps/portail/migrations/0003_wir95_fk_references.py`` :

La version d'origine annonçait « Réversible » — c'était FAUX sur une table
peuplée. Au rollback, le reverse des deux ``RemoveField`` réémet
``ADD COLUMN client_pk_tmp integer NOT NULL`` et
``ADD COLUMN email varchar(254) NOT NULL``, tous deux SANS défaut utilisable
(``EmailField`` a ``blank=False``, donc Django ne substitue même pas la chaîne
vide) : PostgreSQL refuse, la transaction atomique annule tout, et
``migrate compta 0042`` est tout simplement IMPOSSIBLE. L'échec est BRUYANT et
ne perd rien — mais la garantie « ``main`` reste réversible » ne tenait pas.

Trois correctifs, calqués sur le patron WIR95 :

  a. PASSE 1bis — ``client_pk_tmp`` et ``email`` passent ``null=True`` AVANT le
     ``RunPython``. À l'aller c'est un simple ``DROP NOT NULL`` sur deux
     colonnes que la MÊME migration supprime quelques opérations plus loin :
     l'état final (colonnes absentes) est donc RIGOUREUSEMENT IDENTIQUE avec ou
     sans ces deux opérations. Leur unique raison d'être est le RETOUR : le
     reverse des ``RemoveField`` recrée alors des colonnes NULLABLES, ce que
     PostgreSQL accepte sur une table peuplée. Elles sont placées AVANT le
     ``RunPython`` (et non après) pour que leur propre reverse — le retour à
     ``NOT NULL`` — s'exécute APRÈS la recopie des données, jamais avant.
  b. Le reverse du ``RunPython`` RESTITUE les deux colonnes : ``client_pk_tmp``
     depuis ``client_id`` (valeur identique, la FK porte la même PK) et
     ``email`` depuis ``client.email`` (RECONSTRUCTION — voir le point 2).
  c. Le retour à ``NOT NULL`` échoue BRUYAMMENT (et la transaction annule tout)
     si une ligne porte encore un ``client`` NULL : on refuse de deviner une
     valeur, jamais de corruption silencieuse.

1. IMPACT SUR UNE BASE DÉJÀ MIGRÉE : AUCUN. Les deux ``AlterField`` ajoutés ne
   touchent QUE des colonnes que cette même migration supprime ensuite ; l'état
   physique final et l'état Django reconstruit par relecture des opérations sont
   inchangés au bit près. Une base où 0043 est déjà appliqué n'a donc RIEN à
   faire : ni ``ALTER`` manuel, ni ``--fake``, ni reconstruction. (Le contrôle
   est automatisé : ``MigrationAutodetector`` ne détecte aucun écart, et l'état
   d'arrivée est vérifié champ par champ, cf. la preuve DB-free en revue.)

2. LE CHAMP ``email`` SUPPRIMÉ EST DOCUMENTÉ COMME UN DOUBLON DE
   ``client.email`` — mais l'aller ne l'avait JAMAIS vérifié. Toute ligne dont
   l'email portail avait divergé de celui du client perdait sa valeur en
   silence. Deux mesures, dans les limites du possible :
     - GARDE AVANT (bases pas encore migrées) : la passe de copie COMPARE
       maintenant chaque ``email`` à ``client.email`` et, en cas de divergence,
       ÉCRIT SUR ``stderr`` la liste complète (id du compte, valeur portail,
       valeur client) AVANT que la colonne ne soit supprimée. La valeur reste
       donc récupérable dans le journal de ``migrate``. Volontairement une
       ALERTE et non une erreur : bloquer la migration sur une divergence
       légitime (email de contact portail distinct) serait pire que l'annoncer.
     - RETOUR : ``email`` est reconstruit depuis ``client.email``. C'est une
       RECONSTRUCTION, pas une restauration : une valeur divergente déjà perdue
       par un aller antérieur est définitivement irrécupérable (aucune colonne
       ne la porte plus). C'est la limite assumée de ce correctif.
"""
import sys

from django.db import migrations, models
import django.db.models.deletion


def _emails_clients(apps, pks):
    """Table {pk client -> email} bornée aux clients réellement référencés."""
    Client = apps.get_model('crm', 'Client')
    return dict(
        Client.objects.filter(pk__in=[p for p in pks if p is not None])
        .values_list('pk', 'email'))


def copier_client_pk(apps, schema_editor):
    """Aller — recopie la PK dans la vraie FK, et ALERTE sur tout email
    portail divergent AVANT que la colonne ``email`` ne soit supprimée."""
    ComptePortailClient = apps.get_model('compta', 'ComptePortailClient')

    pks = list(ComptePortailClient.objects.values_list('client_pk_tmp', flat=True))
    emails_client = _emails_clients(apps, pks)

    divergents = []
    for compte in ComptePortailClient.objects.all().iterator():
        compte.client_id = compte.client_pk_tmp
        compte.save(update_fields=['client'])
        attendu = emails_client.get(compte.client_pk_tmp)
        if attendu is not None and (compte.email or '') != (attendu or ''):
            divergents.append((compte.pk, compte.email, attendu))

    if divergents:
        sys.stderr.write(
            'DC32 — ALERTE : %d compte(s) portail portaient un email DIFFÉRENT '
            "de celui de leur client ; la colonne `email` est supprimée par "
            'cette migration, ces valeurs ne sont conservées que par ce '
            'journal :\n' % len(divergents))
        for compte_pk, email_portail, email_client in divergents:
            sys.stderr.write(
                '  ComptePortailClient(pk=%s) : portail=%r client=%r\n'
                % (compte_pk, email_portail, email_client))


def recopier_client_pk(apps, schema_editor):
    """Retour — RESTITUE les deux colonnes recréées vides par le rollback.

    À ce point du retour, Django a déjà recréé ``client_pk_tmp`` et ``email``
    (VIDES et nullables grâce à la passe 1bis) ; la FK ``client`` existe encore
    et porte la donnée. Sans cette recopie, le retour à ``NOT NULL`` qui suit
    échouerait sur toutes les lignes.

    ``email`` est RECONSTRUIT depuis ``client.email`` (le doublon que DC32 a
    supprimé) : c'est la meilleure valeur disponible, pas la valeur d'origine
    si elle avait divergé — cf. point 2 de la revue en tête de fichier.
    """
    ComptePortailClient = apps.get_model('compta', 'ComptePortailClient')

    pks = list(ComptePortailClient.objects.values_list('client_id', flat=True))
    emails_client = _emails_clients(apps, pks)

    for compte in ComptePortailClient.objects.all().iterator():
        compte.client_pk_tmp = compte.client_id
        compte.email = emails_client.get(compte.client_id) or ''
        compte.save(update_fields=['client_pk_tmp', 'email'])


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0042_ecriture_validation_sod'),
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='compteportailclient',
            name='uniq_compte_portail_client',
        ),
        migrations.RenameField(
            model_name='compteportailclient',
            old_name='client_id',
            new_name='client_pk_tmp',
        ),
        # ── Passe 1bis — les deux colonnes que cette migration va supprimer
        #    deviennent nullables. Aller : simple `DROP NOT NULL` sur des
        #    colonnes supprimées 4 opérations plus loin => état final
        #    STRICTEMENT identique. Raison d'être : le RETOUR, où le reverse
        #    des `RemoveField` doit pouvoir réémettre un `ADD COLUMN` sur une
        #    table peuplée (impossible en NOT NULL sans défaut). Placées avant
        #    le RunPython pour que leur reverse (retour à NOT NULL) s'exécute
        #    APRÈS la recopie des données. ────────────────────────────────────
        migrations.AlterField(
            model_name='compteportailclient',
            name='client_pk_tmp',
            field=models.PositiveIntegerField(
                null=True, verbose_name='Id du client'),
        ),
        migrations.AlterField(
            model_name='compteportailclient',
            name='email',
            field=models.EmailField(
                max_length=254, null=True, verbose_name='Email du client'),
        ),
        migrations.AddField(
            model_name='compteportailclient',
            name='client',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='comptes_portail',
                to='crm.client',
                verbose_name='Client'),
        ),
        migrations.RunPython(copier_client_pk, recopier_client_pk),
        migrations.RemoveField(
            model_name='compteportailclient',
            name='client_pk_tmp',
        ),
        migrations.RemoveField(
            model_name='compteportailclient',
            name='email',
        ),
        migrations.AlterField(
            model_name='compteportailclient',
            name='client',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='comptes_portail',
                to='crm.client',
                verbose_name='Client'),
        ),
        migrations.AddConstraint(
            model_name='compteportailclient',
            constraint=models.UniqueConstraint(
                fields=['company', 'client'],
                name='uniq_compte_portail_client'),
        ),
    ]
