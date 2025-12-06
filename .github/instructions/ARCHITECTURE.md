# PyCatan Architecture Overview

## מהות הפרויקט

פרויקט PyCatan הוא הרחבה של הספרייה הקיימת למשחק Settlers of Catan, שמוסיפה שכבת סימולציה מלאה עם מנהל משחק, ממשקי משתמש, ו-AI players.

### המטרה
- יצירת פלטפורמה לסימולציות של משחק Catan
- תמיכה בשחקנים אנושיים ו-AI בו-זמנית
- ממשקי ויזואליזציה מרובים (קונסול, ווב)
- ארכיטקטורה מודולרית וניתנת להרחבה

## הארכיטקטורה

```
┌─────────────────────────────────────────────┐
│                GameManager                  │  ← מנהל התורות והזרימה
├─────────────────────────────────────────────┤
│ • game_loop()                               │
│ • handle_turn_rules()                       │
│ • request_input_from_user()                 │
│ • coordinate_interactions()                 │
└─────────────────┬───────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌─────────┐  ┌─────────┐  ┌─────────────┐
│  Game   │  │  Users  │  │Visualizations│
│(קיים)   │  │ (חדש)   │  │   (חדש)      │
└─────────┘  └─────────┘  └─────────────┘
```

### רכיבי המערכת

#### 1. GameManager (חדש)
**תפקיד:** מנהל את זרימת המשחק, התורות, וחוקי התורות
- ניהול לולאת המשחק הראשית
- תיאום בין שחקנים (מסחר, אישורים)
- אכיפת חוקי תורות (7 = השלכת קלפים, וכו')
- ניהול state של התור הנוכחי

#### 2. Game (קיים - התאמות קלות)
**תפקיד:** לוגיקת המשחק הבסיסית וחוקי המשחק
- כל הפונקציונליות הקיימת (add_settlement, trade, וכו')
- הוספת get_full_state() לויזואליזציה
- validation של פעולות

#### 3. User Hierarchy (חדש)
```python
User (Abstract)
├── HumanUser    # אינטראקציה דרך טרמינל
└── AIUser       # החלטות אלגוריתמיות
```
**תפקיד:** מספק אינפוט למנהל המשחק
- get_input() מחזיר פעולות מובנות
- כל User מנהל את הלוגיקה שלו (UI/AI)

#### 4. Visualization (חדש)
```python
Visualization (Base)
├── ConsoleVisualization    # הצגה בטרמינל
├── WebVisualization        # ממשק ווב
└── LogVisualization        # תיעוד לקובץ
```
**תפקיד:** הצגת מצב המשחק ופעולות
- notify_action() - עדכון מיידי
- update_full_state() - עדכון מלא בסוף תור

#### 5. Actions & Data (חדש)
```python
ActionType (Enum)           # סוגי פעולות
Action (DataClass)          # מבנה פעולה
GameState (DataClass)       # מצב משחק
```

## זרימת המשחק

### 1. אתחול
```
GameManager.initialize()
├── יצירת Game instance
├── רישום Users
├── הגדרת Visualizations
└── setup_phase()
```

### 2. לולאת משחק ראשית
```
while not game.has_ended:
    ├── roll_dice() או request_roll()
    ├── handle_dice_effects() (7 = robber, משאבים)
    ├── player_action_loop()
    │   ├── current_user.get_input()
    │   ├── validate_action()
    │   ├── execute_action()
    │   └── update_visualizations()
    └── end_turn()
```

### 3. אינטראקציות בין-שחקנים
```
Player A: propose_trade()
├── GameManager validates proposal
├── GameManager.request_input(Player B, "trade_response")
├── Player B: accept/reject
└── GameManager executes or cancels
```

## עקרונות עיצוב

### הפרדת אחריויות
- **Game** = מה מותר לעשות (חוקי המשחק)
- **GameManager** = מתי ואיך לעשות (זרימת התורות)
- **User** = מה לעשות (החלטות)
- **Visualization** = איך להציג (ממשק)

### מודולריות
- כל רכיב עצמאי וניתן להחלפה
- ממשקים ברורים בין הרכיבים
- קל להוסיף סוגי Users או Visualizations חדשים

### פשטות
- זרימה ישירה וברורה
- בלי abstractions מיותרות
- debugging וטיפול בשגיאות פשוטים

## התאמות לקוד הקיים

המטרה היא למזער שינויים בקוד הקיים:
- Game class נשאר כמעט זהה
- הוספת מתודות get_state() למחלקות קיימות
- Player class יישאר ללא שינוי
- Board/Building/Card classes ללא שינוי

## דוגמת שימוש

```python
# הגדרת המשחק
users = [HumanUser("Alice"), AIUser("Bob"), HumanUser("Charlie")]
visualizations = [ConsoleVisualization(), LogVisualization("game.log")]
game_manager = GameManager(users, visualizations)

# הפעלת המשחק
game_manager.start_game()  # מפעיל את game_loop()
```