# -*- coding: utf-8 -*-
"""ERR-QAC-I7-BLOCS-PERIMES-REPARATION — recalculer les blocs horaires PÉRIMÉS.

    python manage.py rafraichir_blocs_horaires             # DRY-RUN (défaut)
    python manage.py rafraichir_blocs_horaires --appliquer
    python manage.py rafraichir_blocs_horaires --company <id|slug>
    python manage.py rafraichir_blocs_horaires --refs DEV-202609-0053,DEV-…

LE DÉGÂT. Avant le correctif I7 (#740), le bloc ``etude_params['etude_horaire']``
d'un devis à deux options divergentes était calculé sur la SOMME des deux
champs PV. ``pricing._lire_etude_horaire`` refuse un bloc à plus de 2 % du kWc
du devis : ces devis sont chiffrés EN SILENCE au modèle de repli
(« factures » / « estimation ») au lieu de l'étude horaire. Le correctif
empêche d'en fabriquer de nouveaux ; il ne répare pas ceux déjà stockés.

CE QUE FAIT LA COMMANDE. Détection : ``domain.etudes.blocs_horaires_perimes``
(le kWc seulement — pas l'empreinte des entrées). Pour chaque devis détecté,
elle construit le document AVANT, recalcule les blocs par
``rafraichir_etude_horaire_devis(force=True)`` (le seul point d'entrée, qui
écrit ``update_fields=['etude_params']`` UNIQUEMENT — aucun statut, aucune
ligne, aucun total n'est touché, règle #4), puis reconstruit le document APRÈS,
et imprime le diff : kWc des blocs, modèle d'économies, économie annuelle par
option, couverture, −N %, facture après.

DRY-RUN PAR DÉFAUT : le recalcul tourne dans un point de sauvegarde ANNULÉ.
``--appliquer`` écrit. Les devis ENVOYÉS/ACCEPTÉS sont listés À PART : leurs
chiffres imprimés changent — la mémoire « reconfirm-client-visible-repairs »
impose l'accord EXPLICITE du fondateur sur ce diff avant toute application en
production (ciblez alors avec ``--refs``).
"""
from django.core.management.base import BaseCommand, CommandError

#: Statuts dont le document est déjà entre les mains du client.
STATUTS_CLIENT = ('envoye', 'accepte')


class _Annuler(Exception):
    """Sort d'un ``transaction.atomic`` en l'annulant (dry-run)."""


def _chiffres(devis):
    """Les chiffres du document que le client lit (dict), ou ``{'erreur': …}``.

    Construit dans un point de sauvegarde ANNULÉ (``build_quote_data`` peut
    toucher la base) et sans lecture d'image MinIO (comme l'audit)."""
    from django.db import transaction

    from apps.ventes.coherence.contexte import rendu_sans_reseau
    from apps.ventes.quote_engine.builder import build_quote_data
    from apps.ventes.quote_engine.residential.renderer import (
        synthese_economies)

    resultat = {}
    try:
        with transaction.atomic():
            with rendu_sans_reseau():
                data = build_quote_data(devis)
            synthese = synthese_economies(data) or {}
            resultat = {
                'modele_sans': data.get('savings_model_sans'),
                'modele_avec': data.get('savings_model_avec'),
                'eco_sans': data.get('eco_s_ann'),
                'eco_avec': data.get('eco_a_ann'),
                'couverture': synthese.get('coverage_pct'),
                'reduction': synthese.get('pct_cut'),
                'facture_apres': synthese.get('annual_after'),
            }
            raise _Annuler
    except _Annuler:
        pass
    except Exception as exc:  # noqa: BLE001 — un devis n'arrête pas le lot
        return {'erreur': f'{type(exc).__name__}: {str(exc)[:160]}'}
    return resultat


def _kwc_blocs(devis):
    ep = devis.etude_params or {}
    return tuple((ep.get(cle) or {}).get('kwc')
                 if isinstance(ep.get(cle), dict) else None
                 for cle in ('etude_horaire', 'etude_horaire_sans'))


def _fmt(v):
    if v is None:
        return '—'
    if isinstance(v, float):
        return f'{v:.2f}'.rstrip('0').rstrip('.')
    return str(v)


