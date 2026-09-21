"""NTCPQ31 — Toggle "règles de compatibilité strictes vs avertissement".

``ParametresCPQ.compatibilite_mode`` contrôle si une violation INCOMPATIBLE
(NTCPQ1) bloque réellement ``envoyer``/``generer-pdf`` ou reste un simple
badge (NTCPQ21). Par défaut ``AVERTISSEMENT`` : aucune régression pour les
sociétés existantes.
"""
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.cpq import services
from apps.cpq.models import ContrainteCompatibilite, ParametresCPQ
from testkit.factories import (
    CompanyFactory, DevisFactory, LigneDevisFactory, ProduitFactory,
)


class TestCompatibiliteMode(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.pa = ProduitFactory(company=self.company)
        self.pb = ProduitFactory(company=self.company)
        ContrainteCompatibilite.objects.create(
            company=self.company, produit_a=self.pa, produit_b=self.pb,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE,
            message_utilisateur='Incompatibles.')

    def _devis_avec_violation(self):
        devis = DevisFactory(company=self.company)
        LigneDevisFactory(devis=devis, produit=self.pa)
        LigneDevisFactory(devis=devis, produit=self.pb)
        return devis

    def test_defaut_avertissement_envoi_libre(self):
        devis = self._devis_avec_violation()
        # AUCUN ParametresCPQ créé : repli sur le défaut AVERTISSEMENT.
        services.verifier_compatibilite_envoyable(devis)  # ne lève pas

    def test_bloquant_empeche_envoi(self):
        ParametresCPQ.objects.create(
            company=self.company,
            compatibilite_mode=ParametresCPQ.ModeCompatibilite.BLOQUANT)
        devis = self._devis_avec_violation()
        with self.assertRaises(ValidationError):
            services.verifier_compatibilite_envoyable(devis)

    def test_avertissement_explicite_envoi_libre(self):
        ParametresCPQ.objects.create(
            company=self.company,
            compatibilite_mode=ParametresCPQ.ModeCompatibilite.AVERTISSEMENT)
        devis = self._devis_avec_violation()
        services.verifier_compatibilite_envoyable(devis)  # ne lève pas

    def test_isolation_multi_tenant_du_reglage(self):
        """Le mode BLOQUANT d'une société n'affecte jamais une autre société."""
        ParametresCPQ.objects.create(
            company=self.company,
            compatibilite_mode=ParametresCPQ.ModeCompatibilite.BLOQUANT)
        autre_company = CompanyFactory()
        pa2 = ProduitFactory(company=autre_company)
        pb2 = ProduitFactory(company=autre_company)
        ContrainteCompatibilite.objects.create(
            company=autre_company, produit_a=pa2, produit_b=pb2,
            type=ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE)
        autre_devis = DevisFactory(company=autre_company)
        LigneDevisFactory(devis=autre_devis, produit=pa2)
        LigneDevisFactory(devis=autre_devis, produit=pb2)
        # Aucun ParametresCPQ pour autre_company → AVERTISSEMENT par défaut.
        services.verifier_compatibilite_envoyable(autre_devis)  # ne lève pas

    def test_bloquant_sans_violation_envoi_libre(self):
        ParametresCPQ.objects.create(
            company=self.company,
            compatibilite_mode=ParametresCPQ.ModeCompatibilite.BLOQUANT)
        devis = DevisFactory(company=self.company)
        LigneDevisFactory(devis=devis, produit=self.pa)
        services.verifier_compatibilite_envoyable(devis)  # ne lève pas
