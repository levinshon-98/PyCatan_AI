# 🤖 AI Testing Tools

כלים לבדיקת יכולת ה-AI להבין מצבי משחק באמצעות Web Visualizer.

## 🎯 מטרה

הכלים האלה מאפשרים:
1. **לתפוס מצב משחק אמיתי** מתוך משחק רץ
2. **לראות את ה-JSON המדויק והמלא** שעובר לוויזואליזציה (זה מה שנשלח ל-AI)
3. **להציג מצב משחק ספציפי** ב-Web Visualizer
4. **לבדוק אם AI מבין את מצב הלוח** לפני שמפתחים אותו

## 📁 קבצים

```
ai_testing/
├── capture_with_web.py         # תופס JSON + פותח דפדפן 🌟 BEST FOR VIEWING!
├── show_complete_state.py      # מציג מצב מלא וסיכום (ללא דפדפן)
├── simple_capture.py           # תופס JSON בלבד (מהיר)
├── visualize_game_state.py     # מציג JSON קיים בדפדפן
├── sample_states/              # קבצי JSON לדוגמה
│   ├── captured_game.json      # מצב שנתפס ממשחק אמיתי ✅
│   └── ...
├── captured_states/            # כל המצבים שנתפסו
│   ├── state_001_initial.json
│   └── state_XXX_final.json
└── README.md                   # התיעוד הזה
```

## 🚀 שימוש מומלץ

### אופציה 1: תפיסה + צפייה (מומלץ!)

**הדרך הטובה ביותר אם אתה רוצה לראות את הלוח:**

```bash
py examples/ai_testing/capture_with_web.py examples/data/game_moves_3Players.txt
```

**מה זה עושה:**
1. ✅ מריץ משחק עם האינפוטים
2. 🌐 פותח דפדפן עם Web Visualizer
3. 📸 תופס את כל ה-JSON בשקט ברקע
4. 💾 שומר את המצב המלא (כולל points + adjacency!)
5. 🎯 השרת נשאר פעיל - תוכל לראות את הלוח

**בסוף תקבל:**
- הלוח מוצג בדפדפן ✨
- JSON מלא עם כל המידע שמור בקובץ
- אפשר ללחוץ Ctrl+C לסגור

### אופציה 2: תפיסה בלי דפדפן (מהיר)

**אם אתה רק רוצה את ה-JSON בלי להפעיל דפדפן:**

```bash
py examples/ai_testing/show_complete_state.py examples/data/game_moves_3Players.txt
```

**מה זה עושה:**
- מריץ משחק בלי דפדפן
- מדפיס את כל ה-JSON בסוף
- שומר את המצבים לקבצים

### אופציה 3: הצגת JSON קיים בדפדפן

**אם יש לך כבר JSON ואתה רוצה לראות אותו:**

```bash
py examples/ai_testing/visualize_game_state.py --state-file examples/ai_testing/sample_states/captured_game.json
```

---

## 📊 מה כולל ה-JSON המלא?

כדי ליצור מצב משחק משלך:

1. **צור קובץ טקסט** עם פקודות משחק:
```
3          # מספר שחקנים
Alice
Bob
Charlie
s 10       # settlement בנקודה 10
rd 10 11   # road מ-10 ל-11
...
```

2. **הרץ את simple_capture**:
```bash
py examples/ai_testing/simple_capture.py your_inputs.txt
```

3. **תראה את ה-JSON** בקונסול ובקובץ

## 📊 מה מודפס?

### JSON מלא (לשליחה ל-AI)
```json
{
  "hexes": [
    {"id": 1, "type": "wood", "number": 12, ...}
  ],
  "settlements": [
    {"point_id": 10, "owner": 0, "type": "SETTLEMENT"}
  ],
  "cities": [...],
  "roads": [
    {"start_point": 10, "end_point": 11, "owner": 0}
  ],
  "players": [
    {
      "id": 0,
      "name": "Alice",
      "cards": ["WOOD", "BRICK"],
      "victory_points": 2,
      ...
    }
  ],
  "current_player": 0,
  "current_phase": "NORMAL_PLAY",
  "robber_position": {"q": 0, "r": 0}
}
```

