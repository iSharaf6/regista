"""Deterministic multilingual narration.

This is Regista's safety net: when the language model is slow, failing or
disabled, every moment still gets broadcast-ready copy in five languages and
three personas, built only from verified facts. It is also what the offline
chat client "generates", so the whole agent graph runs without any cloud.
"""

from __future__ import annotations

from typing import Any

LANGS = ("en", "es", "fr", "ar", "pt")
PERSONAS = ("casual", "analyst", "new_fan")


def num(v: float | int | None, lang: str, digits: int = 0) -> str:
    if v is None:
        return "-"
    s = f"{v:.{digits}f}"
    return s.replace(".", ",") if lang in {"es", "fr", "pt"} and digits else s


# each phrase names the scoring team exactly once ("puts Northbridge in front", never "... in front for Northbridge")
GOAL_CTX = {
    "en": {"opener": "breaks the deadlock for {team}", "equaliser": "levels it for {team}", "go_ahead": "puts {team} in front",
           "extends_lead": "extends {team}'s lead", "pulls_one_back": "pulls one back for {team}"},
    "es": {"opener": "abre el marcador para {team}", "equaliser": "iguala el partido para {team}",
           "go_ahead": "pone por delante a {team}", "extends_lead": "amplía la ventaja de {team}",
           "pulls_one_back": "recorta distancias para {team}"},
    "fr": {"opener": "ouvre le score pour {team}", "equaliser": "égalise pour {team}", "go_ahead": "donne l'avantage à {team}",
           "extends_lead": "creuse l'écart pour {team}", "pulls_one_back": "réduit l'écart pour {team}"},
    "ar": {"opener": "يفتتح التسجيل لصالح {team}", "equaliser": "يعادل النتيجة لصالح {team}", "go_ahead": "يمنح {team} التقدم",
           "extends_lead": "يعزز تقدم {team}", "pulls_one_back": "يقلص الفارق لصالح {team}"},
    "pt": {"opener": "abre o placar para o {team}", "equaliser": "empata a partida para o {team}",
           "go_ahead": "coloca o {team} na frente", "extends_lead": "amplia a vantagem do {team}",
           "pulls_one_back": "diminui a diferença para o {team}"},
}

# players left after a dismissal, as a commentator says it
MEN = {
    "en": {11: "eleven", 10: "ten", 9: "nine", 8: "eight", 7: "seven"},
    "es": {11: "once", 10: "diez", 9: "nueve", 8: "ocho", 7: "siete"},
    "fr": {11: "onze", 10: "dix", 9: "neuf", 8: "huit", 7: "sept"},
    "ar": {11: "بأحد عشر لاعبًا", 10: "بعشرة لاعبين", 9: "بتسعة لاعبين", 8: "بثمانية لاعبين", 7: "بسبعة لاعبين"},
    "pt": {11: "onze", 10: "dez", 9: "nove", 8: "oito", 7: "sete"},
}

OUTCOME = {
    "en": {"saved": "saved by {keeper}", "blocked": "blocked", "off_target": "off target", "goal": "in"},
    "es": {"saved": "atajado por {keeper}", "blocked": "bloqueado", "off_target": "desviado", "goal": "dentro"},
    "fr": {"saved": "arrêté par {keeper}", "blocked": "contré", "off_target": "à côté", "goal": "au fond"},
    "ar": {"saved": "تصدى لها {keeper}", "blocked": "مُبعدة", "off_target": "خارج المرمى", "goal": "في الشباك"},
    "pt": {"saved": "defendido por {keeper}", "blocked": "bloqueado", "off_target": "para fora", "goal": "dentro"},
}

FACTOR = {
    "Pass completion": {"en": "pass completion", "es": "acierto en el pase", "fr": "réussite des passes",
                        "ar": "دقة التمرير", "pt": "acerto nos passes"},
    "Turnovers per minute": {"en": "turnovers per minute", "es": "pérdidas por minuto", "fr": "pertes de balle par minute",
                             "ar": "فقدان الكرة في الدقيقة", "pt": "perdas por minuto"},
    "Passes per possession": {"en": "passes per possession", "es": "pases por posesión", "fr": "passes par possession",
                              "ar": "التمريرات في كل استحواذ", "pt": "passes por posse"},
    "Duels per minute": {"en": "duels per minute", "es": "duelos por minuto", "fr": "duels par minute",
                         "ar": "الالتحامات في الدقيقة", "pt": "duelos por minuto"},
}

