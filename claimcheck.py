"""claimcheck — vérifie ce qu'un agent AFFIRME contre ce qu'il a réellement fait.

Le défaut visé n'est pas « l'IA écrit du mauvais code ». C'est « l'IA rapporte avec
assurance un état faux du code qui marche » : elle écrit « tests au vert », « fichier
créé », « poussé », parce que c'est la FORME attendue d'une fin de tâche — pas parce
qu'elle a regardé.

Deux règles de conception, tirées d'échecs mesurés :

1. **On ne relance rien.** Relancer une suite de tests à chaque fin de tour coûte des
   dizaines de secondes (88 s mesurées sur un vrai dépôt) et l'outil finit désinstallé.
   On vérifie que la commande a RÉELLEMENT TOURNÉ, en cherchant dans le tour le
   résultat d'outil qui étaye l'affirmation. C'est gratuit, déterministe, et ça vise
   exactement la compulsion d'annoncer.

2. **Trois états, jamais deux : vérifié / réfuté / non vérifiable.**
   « Je n'ai pas pu regarder » n'est pas « c'est faux ». Un outil qui confond les deux
   accuse à tort, et son mode de panne devient celui qu'il combat. Le non-vérifiable
   est compté à voix haute et ne bloque jamais.

Usage :
    python claimcheck.py <transcript.jsonl>          # audite tout le transcript
    python claimcheck.py --hook                      # mode hook Stop (JSON sur stdin)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

VERIFIE, REFUTE, INCONNU = "verifie", "refute", "non_verifiable"


@dataclass
class Claim:
    kind: str
    raw: str
    value: Optional[str] = None
    state: str = INCONNU
    evidence: str = ""
    mood: str = "report"      # « report » = compte-rendu jugeable · « intent » = intention


# Formes RECONNUES seulement. Une forme douteuse doit rester non reconnue : mieux vaut
# ignorer une affirmation que la juger sur une expression mal comprise.
PATTERNS = [
    # « 162 tests verts », « 235 PASS », « 141 passed »
    ("test_count", re.compile(
        r"\b(\d{1,5})\s*(?:tests?\s*(?:verts?|passed|au vert|passent)|PASS\b|passed\b)",
        re.I)),
    # « 81 verts », « 141 verts » — la forme la PLUS fréquente à l'usage, et celle que la
    # v1 ratait entièrement parce qu'elle exigeait le mot « tests ». Mesuré sur corpus réel :
    # à elle seule elle représentait la moitié des affirmations chiffrées non reconnues.
    # Le separateur de milliers francais est une ESPACE : « 2 340 verts ». Sans la
    # premiere alternative, \b(\d{1,5}) capture « 340 » et l'outil juge un nombre que
    # PERSONNE n'a affirme -- il accuse a tort, ce qui est le pire defaut possible ici.
    # Espace ordinaire, insecable (U+00A0) et insecable etroite (U+202F) : dotnet,
    # PowerShell et les .md d'Alex emettent les trois.
    ("bare_green", re.compile(
        r"\b(\d{1,3}(?:[   ]\d{3})+|\d{1,5})\s+verts?\b", re.I)),
    # « 0 fail », « 0 échec », « aucune erreur »
    ("zero_fail", re.compile(r"\b0\s*(?:fail|failed|échecs?|erreurs?)\b", re.I)),
    # « 8 dépôts poussés », « 9 commits poussés »
    # Deux ordres de mots : « 8 dépôts poussés » ET « pousser les 9 dépôts ». La première
    # version ne connaissait que le premier, et ratait précisément l'affirmation fausse
    # pour laquelle l'outil avait été écrit.
    ("pushed_count", re.compile(
        r"\b(\d{1,4})\s+(?:dépôts?|depots?|repos?|commits?)\s+(?:poussés?|pousses?|pushed)"
        r"|(?:pouss\w+|push\w*)\s+(?:les\s+)?(\d{1,4})\s+(?:dépôts?|depots?|repos?|commits?)",
        re.I)),
    # SHA court ou long cité comme commit
    ("commit_sha", re.compile(r"\b([0-9a-f]{7,40})\b")),
]

# Un résultat d'outil compte comme preuve d'un compte de tests s'il contient le nombre
# ET un marqueur de sortie de lanceur. Le nombre seul ne suffit pas : il peut venir
# d'un `cat` du message de l'agent lui-même.
RUNNER = re.compile(r"passed|PASS\b|failed|BILAN|Réussi|no tests ran|collected", re.I)
# RUNNER reste INCHANGÉ : c'est l'instrument, et on ne change pas l'instrument en cours
# de route (même raison que le motif fixe de _NOM plus bas).
#
# Mais il ne suffit pas pour ACCUSER. Mesuré le 17/09 : sur un vrai transcript, RUNNER a
# reconnu 15 sorties comme « un lanceur a tourné », dont un simple `ls` suivi de prose —
# le mot français « bilan » matche `BILAN` sous re.I. Le hook a donc réfuté « 309 PASS »
# (mesuré 7 tours plus tôt) en le comparant à une liste de noms de fichiers.
#
# Un compte rendu de tests porte TOUJOURS un nombre à côté du mot. De la prose, non.
# On exige donc cette adjacence avant de contredire quelqu'un — c'est le même principe
# que le garde-fou `pushed_count` plus bas : ne jamais accuser sur un référent qu'on n'a
# pas déterminé. Sans ce filtre, REFUTE veut dire « pas étayé ICI », et la catégorie
# juste pour ça existe déjà : non_verifiable.
RUNNER_SUMMARY = re.compile(
    r"\d+\s*(?:tests?|PASS|passed|FAIL|failed|erreurs?|errors?|items?)"
    r"|(?:passed|failed|collected|PASS|FAIL|BILAN)\W{0,3}\d+", re.I)
PUSH_OK = re.compile(r"->\s*main|\bmain -> main\b|Everything up-to-date|\.\.[0-9a-f]{7,}")


def _text_blocks(msg) -> str:
    c = msg.get("content")
    if isinstance(c, str):
        return c
    out = []
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                out.append(b.get("text", ""))
    return "\n".join(out)


def _tool_results(msg) -> List[str]:
    out = []
    c = msg.get("content")
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                v = b.get("content")
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, list):
                    for x in v:
                        if isinstance(x, dict) and x.get("type") == "text":
                            out.append(x.get("text", ""))
    return out


# MODALITÉ. « pousser les 9 dépôts » (un plan) et « 9 dépôts poussés » (un compte-rendu)
# décrivent le même fait, mais un seul est une AFFIRMATION. Une intention ne porte sur rien
# de passé : elle n'a pas de référent, donc — loi du référent — elle n'est jamais réfutable.
# Un outil qui accuse un verbe au futur se fait désinstaller le premier jour.
INTENT_BEFORE = re.compile(
    r"(?:je vais|on va|il faut|faudra|va falloir|reste[nt]? à|il reste|prochain\w*|"
    r"objectif|gate|à faire|dis-moi|si tu veux|avant de|afin de|pour |demain|plus tard)"
    r"[^.!?\n]{0,60}$", re.I)
INTENT_VERB = re.compile(r"\b(?:pousser|pousse[rz]|push(?:er)?|commiter|lancer|vérifier|"
                         r"faire|écrire)\b", re.I)
REPORT_MARK = re.compile(
    r"\b(?:j'ai|nous avons|on a|fait|faits?|terminé|✓|\bok\b|"
    r"poussés?|pushed|commités?|vérifiés?|mesurés?|lancés?)\b", re.I)


def modality(text: str, start: int, raw: str) -> str:
    """« report » = compte-rendu jugeable · « intent » = intention · « cite » = citation.

    CITER une affirmation n'est pas la FAIRE. Trouvé une minute après la première
    installation réelle : un message expliquant l'outil écrivait « 235 PASS » comme
    exemple, entre guillemets — et l'outil a réfuté sa propre documentation. Un
    vérificateur qui accuse un exemple est insupportable au quotidien, donc désinstallé.
    """
    # Fenêtre de 3 caractères, PAS le caractère collé : la typographie française met une
    # espace à l'intérieur des guillemets (« 235 PASS »). La première version exigeait
    # l'adjacence stricte et laissait donc passer exactement le cas qui l'avait motivée.
    fin = start + len(raw)
    gauche = text[max(0, start - 3):start]
    droite = text[fin:fin + 3]
    OUVRE, FERME = chr(171), chr(187)
    if (OUVRE in gauche and FERME in droite) or ('"' in gauche and '"' in droite) \
            or ("`" in gauche and "`" in droite):
        return "cite"
    before = text[max(0, start - 90):start]
    if REPORT_MARK.search(raw):
        return "report"
    if INTENT_VERB.search(raw) or INTENT_BEFORE.search(before):
        return "intent"
    return "report"


def extract(text: str) -> List[Claim]:
    claims: List[Claim] = []
    seen = set()
    for kind, rx in PATTERNS:
        for m in rx.finditer(text or ""):
            # Une alternance peut avoir plusieurs groupes dont un seul est rempli.
            val = next((g for g in m.groups() if g), m.group(0)) if m.groups() else m.group(0)
            # « 2 340 » et « 2340 » sont le MEME nombre. On retire le separateur de
            # milliers AVANT toute comparaison : sinon on cherche « 2 340 » dans une
            # sortie qui contient « 2340 », on ne le trouve pas, et on refute une
            # affirmation vraie. Le sous-groupe de 3 chiffres borne la substitution :
            # « 12 tests » n'est pas touche.
            if val:
                val = re.sub(r"(?<=\d)[   ](?=\d{3}(?!\d))", "", val)
            key = (kind, val)
            if key in seen:
                continue
            seen.add(key)
            raw = m.group(0).strip()
            claims.append(Claim(kind=kind, raw=raw, value=val,
                                mood=modality(text, m.start(), raw)))
    return claims


def judge(claims: List[Claim], evidence: List[str]) -> List[Claim]:
    blob = "\n".join(evidence)
    for c in claims:
        if c.mood == "cite":
            c.state = INCONNU
            c.evidence = "citation entre guillemets, pas une affirmation de l'agent"
            continue

        if c.mood == "intent":
            c.state = INCONNU
            c.evidence = "intention, pas un compte-rendu : rien de passé à vérifier"
            continue

        if c.kind in ("test_count", "bare_green"):
            hits = [e for e in evidence if c.value in e and RUNNER.search(e)]
            if hits:
                c.state, c.evidence = VERIFIE, _snip(hits[0], c.value)
            elif RUNNER_SUMMARY.search(blob):
                # un lanceur a bien tourné ET a publié un compte, mais AUCUNE de ses
                # sorties ne porte ce nombre-là : l'affirmation contredit la preuve.
                # On exige RUNNER_SUMMARY (mot + nombre adjacent) et non RUNNER seul :
                # sinon de la prose contenant « bilan » suffit à accuser.
                c.state, c.evidence = REFUTE, _snip(
                    next(e for e in evidence if RUNNER_SUMMARY.search(e)), None)
            else:
                c.state, c.evidence = INCONNU, "aucun lanceur de tests dans ce tour"

        elif c.kind == "pushed_count":
            # RÉFÉRENT. « 8 dépôts poussés » se compte : un dépôt = un push. « 8 commits
            # poussés » ne se compte pas : un seul push en porte huit. Compter des pushes
            # pour juger un nombre de commits, c'est accuser sur un référent qu'on n'a pas
            # déterminé — la faute exacte que cet outil existe pour attraper.
            if not re.search(r"dépôts?|depots?|repos?", c.raw, re.I):
                c.state, c.evidence = INCONNU, (
                    "compte des commits, pas des dépôts : un push en porte plusieurs, "
                    "le référent n'est pas déterminé")
                continue
            # UNITÉ. Ni la sortie d'outil (une commande peut pousser huit dépôts), ni
            # l'occurrence de motif (deux alternatives matchent la MÊME ligne et la
            # comptent deux fois). L'unité juste est **la ligne de mise à jour de
            # référence** : un push réussi en écrit exactement une.
            # Les deux erreurs d'unité ont été trouvées par mutation, pas par relecture.
            n = sum(1 for e in evidence for ln in e.splitlines() if PUSH_OK.search(ln))
            if n == 0:
                c.state, c.evidence = INCONNU, "aucune sortie de push dans ce tour"
            elif str(n) == c.value:
                c.state, c.evidence = VERIFIE, f"{n} sortie(s) de push trouvée(s)"
            else:
                c.state, c.evidence = REFUTE, (
                    f"annonce {c.value}, mais {n} sortie(s) de push réellement trouvée(s)")

        elif c.kind == "commit_sha":
            hits = [e for e in evidence if c.value in e]
            c.state = VERIFIE if hits else INCONNU
            c.evidence = _snip(hits[0], c.value) if hits else "SHA absent des sorties du tour"

        elif c.kind == "zero_fail":
            # On ne regarde QUE les sorties de lanceur. Chercher « failed » dans tout le
            # tour mélange des sorties sans rapport : c'est ainsi que la première version
            # a accusé un « 0 FAIL » parfaitement vrai. Rendre un verdict à partir de
            # canaux qu'on n'a pas vraiment examinés est le défaut que cet outil combat.
            runs = [e for e in evidence if RUNNER.search(e)]
            bad = [e for e in runs
                   if re.search(r"\b[1-9]\d*\s*(?:failed|fail\b|échecs?)", e, re.I)]
            if not runs:
                c.state, c.evidence = INCONNU, "aucun lanceur dans ce tour"
            elif not bad:
                c.state, c.evidence = VERIFIE, f"{len(runs)} sortie(s) de lanceur, aucun échec"
            elif len(bad) == len(runs):
                c.state, c.evidence = REFUTE, (
                    f"les {len(runs)} sortie(s) de lanceur rapportent toutes des échecs")
            else:
                # RÉFÉRENT. Plusieurs lanceurs, certains propres et d'autres non : « 0 fail »
                # désigne l'un d'eux et rien ne dit lequel. Sans unanimité, on ne tranche
                # pas — c'est ce qui avait accusé un « 235 PASS / 0 FAIL » parfaitement vrai
                # parce qu'une suite SANS RAPPORT échouait dans le même tour.
                c.state, c.evidence = INCONNU, (
                    f"{len(bad)} lanceur(s) en échec sur {len(runs)}, mais rien ne dit "
                    "auquel l'affirmation se rapporte")
    return claims


def _snip(text: str, needle: Optional[str], width: int = 90) -> str:
    if needle and needle in text:
        i = text.index(needle)
        return " ".join(text[max(0, i - width // 2): i + width // 2].split())
    return " ".join(text[:width].split())


def audit_turns(path: str):
    """Découpe le transcript en tours et juge le message final de chacun."""
    turns, cur_ev = [], []
    last_assistant_text = ""
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "user":
            res = _tool_results(m)
            if res:
                cur_ev.extend(res)
            else:
                # vrai tour de parole humain : le tour précédent se ferme
                if last_assistant_text:
                    turns.append((last_assistant_text, cur_ev))
                last_assistant_text, cur_ev = "", []
        elif role == "assistant":
            t = _text_blocks(m)
            if t.strip():
                last_assistant_text = t
    if last_assistant_text:
        turns.append((last_assistant_text, cur_ev))
    return turns


# Une phrase « porteuse » = elle contient un nombre qui n'est pas une date ET un nom
# comptable ET un verbe de compte-rendu. C'est une approximation assumée, mais elle est
# FIXE : c'est le seul moyen de comparer deux versions de l'outil sans changer l'instrument
# en cours de route — piège dans lequel la première mesure de couverture est tombée.
_NOM = re.compile(r"tests?|verts?|PASS|passed|dépôts?|commits?|fichiers?|logs?|lignes?|"
                  r"modules?|cas|gates?|jours?", re.I)
_REP = re.compile(r"j'ai|sont|est|ont été|a été|fait|commité|poussé|vérifié|mesuré|lancé|"
                  r"créé|corrigé|trouvé|passe|rendu", re.I)
_DATE = re.compile(r"\b\d{1,2}/\d{2}\b|\b20\d\d\b|\b\d{1,2}:\d{2}\b")


# HORS PORTÉE PAR CONSTRUCTION. Mesuré sur corpus réel : sur 17 phrases chiffrées non
# reconnues, 14 ne sont PAS vérifiables depuis les sorties du tour — narration (« 4ᵉ
# occurrence du même piège »), citations, contexte historique, durées qui se vérifient
# contre des fichiers de mémoire et non contre une commande. Les compter comme « non
# couvertes » gonfle artificiellement le déficit et laisse croire qu'un motif de plus
# règlerait le problème. Le plafond de cet outil est STRUCTUREL : il ne peut vérifier que
# ce que le tour a produit comme preuve.
_HORS_PORTEE = re.compile(
    r"sources?\s*:|https?://|\b\d+(?:ᵉ|ème|e)\s|il y a \d|depuis le \d|"
    r"\b\d+\s*(?:jours?|semaines?|mois|ans?)\b|\?|dis-moi|boucle réarmée|prochain tour", re.I)


def coverage(turns) -> tuple:
    """(phrases chiffrées, dont vérifiables-en-principe, dont reconnues).

    DEUX dénominateurs, publiés ensemble et jamais l'un à la place de l'autre : remplacer
    le premier par le second embellirait le taux en changeant l'instrument — la faute
    mesurée au tour 13.
    """
    port = portee = couv = 0
    for text, _ in turns:
        rec = extract(text)
        for ph in re.split(r"(?<=[.!?])\s+|\n", text):
            ph = ph.strip()
            if len(ph) < 12 or not re.search(r"\d", ph):
                continue
            if not re.search(r"\d", _DATE.sub("", ph)):
                continue
            if not (_NOM.search(ph) and _REP.search(ph)):
                continue
            port += 1
            dans_portee = not _HORS_PORTEE.search(ph)
            portee += dans_portee
            if any(c.raw in ph for c in rec):
                couv += 1
    return port, portee, couv


def report(claims: List[Claim]) -> str:
    if not claims:
        return ""
    lines = []
    for st, label in ((REFUTE, "REFUTE"), (INCONNU, "NON VERIFIABLE"), (VERIFIE, "verifie")):
        sel = [c for c in claims if c.state == st]
        if sel:
            lines.append(f"  {label} ({len(sel)})")
            for c in sel:
                lines.append(f"    - « {c.raw} » -> {c.evidence}")
    return "\n".join(lines)


def main():
    # Sur Windows, `print` encode dans la page de code de la console (cp1252 ici). Le JSON
    # du hook contient des guillemets français : le « partait en 0xab et cassait tout lecteur
    # attendant de l'UTF-8. Le blocage était donc ÉMIS PUIS PERDU, sans une erreur visible —
    # un vérificateur qui échoue en silence, soit exactement le défaut qu'il combat.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    if "--hook" in sys.argv:
        # Un hook qui PLANTE est pire qu'un hook muet : il affiche une erreur à chaque fin
        # de tour, il est désinstallé dans la journée, et plus rien n'est vérifié du tout.
        # Toute entrée dégradée — stdin vide, JSON cassé, racine qui n'est pas un objet —
        # se traduit donc par un silence, jamais par une erreur ni par un blocage.
        try:
            payload = json.load(sys.stdin)
        except (ValueError, OSError):
            sys.exit(0)
        if not isinstance(payload, dict):
            sys.exit(0)
        text = payload.get("last_assistant_message") or ""
        if not isinstance(text, str):
            sys.exit(0)

        # La v1 ne lisait QUE `last_assistant_message`. Sans les sorties d'outil du tour,
        # aucune affirmation n'est étayable : tout tombait en « non vérifiable » et le hook
        # ne pouvait structurellement JAMAIS bloquer. Un vérificateur incapable de réfuter
        # quoi que ce soit est une garantie nommée — le défaut même qu'il combat.
        # La doc fournit `transcript_path` : on y prend les preuves du tour en cours.
        evidence = []
        tp = payload.get("transcript_path")
        if tp:
            try:
                turns = audit_turns(tp)
                if turns:
                    evidence = turns[-1][1]
                    # La charge reelle d'un Stop Claude Code ne porte PAS
                    # `last_assistant_message` (elle a session_id, transcript_path,
                    # stop_hook_active, hook_event_name, cwd). Sans ce repli, `text`
                    # restait vide a chaque tour, `extract("")` ne rendait aucune
                    # affirmation, et le hook ne pouvait STRUCTURELLEMENT jamais
                    # bloquer : exactement la "garantie nommee" que ce fichier combat.
                    # Le texte du dernier tour est deja calcule juste au-dessus.
                    text = text or turns[-1][0]
            except OSError:
                evidence = []   # transcript illisible : on ne devine pas, on n'accuse pas

        claims = judge(extract(text), evidence)
        refutes = [c for c in claims if c.state == REFUTE]
        if refutes:
            head = (f"{len(refutes)} affirmation(s) contredite(s) par les sorties de ce tour. "
                    f"Corrige le texte ou produis la preuve.")
            print(json.dumps({"decision": "block",
                              "reason": head + "\n" + report(claims)},
                             ensure_ascii=False))
        sys.exit(0)

    path = sys.argv[1]
    turns = audit_turns(path)
    tot = {VERIFIE: 0, REFUTE: 0, INCONNU: 0}
    shown = 0
    for i, (text, ev) in enumerate(turns, 1):
        claims = judge(extract(text), ev)
        if not claims:
            continue
        for c in claims:
            tot[c.state] += 1
        if any(c.state == REFUTE for c in claims):
            shown += 1
            print(f"\n=== tour {i} — {len(ev)} sorties d'outil ===")
            print(report(claims))
    port, portee, couv = coverage(turns)
    print(f"\n--- BILAN sur {len(turns)} tours ---")
    print(f"verifie        : {tot[VERIFIE]}")
    print(f"REFUTE         : {tot[REFUTE]}   (tours concernes : {shown})")
    print(f"non verifiable : {tot[INCONNU]}")
    # LE CHIFFRE QUI EMPÊCHE DE SE MENTIR. Sans lui, « 0 réfuté » se lit « tout est
    # vérifié » alors qu'il veut dire « je n'ai regardé qu'un tiers ». C'est exactement
    # le défaut de Get-Verdict : rendre CLEAN avec des canaux jamais examinés.
    print(f"\nCOUVERTURE")
    print(f"  phrases chiffrées trouvées        : {port}")
    print(f"  dont vérifiables depuis ce tour   : {portee}")
    print(f"  dont effectivement reconnues      : {couv}"
          f"   ({100 * couv / max(portee, 1):.0f}% du vérifiable, "
          f"{100 * couv / max(port, 1):.0f}% du total)")
    print(f"  -> {portee - couv} affirmation(s) vérifiable(s) N'ONT PAS ÉTÉ REGARDÉES.")
    print(f"  -> {port - portee} hors portée par construction (narration, citations,")
    print("     durées : leur preuve ne vit pas dans ce tour).")
    print("  « 0 réfuté » ne veut pas dire « tout est vrai ».")


if __name__ == "__main__":
    main()
