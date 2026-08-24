# -*- coding: utf-8 -*-
"""L-2OPT — Commande de réparation : rendre son option « sans batterie » à un
devis à DEUX OPTIONS que la resynchronisation 3D avait rétréci.

    python manage.py reparer_devis_deux_options            # DRY-RUN (défaut)
    python manage.py reparer_devis_deux_options --apply
    python manage.py reparer_devis_deux_options --company <id|slug>
    python manage.py reparer_devis_deux_options --refs DEV-202608-0023

LE DÉGÂT QU'ELLE RÉPARE. Un devis né « Les deux (Sans + Avec) » (U2) porte
LÉGITIMEMENT deux onduleurs : le RÉSEAU sert l'option « sans », l'HYBRIDE +
BATTERIE l'option « avec ». Avant le correctif L-2OPT,
``services.sync_devis_from_layout`` (enregistrement du calepinage 3D) prenait
l'onduleur réseau pour l'« intrus » de l'artefact deux-onduleurs, le supprimait
— il était au prix catalogue, donc supprimé sans un mot — puis réécrivait
``etude_params['scenario']`` avec un libellé MONO. Le moteur PDF relisait cette
déclaration mono (PV86/QF6) : la page publique du client ne montrait plus qu'une
seule option. Le correctif empêche de nouveaux dégâts ; cette commande soigne
les devis DÉJÀ abîmés.

CE QU'ELLE NE FAIT PAS : aucun statut n'est touché (règle #4), aucun prix
existant n'est retouché, aucune ligne n'est supprimée, aucun chiffre n'est
inventé (la ligne recréée porte le prix CATALOGUE du produit choisi, sans
remise). Un devis dont le catalogue société n'offre aucun onduleur réseau
TARIFÉ est SAUTÉ — jamais réparé avec une ligne sans prix.

POURQUOI LA DÉTECTION EST STRUCTURELLE (et donc faillible). Le seul indice
PERSISTÉ de « ce devis est né à deux options » était ``etude_params['scenario']``
lui-même : la création (``build_devis_from_layout``) ne pose aucun autre drapeau
(``deux_options`` n'est qu'un paramètre de composition, jamais un champ du
modèle), et le chatter du devis ne journalise pas le scénario. C'est précisément
cet unique indice que le bug écrasait. On reconnaît donc les victimes à la FORME
que le bug laisse derrière lui :

    statut « brouillon »
    + ``etude_params['scenario'] == 'Avec batterie'``
    + ``roof_layout`` renseigné (le calepinage 3D est bien passé par là)
    + lignes : onduleur HYBRIDE + BATTERIE, et AUCUN onduleur réseau.

CE QUE CETTE DÉTECTION PEUT ATTRAPER À TORT : un devis NÉ mono « Avec batterie »
(le commercial a délibérément choisi la seule option avec batterie) sur lequel
quelqu'un a ensuite dessiné un calepinage porte exactement la même forme. Rien,
dans la base, ne le distingue d'une victime. C'est EXACTEMENT pourquoi le
DRY-RUN est le comportement par défaut et pourquoi ``--refs`` existe : on relit
la liste proposée, on ne garde que les références qu'on reconnaît, et on
n'applique que celles-là.

IDEMPOTENTE : un devis réparé porte réseau + hybride + batterie et le scénario
« Les deux (Sans + Avec) » — il ne correspond donc plus au critère, et une
seconde exécution ne trouve plus rien.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "L-2OPT — répare les devis à deux options rétrécis en mono par la "
        "resynchronisation 3D : recrée l'onduleur RÉSEAU manquant au prix "
        "catalogue et re-stocke le scénario « Les deux (Sans + Avec) ». "
        "DRY-RUN par défaut (--apply pour écrire). Aucun statut n'est touché. "
        "ATTENTION : la détection est structurelle et peut attraper un devis "
        "né mono « Avec batterie » sur lequel un calepinage a été dessiné — "
        "relisez la liste du dry-run et ciblez avec --refs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help="Écrire réellement (sans ce drapeau : DRY-RUN, rien n'est "
                 "modifié).")
        parser.add_argument(
            '--company', default=None,
            help="Ne traiter que cette société (id ou slug). Sans ce "
                 "paramètre : toutes les sociétés — chaque réparation reste "
                 "de toute façon bornée à la société de son devis.")
        parser.add_argument(
            '--refs', default=None,
            help="Ne traiter que ces références de devis, séparées par des "
                 "virgules (ex. DEV-202608-0023,DEV-202608-0031).")

    def handle(self, *args, **options):
        from apps.ventes.models import Devis
        from apps.ventes.services import (SCENARIO_AVEC_BATTERIE,
                                          SCENARIO_LES_DEUX)

        appliquer = bool(options['apply'])
        societe = self._resoudre_societe(options.get('company'))
        references = self._resoudre_references(options.get('refs'))

        qs = Devis.objects.filter(statut=Devis.Statut.BROUILLON)
        if societe is not None:
            qs = qs.filter(company=societe)
        if references:
            qs = qs.filter(reference__in=references)

        candidats, sautes = [], []
        # ``prefetch_related`` : la classification lit les lignes ET leur
        # produit de CHAQUE brouillon — sans lui, un balayage « toutes
        # sociétés » ferait deux requêtes par devis.
        qs = (qs.select_related('company')
                .prefetch_related('lignes__produit').order_by('reference'))
        for devis in qs:
            motif = self._motif_de_rejet(devis, SCENARIO_AVEC_BATTERIE)
            if motif is None:
                candidats.append(devis)
            elif references and devis.reference in references:
                # Référence explicitement demandée : on DIT pourquoi elle n'est
                # pas traitée, au lieu de la faire disparaître en silence.
                sautes.append((devis.reference, motif))

        for reference, motif in sautes:
            self.stdout.write('~ %s — non concerné : %s' % (reference, motif))

        if not candidats:
            self.stdout.write(
                'Aucun devis à réparer%s.'
                % (' pour ces références' if references else ''))
            return

        repares, ignores = 0, 0
        for devis in candidats:
            produit = self._onduleur_reseau_tarife(devis)
            if produit is None:
                ignores += 1
                self.stdout.write(
                    '! %s (société %s) — SAUTÉ : aucun onduleur réseau tarifé '
                    'au catalogue de cette société. Ajoutez-en un (ou levez '
                    'sa marque épinglée dans Paramètres → Gammes), puis '
                    'relancez.'
                    % (devis.reference, getattr(devis.company, 'slug', '?')))
                continue
            if not appliquer:
                self.stdout.write(
                    '· %s (société %s) — À RÉPARER : ajouterait « %s » à %s '
                    '(prix catalogue, sans remise) et re-stockerait le '
                    'scénario « %s ».'
                    % (devis.reference, getattr(devis.company, 'slug', '?'),
                       produit.nom, produit.prix_vente, SCENARIO_LES_DEUX))
                repares += 1
                continue
            if self._reparer(devis):
                repares += 1
                self.stdout.write(
                    '+ %s (société %s) — RÉPARÉ : « %s » ajouté à %s, '
                    'scénario « %s » restauré.'
                    % (devis.reference, getattr(devis.company, 'slug', '?'),
                       produit.nom, produit.prix_vente, SCENARIO_LES_DEUX))
            else:
                ignores += 1
                self.stdout.write(
                    '! %s — SAUTÉ : le devis a changé entre la détection et '
                    'la réparation (il n\'est plus dans l\'état abîmé).'
                    % devis.reference)

        self.stdout.write(
            '%s : %d devis %s, %d sauté(s).'
            % ('APPLIQUÉ' if appliquer else 'DRY-RUN (rien n\'a été écrit)',
               repares, 'réparé(s)' if appliquer else 'à réparer', ignores))

    # ── Résolution des paramètres ──────────────────────────────────────────
    def _resoudre_societe(self, valeur):
        if not valeur:
            return None
        from authentication.models import Company
        societe = (Company.objects.filter(slug=valeur).first()
                   or (Company.objects.filter(pk=valeur).first()
                       if str(valeur).isdigit() else None))
        if societe is None:
            raise CommandError('Société inconnue : %s' % valeur)
        return societe

    def _resoudre_references(self, valeur):
        if not valeur:
            return []
        references = [r.strip() for r in str(valeur).split(',') if r.strip()]
        if not references:
            raise CommandError(
                '--refs ne contient aucune référence exploitable.')
        return references

    # ── Détection ──────────────────────────────────────────────────────────
    def _motif_de_rejet(self, devis, scenario_mono):
        """``None`` si ``devis`` est une victime ; sinon le motif, en français.

        La forme recherchée est celle que le bug laisse derrière lui (voir le
        module) : scénario mono « Avec batterie », calepinage enregistré, et
        des lignes qui portent l'option « avec » sans plus rien pour servir
        l'option « sans ».
        """
        from apps.ventes.services import (_classe_ligne, _is_battery,
                                          _is_hybrid_inverter,
                                          _is_reseau_inverter, _lignes_produit)

        if (devis.etude_params or {}).get('scenario') != scenario_mono:
            return ('son scénario stocké n\'est pas « %s »' % scenario_mono)
        if not devis.roof_layout:
            return 'aucun calepinage 3D n\'est enregistré sur ce devis'
        if devis.lignes.filter(groupe_index__gte=1).exists():
            return ('devis multi-villa : chaque villa a son propre onduleur, '
                    'la réparation ne se devine pas')
        lignes = _lignes_produit(devis)
        if any(_classe_ligne(li, _is_reseau_inverter) for li in lignes):
            return 'il porte déjà un onduleur réseau'
        if not any(_classe_ligne(li, _is_hybrid_inverter) for li in lignes):
            return 'il ne porte aucun onduleur hybride'
        if not any(_classe_ligne(li, _is_battery) for li in lignes):
            return 'il ne porte aucune batterie'
        return None

    def _onduleur_reseau_tarife(self, devis):
        """L'onduleur réseau que la réparation poserait — mêmes helpers que la
        resynchro (marque épinglée de la gamme du devis comprise)."""
        from apps.ventes.services import (_is_reseau_inverter, _pick_product,
                                          gamme_nom)

        return _pick_product(devis.company, _is_reseau_inverter,
                             role='onduleur_reseau', gamme=gamme_nom(devis))

    # ── Réparation ─────────────────────────────────────────────────────────
    def _reparer(self, devis):
        """Répare UN devis sous transaction. Rend False si, sous verrou, il
        n'est plus dans l'état abîmé (concurrence) ou si le catalogue ne peut
        plus servir l'onduleur réseau."""
        from decimal import Decimal

        from django.db import transaction

        from apps.ventes.models import Devis, LigneDevis
        from apps.ventes.services import (SCENARIO_AVEC_BATTERIE,
                                          SCENARIO_LES_DEUX)

        with transaction.atomic():
            verrou = (Devis.objects.select_for_update()
                      .filter(pk=devis.pk).first())
            if verrou is None:
                return False
            # Re-vérification SOUS VERROU : la détection a pu être faite il y a
            # plusieurs devis de cela, et c'est ce qui rend la commande sûre à
            # relancer (idempotence).
            if self._motif_de_rejet(verrou, SCENARIO_AVEC_BATTERIE) is not None:
                return False
            produit = self._onduleur_reseau_tarife(verrou)
            if produit is None:
                return False
            ordre = max([int(ligne.ordre or 0)
                         for ligne in verrou.lignes.all()] or [0])
            LigneDevis.objects.create(
                devis=verrou, produit=produit, designation=produit.nom,
                quantite=Decimal('1'),
                # Aucun chiffre inventé : le PRIX CATALOGUE du produit choisi,
                # sans remise — exactement ce que la composition aurait posé.
                prix_unitaire=Decimal(produit.prix_vente),
                remise=Decimal('0'), ordre=ordre + 1)
            etude = dict(verrou.etude_params or {})
            etude['scenario'] = SCENARIO_LES_DEUX
            verrou.etude_params = etude
            # ``update_fields`` EXCLUT ``statut`` : aucun statut ne peut partir
            # d'ici, même par accident (règle #4).
            verrou.save(update_fields=['etude_params'])
        return True