T: dict[str, dict[str, dict[str, str]]] = {
    "goal": {
        "en": {
            "caption": "GOAL · {player}", "fan_pos": "GET IN! {player}", "fan_neg": "{team} score · {score}",
            "casual": "{player} {ctx}! It's {score}.",
            "analyst": "{player} finishes a {xg} xG chance at {speed} km/h from {dist} m. {team} win probability {wp_from}% → {wp_to}%.",
            "new_fan": "{player} scores for {team}! The score is now {score}.",
            "why_casual": "That goal moves {team}'s chance of winning from {wp_from}% to {wp_to}%.",
            "why_analyst": "A {swing}-point swing in win probability. Chance quality {xg} xG: {quality}.",
            "why_new_fan": "Chance quality (xG) was {xg}: a shot like that goes in about 1 time in {one_in}. {team}'s chance of winning is now {wp_to}%.",
        },
        "es": {
            "caption": "GOL · {player}", "fan_pos": "¡GOLAZO! {player}", "fan_neg": "Marca {team} · {score}",
            "casual": "¡{player} {ctx}! {score}.",
            "analyst": "{player} define una ocasión de {xg} xG a {speed} km/h desde {dist} m. Probabilidad de victoria de {team}: {wp_from}% → {wp_to}%.",
            "new_fan": "¡Gol de {player} para {team}! El marcador queda {score}.",
            "why_casual": "Con este gol, la probabilidad de victoria de {team} pasa del {wp_from}% al {wp_to}%.",
            "why_analyst": "Un vuelco de {swing} puntos en la probabilidad de victoria. Calidad de la ocasión: {xg} xG.",
            "why_new_fan": "El xG mide la calidad de la ocasión: {xg} significa que un disparo así entra 1 de cada {one_in} veces. {team} tiene ahora un {wp_to}% de opciones de ganar.",
        },
        "fr": {
            "caption": "BUT · {player}", "fan_pos": "OUIII ! {player}", "fan_neg": "{team} marque · {score}",
            "casual": "{player} {ctx} ! {score}.",
            "analyst": "{player} convertit une occasion à {xg} xG, frappe à {speed} km/h depuis {dist} m. Probabilité de victoire de {team} : {wp_from} % → {wp_to} %.",
            "new_fan": "But de {player} pour {team} ! Le score est de {score}.",
            "why_casual": "Ce but fait passer les chances de victoire de {team} de {wp_from} % à {wp_to} %.",
            "why_analyst": "Un basculement de {swing} points de probabilité de victoire. Qualité de l'occasion : {xg} xG.",
            "why_new_fan": "Les xG mesurent la qualité d'une occasion : {xg} signifie qu'une frappe comme celle-ci rentre environ une fois sur {one_in}. {team} a désormais {wp_to} % de chances de gagner.",
        },
        "ar": {
            "caption": "هدف · {player}", "fan_pos": "يااااه! {player}", "fan_neg": "{team} يسجل · {score}",
            "casual": "{player} {ctx}! النتيجة {score}.",
            "analyst": "{player} يحوّل فرصة بقيمة {xg} xG بسرعة {speed} كم/س من مسافة {dist} م. احتمال فوز {team}: {wp_from}% ← {wp_to}%.",
            "new_fan": "{player} يسجل لـ{team}! النتيجة الآن {score}.",
            "why_casual": "هذا الهدف يرفع حظوظ {team} في الفوز من {wp_from}% إلى {wp_to}%.",
            "why_analyst": "تحوّل بمقدار {swing} نقطة في احتمال الفوز. جودة الفرصة {xg} xG.",
            "why_new_fan": "مؤشر الأهداف المتوقعة (xG) يقيس جودة الفرصة: {xg} تعني أن تسديدة كهذه تدخل المرمى مرة من كل {one_in} تقريبا. فرصة فوز {team} الآن {wp_to}%.",
        },
        "pt": {
            "caption": "GOL · {player}", "fan_pos": "GOLAÇO! {player}", "fan_neg": "{team} marca · {score}",
            "casual": "{player} {ctx}! {score}.",
            "analyst": "{player} converte uma chance de {xg} xG a {speed} km/h de {dist} m. Probabilidade de vitória do {team}: {wp_from}% → {wp_to}%.",
            "new_fan": "Gol de {player} para o {team}! O placar agora é {score}.",
            "why_casual": "Com esse gol, a chance de vitória do {team} vai de {wp_from}% para {wp_to}%.",
            "why_analyst": "Uma virada de {swing} pontos na probabilidade de vitória. Qualidade da chance: {xg} xG.",
            "why_new_fan": "O xG mede a qualidade da chance: {xg} significa que um chute assim entra cerca de 1 vez a cada {one_in}. O {team} agora tem {wp_to}% de chance de vencer.",
        },
    },
    "big_chance": {
        "en": {"caption": "BIG CHANCE · {player}", "casual": "What a chance for {player}! {outcome}.",
               "analyst": "{player}: {xg} xG from {dist} m, {speed} km/h, {outcome}.",
               "new_fan": "{player} had a great chance to score, but it was {outcome}.",
               "why_casual": "A chance like that is scored about 1 time in {one_in}.",
               "why_analyst": "{team} now on {team_xg} xG from {team_goals} goals.",
               "why_new_fan": "xG of {xg} means a shot from there goes in about 1 time in {one_in}."},
        "es": {"caption": "OCASIÓN · {player}", "casual": "¡Qué ocasión de {player}! {outcome}.",
               "analyst": "{player}: {xg} xG desde {dist} m, {speed} km/h, {outcome}.",
               "new_fan": "{player} tuvo una gran ocasión, pero el disparo fue {outcome}.",
               "why_casual": "Una ocasión así se convierte 1 de cada {one_in} veces.",
               "why_analyst": "{team} acumula {team_xg} xG con {team_goals} goles.",
               "why_new_fan": "Un xG de {xg} significa que un disparo desde ahí entra 1 de cada {one_in} veces."},
        "fr": {"caption": "GROSSE OCCASION · {player}", "casual": "Quelle occasion pour {player} ! {outcome}.",
               "analyst": "{player} : {xg} xG à {dist} m, {speed} km/h, {outcome}.",
               "new_fan": "{player} avait une belle occasion, mais la frappe est {outcome}.",
               "why_casual": "Une occasion comme celle-ci finit au fond une fois sur {one_in}.",
               "why_analyst": "{team} cumule {team_xg} xG pour {team_goals} but(s).",
               "why_new_fan": "Des xG de {xg} signifient qu'une frappe de là rentre une fois sur {one_in} environ."},
        "ar": {"caption": "فرصة محققة · {player}", "casual": "يا لها من فرصة لـ{player}! {outcome}.",
               "analyst": "{player}: {xg} xG من {dist} م، بسرعة {speed} كم/س، {outcome}.",
               "new_fan": "أتيحت لـ{player} فرصة رائعة للتسجيل، لكن الكرة {outcome}.",
               "why_casual": "فرصة كهذه تتحول إلى هدف مرة من كل {one_in} تقريبا.",
               "why_analyst": "رصيد {team} الآن {team_xg} xG مقابل {team_goals} أهداف.",
               "why_new_fan": "قيمة {xg} xG تعني أن تسديدة من هناك تدخل مرة من كل {one_in}."},
        "pt": {"caption": "CHANCE CLARA · {player}", "casual": "Que chance para {player}! {outcome}.",
               "analyst": "{player}: {xg} xG de {dist} m, {speed} km/h, {outcome}.",
               "new_fan": "{player} teve uma grande chance, mas o chute foi {outcome}.",
               "why_casual": "Uma chance assim vira gol cerca de 1 vez a cada {one_in}.",
               "why_analyst": "O {team} soma {team_xg} xG com {team_goals} gols.",
               "why_new_fan": "Um xG de {xg} significa que um chute dali entra cerca de 1 vez a cada {one_in}."},
    },
    "thunderbolt": {
        "en": {"caption": "{speed} KM/H · {player}", "casual": "{player} hits it at {speed} km/h! {outcome}.",
               "analyst": "{player}: {speed} km/h strike from {dist} m, {outcome}.",
               "new_fan": "{player} struck that at {speed} km/h, faster than a car on a motorway.",
               "why_casual": "One of the hardest shots of the match.", "why_analyst": "Shot speed in the top band for this league.",
               "why_new_fan": "Most shots travel between 70 and 100 km/h."},
        "es": {"caption": "{speed} KM/H · {player}", "casual": "¡{player} le pega a {speed} km/h! {outcome}.",
               "analyst": "{player}: disparo a {speed} km/h desde {dist} m, {outcome}.",
               "new_fan": "{player} disparó a {speed} km/h, más rápido que un coche en autopista.",
               "why_casual": "Uno de los disparos más potentes del partido.", "why_analyst": "Velocidad de disparo en la franja alta de la liga.",
               "why_new_fan": "La mayoría de los disparos van entre 70 y 100 km/h."},
        "fr": {"caption": "{speed} KM/H · {player}", "casual": "{player} frappe à {speed} km/h ! {outcome}.",
               "analyst": "{player} : frappe à {speed} km/h depuis {dist} m, {outcome}.",
               "new_fan": "{player} a frappé à {speed} km/h, plus vite qu'une voiture sur l'autoroute.",
               "why_casual": "L'une des frappes les plus puissantes du match.", "why_analyst": "Vitesse de frappe dans la tranche haute du championnat.",
               "why_new_fan": "La plupart des frappes vont de 70 à 100 km/h."},
        "ar": {"caption": "{speed} كم/س · {player}", "casual": "{player} يسدد بسرعة {speed} كم/س! {outcome}.",
               "analyst": "{player}: تسديدة بسرعة {speed} كم/س من {dist} م، {outcome}.",
               "new_fan": "سدد {player} بسرعة {speed} كم/س، أسرع من سيارة على الطريق السريع.",
               "why_casual": "واحدة من أقوى تسديدات المباراة.", "why_analyst": "سرعة تسديد ضمن الفئة الأعلى في الدوري.",
               "why_new_fan": "معظم التسديدات تتراوح سرعتها بين 70 و100 كم/س."},
        "pt": {"caption": "{speed} KM/H · {player}", "casual": "{player} bate a {speed} km/h! {outcome}.",
               "analyst": "{player}: chute a {speed} km/h de {dist} m, {outcome}.",
               "new_fan": "{player} chutou a {speed} km/h, mais rápido que um carro na estrada.",
               "why_casual": "Um dos chutes mais fortes da partida.", "why_analyst": "Velocidade de chute na faixa mais alta da liga.",
               "why_new_fan": "A maioria dos chutes vai de 70 a 100 km/h."},
    },
    "master_pass": {
        "en": {"caption": "PASS · DIFFICULTY {difficulty}/100", "casual": "Brilliant ball from {player} to {receiver}!",
               "analyst": "{player} → {receiver}: {length} m, difficulty {difficulty}/100, {bypassed} opponents bypassed, {ball_speed} km/h.",
               "new_fan": "{player} found {receiver} with a pass most players would not even try.",
               "why_casual": "Only about {success_pct}% of passes like that find their target.",
               "why_analyst": "{player} is at {accuracy}% accuracy from {passes} passes today.",
               "why_new_fan": "Difficulty {difficulty} means roughly {fail_pct} in 100 similar passes fail. It took {bypassed} defenders out of the game."},
        "es": {"caption": "PASE · DIFICULTAD {difficulty}/100", "casual": "¡Qué balón de {player} para {receiver}!",
               "analyst": "{player} → {receiver}: {length} m, dificultad {difficulty}/100, {bypassed} rivales superados, {ball_speed} km/h.",
               "new_fan": "{player} encontró a {receiver} con un pase que muy pocos se atreverían a intentar.",
               "why_casual": "Solo un {success_pct}% de los pases así llega a su destino.",
               "why_analyst": "{player} lleva un {accuracy}% de acierto en {passes} pases.",
               "why_new_fan": "Dificultad {difficulty} significa que unos {fail_pct} de cada 100 pases parecidos fallan. Dejó atrás a {bypassed} rivales."},
        "fr": {"caption": "PASSE · DIFFICULTÉ {difficulty}/100", "casual": "Quel ballon de {player} pour {receiver} !",
               "analyst": "{player} → {receiver} : {length} m, difficulté {difficulty}/100, {bypassed} adversaires éliminés, {ball_speed} km/h.",
               "new_fan": "{player} trouve {receiver} avec une passe que peu de joueurs tenteraient.",
               "why_casual": "Seules {success_pct} % des passes de ce type trouvent leur cible.",
               "why_analyst": "{player} tourne à {accuracy} % de réussite sur {passes} passes.",
               "why_new_fan": "Une difficulté de {difficulty} veut dire qu'environ {fail_pct} passes semblables sur 100 échouent. Elle a éliminé {bypassed} adversaires."},
        "ar": {"caption": "تمريرة · صعوبة {difficulty}/100", "casual": "كرة رائعة من {player} إلى {receiver}!",
               "analyst": "{player} ← {receiver}: {length} م، صعوبة {difficulty}/100، تجاوزت {bypassed} لاعبين، {ball_speed} كم/س.",
               "new_fan": "{player} وجد {receiver} بتمريرة لا يجرؤ عليها معظم اللاعبين.",
               "why_casual": "فقط {success_pct}% من التمريرات المشابهة تصل إلى هدفها.",
               "why_analyst": "دقة تمرير {player} اليوم {accuracy}% من {passes} تمريرة.",
               "why_new_fan": "صعوبة {difficulty} تعني أن نحو {fail_pct} من كل 100 تمريرة مشابهة تفشل. لقد أخرجت {bypassed} مدافعين من اللعب."},
        "pt": {"caption": "PASSE · DIFICULDADE {difficulty}/100", "casual": "Que bola de {player} para {receiver}!",
               "analyst": "{player} → {receiver}: {length} m, dificuldade {difficulty}/100, {bypassed} adversários superados, {ball_speed} km/h.",
               "new_fan": "{player} achou {receiver} com um passe que poucos tentariam.",
               "why_casual": "Só cerca de {success_pct}% dos passes assim chegam ao destino.",
               "why_analyst": "{player} tem {accuracy}% de acerto em {passes} passes hoje.",
               "why_new_fan": "Dificuldade {difficulty} quer dizer que uns {fail_pct} em cada 100 passes parecidos falham. Tirou {bypassed} adversários da jogada."},
    },
    "speed": {
        "en": {"caption": "{speed} KM/H · {player}", "casual": "{player} is flying: {speed} km/h!",
               "analyst": "{player} tops out at {speed} km/h; {sprints} sprints, {distance} km covered.",
               "new_fan": "{player} just hit {speed} km/h, about as fast as a footballer can run.",
               "why_casual": "That is elite sprint speed.", "why_analyst": "Sprint threshold is 25 km/h.",
               "why_new_fan": "Anything over 33 km/h is among the fastest in the game."},
        "es": {"caption": "{speed} KM/H · {player}", "casual": "¡{player} vuela: {speed} km/h!",
               "analyst": "{player} alcanza {speed} km/h; {sprints} sprints, {distance} km recorridos.",
               "new_fan": "{player} acaba de llegar a {speed} km/h, casi lo máximo que puede correr un futbolista.",
               "why_casual": "Velocidad de élite.", "why_analyst": "El umbral de sprint es 25 km/h.",
               "why_new_fan": "Más de 33 km/h está entre lo más rápido del fútbol."},
        "fr": {"caption": "{speed} KM/H · {player}", "casual": "{player} s'envole : {speed} km/h !",
               "analyst": "{player} atteint {speed} km/h ; {sprints} sprints, {distance} km parcourus.",
               "new_fan": "{player} vient d'atteindre {speed} km/h, presque le maximum pour un footballeur.",
               "why_casual": "Vitesse de pointe d'élite.", "why_analyst": "Le seuil de sprint est de 25 km/h.",
               "why_new_fan": "Au-delà de 33 km/h, on parle des joueurs les plus rapides."},
        "ar": {"caption": "{speed} كم/س · {player}", "casual": "{player} ينطلق كالصاروخ: {speed} كم/س!",
               "analyst": "{player} يصل إلى {speed} كم/س؛ {sprints} انطلاقات، {distance} كم مقطوعة.",
               "new_fan": "وصل {player} إلى {speed} كم/س، وهي من أعلى السرعات الممكنة للاعب كرة قدم.",
               "why_casual": "سرعة من طراز النخبة.", "why_analyst": "حد الانطلاقة السريعة 25 كم/س.",
               "why_new_fan": "أي سرعة فوق 33 كم/س تُعد من الأسرع في اللعبة."},
        "pt": {"caption": "{speed} KM/H · {player}", "casual": "{player} voando: {speed} km/h!",
               "analyst": "{player} chega a {speed} km/h; {sprints} sprints, {distance} km percorridos.",
               "new_fan": "{player} acabou de atingir {speed} km/h, quase o máximo para um jogador.",
               "why_casual": "Velocidade de elite.", "why_analyst": "O limite de sprint é 25 km/h.",
               "why_new_fan": "Acima de 33 km/h está entre os mais rápidos do futebol."},
    },
    "milestone": {
        "en": {"caption": "MILESTONE · {player}", "casual": "{player}: {label}.", "analyst": "{player}: {label}.",
               "new_fan": "{player} reaches {label}.", "why_casual": "", "why_analyst": "", "why_new_fan": ""},
        "es": {"caption": "HITO · {player}", "casual": "{player}: {label}.", "analyst": "{player}: {label}.",
               "new_fan": "{player} alcanza {label}.", "why_casual": "", "why_analyst": "", "why_new_fan": ""},
        "fr": {"caption": "CAP FRANCHI · {player}", "casual": "{player} : {label}.", "analyst": "{player} : {label}.",
               "new_fan": "{player} atteint {label}.", "why_casual": "", "why_analyst": "", "why_new_fan": ""},
        "ar": {"caption": "إنجاز · {player}", "casual": "{player}: {label}.", "analyst": "{player}: {label}.",
               "new_fan": "{player} يبلغ {label}.", "why_casual": "", "why_analyst": "", "why_new_fan": ""},
        "pt": {"caption": "MARCA · {player}", "casual": "{player}: {label}.", "analyst": "{player}: {label}.",
               "new_fan": "{player} chega a {label}.", "why_casual": "", "why_analyst": "", "why_new_fan": ""},
    },
    "press_shift": {
        "en": {"caption": "TACTICAL SHIFT · {team}", "casual_up": "{team} have changed gear: they are hunting the ball high up the pitch.",
               "casual_down": "{team} have sat back and are defending deep.",
               "analyst_up": "{team} have pushed their press up since {onset}: {near_after} players near the ball in the opponent's build-up (was {near_before}); line up from {line_before} m to {line_after} m.",
               "analyst_down": "{team} have dropped off since {onset}: {near_after} players pressing the build-up (was {near_before}); line down from {line_before} m to {line_after} m.",
               "new_fan_up": "{team} are pressing: more players are chasing the ball near the opposition goal to win it back quickly.",
               "new_fan_down": "{team} are now defending deep, protecting their own goal instead of chasing the ball.",
               "why_casual": "Watch for mistakes in the build-up: that is where this change bites.",
               "why_analyst": "Detected from tracking data, not inferred from the score. Confidence z = {z}.",
               "why_new_fan": "Pressing means closing opponents down fast so they rush their passes."},
        "es": {"caption": "CAMBIO TÁCTICO · {team}", "casual_up": "{team} ha cambiado el chip: presiona arriba para robar rápido.",
               "casual_down": "{team} se ha replegado y defiende atrás.",
               "analyst_up": "{team} adelanta la presión desde el {onset}: {near_after} jugadores cerca del balón en la salida rival (antes {near_before}); línea de {line_before} m a {line_after} m.",
               "analyst_down": "{team} recula desde el {onset}: {near_after} jugadores presionando la salida (antes {near_before}); línea de {line_before} m a {line_after} m.",
               "new_fan_up": "{team} está presionando: más jugadores persiguen el balón cerca del área rival para recuperarlo rápido.",
               "new_fan_down": "{team} defiende ahora muy atrás, protegiendo su portería en lugar de perseguir el balón.",
               "why_casual": "Ojo a los errores en la salida de balón: ahí se nota el cambio.",
               "why_analyst": "Detectado con datos de tracking, no deducido del marcador. Confianza z = {z}.",
               "why_new_fan": "Presionar es cerrar rápido al rival para que se precipite con el pase."},
        "fr": {"caption": "CHANGEMENT TACTIQUE · {team}", "casual_up": "{team} a changé de braquet : le pressing est monté d'un cran.",
               "casual_down": "{team} a reculé et défend bas.",
               "analyst_up": "{team} presse plus haut depuis la {onset} : {near_after} joueurs près du ballon à la relance adverse (contre {near_before}) ; ligne de {line_before} m à {line_after} m.",
               "analyst_down": "{team} a reculé depuis la {onset} : {near_after} joueurs au pressing (contre {near_before}) ; ligne de {line_before} m à {line_after} m.",
               "new_fan_up": "{team} fait du pressing : plus de joueurs chassent le ballon près du but adverse pour le récupérer vite.",
               "new_fan_down": "{team} défend désormais très bas, en protégeant son but plutôt qu'en chassant le ballon.",
               "why_casual": "Surveillez la relance adverse : c'est là que ce changement fait mal.",
               "why_analyst": "Détecté à partir des données de tracking, pas déduit du score. Confiance z = {z}.",
               "why_new_fan": "Presser, c'est fondre sur l'adversaire pour le pousser à la faute."},
        "ar": {"caption": "تغيير تكتيكي · {team}", "casual_up": "{team} رفع النسق: يضغط عاليا لاستعادة الكرة بسرعة.",
               "casual_down": "{team} تراجع إلى الخلف ويدافع بعمق.",
               "analyst_up": "{team} رفع الضغط منذ الدقيقة {onset}: {near_after} لاعبين قرب الكرة أثناء بناء الخصم (مقابل {near_before})؛ خط الدفاع من {line_before} م إلى {line_after} م.",
               "analyst_down": "{team} خفف الضغط منذ الدقيقة {onset}: {near_after} لاعبين يضغطون (مقابل {near_before})؛ خط الدفاع من {line_before} م إلى {line_after} م.",
               "new_fan_up": "{team} يمارس الضغط: لاعبون أكثر يطاردون الكرة قرب مرمى الخصم لاستعادتها بسرعة.",
               "new_fan_down": "{team} يدافع الآن بعمق ويحمي مرماه بدلا من مطاردة الكرة.",
               "why_casual": "راقبوا أخطاء الخصم في بناء اللعب: هناك يظهر أثر هذا التغيير.",
               "why_analyst": "تم رصده من بيانات التتبع، لا من النتيجة. مستوى الثقة z = {z}.",
               "why_new_fan": "الضغط يعني الاقتراب السريع من الخصم لإجباره على التسرع في التمرير."},
        "pt": {"caption": "MUDANÇA TÁTICA · {team}", "casual_up": "O {team} mudou a marcha: está pressionando lá no alto.",
               "casual_down": "O {team} recuou e defende baixo.",
               "analyst_up": "O {team} adiantou a pressão desde os {onset}: {near_after} jogadores perto da bola na saída adversária (antes {near_before}); linha de {line_before} m para {line_after} m.",
               "analyst_down": "O {team} recuou desde os {onset}: {near_after} jogadores pressionando a saída (antes {near_before}); linha de {line_before} m para {line_after} m.",
               "new_fan_up": "O {team} está pressionando: mais jogadores correm atrás da bola perto do gol adversário para recuperá-la rápido.",
               "new_fan_down": "O {team} agora defende recuado, protegendo o próprio gol em vez de correr atrás da bola.",
               "why_casual": "Fique de olho nos erros na saída de bola: é ali que essa mudança aparece.",
               "why_analyst": "Detectado por dados de rastreamento, não deduzido do placar. Confiança z = {z}.",
               "why_new_fan": "Pressionar é fechar o adversário rápido para ele errar o passe."},
    },
    "control_chaos": {
        "en": {"caption_control": "CONTROL · {team}", "caption_chaos": "CHAOS",
               "casual_control": "{team} have got hold of this game.", "casual_chaos": "This has turned into a scrap!",
               "analyst_control": "Control index {index}: {team} dictating, {f1} {d1}, {f2} {d2}.",
               "analyst_chaos": "Chaos index {index}: {f1} {d1}, {f2} {d2}.",
               "new_fan_control": "{team} are in control: keeping the ball, stringing passes together, few mistakes.",
               "new_fan_chaos": "It's chaotic: the ball keeps changing hands and nobody can settle.",
               "why_control": "The biggest driver is {f1}: {d1}.", "why_chaos": "The biggest driver is {f1}: {d1}."},
        "es": {"caption_control": "CONTROL · {team}", "caption_chaos": "CAOS",
               "casual_control": "{team} se ha adueñado del partido.", "casual_chaos": "¡Esto se ha convertido en una batalla!",
               "analyst_control": "Índice de control {index}: manda {team}, {f1} {d1}, {f2} {d2}.",
               "analyst_chaos": "Índice de caos {index}: {f1} {d1}, {f2} {d2}.",
               "new_fan_control": "{team} controla: tiene el balón, encadena pases y apenas falla.",
               "new_fan_chaos": "Es un caos: el balón cambia de manos constantemente y nadie se asienta.",
               "why_control": "El factor principal es {f1}: {d1}.", "why_chaos": "El factor principal es {f1}: {d1}."},
        "fr": {"caption_control": "MAÎTRISE · {team}", "caption_chaos": "CHAOS",
               "casual_control": "{team} a pris les commandes du match.", "casual_chaos": "C'est devenu un vrai combat !",
               "analyst_control": "Indice de maîtrise {index} : {team} dicte le tempo, {f1} {d1}, {f2} {d2}.",
               "analyst_chaos": "Indice de chaos {index} : {f1} {d1}, {f2} {d2}.",
               "new_fan_control": "{team} maîtrise : garde le ballon, enchaîne les passes, peu d'erreurs.",
               "new_fan_chaos": "C'est le chaos : le ballon change de camp sans arrêt, personne ne s'installe.",
               "why_control": "Le facteur principal : {f1} ({d1}).", "why_chaos": "Le facteur principal : {f1} ({d1})."},
        "ar": {"caption_control": "سيطرة · {team}", "caption_chaos": "فوضى",
               "casual_control": "{team} أحكم قبضته على المباراة.", "casual_chaos": "المباراة تحولت إلى معركة!",
               "analyst_control": "مؤشر السيطرة {index}: {team} يفرض إيقاعه، {f1} {d1}، {f2} {d2}.",
               "analyst_chaos": "مؤشر الفوضى {index}: {f1} {d1}، {f2} {d2}.",
               "new_fan_control": "{team} مسيطر: يحتفظ بالكرة ويربط التمريرات بأخطاء قليلة.",
               "new_fan_chaos": "إنها فوضى: الكرة تنتقل بين الفريقين باستمرار ولا أحد يستقر.",
               "why_control": "العامل الأبرز هو {f1}: {d1}.", "why_chaos": "العامل الأبرز هو {f1}: {d1}."},
        "pt": {"caption_control": "CONTROLE · {team}", "caption_chaos": "CAOS",
               "casual_control": "O {team} tomou conta do jogo.", "casual_chaos": "Virou uma batalha!",
               "analyst_control": "Índice de controle {index}: {team} dita o ritmo, {f1} {d1}, {f2} {d2}.",
               "analyst_chaos": "Índice de caos {index}: {f1} {d1}, {f2} {d2}.",
               "new_fan_control": "O {team} está no controle: fica com a bola, troca passes e erra pouco.",
               "new_fan_chaos": "Está um caos: a bola troca de dono o tempo todo e ninguém se acerta.",
               "why_control": "O fator principal é {f1}: {d1}.", "why_chaos": "O fator principal é {f1}: {d1}."},
    },
    "rhythm": {
        "en": {"caption": "GAME RHYTHM", "siege": "{team} are laying siege: {tilt}% of final-third play.",
               "end_to_end": "End to end! Chances at both ends.", "sterile_possession": "{team} have the ball but no bite: {xg} xG in eight minutes.",
               "why": "Measured over the last eight minutes."},
        "es": {"caption": "RITMO DEL PARTIDO", "siege": "{team} encierra a su rival: {tilt}% del juego en el último tercio.",
               "end_to_end": "¡Ida y vuelta! Ocasiones en las dos áreas.", "sterile_possession": "{team} tiene el balón pero no muerde: {xg} xG en ocho minutos.",
               "why": "Medido en los últimos ocho minutos."},
        "fr": {"caption": "RYTHME DU MATCH", "siege": "{team} assiège le camp adverse : {tilt} % du jeu dans le dernier tiers.",
               "end_to_end": "Ça va d'un but à l'autre ! Des occasions des deux côtés.", "sterile_possession": "{team} a le ballon mais pas de mordant : {xg} xG en huit minutes.",
               "why": "Mesuré sur les huit dernières minutes."},
        "ar": {"caption": "إيقاع المباراة", "siege": "{team} يحاصر منافسه: {tilt}% من اللعب في الثلث الأخير.",
               "end_to_end": "هجمة مقابل هجمة! فرص على المرميين.", "sterile_possession": "{team} يستحوذ بلا خطورة: {xg} xG في ثماني دقائق.",
               "why": "محسوب على آخر ثماني دقائق."},
        "pt": {"caption": "RITMO DO JOGO", "siege": "O {team} encurrala o rival: {tilt}% do jogo no terço final.",
               "end_to_end": "Lá e cá! Chances nas duas áreas.", "sterile_possession": "O {team} tem a bola mas não ameaça: {xg} xG em oito minutos.",
               "why": "Medido nos últimos oito minutos."},
    },
    "momentum_swing": {
        "en": {"caption": "MOMENTUM · {team}", "line": "The momentum has swung towards {team}.", "why": "Based on chances, box entries and high regains over the last few minutes."},
        "es": {"caption": "INERCIA · {team}", "line": "La inercia del partido ahora es de {team}.", "why": "Según ocasiones, llegadas al área y recuperaciones altas de los últimos minutos."},
        "fr": {"caption": "DYNAMIQUE · {team}", "line": "La dynamique a basculé en faveur de {team}.", "why": "D'après les occasions, entrées dans la surface et récupérations hautes récentes."},
        "ar": {"caption": "الزخم · {team}", "line": "الزخم انتقل لصالح {team}.", "why": "استنادا إلى الفرص والدخول إلى المنطقة واستعادة الكرة عاليا في الدقائق الأخيرة."},
        "pt": {"caption": "EMBALO · {team}", "line": "O embalo do jogo agora é do {team}.", "why": "Com base em chances, chegadas na área e recuperações altas nos últimos minutos."},
    },
    "red_card": {
        "en": {"caption": "RED CARD · {player}", "line": "{player} is sent off! {team} down to {men}.", "why": "{team}'s win probability drops from {wp_from}% to {wp_to}%."},
        "es": {"caption": "ROJA · {player}", "line": "¡Expulsado {player}! {team} se queda con {men}.", "why": "La probabilidad de victoria de {team} cae del {wp_from}% al {wp_to}%."},
        "fr": {"caption": "CARTON ROUGE · {player}", "line": "{player} est expulsé ! {team} réduit à {men}.", "why": "La probabilité de victoire de {team} passe de {wp_from} % à {wp_to} %."},
        "ar": {"caption": "بطاقة حمراء · {player}", "line": "طرد {player}! {team} يكمل {men}.", "why": "احتمال فوز {team} يتراجع من {wp_from}% إلى {wp_to}%."},
        "pt": {"caption": "VERMELHO · {player}", "line": "{player} expulso! O {team} fica com {men}.", "why": "A probabilidade de vitória do {team} cai de {wp_from}% para {wp_to}%."},
    },
    "period_end": {
        "en": {"half_time": "HALF TIME", "full_time": "FULL TIME", "line": "{home} {score} {away}. xG {home_xg} – {away_xg}, possession {home_poss}% – {away_poss}%.",
               "why": "Top performer: {top_player} ({top_rating})."},
        "es": {"half_time": "DESCANSO", "full_time": "FINAL", "line": "{home} {score} {away}. xG {home_xg} – {away_xg}, posesión {home_poss}% – {away_poss}%.",
               "why": "Mejor jugador: {top_player} ({top_rating})."},
        "fr": {"half_time": "MI-TEMPS", "full_time": "FIN DU MATCH", "line": "{home} {score} {away}. xG {home_xg} – {away_xg}, possession {home_poss} % – {away_poss} %.",
               "why": "Homme du match : {top_player} ({top_rating})."},
        "ar": {"half_time": "نهاية الشوط الأول", "full_time": "نهاية المباراة", "line": "{home} {score} {away}. xG {home_xg} – {away_xg}، الاستحواذ {home_poss}% – {away_poss}%.",
               "why": "الأفضل: {top_player} ({top_rating})."},
        "pt": {"half_time": "INTERVALO", "full_time": "FIM DE JOGO", "line": "{home} {score} {away}. xG {home_xg} – {away_xg}, posse {home_poss}% – {away_poss}%.",
               "why": "Melhor em campo: {top_player} ({top_rating})."},
    },
}

