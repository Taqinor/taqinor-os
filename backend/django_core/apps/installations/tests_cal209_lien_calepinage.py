"""CAL209 — le chantier lit le calepinage retenu via selectors (et rien de
plus).

Couvre :
  * ``apps.calepinage.selectors.calepinage_retenu_pour_devis`` — id/kWc/nb
    modules/lien, lus depuis la variante RETENUE d'un devis, ``None`` sinon ;
  * ``apps.installations.selectors.calepinage_retenu_du_chantier`` — le même
    bloc pour UN chantier, sans aucun nouveau champ sur ``Installation``.

Règle fondateur 12/09/2026 : « le module chantier ne garde QUE son cœur » —
ce test PROUVE l'absence de migration : ``Installation`` ne gagne aucun champ
calepinage (le chantier se BRANCHE sur le sélecteur, il n'absorbe pas).

Run :
    python manage.py test apps.installations.tests_cal209_lien_calepinage -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.selectors import calepinage_retenu_pour_devis
from apps.calepinage.services.variantes import bascule_autorisee
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.selectors import calepinage_retenu_du_chantier
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(nom=f'CAL209 Co {n}', slug=f'cal209-co-{n}')


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CAL209',
        email=f'cal209-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CAL209-{n}', client=client,
        taux_tva=Decimal('20'))


def make_installation(company, client, devis=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-CAL209-{n}', client=client,
        devis=devis)


def make_calepinage(company, client, devis):
    return Calepinage.objects.create(
        company=company, client=client, devis=devis)


def make_variante(company, calepinage, retenue, resultat=None,
                  roof_layout=None):
    kwargs = dict(company=company, calepinage=calepinage, nom='V1',
                  resultat=resultat, roof_layout=roof_layout)
    if retenue:
        with bascule_autorisee():
            return CalepinageVariante.objects.create(retenue=True, **kwargs)
    return CalepinageVariante.objects.create(retenue=False, **kwargs)


class TestCalepinageRetenuPourDevis(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)

    def test_sans_calepinage_renvoie_none(self):
        self.assertIsNone(
            calepinage_retenu_pour_devis(self.devis.id, self.company))

    def test_calepinage_sans_variante_retenue_renvoie_none(self):
        calepinage = make_calepinage(self.company, self.client_obj, self.devis)
        make_variante(self.company, calepinage, retenue=False)
        self.assertIsNone(
            calepinage_retenu_pour_devis(self.devis.id, self.company))

    def test_lit_le_resultat_du_moteur_en_priorite(self):
        calepinage = make_calepinage(self.company, self.client_obj, self.devis)
        make_variante(
            self.company, calepinage, retenue=True,
            resultat={'pose': {'kwc': 8.64, 'total_modules': 12}},
            roof_layout={'result': {'kwc': 999, 'panels': 999}})
        bloc = calepinage_retenu_pour_devis(self.devis.id, self.company)
        self.assertEqual(bloc['id'], calepinage.id)
        self.assertEqual(bloc['kwc'], 8.64)
        self.assertEqual(bloc['nb_modules'], 12)
        self.assertEqual(bloc['planche_url'], f'/calepinage/{calepinage.id}')

    def test_repli_sur_le_resume_de_l_atelier_sans_resultat_moteur(self):
        calepinage = make_calepinage(self.company, self.client_obj, self.devis)
        make_variante(
            self.company, calepinage, retenue=True,
            resultat=None,
            roof_layout={'result': {'kwc': 5.76, 'panels': 8}})
        bloc = calepinage_retenu_pour_devis(self.devis.id, self.company)
        self.assertEqual(bloc['kwc'], 5.76)
        self.assertEqual(bloc['nb_modules'], 8)

    def test_sans_devis_id_renvoie_none(self):
        self.assertIsNone(calepinage_retenu_pour_devis(None, self.company))

    def test_sans_company_renvoie_none(self):
        self.assertIsNone(calepinage_retenu_pour_devis(self.devis.id, None))


class TestCalepinageRetenuDuChantier(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)

    def test_chantier_sans_devis_renvoie_none(self):
        chantier = make_installation(self.company, self.client_obj)
        self.assertIsNone(calepinage_retenu_du_chantier(chantier))

    def test_chantier_avec_devis_sans_calepinage_renvoie_none(self):
        chantier = make_installation(self.company, self.client_obj, self.devis)
        self.assertIsNone(calepinage_retenu_du_chantier(chantier))

    def test_chantier_avec_calepinage_retenu_renvoie_le_bloc(self):
        calepinage = make_calepinage(self.company, self.client_obj, self.devis)
        make_variante(
            self.company, calepinage, retenue=True,
            resultat={'pose': {'kwc': 8.64, 'total_modules': 12}})
        chantier = make_installation(self.company, self.client_obj, self.devis)
        bloc = calepinage_retenu_du_chantier(chantier)
        self.assertEqual(bloc['calepinage_id'], calepinage.id)
        self.assertEqual(bloc['kwc'], 8.64)
        self.assertEqual(bloc['nb_modules'], 12)
        self.assertEqual(bloc['planche_url'], f'/calepinage/{calepinage.id}')
        self.assertEqual(
            bloc['plan_pose_url'], f'/ventes/devis/{self.devis.id}/3d')

    def test_installation_ne_gagne_aucun_champ_calepinage(self):
        """CAL209 — le chantier ne garde que son cœur : aucun nouveau champ
        calepinage sur le modèle Installation (la lecture passe UNIQUEMENT
        par le sélecteur, jamais par une colonne locale)."""
        noms_champs = {f.name for f in Installation._meta.get_fields()}
        for interdit in ('calepinage', 'calepinage_id', 'calepinage_retenu'):
            self.assertNotIn(
                interdit, noms_champs,
                f"Installation a gagné un champ « {interdit} » — le chantier "
                "doit se BRANCHER sur apps.calepinage.selectors, jamais "
                "absorber la donnée (règle fondateur 12/09/2026).")