## 🎮 מבנה ה-JSON

### Hexes (משושים)
```json
{
  "coords": [0, 0],
  "type": "HILLS",
  "number": 3,
  "has_robber": false
}
```

### Buildings (התנחלויות וערים)
```json
{
  "point_id": 5,
  "owner": 0,
  "type": "SETTLEMENT"  // או "CITY"
}
```

### Roads (דרכים)
```json
{
  "start_point": 5,
  "end_point": 8,
  "owner": 0
}
```

### Players (שחקנים)
```json
{
  "id": 0,
  "name": "Player 0",
  "cards": ["WOOD", "BRICK"],
  "dev_cards": ["KNIGHT"],
  "victory_points": 6,
  "has_longest_road": true,
  "has_largest_army": false,
  "knights_played": 1
}
```

## 📝 יצירת קובץ JSON חדש

כדי ליצור מצב משחק משלך:

1. העתק אחד מהקבצים ב-`sample_states/`
2. ערוך את הערכים:
   - `tiles` - המשושים בלוח
   - `buildings` - התנחלויות וערים
   - `roads` - דרכים
   - `players_state` - מידע על כל שחקן
3. שמור עם שם תיאורי
4. הרץ: `python visualize_game_state.py --state-file your_file.json`

## 🔍 למה זה חשוב ל-AI?

1. **AI צריך להבין את הלוח** - ה-JSON הזה מכיל את **כל המידע** שהוא יקבל
2. **בדיקת הבנה** - אפשר לבדוק אם AI מבין מצבים שונים לפני שבונים אותו
3. **תיעוד מדויק** - רואים בדיוק איזה מידע זמין לקבלת החלטות

## 💡 טיפים

- **הרץ את הסקריפט** בכל שלב של משחק רגיל כדי לראות איך המידע משתנה
- **שמור JSON** ממצבי משחק מעניינים לבדיקה מאוחר יותר
- **השווה בין מצבים** - ראה איך הלוח משתנה במהלך המשחק

## 🛠️ שילוב עם AI

כשתבנה AI agent:

```python
from examples.ai_testing.visualize_game_state import game_to_game_state

# צור מצב משחק
game_state = game_to_game_state(game)

# המר לפורמט web (זה מה שה-AI יקבל)
web_format = web_viz._convert_game_state(game_state)

# שלח ל-AI
ai_decision = ai_agent.decide(web_format)
```

---

**עכשיו יש לך את כל הכלים כדי לבדוק שה-AI מבין את הלוח!** 🎯

## 🎯 המידע המלא שה-AI מקבל - עכשיו עם Points!

### ⭐ חשוב! מידע חדש שהוספנו:

#### 📍 Points (54 נקודות)
כל נקודה כוללת:
- `point_id` - מזהה (1-54)
- `adjacent_points` - רשימת נקודות מחוברות (לדרכים!)
- `adjacent_hexes` - רשימת משושים צמודים (למשאבים!)

**דוגמה:**
```json
{
  "point_id": 10,
  "adjacent_points": [9, 11, 20],  // יכול לבנות דרך לכיוון אלה
  "adjacent_hexes": [5, 4, 1]       // יקבל משאבים מאלה
}
```

#### 🗺️ Board Graph
```json
{
  "adjacency": {"10": [9, 11, 20]},        // גרף קישוריות מלא
  "hex_to_points": {"5": [9,10,11,19,20,21]}  // נקודות על כל משושה
}
```

**למה זה קריטי:**
- 🛣️ חישוב הדרך הארוכה ביותר
- 🎯 מציאת נקודות חסימה
- 📊 אסטרטגיה - אילו נקודות כדאי לתפוס

---
