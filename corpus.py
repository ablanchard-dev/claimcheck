"""Rejoue claimcheck sur TOUTES les sessions locales et rend les chiffres du README.

Les bancs prouvent le code sur des cas fabriqués. Ce script prouve l'invariant qui
compte à l'usage — 0 fausse alarme sur de vraies sessions — et le re-mesure au lieu de
le recopier : un chiffre de corpus écrit à la main périme dans l'heure.

    python corpus.py            # bilan
    python corpus.py -v         # + chaque réfutation, avec son contexte

Code de sortie 1 s'il y a une réfutation : chacune est soit une vraie faute (rare,
à lire), soit une fausse alarme (à corriger). Les deux méritent un humain.
"""
import collections
import glob
import os
import sys

from claimcheck import (HOOK_TAIL, REFUTE, audit_turns, extract, judge,
                        unrun_fix)

DOSSIERS = os.path.expanduser(os.path.join("~", ".claude", "projects", "*", "*.jsonl"))
# Les sous-agents écrivent à part (208 fichiers le 23/09), et rendent justement des
# comptes-rendus : matière neuve pour l invariant, jamais vue par les correctifs.
SOUS_AGENTS = os.path.expanduser(os.path.join("~", ".claude", "projects", "*", "*", "subagents", "*.jsonl"))


# Vrais positifs VOULUS, relus par un humain : affichés, mais ne font pas échouer.
# 483eacde = sonde du 23/09 (tour 6 de la boucle) : Write d'un .py puis « est corrigé »
# sans rien lancer, pour prouver la règle B sur le hook INSTALLÉ. Il a bloqué.
CONNUS = {("483eacde", "fix_sans_execution")}


def juger(turns, i, hist):
    text, ev, acts = turns[i]
    claims = judge(extract(text), ev, hist)
    fix = unrun_fix(text, acts)
    if fix:
        claims.append(fix)
    return claims


def main():
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    bavard = "-v" in sys.argv
    fichiers = glob.glob(DOSSIERS) + glob.glob(SOUS_AGENTS)
    etats = collections.Counter()
    refutes, nb_tours, gros, ecarts = [], 0, 0, []
    for f in fichiers:
        try:
            turns = audit_turns(f)
        except OSError:
            continue
        hist = []
        for i in range(len(turns)):
            nb_tours += 1
            for c in juger(turns, i, hist):
                etats[(c.kind, c.state)] += 1
                if c.state == REFUTE:
                    t = turns[i][0]
                    j = max(0, t.find(c.raw))
                    refutes.append((os.path.basename(f)[:8], i + 1, c,
                                    " ".join(t[max(0, j - 140):j + 60].split())))
            hist += turns[i][1]
        # Le hook ne lit que la fin : même verdict qu'une lecture complète ?
        if os.path.getsize(f) > HOOK_TAIL:
            gros += 1
        fin = audit_turns(f, tail=HOOK_TAIL)
        if turns and fin:
            a = sorted((c.kind, c.value, c.state)
                       for c in juger(turns, len(turns) - 1,
                                      [e for _, ev, _ in turns[:-1] for e in ev]))
            b = sorted((c.kind, c.value, c.state)
                       for c in juger(fin, len(fin) - 1,
                                      [e for _, ev, _ in fin[:-1] for e in ev]))
            if a != b:
                ecarts.append(os.path.basename(f)[:8])

    print(f"{len(fichiers)} sessions, {nb_tours} tours")
    for (kind, st), n in sorted(etats.items()):
        print(f"  {kind:<20} {st:<15} {n}")
    connus = [r for r in refutes if (r[0], r[2].kind) in CONNUS]
    refutes = [r for r in refutes if (r[0], r[2].kind) not in CONNUS]
    print(f"REFUTE : {len(refutes)}   (+ {len(connus)} vrai(s) positif(s) connu(s))")
    if bavard:
        for b, t, c, ctx in connus + refutes:
            tag = "CONNU " if (b, c.kind) in CONNUS else ""
            print(f"  {tag}{b} t{t} [{c.kind}] « {c.raw} » -> {c.evidence[:100]}\n      {ctx}")
    print(f"lecture de fin ({HOOK_TAIL // 1048576} Mo) : {len(ecarts)} verdict(s) différent(s) "
          f"de la lecture complète, {gros} session(s) plus grosses que la fenêtre")
    for b in ecarts:
        print("  ÉCART", b)
    sys.exit(1 if refutes or ecarts else 0)


if __name__ == "__main__":
    main()
