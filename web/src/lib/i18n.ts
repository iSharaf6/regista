// The fixed words around the broadcast graphics (kickers, metric names, the "checked" receipt) in each viewer's
// language. The commentary itself is written per language by the Narrator and Localizer agents; these labels frame it,
// so an Arabic or Spanish broadcast doesn't wrap native copy in English chrome.
import type { Lang } from "./types";

type Labels = Record<string, string>;

const EN: Labels = {
  goal: "Goal", red_card: "Red card", big_chance: "Big chance", thunderbolt: "Shot speed", master_pass: "Pass quality",
  press_shift: "Tactical shift", control_chaos: "Control vs chaos", rhythm: "Game rhythm", momentum_swing: "Momentum",
  half_time: "Half time", full_time: "Full time", milestone: "Milestone", speed: "Top speed",
  shot: "Shot", player_cam: "Player cam", live: "LIVE",
  saved: "saved", blocked: "blocked", out: "off target", off_target: "off target", post: "post",
  checked_n: "CHECKED · {a}/{b} FIGURES", checked: "CHECKED", from_data: "FROM THE MATCH DATA", not_checked: "NOT CHECKED",
  template: "TEMPLATE", win_probability: "Win probability",
  rating: "rating", top_kmh: "top km/h", passes: "passes", accuracy: "accuracy", avg_difficulty: "avg difficulty",
  difficulty: "difficulty", metres: "metres", bypassed: "bypassed", near_ball: "Near ball", line_m: "Line (m)",
  passer_acc: "passer {n}% accurate",
};

const L: Record<Lang, Labels> = {
  en: EN,
  es: {
    goal: "Gol", red_card: "Tarjeta roja", big_chance: "Ocasión clara", thunderbolt: "Velocidad de tiro",
    master_pass: "Pase de calidad", press_shift: "Cambio táctico", control_chaos: "Control o caos", rhythm: "Ritmo del partido",
    momentum_swing: "Dominio", half_time: "Descanso", full_time: "Final del partido", milestone: "Hito", speed: "Velocidad punta",
    shot: "Tiro", player_cam: "Cámara del jugador", live: "EN VIVO",
    saved: "parado", blocked: "bloqueado", out: "fuera", off_target: "fuera", post: "al palo",
    checked_n: "VERIFICADO · {a}/{b} CIFRAS", checked: "VERIFICADO", from_data: "DATOS DEL PARTIDO", not_checked: "SIN VERIFICAR",
    template: "PLANTILLA", win_probability: "Probabilidad de victoria",
    rating: "nota", top_kmh: "km/h máx.", passes: "pases", accuracy: "precisión", avg_difficulty: "dificultad media",
    difficulty: "dificultad", metres: "metros", bypassed: "superados", near_ball: "Cerca del balón", line_m: "Línea (m)",
    passer_acc: "pasador: {n}% de acierto",
  },
  fr: {
    goal: "But", red_card: "Carton rouge", big_chance: "Grosse occasion", thunderbolt: "Vitesse de frappe",
    master_pass: "Passe de qualité", press_shift: "Changement tactique", control_chaos: "Maîtrise ou chaos", rhythm: "Rythme du match",
    momentum_swing: "Dynamique", half_time: "Mi-temps", full_time: "Fin du match", milestone: "Cap franchi", speed: "Vitesse de pointe",
    shot: "Tir", player_cam: "Caméra joueur", live: "EN DIRECT",
    saved: "arrêté", blocked: "contré", out: "non cadré", off_target: "non cadré", post: "poteau",
    checked_n: "VÉRIFIÉ · {a}/{b} CHIFFRES", checked: "VÉRIFIÉ", from_data: "DONNÉES DU MATCH", not_checked: "NON VÉRIFIÉ",
    template: "MODÈLE", win_probability: "Probabilité de victoire",
    rating: "note", top_kmh: "km/h max", passes: "passes", accuracy: "précision", avg_difficulty: "difficulté moy.",
    difficulty: "difficulté", metres: "mètres", bypassed: "dépassés", near_ball: "Près du ballon", line_m: "Ligne (m)",
    passer_acc: "passeur : {n} % de réussite",
  },
  pt: {
    goal: "Gol", red_card: "Cartão vermelho", big_chance: "Grande chance", thunderbolt: "Velocidade do chute",
    master_pass: "Passe de qualidade", press_shift: "Mudança tática", control_chaos: "Controle ou caos", rhythm: "Ritmo do jogo",
    momentum_swing: "Domínio", half_time: "Intervalo", full_time: "Fim de jogo", milestone: "Marco", speed: "Velocidade máxima",
    shot: "Chute", player_cam: "Câmera do jogador", live: "AO VIVO",
    saved: "defendido", blocked: "bloqueado", out: "para fora", off_target: "para fora", post: "na trave",
    checked_n: "VERIFICADO · {a}/{b} NÚMEROS", checked: "VERIFICADO", from_data: "DADOS DA PARTIDA", not_checked: "NÃO VERIFICADO",
    template: "MODELO", win_probability: "Probabilidade de vitória",
    rating: "nota", top_kmh: "km/h máx.", passes: "passes", accuracy: "precisão", avg_difficulty: "dificuldade média",
    difficulty: "dificuldade", metres: "metros", bypassed: "superados", near_ball: "Perto da bola", line_m: "Linha (m)",
    passer_acc: "passador: {n}% de acerto",
  },
  ar: {
    goal: "هدف", red_card: "بطاقة حمراء", big_chance: "فرصة محققة", thunderbolt: "سرعة التسديدة", master_pass: "تمريرة مميزة",
    press_shift: "تحول تكتيكي", control_chaos: "سيطرة أم فوضى", rhythm: "إيقاع المباراة", momentum_swing: "الأفضلية",
    half_time: "بين الشوطين", full_time: "نهاية المباراة", milestone: "إنجاز", speed: "السرعة القصوى",
    shot: "تسديدة", player_cam: "كاميرا اللاعب", live: "مباشر",
    saved: "تصدى لها الحارس", blocked: "مصدودة", out: "خارج المرمى", off_target: "خارج المرمى", post: "في القائم",
    checked_n: "تم التحقق · الأرقام {a}/{b}", checked: "تم التحقق", from_data: "من بيانات المباراة", not_checked: "لم يتم التحقق",
    template: "قالب", win_probability: "احتمال الفوز",
    rating: "التقييم", top_kmh: "أقصى سرعة كم/س", passes: "تمريرات", accuracy: "الدقة", avg_difficulty: "متوسط الصعوبة",
    difficulty: "الصعوبة", metres: "متر", bypassed: "لاعبون تم تجاوزهم", near_ball: "قرب الكرة", line_m: "خط الدفاع (م)",
    passer_acc: "دقة الممرر {n}%",
  },
};

/** A broadcast label in the cue's locale ("ar", "es-ES" …), falling back to English, with {placeholders} filled in. */
export function label(locale: string | null | undefined, key: string, vars: Record<string, string | number> = {}): string {
  const lang = (locale ?? "en").slice(0, 2) as Lang;
  const text = L[lang]?.[key] ?? EN[key] ?? key.replaceAll("_", " ");
  return text.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}
