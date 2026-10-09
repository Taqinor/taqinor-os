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

    # --- rollback checks of the previous probes (read only) ---
    f8 = Facture.objects.get(pk=8)
    print('[RB] facture 8 note contains probe marker:', '[probe]' in (f8.note or ''), '| retenue_garantie_mad', f8.retenue_garantie_mad)
    print('[RB] AV-PROBE avoir exists:', Avoir.objects.filter(reference='AV-PROBE-R3V1').exists())
    print('[RB] devis 637/643 factures:', Facture.objects.filter(devis_id__in=[637, 643]).count())
    print('[RB] company payment_terms:', CompanyProfile.get(company=co).payment_terms)
    # --- why devis 313 is "already invoiced" with tranches_facturees 0 ---
    fd = Facture.objects.filter(reference='FAC-DEMO-0001').first()
    if fd:
        print('[313] FAC-DEMO-0001 devis_id', fd.devis_id, 'bon_commande_id', fd.bon_commande_id,
              'bc.devis_id', fd.bon_commande.devis_id if fd.bon_commande_id else None, 'type', fd.type_facture, 'statut', fd.statut)


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


    try:
        with transaction.atomic():
            d = Devis.objects.get(pk=683, company=co)
            print('[C2] devis', d.id, d.statut, 'factures before', Facture.objects.filter(devis=d).count(),
                  'BC', BonCommande.objects.filter(devis=d).count())
            facture, paiements = facturer_devis_complet(devis=d, user=u, company=co, paiements=[])
            print('[C2] facturer_devis_complet ->', facture.reference, facture.type_facture, facture.statut,
                  'devis_id', facture.devis_id, 'ttc', facture.total_ttc)
            d = Devis.objects.get(pk=683)
            s = DevisSerializer(d).data['solde']
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
