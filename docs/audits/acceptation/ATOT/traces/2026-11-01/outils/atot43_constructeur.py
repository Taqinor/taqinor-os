# ATOT53 P4 (ATOT43) — rejeu du constructeur unique d'avoir d'écart sur la pile locale (société démo).
# Lancé par `python manage.py shell < ce fichier` (mail en mémoire, Celery hors ligne). Données
# créées sous la société de demo_admin, préfixe « ATOT53-P4 » ; rien d'existant n'est touché.
# Mode PHASE=ecrire : crée la vente (devis posé ORM comme la sonde C-ATOT-VER-004, 5 tranches par la
# vraie route generer-facture + emettre), appelle crediter_ecart_de_vente, COMMIT.
# Mode PHASE=relire DEVIS=<id> : relit factures et avoirs (persistance) dans un second processus.
import json
import os
import time
from decimal import Decimal

from django.conf import settings
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver', 'localhost']
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Devis, Facture, LigneDevis

PHASE = os.environ.get('PHASE', 'ecrire')
OUT = os.environ['OUT']
u = get_user_model().objects.get(username='demo_admin')
co = u.company


def etat(devis_id):
    fs = Facture.objects.filter(company=co, devis_id=devis_id).order_by('pk')
    rows = []
    for f in fs:
        f.refresh_from_db()
        avs = Avoir.objects.filter(facture=f).order_by('pk')
        rows.append({'facture': f.reference, 'statut': f.statut, 'ttc': str(f.total_ttc), 'montant_du': str(f.montant_du),
                     'avoirs': [{'ref': a.reference, 'type': a.type, 'statut': a.statut, 'ttc': str(a.total_ttc),
                                 'tva_par_taux': json.loads(json.dumps(a.tva_par_taux, default=str))}
                                for a in avs]})
    return {'factures': rows, 'du_total': str(sum(Decimal(r['montant_du']) for r in rows))}


if PHASE == 'ecrire':
    out = {}
    try:
        from apps.ventes.domain.facturation_vente import crediter_ecart_de_vente
        from apps.ventes.domain.facturation_ops import AvoirPlafondDepasse
    except ImportError as e:
        out = {'constructeur': f'ABSENT ({e})'}
        print('@@RESULT ' + json.dumps(out))
        raise SystemExit(0)
    run = time.strftime('%H%M%S')
    cl = Client.objects.create(company=co, nom='ATOT53-P4', prenom=run, email=f'atot53-p4-{run}@example.invalid')
    p = Produit.objects.create(company=co, nom=f'ATOT53-P4 Panneau {run}', sku=f'ATOT53-P4-{run}',
                               prix_vente=Decimal('1000'), quantite_stock=1000)
    d = Devis.objects.create(company=co, reference=f'DEV-ATOT53-P4-{run}', client=cl, statut=Devis.Statut.ACCEPTE,
                             taux_tva=Decimal('20'), mode_installation='residentiel', created_by=u,
                             echeancier=[{'pct_or_montant': 20}] * 5)
    LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                              prix_unitaire=Decimal('1000'), remise=Decimal('0'), taux_tva=Decimal('20'))
    api = APIClient()
    api.force_authenticate(u)
    H = {'format': 'json', 'HTTP_HOST': 'localhost'}
    codes = []
    for _ in range(5):
        r0 = api.post(f'/api/django/ventes/devis/{d.pk}/generer-facture/', {}, **H)
        fid = (r0.data or {}).get('id') if r0.status_code in (200, 201) else None
        r1 = api.post(f'/api/django/ventes/factures/{fid}/emettre/', {}, **H) if fid else None
        codes.append([r0.status_code, (r0.data or {}).get('statut') if isinstance(r0.data, dict) else None, r1.status_code if r1 else None])
    from core.events import avoir_cree
    EMIS = []
    def _rec(sender, instance=None, **kw):
        EMIS.append(getattr(instance, 'reference', None))
    avoir_cree.connect(_rec, weak=False)
    out['devis'] = d.pk
    out['generer_emettre'] = codes
    out['avant'] = etat(d.pk)
    # Écart > Σ créditable : AvoirPlafondDepasse, rien d'écrit.
    n_av = Avoir.objects.filter(company=co, facture__devis_id=d.pk).count()
    try:
        crediter_ecart_de_vente(d, Decimal('12000.01'), [{'taux': 20, 'base_ht': '10000.01', 'montant': '2000.00'}],
                                user=u, motif='ATOT53 P4 dépassement')
        out['depassement'] = 'ACCEPTÉ (défaut)'
    except AvoirPlafondDepasse as e:
        out['depassement'] = f'AvoirPlafondDepasse : {e}'
    out['avoirs_apres_depassement'] = Avoir.objects.filter(company=co, facture__devis_id=d.pk).count() - n_av
    avs = crediter_ecart_de_vente(d, Decimal('3000'), [{'taux': 20, 'base_ht': '2500', 'montant': '500'}],
                                  user=u, motif='ATOT53 P4 écart 3 000')
    out['retour'] = [str(a) for a in (avs or [])]
    out['apres'] = etat(d.pk)
    out['avoir_cree_emis'] = EMIS
    print('@@RESULT ' + json.dumps(out, ensure_ascii=False))
else:
    print('@@RESULT ' + json.dumps({'relu': etat(int(os.environ['DEVIS']))}, ensure_ascii=False))
