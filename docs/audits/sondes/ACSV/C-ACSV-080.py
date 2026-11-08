# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""T1 — `chantier_annule` sans abonné SAV : contrat d'entretien, parc et KPI survivent à l'annulation
MANUELLE du chantier (vraie route `installations/chantiers/<id>/annuler/`).
(R) chantier réceptionné, contrat actif lié, équipement au parc, puis « Annuler le chantier » ;
`generer_visites_dues(avance_jours=400)` -> ticket préventif sur le chantier annulé ?
(T) témoin : même contrat sur un chantier NON annulé -> la génération crée bien 1 ticket (mécanisme vivant)."""
SONDE = {"constat": "C-ACSV-080", "sha": "7f4ba787d",
         "attendu": "repro si R : annuler 200, contrat.actif True, 1 ticket PREVENTIF sur le chantier annulé, "
                    "chantier présent dans chantiers_receptionnes ; T : 1 ticket généré",
         "modeles": ["sav.Ticket", "sav.ContratMaintenance", "installations.Installation", "sav.Equipement"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.installations.selectors import chantiers_receptionnes
    from apps.sav.maintenance import generer_visites_dues
    from apps.sav.models import ContratMaintenance, Equipement, Ticket
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 080', slug='sonde-acsv-080')
    u = get_user_model().objects.create_user(username='sonde-acsv-080', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-080', prix_achat=Decimal('2000'), prix_vente=Decimal('5000'))

    def jeu(nom):
        cl = Client.objects.create(company=co, nom='Client', prenom=nom, email=f'acsv080-{nom}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-ACSV-080-{nom}', client=cl,
                                           statut=Installation.Statut.RECEPTIONNE,
                                           date_reception=today - timedelta(days=60))
        eq = Equipement.objects.create(company=co, installation=inst, produit=p, numero_serie=f'SN-080-{nom}',
                                       date_pose=today - timedelta(days=60),
                                       date_fin_garantie=today + timedelta(days=3000))
        c = ContratMaintenance.objects.create(company=co, client=cl, installation=inst,
                                              periodicite='annuel', date_debut=today - timedelta(days=60),
                                              notes='[devis:999999] contrat sonde')
        return inst, eq, c

    instR, eqR, cR = jeu('R')
    instT, eqT, cT = jeu('T')
    r = api.post(f'/api/django/installations/chantiers/{instR.pk}/annuler/', {'motif': 'client parti'},
                 format='json', **H)
    instR.refresh_from_db()
    cR.refresh_from_db()
    eqR.refresh_from_db()
    n = generer_visites_dues(co, u, avance_jours=400)
    ids_recep = [row[0] for row in chantiers_receptionnes(co)]
    R = {'annuler_http': r.status_code, 'detail': None if r.status_code < 400 else str(getattr(r, 'data', ''))[:200],
         'inst_annule': instR.annule, 'contrat_actif_apres_annulation': cR.actif,
         'equipement_statut': eqR.statut,
         'tickets_preventifs': Ticket.objects.filter(installation=instR, type=Ticket.Type.PREVENTIF).count(),
         'dans_chantiers_receptionnes': instR.pk in ids_recep}
    T = {'tickets_preventifs': Ticket.objects.filter(installation=instT, type=Ticket.Type.PREVENTIF).count()}
    out = {'generes_total': n, 'R': R, 'T': T}
    print(out)
    temoin_ok = T['tickets_preventifs'] == 1
    defaut = R['annuler_http'] == 200 and R['inst_annule'] and R['contrat_actif_apres_annulation'] \
        and R['tickets_preventifs'] >= 1
    out.update({'temoin_ok': temoin_ok, 'repro': bool(temoin_ok and defaut)})
    return out