MILESTONE_LABEL = {
    "passes": {"en": "{n} passes at {acc}%", "es": "{n} pases con un {acc}% de acierto", "fr": "{n} passes à {acc} % de réussite",
               "ar": "{n} تمريرة بدقة {acc}%", "pt": "{n} passes com {acc}% de acerto"},
    "km": {"en": "{n} km covered", "es": "{n} km recorridos", "fr": "{n} km parcourus", "ar": "{n} كم مقطوعة", "pt": "{n} km percorridos"},
}


class Names:
    """Resolves ids to display names."""

    def __init__(self, players: dict[str, str], teams: dict[str, str]):
        self.players = players
        self.teams = teams

    def p(self, pid: str | None) -> str:
        return self.players.get(pid or "", "")

    def t(self, tid: str | None) -> str:
        return self.teams.get(tid or "", "")


def _ctx(m: dict[str, Any], names: Names, lang: str, home: str, away: str) -> dict[str, Any]:
    f = m.get("facts", {})
    team = m.get("team")
    opp = away if team == home else home
    players = m.get("players", [])
    c: dict[str, Any] = {"team": names.t(team), "opp": names.t(opp), "player": names.p(players[0] if players else None)}
    kind = m["kind"]
    if kind == "goal":
        idx = 0 if team == home else 2
        wp_from, wp_to = f["wp_before"][idx], f["wp_after"][idx]
        xg = f.get("xg") or 0.0
        c.update(
            score=f["score_text"], xg=num(xg, lang, 2), one_in=max(1, round(1 / max(xg, 0.01))),
            wp_from=round(100 * wp_from), wp_to=round(100 * wp_to),
            swing=round(100 * abs(f["wp_swing"] if f.get("wp_swing") is not None else wp_to - wp_from)),  # the fact, not a re-derivation
            speed=num(f.get("shot_speed_kmh") or 0, lang), dist=num(f.get("distance_m") or 0, lang),
            ctx=GOAL_CTX[lang].get(f.get("context", "go_ahead"), "").format(team=names.t(team)),
            quality={"en": "against the odds", "es": "contra pronóstico", "fr": "contre toute attente", "ar": "عكس التوقعات",
                     "pt": "contra as probabilidades"}[lang] if xg < 0.08 else (
                {"en": "a big chance taken", "es": "una ocasión clara aprovechada", "fr": "une grosse occasion convertie",
                 "ar": "فرصة محققة استُغلت", "pt": "uma chance clara aproveitada"}[lang] if xg >= 0.3 else
                {"en": "a half-chance taken", "es": "una media ocasión aprovechada", "fr": "une demi-occasion convertie",
                 "ar": "نصف فرصة استُغلت", "pt": "meia chance aproveitada"}[lang]),
        )
    elif kind in {"big_chance", "thunderbolt"}:
        xg = f.get("xg") or 0.0
        keeper = names.p(f.get("keeper"))
        c.update(
            xg=num(xg, lang, 2), one_in=max(1, round(1 / max(xg, 0.01))), speed=num(f.get("shot_speed_kmh"), lang),
            dist=num(f.get("distance_m"), lang), outcome=OUTCOME[lang].get(f.get("outcome", ""), "").format(keeper=keeper),
            team_xg=num(f.get("team_xg"), lang, 2), team_goals=f.get("team_goals", 0),
        )
    elif kind == "master_pass":
        d = f["difficulty"]
        c.update(
            receiver=names.p(players[1] if len(players) > 1 else None), difficulty=round(d), length=num(f["length_m"], lang),
            bypassed=f["opponents_bypassed"], ball_speed=num(f["ball_speed_kmh"], lang), accuracy=num(f["passer_accuracy"], lang),
            passes=f["passer_passes"], success_pct=max(1, round(100 - d)), fail_pct=round(d),
        )
    elif kind == "speed":
        c.update(speed=num(f["speed_kmh"], lang, 1), sprints=f["sprints"], distance=num(f["distance_km"], lang, 1))
    elif kind == "milestone":
        if "accuracy" in f:
            c["label"] = MILESTONE_LABEL["passes"][lang].format(n=f["value"], acc=num(f["accuracy"], lang))
        else:
            c["label"] = MILESTONE_LABEL["km"][lang].format(n=f["distance_km"])
    elif kind == "press_shift":
        near_before, near_after = _pair(f["players_near_ball_before"], f["players_near_ball_after"], lang, 1)
        line_before, line_after = _pair(f["line_height_before_m"], f["line_height_after_m"], lang, 0)
        c.update(
            onset=f["onset_clock"].rstrip("'") if lang == "ar" else f["onset_clock"], near_before=near_before,
            near_after=near_after, line_before=line_before, line_after=line_after, z=num(f["z_score"], lang, 1),
            direction=f["direction"],
        )
    elif kind == "control_chaos":
        fs = f.get("factors", [])
        c.update(
            index=num(f["index"], lang), label=f["label"], team=names.t(f.get("controller")),
            f1=FACTOR.get(fs[0]["label"], {}).get(lang, fs[0]["label"]) if fs else "",
            d1=_fdetail(fs[0], lang) if fs else "",
            f2=FACTOR.get(fs[1]["label"], {}).get(lang, fs[1]["label"]) if len(fs) > 1 else "",
            d2=_fdetail(fs[1], lang) if len(fs) > 1 else "",
        )
    elif kind == "rhythm":
        tm = f.get("team")
        c.update(team=names.t(tm), tilt=num((f.get("field_tilt") or {}).get(tm, 0), lang),
                 xg=num((f.get("xg") or {}).get(tm, 0), lang, 2), label=f["label"])
    elif kind == "red_card":
        idx = 0 if team == home else 2
        wb, wa = f.get("wp_before") or [0, 0, 0], f.get("wp_after") or [0, 0, 0]
        left = int(f.get("players_remaining") or 10)
        c.update(wp_from=round(100 * wb[idx]), wp_to=round(100 * wa[idx]), players_remaining=left,
                 men=MEN[lang].get(left, str(left)))
    elif kind in {"half_time", "full_time"}:
        teams = f["teams"]
        tp = (f.get("top_players") or [{}])[0]
        c.update(
            home=names.t(home), away=names.t(away), score=f"{f['score'][home]}-{f['score'][away]}",
            home_xg=num(teams[home]["xg"], lang, 2), away_xg=num(teams[away]["xg"], lang, 2),
            home_poss=num(teams[home]["possession"], lang), away_poss=num(teams[away]["possession"], lang),
            top_player=tp.get("name", ""), top_rating=num(tp.get("rating"), lang, 1),
        )
    return c


