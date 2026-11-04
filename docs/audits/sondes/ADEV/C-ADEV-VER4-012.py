# flake8: noqa  (sonde d'audit, contre-visite ADEV du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ADEV96 — les tests du sceau v3 (`test_adev51_empreinte_signature`, `test_qjr144_empreinte_signature`)
MOCKENT `modifiabilite.synthese_ci_lue` : la chaîne réelle `etude_params.etude_ci` → `build_quote_data`
→ `synthese_ci` → `figures_etude_scellees` → `empreinte_contenu_signable` n'y est jamais exercée.
Sonde sur un devis C&I RÉEL de la base locale : (1) figures réelles non nulles, (2) empreinte stable
à la relecture, (3) une correction de la SEULE étude dérivée (production du bilan +10 %) change
l'empreinte. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADEV-VER4-012", "sha": "fcbed3760",
         "attendu": "figures_sceau réelles (kwc, production…) ; empreinte identique à deux lectures ; "
                    "empreinte différente après +10 % sur etude_params.etude_ci.bilan.production_kwh",
         "modeles": ["ventes.Devis", "ventes.DevisSignature"]}


def sonde(ctx):
    import copy
    from apps.ventes.models import Devis
    from apps.ventes.domain.modifiabilite import empreinte_contenu_signable, figures_sceau
    candidats = (Devis.objects.filter(mode_installation__in=('commercial', 'industriel'),
                                      etude_params__has_key='etude_ci')
                 .order_by('-id')[:15])
    essais = []
    for devis in candidats:
        params = devis.etude_params if isinstance(devis.etude_params, dict) else {}
        bilan = ((params.get('etude_ci') or {}).get('bilan') or {})
        if not bilan.get('production_kwh'):
            essais.append((devis.reference, 'sans production'))
            continue
        figures = figures_sceau(devis)
        if not figures or not (figures.get('chiffres') or {}).get('production_kwh_an'):
            essais.append((devis.reference, 'figures vides', figures and figures.get('chiffres')))
            continue
        e1 = empreinte_contenu_signable(devis)
        e2 = empreinte_contenu_signable(devis)
        nouveau = copy.deepcopy(params)
        nouveau['etude_ci']['bilan']['production_kwh'] = round(float(bilan['production_kwh']) * 1.1, 1)
        Devis.objects.filter(pk=devis.pk).update(etude_params=nouveau)
        devis.refresh_from_db()
        figures2 = figures_sceau(devis)
        e3 = empreinte_contenu_signable(devis)
        obs = {'devis': devis.reference, 'mode': devis.mode_installation, 'statut': devis.statut,
               'chiffres_avant': figures['chiffres'], 'production_apres': (figures2 or {}).get('chiffres', {}).get('production_kwh_an'),
               'stable': e1 == e2, 'change_apres_etude': e1 != e3, 'essais_ecartes': essais}
        print(obs)
        return {'repro': e1 == e2 and e1 != e3, **obs}
    return {'repro': False, 'motif': 'aucun devis C&I à étude chiffrée exploitable', 'essais': essais}
