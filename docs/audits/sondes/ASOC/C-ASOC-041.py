# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K41 — baisser « Validité du devis (jours) » expire RÉTROACTIVEMENT un devis déjà envoyé.
`apps/ventes/utils/expiry.py::date_expiration` (date_validite sinon date_creation + réglage VIVANT) ;
l'envoi (`domain/envoi.py::mark_devis_sent`) ne pose pas `date_validite` (seul `crm/cadence_plan.py` appelle
`poser_validite_devis`). Chemin : réglage 30 j ; devis client direct (sans lead) créé il y a 20 j, envoyé
(`mark_devis_sent`) ; GET /proposal (vraie route, texte fitz) → « valable jusqu'au J+10 » ; l'admin passe le
réglage à 15 ; acceptation CLIENT (`accept_devis(user=None)`, porte du lien public) ; beat
`recouvrement.expire_stale_devis()` (borné à la société de la sonde)."""
SONDE = {"constat": "C-ASOC-041", "sha": "c514bd8ba",
         "attendu": "repro si date_validite reste NULL à l'envoi, le PDF imprime J+10, puis après réglage 15 : "
                    "acceptation client refusée « expiree » et le beat passe le devis à « expire » en base",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "parametres.CompanyProfile", "crm.Client", "stock.Produit"]}


def sonde(ctx):
    import re
    from datetime import timedelta
    from decimal import Decimal
    from unittest import mock
    import fitz
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.domain.envoi import mark_devis_sent
    from apps.ventes.domain.cycle_vie import accept_devis, AcceptError
    from apps.ventes.domain import recouvrement
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 041', slug='sonde-asoc-041')
    u = get_user_model().objects.create_user(username='sonde-asoc-041', password='x', role_legacy='admin', company=co)
    prof = CompanyProfile.get(company=co)
    prof.quote_validity_days = 30
    prof.save()
    cl = Client.objects.create(company=co, nom='Alaoui', prenom='K41', email='asoc041@example.invalid',
                               telephone='+212600000041')
    d = Devis.objects.create(company=co, client=cl, reference='DEV-SONDE-ASOC041', statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20'), mode_installation='residentiel', created_by=u)
    for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1200'),
                                        ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000'))):
        p = Produit.objects.create(company=co, nom=nom, sku=f'ASOC041-{i}', prix_vente=Decimal(pu),
                                   prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                  prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)
    today = timezone.localdate()
    Devis.objects.filter(pk=d.pk).update(date_creation=timezone.now() - timedelta(days=20))
    d.refresh_from_db()
    mark_devis_sent(devis=d, user=u)
    d.refresh_from_db()
    obs = {'aujourdhui': today.isoformat(), 'cree_le': d.date_creation.date().isoformat(), 'statut': d.statut,
           'date_validite_apres_envoi': d.date_validite, 'date_envoi': str(d.date_envoi)[:10]}
    api = APIClient()
    api.force_authenticate(u)
    r = api.get(f'/api/django/ventes/devis/{d.pk}/proposal/', **H)
    valable = None
    if r.status_code == 200:
        raw = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        with fitz.open(stream=raw, filetype='pdf') as doc:
            t = re.sub(r'\s+', ' ', ' '.join(pg.get_text() for pg in doc))
        valable = sorted(set(re.findall(r'\d{2}/\d{2}/20\d{2}', t)))
    attendu_pdf = (today + timedelta(days=10)).strftime('%d/%m/%Y')
    obs['proposal_http'] = r.status_code
    obs['pdf_dates'] = valable
    obs['pdf_imprime_J+10'] = bool(valable and attendu_pdf in valable)
    # l'admin raccourcit la validité après l'envoi
    prof = CompanyProfile.get(company=co)
    prof.quote_validity_days = 15
    prof.save()
    d = Devis.objects.get(pk=d.pk)
    try:
        accept_devis(devis=d, user=None, nom='K41 Alaoui')
        obs['acceptation_client'] = 'acceptee'
    except AcceptError as exc:
        obs['acceptation_client'] = ['refus', getattr(exc, 'code', None), str(exc)[:90]]
    d = Devis.objects.get(pk=d.pk)
    obs['statut_avant_beat'] = d.statut
    with mock.patch('authentication.selectors.active_company_ids', return_value=[co.pk]):
        res = recouvrement.expire_stale_devis()
    d.refresh_from_db()
    obs['beat'] = res
    obs['statut_apres_beat'] = d.statut
    print(obs)
    obs['repro'] = bool(obs['date_validite_apres_envoi'] is None and obs['pdf_imprime_J+10']
                        and isinstance(obs['acceptation_client'], list) and obs['acceptation_client'][1] == 'expiree'
                        and obs['statut_apres_beat'] == 'expire')
    return obs
