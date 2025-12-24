# AI Testing - Usage Examples

## דוגמאות שימוש מהירות

### 1. תפיסת JSON ממשחק קיים

```bash
# שימוש בקובץ אינפוטים קיים
py examples/ai_testing/simple_capture.py examples/data/game_moves_3Players.txt

# הפלט:
# - JSON מודפס לקונסול בכל עדכון
# - המצב האחרון נשמר ל: examples/ai_testing/sample_states/captured_game.json
```

### 2. הצגת המצב שנתפס

```bash
# הצג את המצב בדפדפן
py examples/ai_testing/visualize_game_state.py --state-file examples/ai_testing/sample_states/captured_game.json
```

### 3. שמירת כל הפלט לקובץ

```bash
# שמור את כל הפלט (כולל כל ה-JSONs) לקובץ
py examples/ai_testing/simple_capture.py examples/data/game_moves_3Players.txt > output.txt 2>&1
```

## מבנה ה-JSON

### Hexes (משושים)
כל משושה מכיל:
- `id` - מזהה ייחודי (1-19)
- `type` - סוג המשאב: "wood", "brick", "sheep", "wheat", "ore", "desert"
- `number` - המספר על המשושה (2-12, או null למדבר)
- `has_robber` - האם השודד נמצא שם
- `position` - [row, col] - מיקום בלוח המקורי
- `axial_coords` / `q`, `r` - קואורדינטות hexagonal

### Buildings (מבנים)
```json
{
  "settlements": [
    {
      "point_id": 10,
      "owner": 0,
      "type": "SETTLEMENT"
    }
  ],
  "cities": [
    {
      "point_id": 14,
      "owner": 1,
      "type": "CITY"
    }
  ]
}
```

### Roads (דרכים)
```json
{
  "roads": [
    {
      "start_point": 10,
      "end_point": 11,
      "owner": 0
    }
  ]
}
```

### Players (שחקנים)
```json
{
  "players": [
    {
      "id": 0,
      "name": "Alice",
      "cards": ["WOOD", "BRICK", "SHEEP"],  // משאבים בידיים
      "dev_cards": ["KNIGHT"],               // קלפי פיתוח
      "victory_points": 3,
      "has_longest_road": false,
      "has_largest_army": false,
      "knights_played": 1
    }
  ]
}
```

### Game State (מצב משחק כללי)
```json
{
  "current_player": 0,          // מי התור
  "current_phase": "NORMAL_PLAY",  // שלב המשחק
  "robber_position": {          // איפה השודד
    "q": 0,
    "r": 0
  }
}
```

## טיפים לשימוש

### יצירת מצבי בדיקה

1. **ערוך קובץ אינפוט** - צור משחק עם המצב הרצוי
2. **הרץ simple_capture** - תפוס את המצב
3. **שמור את ה-JSON** - יש לך עכשיו מצב לבדיקה

### בדיקת הבנת AI

1. **תפוס מצב** מעניין ממשחק
2. **שלח ל-AI** את ה-JSON
3. **בקש החלטה** - מה הפעולה הטובה ביותר?
4. **הצג בדפדפן** - ראה את אותו המצב ויזואלית

### דיבוג

אם AI מקבל החלטות מוזרות:
1. הדפס את ה-JSON שהוא קיבל
2. הצג אותו ב-visualizer
3. ראה מה הוא אמור לראות
4. זהה פערים בהבנה

## דוגמה מלאה

```bash
# 1. תפוס מצב ממשחק
py examples/ai_testing/simple_capture.py examples/data/game_moves_3Players.txt

# 2. הקובץ נשמר ב:
# examples/ai_testing/sample_states/captured_game.json

# 3. הצג אותו בדפדפן
py examples/ai_testing/visualize_game_state.py --state-file examples/ai_testing/sample_states/captured_game.json

# 4. עכשיו אתה יכול:
#    - לראות את הלוח ויזואלית
#    - לקרוא את ה-JSON
#    - לשלוח ל-AI לבדיקה
```

---

**עכשיו יש לך את כל הכלים כדי לבדוק שה-AI מבין את הלוח!** 🎯
