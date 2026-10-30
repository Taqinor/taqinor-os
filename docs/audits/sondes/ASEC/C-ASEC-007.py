SONDE = {"constat": "C-ASEC-007", "sha": "5908d43bb",
         "attendu": "STATIQUE : les gardes de dépôt voient les FK écrites — check_fk_scoping.py vert et --list voit "
                    "FactureWriteSerializer (sérialiseurs exclude=) ; balai multi-société doté d'une étape écriture"}


def sonde(ctx):
    # Les gardes vivent dans scripts/ (hors du conteneur django) : elles sont exécutées sur l'hôte par
    # l'orchestrateur, sortie dans traces/2026-10-30/C-ASEC-007-gardes.txt. Ici : présence de l'étape
    # « écriture » du balai dans le code monté.
    import os
    chemin = os.path.join('tests', 'test_tenant_sweep.py')
    present = os.path.isfile(chemin) and 'test_ecriture_fk_voisine_refusee' in open(chemin, encoding='utf-8').read()
    return ('STATIQUE — garde de classe, rien à rejouer en HTTP. Balai tests/test_tenant_sweep.py : étape écriture '
            '`test_ecriture_fk_voisine_refusee` présente=%s. Gardes hôte (check_fk_scoping.py, --list, '
            'check_machine_etats_statut_readonly.py) : voir la trace C-ASEC-007-gardes.txt.' % present)
