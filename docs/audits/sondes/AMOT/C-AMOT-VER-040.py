# flake8: noqa  (sonde de contre-visite vérifie AMOT, rejouable par scripts/sonde.py — AMET93)
"""AMOT80 : « communiquez-nous vos 12 dernières factures » n'est imprimé que si la consommation manque réellement.
Dossier commercial dont la consommation est CONNUE (12 kWh mensuels relevés sur facture, baseline « factures » servie
par la synthèse) mais dont l'économie est omise pour une autre raison (contrat non déclaré ⇒ tarif omis) : la couverture
commerciale imprime quand même la demande des 12 factures (`ci/couverture.py::ligne_non_chiffre`, motif BT par défaut
de `ci/synthese.py::_bloc_argent`). Fonctions réelles, ligne de couverture réelle (celle que `commercial/cover.py` imprime quand l'économie manque), ni base ni HTTP."""
SONDE = {"constat": "C-AMOT-VER-040", "sha": "56d5b623a",
         "attendu": "baseline source=factures (conso connue) ET la couverture demande « vos 12 dernières factures »"}


def sonde(ctx):
    import copy
    from apps.ventes import economie_ci as eco
    from apps.ventes.quote_engine.ci.synthese import synthese_ci
    from apps.ventes.quote_engine.ci import couverture
    from apps.ventes.quote_engine.ci.synthese import chiffres_cles
    from apps.ventes.quote_engine.commercial import sample_data as com_sample
    from apps.ventes.tests.test_ciq303_synthese_ci_coeur import _etude_ci
    etude_ci = _etude_ci()
    economie = eco.assembler_economie_ci(copy.deepcopy(etude_ci), tarif_declare={},
                                         mode_installation='commercial')
    data = copy.deepcopy(com_sample.build())
    data['etude']['etude_ci'] = etude_ci
    data['economie_ci'] = economie
    s = synthese_ci(data) or {}
    base = s.get('baseline') or {}
    ch = chiffres_cles(s)
    # Clés posées par `commercial/renderer.py::_augment` (lignes 118-124), lues par `commercial/cover.py` (l. 140-142).
    d = {'com_synthese': s, 'com_economies': ch['economie_annuelle_mad'], 'com_motif_argent': ch['motif_argent'],
         'com_payback': ch['payback_ans'], 'langue_sortie': 'fr'}
    html = couverture.ligne_non_chiffre(d, 'com', 'c1c')
    demande = 'communiquez-nous vos 12 dernières factures' in html
    print(f"economie statut={economie.get('statut')} motif={(economie.get('motifs_omission') or [None])[0]!r} "
          f"baseline source={base.get('source')} demande_12_factures={demande}")
    return {'repro': base.get('source') == 'factures' and demande,
            'statut': economie.get('statut'), 'source': base.get('source'), 'demande': demande}