def _pair(a: float | None, b: float | None, lang: str, digits: int) -> tuple[str, str]:
    """A before/after pair that shows its change: 0.65 -> 0.69 must not read "0.7 to 0.7"."""
    a, b = a or 0.0, b or 0.0
    while digits < 3 and round(a, digits) == round(b, digits) and a != b:
        digits += 1
    return num(a, lang, digits), num(b, lang, digits)


def _fdetail(factor: dict[str, Any], lang: str) -> str:
    v = factor["value"]
    if factor["label"] == "Pass completion":
        return f"{num(100 * v, lang)}%"
    return num(v, lang, 1)


def narrate(m: dict[str, Any], names: Names, lang: str, persona: str, home: str, away: str,
            fan_team: str | None = None) -> dict[str, str]:
    """Return {caption, line, explainer} for one moment, language and persona."""
    lang = lang if lang in LANGS else "en"
    persona = persona if persona in PERSONAS else "casual"
    kind = m["kind"]
    c = _ctx(m, names, lang, home, away)
    if kind in {"half_time", "full_time"}:
        t = T["period_end"][lang]
        return {"caption": t[kind], "line": t["line"].format(**c), "explainer": t["why"].format(**c)}
    if kind == "press_shift":
        t = T[kind][lang]
        d = c["direction"]
        return {"caption": t["caption"].format(**c), "line": t[f"{persona}_{d}"].format(**c),
                "explainer": t[f"why_{persona}"].format(**c)}
    if kind == "control_chaos":
        t = T[kind][lang]
        lab = c["label"] if c["label"] in {"control", "chaos"} else "chaos"
        return {"caption": t[f"caption_{lab}"].format(**c), "line": t[f"{persona}_{lab}"].format(**c),
                "explainer": t[f"why_{lab}"].format(**c)}
    if kind == "rhythm":
        t = T[kind][lang]
        return {"caption": t["caption"], "line": t.get(c["label"], t["end_to_end"]).format(**c), "explainer": t["why"]}
    if kind in {"momentum_swing", "red_card"}:
        t = T[kind][lang]
        return {"caption": t["caption"].format(**c), "line": t["line"].format(**c), "explainer": t["why"].format(**c)}
    t = T.get(kind, {}).get(lang)
    if not t:
        return {"caption": m.get("headline", ""), "line": m.get("headline", ""), "explainer": ""}
    caption = t["caption"]
    if kind == "goal" and fan_team:
        caption = t["fan_pos"] if fan_team == m.get("team") else t["fan_neg"]
    return {"caption": caption.format(**c), "line": t[persona].format(**c), "explainer": t[f"why_{persona}"].format(**c)}


def narrate_all(m: dict[str, Any], names: Names, langs: list[str], home: str, away: str) -> dict[str, dict[str, dict[str, str]]]:
    return {lang: {p: narrate(m, names, lang, p, home, away) for p in PERSONAS} for lang in langs}
