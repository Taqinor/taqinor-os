# -*- coding: utf-8 -*-
"""ACAL239 — ``DossierReglementaire.genere_empreinte`` : l'empreinte des
entrées au moment de la génération, vide par défaut, relue à l'identique
après rechargement depuis la base."""
from __future__ import annotations

from apps.calepinage.models import (
    Calepinage, DossierReglementaire, GabaritDossierReglementaire,
)

from .test_api_liste import BaseApiCalepinage


class SchemaDossierTest(BaseApiCalepinage):

    def test_genere_empreinte_vide_par_defaut_et_relue(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa')
        gabarit = GabaritDossierReglementaire.objects.create(
            company=self.company, pays='ma', code='dp', intitule='DP')
        dossier = DossierReglementaire.objects.create(
            company=self.company, calepinage=calepinage, gabarit=gabarit)

        dossier.refresh_from_db()
        self.assertEqual(dossier.genere_empreinte, '')

        empreinte = 'a' * 64
        dossier.genere_empreinte = empreinte
        dossier.save(update_fields=['genere_empreinte'])
        relu = DossierReglementaire.objects.get(pk=dossier.pk)
        self.assertEqual(relu.genere_empreinte, empreinte)
