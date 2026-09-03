"""AUD308 — « Document généré le » n'est plus figé au démarrage du process.

Défaut : `erp_agentique/jinja2.py` posait ``env.globals['now'] =
datetime.now()`` — une VALEUR, évaluée dans la factory ``environment()``. Or
cette factory n'est appelée qu'une fois par process (Django met le moteur en
cache dans ``django.template.utils.EngineHandler.__getitem__``) : `now` était
donc l'instant de démarrage de Gunicorn/Celery, pas celui du rendu. Un PV
téléchargé trois semaines après le dernier redémarrage affichait « Document
généré le <date du redémarrage> » — sur un document à valeur d'acceptation, et
sur les 20+ autres gabarits PDF qui partagent la même factory.

Rouge d'abord, PAR EXÉCUTION : on rend deux fois via le moteur RÉELLEMENT
configuré (le même objet mis en cache par Django, celui dont le global était
figé) avec une avance de temps simulée entre les deux, et on constate deux
dates identiques avant le correctif.

Run :
    docker compose exec django_core python manage.py test \
        apps.documents.tests.test_aud308_date_generation -v 2
"""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.template import engines
from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

T1 = datetime(2026, 1, 5, 8, 15)
T2 = datetime(2026, 3, 27, 17, 42)
GABARIT = "Document généré le {{ now.strftime('%d/%m/%Y à %H:%M') }}"


class DateGenerationEvalueeAuRenduTests(TestCase):
    """Le moteur Jinja2 EN CACHE doit rendre une date fraîche à chaque rendu."""

    def test_deux_rendus_du_meme_moteur_portent_deux_dates(self):
        # `engines['jinja2']` est l'instance mise en cache par Django — celle
        # dont le global `now` était figé au démarrage du process.
        moteur = engines['jinja2']
        tpl = moteur.from_string(GABARIT)

        with patch('erp_agentique.jinja2.datetime') as faux:
            faux.now.return_value = T1
            premier = tpl.render({})
            faux.now.return_value = T2
            second = tpl.render({})

        self.assertIn('05/01/2026 à 08:15', premier)
        self.assertIn('27/03/2026 à 17:42', second)
        self.assertNotEqual(premier, second)

    def test_now_reste_appelable_et_affichable(self):
        moteur = engines['jinja2']

        with patch('erp_agentique.jinja2.datetime') as faux:
            faux.now.return_value = T1
            rendu = moteur.from_string(
                "{{ now().strftime('%Y') }}|{{ now.year }}").render({})

        self.assertEqual(rendu, '2026|2026')


def _chantier(company, ref):
    client = Client.objects.create(
        company=company, nom='Berrada', prenom='Nour',
        telephone='+212600000308', adresse='9 rue Test, Fès')
    produit = Produit.objects.create(
        company=company, nom='Panneau 550W', sku=f'PV-{ref}',
        prix_vente=Decimal('1500.00'), prix_achat=Decimal('444.44'),
        quantite_stock=6, marque='JA Solar', garantie='25 ans')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{ref}', client=client,
        statut='accepte', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'))
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Panneau 550W',
        quantite=Decimal('6'), prix_unitaire=Decimal('1500.00'),
        remise=Decimal('0'))
    return Installation.objects.create(
        company=company, reference=ref, client=client, devis=devis,
        puissance_installee_kwc=Decimal('3.30'),
        date_mise_en_service='2026-06-01', date_pose_reelle='2026-05-28',
        site_adresse='9 rue Test', site_ville='Fès')


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class PvReceptionDateReelleTests(TestCase):
    """Bout en bout sur un vrai document client (le PV de réception, N21)."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aud308-co', defaults={'nom': 'AUD308 Co'})[0]

    def test_pv_rendu_a_deux_instants_porte_deux_dates(self, mock_pdf, _dl):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        chantier = _chantier(self.company, 'CH-AUD308-PV')

        with patch('erp_agentique.jinja2.datetime') as faux:
            faux.now.return_value = T1
            builders.generate_pv_reception(chantier)
            premier = mock_pdf.call_args[0][0]
            faux.now.return_value = T2
            builders.generate_pv_reception(chantier)
            second = mock_pdf.call_args[0][0]

        self.assertIn('Document généré le 05/01/2026 à 08:15', premier)
        self.assertIn('Document généré le 27/03/2026 à 17:42', second)