class Command(BaseCommand):
    help = (
        "ERR-QAC-I7 — recalcule les blocs d'étude horaire dont le kWc ne "
        "décrit plus le devis (chiffrés en silence au modèle de repli). "
        "DRY-RUN par défaut : imprime le diff des chiffres du document "
        "(--appliquer pour écrire). Aucun statut, aucune ligne, aucun total "
        "n'est touché. Devis envoyés/acceptés listés à part : accord "
        "explicite du fondateur requis avant de les appliquer en production."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--appliquer', action='store_true',
            help="Écrire réellement (sans ce drapeau : DRY-RUN, rien n'est "
                 "modifié).")
        parser.add_argument(
            '--company', default=None,
            help="Ne traiter que cette société (id ou slug).")
        parser.add_argument(
            '--refs', default=None,
            help="Ne traiter que ces références, séparées par des virgules.")

    def handle(self, *args, **options):
        from django.db import transaction

        from apps.ventes.domain.etudes import (
            blocs_horaires_perimes, rafraichir_etude_horaire_devis)
        from apps.ventes.models import Devis

        appliquer = bool(options['appliquer'])
        societe = self._resoudre_societe(options.get('company'))
        references = [r.strip() for r in (options.get('refs') or '').split(',')
                      if r.strip()]

        qs = Devis.objects.filter(mode_installation='residentiel',
                                  etude_params__has_key='etude_horaire')
        if societe is not None:
            qs = qs.filter(company=societe)
        if references:
            qs = qs.filter(reference__in=references)
        qs = qs.select_related('company').order_by('company_id', 'reference')

        traites, client_visibles, echecs = [], [], 0
        for devis in qs:
            perimes = blocs_horaires_perimes(devis)
            if not perimes:
                continue
            avant_kwc = _kwc_blocs(devis)
            avant = _chiffres(devis)
            try:
                with transaction.atomic():
                    verrou = (Devis.objects.select_for_update()
                              .get(pk=devis.pk))
                    rafraichir_etude_horaire_devis(verrou, force=True)
                    frais = Devis.objects.get(pk=devis.pk)
                    apres_kwc = _kwc_blocs(frais)
                    apres = _chiffres(frais)
                    if not appliquer:
                        raise _Annuler
            except _Annuler:
                pass
            except Exception as exc:  # noqa: BLE001 — un devis n'arrête rien
                echecs += 1
                self.stdout.write('! %s — ÉCHEC : %s: %s'
                                  % (devis.reference, type(exc).__name__, exc))
                continue
            traites.append(devis.reference)
            if devis.statut in STATUTS_CLIENT:
                client_visibles.append((devis.reference, devis.statut))
            self.stdout.write(self._ligne(devis, perimes, avant_kwc, apres_kwc,
                                          avant, apres))

        if client_visibles:
            self.stdout.write(
                '\nDEVIS ENVOYÉS/ACCEPTÉS (chiffres imprimés modifiés — accord '
                'EXPLICITE du fondateur requis avant application en '
                'production) : %d' % len(client_visibles))
            for ref, statut in client_visibles:
                self.stdout.write('  - %s (%s)' % (ref, statut))
        self.stdout.write(
            '%s : %d devis %s, %d dont le client a le document, %d échec(s).'
            % ('APPLIQUÉ' if appliquer else "DRY-RUN (rien n'a été écrit)",
               len(traites), 'rafraîchi(s)' if appliquer else 'à rafraîchir',
               len(client_visibles), echecs))

    def _ligne(self, devis, perimes, avant_kwc, apres_kwc, avant, apres):
        detail = ', '.join('%s %s≠%s kWc' % (cle, _fmt(kb), _fmt(att))
                           for cle, kb, att in perimes)
        morceaux = [
            '· %s (%s, société %s) — %s' % (
                devis.reference, devis.statut,
                getattr(devis.company, 'slug', '?'), detail),
            '    bloc kWc : %s → %s ; bloc « sans » : %s → %s' % (
                _fmt(avant_kwc[0]), _fmt(apres_kwc[0]),
                _fmt(avant_kwc[1]), _fmt(apres_kwc[1])),
        ]
        if 'erreur' in avant or 'erreur' in apres:
            morceaux.append('    rendu impossible : %s'
                            % (avant.get('erreur') or apres.get('erreur')))
            return '\n'.join(morceaux)
        for libelle, cle, unite in (
                ('modèle sans', 'modele_sans', ''),
                ('modèle avec', 'modele_avec', ''),
                ('économie sans', 'eco_sans', ' MAD/an'),
                ('économie avec', 'eco_avec', ' MAD/an'),
                ('couverture', 'couverture', ' %'),
                ('réduction −N', 'reduction', ' %'),
                ('facture après', 'facture_apres', ' MAD/an')):
            morceaux.append('    %s : %s → %s%s' % (
                libelle, _fmt(avant.get(cle)), _fmt(apres.get(cle)), unite))
        return '\n'.join(morceaux)

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
