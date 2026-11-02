# flake8: noqa  (sonde de contre-visite vérifie AMOT, rejouable par scripts/sonde.py — AMET93)
"""AMOT14 (CLAUSE CLIENT « l'e-mail et Télécharger livrent le format validé par le commercial ») : un devis dont le
dernier rendu PERSISTÉ est la une-page (`pdf_render_meta.options.pdf_mode = 'onepage'`) est envoyé par
« Envoyer par e-mail » avec le corps que les deux écrans envoient (`{to_email}` seul, sans `pdf_mode` :
`features/crm/workspace/useEnvoiDevis.js`, `pages/ventes/devisList/useDevisEnvoi.js`). La vue
`views/devis_envoi.py::envoyer_email` rend la pièce jointe avec `pdf_mode = request.data.get('pdf_mode') or 'full'`.
Le moteur est intercepté (on lit seulement les options demandées), rien n'est rendu ni téléversé ; transaction annulée."""
SONDE = {"constat": "C-AMOT-VER-050", "sha": "56d5b623a",
         "attendu": "dernier rendu persisté une-page, POST envoyer-email {to_email} : la pièce jointe est demandée en 'full' (3 pages), pas au format mémorisé"}


def sonde(ctx):
    from unittest import mock
    from rest_framework.test import APIClient
    from django.contrib.auth import get_user_model
    from apps.ventes.quote_engine.builder import clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis
    U = get_user_model()
    co = make_company(slug='sonde-amot-ver-050', nom='SONDE AMOT VER-050')
    admin = U.objects.create_user(username='sonde-amot-ver-050-a', password='x', company=co,
                                  is_superuser=True, is_staff=True)
    cl = make_client(co)
    dv = make_devis(co, admin, cl, [('Panneau mono 550W', '12', '1100'), ('Onduleur réseau 5kW', '1', '11700')],
                    reference='DEV-SONDE-AMOT-050')
    cle = f'devis/{co.pk}/{dv.reference}.pdf'
    dv.fichier_pdf = cle
    dv.pdf_render_meta = {'empreinte': 'x', 'options': clean_pdf_options({'pdf_mode': 'onepage'})}
    dv.save(update_fields=['fichier_pdf', 'pdf_render_meta'])
    demandes = []

    def moteur(devis_id, pdf_options=None, persist=True):
        demandes.append((dict(pdf_options or {}), persist))
        return cle + '__apercu'
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(admin)
    with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf', moteur), \
            mock.patch('apps.ventes.utils.pdf.download_pdf', lambda k: b'%PDF-1.4 sonde'):
        r = api.post(f'/api/django/ventes/devis/{dv.pk}/envoyer-email/',
                     {'to_email': 'sonde-amot-ver-050@example.invalid'}, format='json', HTTP_HOST='localhost')
    mode_demande = demandes[0][0].get('pdf_mode') if demandes else None
    print(f"statut={r.status_code} ; format memorise=onepage ; rendus demandes={[(d.get('pdf_mode'), p) for d, p in demandes]}")
    return {'repro': mode_demande == 'full', 'statut': r.status_code, 'mode_piece_jointe': mode_demande}
