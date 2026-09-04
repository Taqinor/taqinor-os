from django.db import migrations, models


class Migration(migrations.Migration):
    """CRX35 — retrait d'un drapeau qui ne bloquait rien + libellé honnête.

    ``Playbook.bloquant`` promettait un blocage dur du changement d'étape
    quand des tâches obligatoires restaient à cocher. AUCUN code ne lisait la
    colonne (vérifié deux fois par l'audit L3) : la case existait dans l'API,
    l'utilisatrice pouvait la cocher, et il ne se passait rien. Une promesse
    d'UI sans exécution est pire qu'une absence de fonctionnalité — on retire
    la colonne ; la rétablir supposera d'écrire la garde, pas seulement le
    champ.

    ``Lead.Source.ODOO_IMPORT_TEST`` : la VALEUR en base
    (``'odoo_import_test'``) est INCHANGÉE — des milliers de lignes la
    portent et un renommage serait une migration de données pour rien. Seul
    le LIBELLÉ passe de « Import test Odoo » à « Import Odoo » : la
    synchronisation Odoo→ERP n'est plus un test depuis le 01/09/2026, et le
    mot « test » induisait en erreur dans les filtres et les exports.

    Réversible : la migration inverse restaure la colonne (avec son défaut
    ``False``) et l'ancien libellé.
    """

    dependencies = [
        ('crm', '0087_crx22_lead_score_ajustement'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='playbook',
            name='bloquant',
        ),
        migrations.AlterField(
            model_name='lead',
            name='source',
            field=models.CharField(
                choices=[('os_native', 'Créé dans TAQINOR'),
                         ('odoo_import_test', 'Import Odoo'),
                         ('site_web', 'Site web'),
                         ('meta_lead_ads', 'Meta Lead Ads')],
                default='os_native', max_length=32),
        ),
    ]
