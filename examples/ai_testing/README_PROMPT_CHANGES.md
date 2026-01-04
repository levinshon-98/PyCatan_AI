# 🔄 עדכון: מערכת ניהול הפרומפטים החדשה

תאריך: 4 ינואר 2026

## סיכום השינויים

עדכנו את מערכת ניהול הפרומפטים כך שכל פרומפט נשמר עם מספר ייחודי, במקום לדרוס פרומפטים קודמים.

---

## מבנה התיקיות החדש

```
examples/ai_testing/my_games/ai_logs/
└── session_20260104_HHMMSS/          # כל משחק = סשן נפרד
    ├── current_session.txt            # קישור לסשן הנוכחי
    ├── chat_history.json              # היסטוריית צ'אט
    ├── agent_memories.json            # זיכרונות של כל AI
    │
    ├── NH/                            # תיקיית שחקן NH
    │   ├── prompts/                   # כל הפרומפטים של NH
    │   │   ├── prompt_1.json         # פרומפט ראשון
    │   │   ├── prompt_1.txt          # גרסה קריאה
    │   │   ├── prompt_2.json         # פרומפט שני
    │   │   ├── prompt_2.txt
    │   │   └── ...
    │   └── player_NH.md              # לוג מפורט של NH
    │
    ├── Alex/                          # תיקיית שחקן Alex
    │   ├── prompts/
    │   │   ├── prompt_1.json
    │   │   └── ...
    │   └── player_Alex.md
    │
    └── Sarah/                         # תיקיית שחקן Sarah
        ├── prompts/
        └── player_Sarah.md
```

---

## קבצים שהשתנו

### 1. `generate_prompts_from_state.py`

#### ✅ שונה:
- **`save_prompt_to_file()`** - שומר במספרים סדרתיים (`prompt_1`, `prompt_2`, ...)
- **`main()`** - יוצר תיקיות לפי שחקן

#### ➕ חדש:
- **`get_latest_prompt(player_name)`** - מחזיר את הפרומפט העדכני ביותר

**שימוש:**
```python
from examples.ai_testing.generate_prompts_from_state import get_latest_prompt

# קבל את הפרומפט האחרון
file, data = get_latest_prompt("NH")
if data:
    print(f"Latest: {file}")
```

---

### 2. `test_ai_live.py`

#### ✅ שונה:
- **`monitor_prompts()`** - מחפש ב-`player_name/prompts/` במקום `prompts/`
- **`process_prompt()`** - קורא ישירות JSON במקום TXT

**עכשיו עובד עם:**
```
session_X/player/prompts/prompt_N.json ✅
```

**במקום:**
```
session_X/prompts/prompt_player_X.json ❌
```

---

### 3. `example_get_latest_prompt.py` ➕ חדש

סקריפט לדוגמה שמראה איך לקבל את הפרומפט העדכני ביותר.

**הרצה:**
```bash
python examples/ai_testing/example_get_latest_prompt.py NH
```

**פלט:**
```
✅ Found latest prompt!
📁 File: session_X/NH/prompts/prompt_5.json
📊 Size: 12,543 bytes

Turn: 8
Phase: MAIN_PHASE
Current Player: NH
```

---

### 4. תיעוד חדש

- **`PROMPT_STRUCTURE.md`** - מבנה ושימוש במערכת הפרומפטים
- **`CHANGES_PROMPT_SYSTEM.md`** - סיכום השינויים (בעברית)
- **`FIX_test_ai_live.md`** - הסבר על התיקון ל-`test_ai_live.py`

---

## איך להשתמש?

### תסריט רגיל (משחק עם פרומפטים)

```bash
# טרמינל 1: הרץ משחק עם פרומפטים
python examples/ai_testing/play_with_prompts.py

# טרמינל 2: הרץ AI tester
python examples/ai_testing/test_ai_live.py
```

### קבלת פרומפט עדכני בקוד

```python
from examples.ai_testing.generate_prompts_from_state import get_latest_prompt

# דרך 1: קבל את הפרומפט האחרון
prompt_file, prompt_data = get_latest_prompt("NH")

if prompt_data:
    # שלח ל-LLM
    llm_response = llm.send(prompt_data)

# דרך 2: מצא את כל הפרומפטים
from pathlib import Path

session = Path("examples/ai_testing/my_games/ai_logs/session_XXXXX")
all_prompts = sorted((session / "NH" / "prompts").glob("prompt_*.json"))

# הפרומפט האחרון הוא תמיד האחרון ברשימה
latest = all_prompts[-1]
```

---

## יתרונות המבנה החדש

1. ✅ **אין דריסה** - כל פרומפט נשמר
2. ✅ **היסטוריה מלאה** - תמיד יש גישה לפרומפטים קודמים
3. ✅ **קל למעקב** - המספר הגבוה ביותר = העדכני ביותר
4. ✅ **ארגון ברור** - כל שחקן בתיקייה נפרדת
5. ✅ **קל לדיבאג** - אפשר להשוות פרומפטים בין תורים

---

## שינויים עתידיים אפשריים

- [ ] הוספת תיקיית `responses/` לכל שחקן
- [ ] יצירת זוגות prompt-response לאימון
- [ ] ניקוי אוטומטי של סשנים ישנים
- [ ] דחיסת פרומפטים ארוכים
- [ ] כלי להשוואת פרומפטים (diff tool)

---

## בעיות? 

### בעיה: "No prompts found"
**פתרון:** ודא שהרצת `play_with_prompts.py` קודם

### בעיה: "test_ai_live תקוע"
**פתרון:** ודא שהסשן קיים ויש תיקיות שחקנים עם פרומפטים

### בעיה: "Player directory not found"
**פתרון:** המערכת יוצרת תיקיות אוטומטית כשיש פרומפטים חדשים

---

**תודה על השאלה הטובה! 🎯**  
עכשיו המערכת הרבה יותר נוחה לשימוש ולמעקב.
