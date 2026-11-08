# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K24 — « Facture en retard » sur un BROUILLON de tranche. Facture BROUILLON (jamais émise) avec
`date_echeance = J-5` (comme `facturation_vente._champs_tranche`, délai de règlement de la tranche),
TTC 1 000, aucun paiement -> `factures_echues`, `jours_retard`, `_sweep_facture_overdue` ; puis le récap
`digests.build_summary` (« Paiements en retard »). (T) facture ÉMISE identique : notifiée (attendu)."""
SONDE = {"constat": "C-ASOC-007", "sha": "c514bd8ba",
         "attendu": "repro si brouillon : dans factures_echues, jours_retard 5, 1 notification facture_overdue ; "
                    "récap « Paiements en retard » 0 ; T : émise notifiée",
         "modeles": ["notifications.Notification", "ventes.Facture"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase, override_settings
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.notifications import sweeps
    from apps.notifications.digests import build_summary
    from apps.notifications.models import Notification
    from apps.ventes.models import Facture
    from apps.ventes.selectors import factures_echues
    U = get_user_model()
    j0 = timezone.localdate()
    obs = {}

    def scenario(tag, statut):
        c = Company.objects.create(nom=f'Sonde ASOC 007 {tag}', slug=f'sonde-asoc-007-{tag.lower()}')
        u = U.objects.create_user(username=f'sonde-asoc-007-{tag.lower()}', password='x', role_legacy='admin',
                                  company=c)
        cl = Client.objects.create(company=c, nom='Client', prenom=tag, email=f'asoc007-{tag.lower()}@example.invalid')
        ref = f'BROUILLON-ASOC007-{tag}' if statut == 'brouillon' else f'FAC-ASOC007-{tag}'
        extra = {} if statut == 'brouillon' else {'date_emission': j0 - timedelta(days=35)}
        f = Facture.objects.create(company=c, reference=ref, client=cl, statut=statut, taux_tva=Decimal('20'),
                                   montant_ht=Decimal('833.33'), montant_tva=Decimal('166.67'),
                                   montant_ttc=Decimal('1000'), date_echeance=j0 - timedelta(days=5),
                                   created_by=u, **extra)
        f = Facture.objects.get(pk=f.pk)
        res = {'statut': f.statut, 'dans_factures_echues': factures_echues(c, today=j0).filter(pk=f.pk).exists(),
               'jours_retard': f.jours_retard}
        with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False):
            with TestCase.captureOnCommitCallbacks(execute=True):
                res['sweep_count'] = sweeps._sweep_facture_overdue(c)
        notifs = Notification.objects.filter(company=c, event_type='facture_overdue')
        res['notifications'] = notifs.count()
        res['titre_corps'] = list(notifs.values_list('body', flat=True))[:1]
        try:
            summ = build_summary(c)
            res['recap_paiements_en_retard'] = dict(summ).get('Paiements en retard') if not isinstance(summ, list) \
                else next((v for k, v in summ if k == 'Paiements en retard'), None)
        except Exception as e:
            res['recap_paiements_en_retard'] = repr(e)[:160]
        return res

    obs['R_brouillon'] = scenario('R', 'brouillon')
    obs['T_emise'] = scenario('T', 'emise')
    print(obs)
    r, t = obs['R_brouillon'], obs['T_emise']
    defaut = r['notifications'] == 1 and r['jours_retard'] > 0
    obs['repro'] = bool(defaut and t['notifications'] == 1)
    return obs
