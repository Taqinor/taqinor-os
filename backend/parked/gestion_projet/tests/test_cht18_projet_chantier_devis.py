"""CHT18 — Pont chantier -> projet de facturation (situations de travaux).

Couvre : ``creer_projet_depuis_devis`` rattache le ``ProjetChantier`` du
chantier lié au devis DANS le MEME appel (un seul appel réseau au lieu de
deux) ; un re-run sur un devis déjà lié renvoie un message CIBLE nommant le
projet déjà rattaché (le chantier, quand identifiable) plutôt que le 400
générique d'avant ; étanchéité multi-sociétés (le chantier d'une autre
société n'est jamais rattaché).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.ventes.models import Devis

from apps.gestion_projet.models import ProjetChantier, ProjetLien
from apps.gestion_projet.services import (
    DevisVersProjetError, creer_projet_depuis_devis,
)
from apps.ventes.selectors import devis_pour_projet

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CreerProjetDepuisDevisChantierTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-cht18', 'S')
        self.autre_co = make_company('gp-cht18-autre', 'Autre')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Client', prenom='CHT18',
            email='cht18@example.com', telephone='+212600000181')
        self.devis = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0181',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        self.chantier = Installation.objects.create(
            company=self.co, reference='CH-CHT18-001', devis=self.devis,
            client=self.client_obj)

    def test_creation_pose_le_projet_chantier(self):
        """Le chantier lié au devis est rattaché EN UN SEUL appel — aucun
        second POST `projet-chantiers` n'est nécessaire côté frontend."""
        devis_data = devis_pour_projet(self.devis.id, self.co)
        resultat = creer_projet_depuis_devis(devis_data, company=self.co)

        pc = ProjetChantier.objects.get(
            company=self.co, projet=resultat['projet'])
        self.assertEqual(pc.chantier_id, self.chantier.id)
        self.assertEqual(pc.libelle, self.chantier.reference)

    def test_sans_chantier_lie_aucun_projet_chantier_cree(self):
        """Un devis sans chantier (YSERV1/YSERV9) crée quand même le projet,
        simplement sans rattachement (comportement dégradé assumé)."""
        client_obj = Client.objects.create(
            company=self.co, nom='Client', prenom='SansCh',
            email='cht18-sanschantier@example.com', telephone='+212600000182')
        devis_sans_chantier = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0182',
            client=client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        devis_data = devis_pour_projet(devis_sans_chantier.id, self.co)
        resultat = creer_projet_depuis_devis(devis_data, company=self.co)

        self.assertFalse(
            ProjetChantier.objects.filter(projet=resultat['projet']).exists())

    def test_rerun_message_cible_nomme_le_projet(self):
        """Re-run sur le même devis (déjà lié) -> message CIBLE nommant le
        chantier ET le projet déjà rattaché, au lieu du 400 générique."""
        devis_data = devis_pour_projet(self.devis.id, self.co)
        premier = creer_projet_depuis_devis(devis_data, company=self.co)

        with self.assertRaises(DevisVersProjetError) as ctx:
            creer_projet_depuis_devis(devis_data, company=self.co)

        message = str(ctx.exception)
        self.assertIn(self.chantier.reference, message)
        self.assertIn(premier['projet'].code, message)

    def test_rerun_sans_chantier_nomme_le_devis(self):
        """Sans chantier résolvable, le message ciblé retombe sur la
        référence du devis (toujours nommer LE projet déjà rattaché)."""
        client_obj = Client.objects.create(
            company=self.co, nom='Client', prenom='SansCh2',
            email='cht18-sanschantier2@example.com', telephone='+212600000183')
        devis_sans_chantier = Devis.objects.create(
            company=self.co, reference=f'DEV-{MONTH}-0183',
            client=client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        devis_data = devis_pour_projet(devis_sans_chantier.id, self.co)
        premier = creer_projet_depuis_devis(devis_data, company=self.co)

        with self.assertRaises(DevisVersProjetError) as ctx:
            creer_projet_depuis_devis(devis_data, company=self.co)

        message = str(ctx.exception)
        self.assertIn(devis_sans_chantier.reference, message)
        self.assertIn(premier['projet'].code, message)

    def test_cross_societe_chantier_autre_societe_jamais_rattache(self):
        """Etanchéité : un chantier d'une AUTRE société portant par bug/
        collision le même devis_id ne doit jamais être rattaché — la
        résolution passe par ``installation_for_devis(..., company=...)``
        (CHT12), scopée société."""
        # Devis + chantier de l'autre société (id de devis DIFFERENT, mais on
        # vérifie que la résolution ne traverse jamais la frontière société).
        autre_client = Client.objects.create(
            company=self.autre_co, nom='Client', prenom='Autre',
            email='cht18-autre@example.com', telephone='+212600000184')
        autre_devis = Devis.objects.create(
            company=self.autre_co, reference=f'DEV-{MONTH}-0184',
            client=autre_client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        Installation.objects.create(
            company=self.autre_co, reference='CH-CHT18-AUTRE',
            devis=autre_devis, client=autre_client)

        devis_data = devis_pour_projet(self.devis.id, self.co)
        resultat = creer_projet_depuis_devis(devis_data, company=self.co)

        pc = ProjetChantier.objects.get(projet=resultat['projet'])
        self.assertEqual(pc.chantier_id, self.chantier.id)
        self.assertEqual(pc.company_id, self.co.id)
        self.assertFalse(
            ProjetChantier.objects.filter(company=self.autre_co).exists())

    def test_lien_existant_toujours_pose(self):
        """Non-régression : le ``ProjetLien`` vers le devis est toujours créé
        (comportement XPRJ21 d'origine, inchangé par CHT18)."""
        devis_data = devis_pour_projet(self.devis.id, self.co)
        resultat = creer_projet_depuis_devis(devis_data, company=self.co)
        self.assertTrue(
            ProjetLien.objects.filter(
                company=self.co, projet=resultat['projet'],
                type_cible=ProjetLien.TypeCible.DEVIS,
                cible_id=self.devis.id).exists())
