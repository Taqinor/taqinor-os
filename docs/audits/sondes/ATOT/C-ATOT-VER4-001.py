# flake8: noqa  (sonde d'audit vérifie ATOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""ATOT15 / ATOT50 : l'invariant « Σ factures ≤ devis » de
`apps/facturation/tests/test_atot_machine_facturation.py::MachineFacturation._verifier_borne` prend pour plafond
`option_totaux(devis)['ttc'] + max(0, plan['prevu'] - plan['prix_convenu_ttc'])` — `prevu` est LU sur
`vente_facturation.plan_facturation`, c'est-à-dire sur le code sous test. Comme `prevu` = émis net (avoirs de
correction déduits) + brouillons ≥ le « net » que le test calcule, le plafond monte avec toute sur-facturation :
l'invariant ne peut plus échouer. Preuve : on SUR-FACTURE à la main (ORM, deux factures émises 150 000 + 90 000
sur un devis de 150 000 TTC — l'état que la machine doit attraper, celui d'avant ATOT2) et on appelle la VRAIE
méthode d'invariant du test (module importé tel quel ; `hypothesis`, absent de l'image, est remplacé par des
décorateurs neutres qui ne touchent pas le corps des méthodes). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ATOT-VER4-001", "sha": "64c9c7317",
         "attendu": "devis 150 000 TTC, 240 000 émis : somme_factures_bornee_par_devis() ne lève RIEN (plafond 240 000) alors que l'ancien plafond option_totaux (150 000) lèverait ; attendu sain : AssertionError",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "facturation.Facture", "crm.Client", "stock.Produit"]}


def _stub_hypothesis():
    import sys
    import types
    if 'hypothesis' in sys.modules:
        return
    ident = lambda *a, **k: (lambda f: f)
    h = types.ModuleType('hypothesis')
    h.HealthCheck = type('HealthCheck', (), {'too_slow': 1, 'filter_too_much': 2})
    h.settings = lambda *a, **k: None
    st = types.ModuleType('hypothesis.strategies')
    st.integers = lambda *a, **k: None
    st.sampled_from = lambda *a, **k: None
    h.strategies = st
    extra = types.ModuleType('hypothesis.extra')
    dj = types.ModuleType('hypothesis.extra.django')
    from django.test import TestCase
    dj.TestCase = TestCase
    stateful = types.ModuleType('hypothesis.stateful')
    stateful.RuleBasedStateMachine = type('RuleBasedStateMachine', (), {'__init__': lambda self: None})
    stateful.invariant = ident
    stateful.rule = ident
    stateful.run_state_machine_as_test = lambda *a, **k: None
    for nom, mod in (('hypothesis', h), ('hypothesis.strategies', st), ('hypothesis.extra', extra),
                     ('hypothesis.extra.django', dj), ('hypothesis.stateful', stateful)):
        sys.modules[nom] = mod


def sonde(ctx):
    from decimal import Decimal
    _stub_hypothesis()
    from apps.facturation.tests.test_atot_machine_facturation import MachineFacturation
    from apps.ventes.models import Devis, Facture, LigneDevis
    from apps.ventes.utils.options import option_totaux
    from apps.ventes.vente_facturation import plan_facturation

    m = MachineFacturation()
    devis = Devis.objects.create(
        company=m.company, reference='DEV-SONDE-ATOTV4-001', client=m.client_obj,
        statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'), mode_installation='residentiel')
    LigneDevis.objects.create(devis=devis, produit=m.onduleur, designation='Onduleur', quantite=Decimal('1'),
                              prix_unitaire=Decimal('125000'), remise=Decimal('0'), taux_tva=Decimal('20.00'))
    ttc = Decimal(str(option_totaux(devis)['ttc']))
    # Sur-facturation posée à la main : l'état « deux portes ont facturé » (pré-ATOT2 : 240 000 pour 150 000).
    for ref, ht, typ in (('FAC-SONDE-ATOTV4-001A', Decimal('125000'), 'complete'),
                         ('FAC-SONDE-ATOTV4-001B', Decimal('75000'), 'acompte')):
        Facture.objects.create(company=m.company, reference=ref, client=m.client_obj, devis=devis,
                               statut=Facture.Statut.EMISE, type_facture=typ, taux_tva=Decimal('20.00'),
                               montant_ht=ht, montant_tva=ht * Decimal('0.2'), montant_ttc=ht * Decimal('1.2'),
                               libelle=f'Sonde {ref}')
    m.devis_id = devis.pk
    net, actives = m._net(devis)
    plan = plan_facturation(devis)
    leve = None
    try:
        m.somme_factures_bornee_par_devis()
    except AssertionError as exc:
        leve = str(exc)[:300]
    tolerance = Decimal('0.01') * (len(actives) + 1)
    ancien_plafond_leverait = net > ttc + tolerance
    obs = {'ttc_devis': str(ttc), 'net_emis_test': str(net), 'nb_factures': len(actives),
           'plan_prevu': str(plan['prevu']), 'plan_prix_convenu': str(plan['prix_convenu_ttc']),
           'plafond_test': str(ttc + max(Decimal('0'), plan['prevu'] - plan['prix_convenu_ttc'])),
           'invariant_leve': leve, 'ancien_plafond_option_totaux_leverait': ancien_plafond_leverait}
    print(obs)
    repro = leve is None and net > ttc and ancien_plafond_leverait
    return {'repro': repro, **obs}
