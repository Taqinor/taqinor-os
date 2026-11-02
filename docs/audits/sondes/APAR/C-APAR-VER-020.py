SONDE = {"constat": "C-APAR-VER-020", "sha": "56d5b623a",
         "modeles": ["parametres.EmailTemplate", "ventes.EmailLog", "ventes.Facture"],
         "attendu": "après « Réinitialiser » (ou un simple enregistrement du sujet) du modèle « Facture » dans "
                    "Paramètres › E-mails, l'e-mail de facture envoyé au client ne contient pas de phrase "
                    "« au lien suivant : » sans lien ; le texte reste celui d'avant (ci-joint) ou porte un vrai lien"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from unittest import mock
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture
    from apps.ventes.email_service import send_document_email
    co = Company.objects.create(nom='Sonde APAR VER-020', slug='sonde-apar-ver-020')
    admin = get_user_model().objects.create_user(username='sonde-apar-ver-020-adm', password='x', company=co,
                                                 role_legacy='admin')
    cli = Client.objects.create(company=co, nom='Alaoui', prenom='Karim', email='k.ver020@example.invalid')
    fac = Facture.objects.create(company=co, reference='FAC-VER020-0001', client=cli,
                                 statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'))
    api = APIClient()
    api.force_authenticate(admin)
    eff = api.get('/api/django/parametres/email-templates/effective/', HTTP_HOST='localhost')
    ligne = next(t for t in eff.data['results'] if t['cle'] == 'facture')
    # Geste exact du bouton « Réinitialiser » d'EmailSection.jsx (resetTemplate).
    r = api.put('/api/django/parametres/email-templates/bulk/',
                {'templates': [{'cle': 'facture', 'sujet': ligne['sujet_defaut'],
                                'corps': ligne['corps_defaut']}]}, format='json', HTTP_HOST='localhost')
    envoyes = []
    # Transport seul remplacé (aucun appel réseau) : la composition du corps reste réelle.
    with mock.patch('apps.ventes.email_service._send',
                    side_effect=lambda to, sujet, corps, *a, **k: (envoyes.append(corps) or (True, ''))):
        log = send_document_email(fac, user=admin, attach_pdf=False)
    log.refresh_from_db()
    corps = log.corps or ''
    lien_vide = 'au lien suivant : \n' in corps or corps.rstrip().endswith('au lien suivant :')
    print(f'reset bulk={r.status_code} ; EmailLog.corps={corps[:160]!r} ; lien vide={lien_vide} ; '
          f'ci-joint={"ci-joint" in corps} ; transport appelé={len(envoyes)}')
    return {'repro': r.status_code == 200 and lien_vide, 'corps': corps[:200]}
