# Fichiers PVsyst réels — source et licence (CALX339)

Les deux fichiers de ce dossier sont des fichiers PVsyst RÉELS, déposés tels
quels (octet pour octet), jamais modifiés ni inventés. Ils servent d'exemple au
contrat `../fiche_import_pan_ond.json` et aux tests de l'import
(`apps/stock/test_cal_import_pan_ond.py`, `frontend/src/pages/stock/ImportFichePvsyst.test.jsx`).

| Fichier ici | Nom d'origine | Octets | SHA-256 |
|---|---|---|---|
| `ET-M772BH550GL.PAN` | `ET-M772BH550GL.PAN` | 1 399 | `54100e595ce23e842c700e007aa577283d5da76630a9e3cc103b831439b788a4` |
| `CPS_SCH275KTL-DO-US-800-250kW_275kVA_1.OND` | `CPS SCH275KTL-DO-US-800-250kW_275kVA_1.OND` (renommé SANS espace) | 3 284 | `28260c968f1f87ef413740b11ded2e757c30765c6752996789d4853f2203efd9` |

- Dépôt : https://github.com/pvlib/pvlib-python — tag `v0.16.1`, dossier `tests/data`.
- URL lues :
  - https://raw.githubusercontent.com/pvlib/pvlib-python/v0.16.1/tests/data/ET-M772BH550GL.PAN
  - https://raw.githubusercontent.com/pvlib/pvlib-python/v0.16.1/tests/data/CPS%20SCH275KTL-DO-US-800-250kW_275kVA_1.OND
- Date de lecture : 21/11/2026.
- Le `.PAN` (module ET SOLAR ET-M772BH550GL, PVsyst 7.2, « DataSource=Manufacturer 2021 ») est en ASCII ;
  le `.OND` (onduleur ChintPower CPS SCH275KTL-DO/US-800, PVsyst 6.81, « Manufacturer 2020 ») commence par un
  BOM UTF-8 — conservé, c'est un cas réel que le lecteur doit savoir lire.

Pourquoi pvlib : la recherche du 21/11/2026 n'a trouvé aucun `.PAN`/`.OND` publié sur les sites publics de
Jinko, Canadian Solar, Huawei et Deye ; pvlib publie ces deux fichiers constructeur comme données de test.

## Licence (BSD-3-Clause — texte exact du fichier LICENSE de pvlib-python au tag v0.16.1)

```
BSD 3-Clause License

Copyright (c) 2023 pvlib python Contributors
Copyright (c) 2014 PVLIB python Development Team
Copyright (c) 2013 Sandia National Laboratories

All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

  Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

  Redistributions in binary form must reproduce the above copyright notice, this
  list of conditions and the following disclaimer in the documentation and/or
  other materials provided with the distribution.

  Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
