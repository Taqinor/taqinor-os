# flake8: noqa  (sonde de session reprise telle quelle : style libre, logique validee le 09/10)
"""Sonde de la session audit-méthode du 09/10/2026 (R3), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
"""
SONDE = {
    'constat': 'C-AMET-002',
    'sha': 'f3716e3f0',
    'attendu': 'solde.tranches_facturees = 0 après facture complète → boutons Facturer réaffichés',
}


def sonde(ctx):
    from django.db import transaction
    class R(Exception):
        pass
    _CELERY = _CELERY_CALLS = ctx['celery']


    from django.db.models import Q
    from authentication.models import CustomUser
    from apps.ventes.models import Devis, Facture, Avoir, BonCommande
    from apps.ventes.serializers import DevisSerializer
    from apps.ventes.domain.facturation_ops import facturer_devis_complet
    from apps.ventes.utils.echeancier import factures_actives, creer_facture_tranche
    from apps.parametres.models import CompanyProfile

    u = CustomUser.objects.get(username='demo_admin')
    co = u.company

    def row_predicate(statut, s):
        if statut != 'accepte':
            return ['Generer facture (disabled)']
        tf, tt = s['tranches_facturees'], s['tranches_total']
        if tf >= tt:  # both strings in JS -> lexicographic
            return ['Echeancier complet (disabled)']
        gt = float(tf) > 0
        return (([] if gt else ['Facturer (facture complete)'])
                + ['Generer facture' if gt else 'Facturer par tranches (acompte...)'])


    def tab_predicate(statut, s):
        gt = float(s['tranches_facturees']) > 0
        return (([] if gt else ['Facturer (facture complete)'])
                + ['Generer la facture' if gt else 'Facturer par tranches (acompte...)'])


    obs = {}
    try:
        with transaction.atomic():
            # Données choisies dynamiquement (la session du 09/10 visait le devis 683 de SA base) :
            # premier devis ACCEPTÉ de la société démo sans aucune facture.
            # premier devis ACCEPTÉ que la règle métier laisse facturer en entier (savepoint par essai).
            d = facture = None
            for x in Devis.objects.filter(company=co, statut='accepte').order_by('id'):
                try:
                    with transaction.atomic():
                        facture, paiements = facturer_devis_complet(devis=x, user=u, company=co, paiements=[])
                    d = x
                    break
                except Exception:
                    continue
            if d is None:
                return 'STATIQUE : aucun devis accepté facturable en entier dans la base locale'
            print('[C2] devis', d.id, d.statut, 'factures before', Facture.objects.filter(devis=d).count(),
                  'BC', BonCommande.objects.filter(devis=d).count())
            print('[C2] facturer_devis_complet ->', facture.reference, facture.type_facture, facture.statut,
                  'devis_id', facture.devis_id, 'ttc', facture.total_ttc)
            d = Devis.objects.get(pk=d.pk)
            s = DevisSerializer(d).data['solde']
            obs = {'devis': d.pk, 'tranches_facturees': s.get('tranches_facturees'),
                   'tranches_total': s.get('tranches_total'), 'porte_facturation': s.get('porte_facturation')}
            print('[C2] served solde after COMPLETE invoice:', dict(s))
            print('[C2] DevisRow buttons ->', row_predicate(d.statut, s))
            print('[C2] DevisTab buttons ->', tab_predicate(d.statut, s))
            print('[C2] pre-ATOT2 value len(factures_actives) =', len(factures_actives(d)))
            try:
                creer_facture_tranche(d, u, co, None)
                print('[C2] tranche AFTER complete: CREATED (money not protected!)')
            except Exception as exc:
                print('[C2] tranche AFTER complete raised:', type(exc).__name__, str(exc)[:120])
            print('celery intercepted:', _CELERY)
            raise R()
    except R:
        print('ROLLED BACK')
    # REPRO = le défaut du constat : facture COMPLÈTE émise, le solde servi dit encore 0 tranche facturée.
    return dict(obs, repro=float(obs['tranches_facturees'] or 0) == 0)
