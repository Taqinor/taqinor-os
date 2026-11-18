#!/bin/bash
# Retire de /dev/shm les fichiers laissés par des `faketime` MORTS (faketime_shm_<pid>, sem.faketime_sem_<pid>).
# Sans cela, un nouveau lanceur qui reçoit le pid d'un ancien échoue : « faketime: sem_open: File exists »
# (constaté le 18/11/2026 : 836 fichiers, le Django d'une pile est mort en plein rejeu officiel).
# Le pid du nom est celui du programme lancé (le lanceur `faketime` fait un exec) : vivant = on garde.
for f in /dev/shm/faketime_shm_* /dev/shm/sem.faketime_sem_*; do
  [ -e "$f" ] || continue
  pid="${f##*_}"
  case "$pid" in ''|*[!0-9]*) continue;; esac
  kill -0 "$pid" 2>/dev/null && continue
  rm -f "$f" 2>/dev/null || true
done
