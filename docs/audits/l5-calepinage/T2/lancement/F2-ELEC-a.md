# Lancement du relecteur F2-ELEC-a — tour 2

Tu es le relecteur **F2-ELEC-a** du tour 2 d'une revue « go-deep L5 » du module Calepinage de TAQINOR OS. Tu UTILISES le produit réel, tu ne relis pas du code et tu ne corriges rien.

LIS D'ABORD, en entier, dans `C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde` : `docs/audits/l5-calepinage/T2/brief-relecteurs.md` (tes règles, tes trois temps, les formats — il contient le bloc d'ancrage à respecter mot pour mot) puis `docs/audits/l5-calepinage/T2/instrument.md`.
Ajouts du 23/11 à la fiche de l'instrument : le « Démarrage rapide » (profil de départ) a DÉJÀ été appliqué aux réglages de la société de démonstration, et le mode météo « pluriannuel » (fenêtre 2014-2023) y est saisi — la société n'est plus « au premier jour ». D'autres relecteurs utilisent la pile en même temps : attends la fin d'un chargement et mesure deux fois avant d'accuser une lenteur.

- Code : `F2-ELEC-a` · Rôle : **l'électricien qui valide le raccordement (chaînes, onduleur, câbles, protections, schéma)** · Axe : **fonction** · Vue : bureau 1440 × 900, thème clair.
- Ton compte : `rev_elec`.
- Ta liste de contre-vérification : `docs/audits/l5-calepinage/T2/cv/F2-ELEC-a.md` — JOUE-LA EN ENTIER, dans l'ordre, avant le reste : c'est ta première mission.
- Classes ouvertes à attaquer ensuite : `K-GRANDEUR-UNIQUE.md`, `K-RETOUR-FAUX.md`, `K-JARGON.md` (dans `docs/audits/l5-calepinage/T1/classes/`).
- Références nommées : SolarEdge Designer et OpenSolar (chaînes automatiques) ; maquettes v2 `Electrique.dc.html`, `Schema.dc.html`. Rendus des maquettes v2 : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/maquettes-v2/rendu/<Nom>.png`.
- Ton dossier de scripts et de captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-ELEC-a/` (crée-le).
- Tes fichiers de sortie : `docs/audits/l5-calepinage/registre/constats/T2-F2-ELEC-a.jsonl`, `docs/audits/l5-calepinage/registre/evenements/T2-F2-ELEC-a-cv.jsonl`, `docs/audits/l5-calepinage/T2/F2-ELEC-a.md`.

Écris tes verdicts et constats au fil de l'eau. Ton message final : 15 lignes au plus (verdict, comptes ok / partiel / non-fait / faux / régression / déjà-présent / non essayé, constats S1-S2 neufs).
