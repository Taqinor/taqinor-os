"""
EZ7 — « Signature client obligatoire pour clôturer » (réglage société ADDITIF).

La signature terrain (FG69) existait mais restait hors de la garde
« Terminée » : une intervention pouvait être clôturée sans preuve signée.
Ce test couvre :
  * défaut OFF → comportement historique BYTE-IDENTIQUE (aucun blocage) ;
  * réglage ON + aucune signature → transition vers « Terminée » refusée avec
    un message français ;
  * réglage ON + signature enregistrée → la transition passe ;
  * le réglage d'une société n'affecte pas l'autre (multi-tenant) ;
  * la garde ne s'applique QU'À l'entrée dans « Terminée » (un recul reste
    permis, une transition intermédiaire n'est pas touchée).

Run :
    python manage.py test apps.installations.tests_ez7_signature_obligatoire -v2
"""
import itertools

from django.test import TestCase

from apps.crm.models import Client
from apps.installations import field_services
from apps.installations.models import Installation, Intervention
from apps.parametres.models import CompanyProfile

_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ez7-co-{n}', defaults={'nom': f'EZ7 Co {n}'})
    return company


def make_intervention(company, statut=Intervention.Statut.SUR_SITE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='EZ7',
        email=f'ez7-{company.id}-{n}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=f'CHT-EZ7-{n}', client=client)
    return Intervention.objects.create(
        company=company, installation=inst,
        type_intervention='controle', statut=statut)


class TestSignatureObligatoire(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_defaut_off_ne_bloque_rien(self):
        """Défaut = False : la garde est exactement celle d'avant EZ7."""
        prof = CompanyProfile.get(self.company)
        self.assertFalse(prof.signature_client_obligatoire)
        interv = make_intervention(self.company)
        self.assertIsNone(field_services.transition_block_reason(
            interv, Intervention.Statut.TERMINEE))

    def test_reglage_on_sans_signature_bloque(self):
        prof = CompanyProfile.get(self.company)
        prof.signature_client_obligatoire = True
        prof.save(update_fields=['signature_client_obligatoire'])
        interv = make_intervention(self.company)
        raison = field_services.transition_block_reason(
            interv, Intervention.Statut.TERMINEE)
        self.assertIsNotNone(raison)
        self.assertIn('Signature du client', raison)

    def test_reglage_on_avec_signature_passe(self):
        prof = CompanyProfile.get(self.company)
        prof.signature_client_obligatoire = True
        prof.save(update_fields=['signature_client_obligatoire'])
        interv = make_intervention(self.company)
        interv.signature_client = 'data:image/png;base64,AAA'
        interv.save(update_fields=['signature_client'])
        self.assertIsNone(field_services.transition_block_reason(
            interv, Intervention.Statut.TERMINEE))

    def test_signature_vide_ne_compte_pas(self):
        prof = CompanyProfile.get(self.company)
        prof.signature_client_obligatoire = True
        prof.save(update_fields=['signature_client_obligatoire'])
        interv = make_intervention(self.company)
        interv.signature_client = '   '
        interv.save(update_fields=['signature_client'])
        raison = field_services.transition_block_reason(
            interv, Intervention.Statut.TERMINEE)
        self.assertIsNotNone(raison)

    def test_reglage_isole_par_societe(self):
        prof = CompanyProfile.get(self.company)
        prof.signature_client_obligatoire = True
        prof.save(update_fields=['signature_client_obligatoire'])
        autre = make_company()
        interv_autre = make_intervention(autre)
        self.assertIsNone(field_services.transition_block_reason(
            interv_autre, Intervention.Statut.TERMINEE))

    def test_ne_touche_pas_les_transitions_intermediaires(self):
        prof = CompanyProfile.get(self.company)
        prof.signature_client_obligatoire = True
        prof.save(update_fields=['signature_client_obligatoire'])
        interv = make_intervention(self.company, Intervention.Statut.EN_ROUTE)
        self.assertIsNone(field_services.transition_block_reason(
            interv, Intervention.Statut.SUR_SITE))

    def test_recul_depuis_terminee_reste_permis(self):
        prof = CompanyProfile.get(self.company)
        prof.signature_client_obligatoire = True
        prof.save(update_fields=['signature_client_obligatoire'])
        interv = make_intervention(self.company, Intervention.Statut.TERMINEE)
        self.assertIsNone(field_services.transition_block_reason(
            interv, Intervention.Statut.SUR_SITE))


class TestSignatureRequiseHelper(TestCase):
    def test_sans_company_retombe_sur_faux(self):
        company = make_company()
        interv = make_intervention(company)
        interv.company = None
        self.assertFalse(field_services.signature_client_requise(interv))
