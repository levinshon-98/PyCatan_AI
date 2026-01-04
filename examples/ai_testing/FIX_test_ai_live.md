# ✅ תיקון: test_ai_live.py עובד עם המבנה החדש

## הבעיה שנפתרה

ה-`test_ai_live.py` היה תקוע על "Waiting for NEW prompts to be generated..." כי הוא חיפש פרומפטים במבנה הישן:

```
session_X/prompts/prompt_player_NH.json  ❌ לא קיים יותר
```

## הפתרון

עדכנו את `test_ai_live.py` לעבוד עם המבנה החדש:

```
session_X/
├── NH/
│   └── prompts/
│       ├── prompt_1.json  ✅ זה מה שהוא מחפש עכשיו
│       ├── prompt_2.json
│       └── ...
├── Alex/
│   └── prompts/
│       └── ...
```

## שינויים שבוצעו

### 1. **פונקציה `monitor_prompts()`**
**לפני:**
```python
prompts_dir = session_dir / 'prompts'
prompt_files = sorted(prompts_dir.glob("prompt_player_*.txt"))
```

**אחרי:**
```python
# מצא את כל תיקיות השחקנים
player_dirs = [d for d in session_dir.iterdir() if d.is_dir()]

# עבור על כל שחקן
for player_dir in player_dirs:
    prompts_subdir = player_dir / 'prompts'
    player_prompts = sorted(prompts_subdir.glob("prompt_*.json"))
```

### 2. **פונקציה `process_prompt()`**
**לפני:**
```python
player_name = prompt_file.stem.replace("prompt_player_", "")
json_file = prompt_file.with_suffix('.json')
```

**אחרי:**
```python
# חלץ שם שחקן מהנתיב: session/player_name/prompts/prompt_N.json
player_name = prompt_file.parent.parent.name

# הקובץ כבר JSON - קרא ישירות
with open(prompt_file, 'r') as f:
    prompt_json = json.load(f)
```

### 3. **עיבוד מקביל**
עדכון הלוגיקה שעוקבת אחרי פרומפטים שעובדו:

**לפני:**
```python
processed_files[filename] = content_hash
```

**אחרי:**
```python
file_key = (player_name, prompt_num)
processed_files[file_key] = content_hash
```

## בדיקה

כדי לבדוק שהתיקון עובד:

1. **הרץ משחק עם פרומפטים:**
   ```bash
   python examples/ai_testing/play_with_prompts.py
   ```

2. **בטרמינל נפרד, הרץ את ה-AI tester:**
   ```bash
   python examples/ai_testing/test_ai_live.py
   ```

3. **אתה אמור לראות:**
   ```
   📁 Watching: examples\ai_testing\my_games\ai_logs\session_XXXXXXX
      Structure: session/player_name/prompts/prompt_N.json
   🤖 Model: models/gemini-2.5-flash
   ⏳ Waiting for NEW prompts to be generated...
   
   🆕 Detected 3 new prompt(s)
   📤 Submitting to queue: NH, Alex, Sarah
   ```

## מה הלאה?

עכשיו המערכת מזהה פרומפטים חדשים ושולחת אותם ל-AI! 🎉

הקובץ `test_ai_live.py` עכשיו:
- ✅ מזהה את המבנה החדש של פרומפטים
- ✅ קורא ישירות מקבצי JSON
- ✅ מעבד מספר שחקנים במקביל
- ✅ מסנן שחקנים שכבר יש להם בקשות פעילות
