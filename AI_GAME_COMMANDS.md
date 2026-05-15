# PyCatan AI - פקודות הרצה חשובות

מסמך קצר לפקודות היומיומיות של הרצת משחק, המשך מסשן קודם, replay, ושפת צ'אט.

## ריצה חדשה רגילה

```powershell
.\play_ai_auto.bat
```

פותח:

- Board / Unified view: `http://localhost:5000/unified`
- AI Viewer: `http://localhost:5001`
- LLM Logger console

כל ריצה יוצרת סשן חדש תחת:

```text
examples\ai_testing\my_games\session_YYYYMMDD_HHMMSS
```

## ריצה חדשה עם צ'אט בעברית

```powershell
.\play_ai_auto.bat --hebrew-chat
```

## ריצה חדשה עם צ'אט באנגלית

```powershell
.\play_ai_auto.bat --english-chat
```

אפשר גם להשתמש בצורה הכללית:

```powershell
.\play_ai_auto.bat --chat-language hebrew
.\play_ai_auto.bat --chat-language english
```

## ריצה עם שמות שחקנים

```powershell
.\play_ai_auto.bat --names Hadar Shon Ziv --hebrew-chat
```

מספר השמות קובע את מספר השחקנים.

## ריצה עם מסך הגדרות

```powershell
.\PLAY_WITH_SET_SETTINGS.bat
```

זה פותח דף בדפדפן לבחירת model, API key, מספר שחקנים, שמות ושפת table-talk.

אפשר להעביר גם flags:

```powershell
.\PLAY_WITH_SET_SETTINGS.bat --hebrew-chat
```

Key modes for the browser setup:

```powershell
.\PLAY_WITH_SET_SETTINGS.bat --use-env-keys
.\PLAY_WITH_SET_SETTINGS.bat --ask-api-keys
```

Default is `--use-env-keys`: empty key fields use `GEMINI_API_KEY`,
`ELEVENLABS_API_KEY`, and `ELEVENLABS_DEFAULT_VOICE_ID` from ENV or `.env`.
Use `--ask-api-keys` / `--ask-keys` when you want the browser form to require
typed keys for this run.

## לראות מה הסשן הנוכחי

```powershell
Get-Content examples\ai_testing\my_games\current_session.txt
```

## למצוא סשנים אחרונים

```powershell
Get-ChildItem examples\ai_testing\my_games -Directory |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 10 Name,LastWriteTime
```

## להמשיך סשן קודם

בפועל זה fast replay: הקוד משחק מחדש את הפעולות המוקלטות מהר, ואז ממשיך live עם הקוד הנוכחי.

```powershell
.\play_ai_auto.bat --replay-session session_20260515_235539
```

חשוב: זה יוצר סשן חדש נגזר. הסשן המקורי לא משתנה.

אל תשתמש כסורס בסשן שנוצר על ידי `--watch-replay`. סשן כזה הוא תצוגה בלבד ובדרך כלל אין בו `responses/response_*.json`. אם פתחת `session_metadata.json` ורואים:

```json
"mode": "watch_replay_visual_playback"
```

אז צריך להשתמש בסשן המקורי שמופיע תחת `replay.source_session` או `derived_from`.

## לעצור לפני נקודת באג ולהמשיך live

אם הבאג קרה בפעולה של שחקן מסוים, עדיף לעצור לפני הפעולה החשודה:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_235539 --replay-stop-before Shon:4
```

המשמעות: משחזר הכל עד לפני `Shon` בקשה 4, ואז נותן ל-AI להחליט מחדש עם הקוד המתוקן.

## לשחזר כולל פעולה מסוימת ואז להמשיך

אם הפעולה כבר ידועה כתקינה ורוצים לדלג עליה:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_235539 --replay-through Shon:4
```

זה משחזר גם את `Shon:4`, כולל צ'אט וזיכרון שהוקלטו שם.

## איך למצוא את `Player:N`

פתח את תיקיית הסשן:

```text
examples\ai_testing\my_games\session_YYYYMMDD_HHMMSS
```

ואז חפש אצל השחקן:

```text
<Player>\prompts\prompt_N.json
<Player>\responses\response_N.json
```

אם הקובץ הוא:

```text
examples\ai_testing\my_games\session_20260515_235539\Shon\responses\response_4.json
```

אז הסמן הוא:

```text
Shon:4
```

## Replay וצ'אט בעברית/אנגלית

דוגמה להמשך סשן ישן, אבל הודעות חדשות בעברית:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_235539 --hebrew-chat
```

דוגמה להמשך סשן ישן, אבל הודעות חדשות באנגלית:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_235539 --english-chat
```

חשוב: הודעות שכבר הוקלטו בסשן המקורי נשארות בשפה המקורית שלהן. הדגל `--hebrew-chat` או `--english-chat` משפיע בעיקר על ההודעות החדשות אחרי שהמשחק ממשיך live.

## לא להציג צ'אט ישן בזמן replay

אם לא רוצים שהצ'אט הישן יוזרק מחדש:

```powershell
.\play_ai_auto.bat --replay-session session_20260515_235539 --replay-skip-chat --hebrew-chat
```

זה שימושי אם הצ'אט הישן הכיל אמונה שגויה או בלבול סביב באג.

## צפייה ב-replay בלי להמשיך AI live

```powershell
.\play_ai_auto.bat --watch-replay --replay-session session_20260515_235539 --replay-delay 2.5
```

עם צ'אט שמופיע קצת לפני הפעולה:

```powershell
.\play_ai_auto.bat --watch-replay --replay-session session_20260515_235539 --replay-delay 2.5 --replay-text-lead 0.5
```

## ניתוח משחק מוקלט - ANALYSE_GAME

כשרוצים לא רק לצפות בריפליי אלא להבין את קבלת ההחלטות של השחקנים:

```powershell
.\ANALYSE_GAME.bat --session session_20260516_002753
```

אפשר גם להעביר אופציות ריפליי רגילות:

```powershell
.\ANALYSE_GAME.bat --session session_20260516_002753 --replay-delay 1.5 --replay-text-lead 0.5
```

זה פותח את ה-Unified View במצב replay ונותן כפתור `Analyse` ליד בקרי הריפליי. עוצרים על נקודה בסליידר ולוחצים `Analyse` כדי לפתוח פופאפ Decision Trace.

בפופאפ רואים את המציאות כפי שהמודל ראה אותה באותו רגע, מתוך קובץ הפרומפט המקורי:

- `task_context`: מה קרה ומה התבקש ממנו לעשות.
- `game_state`: מצב המשחק הדחוס/מסונן שנכנס לפרומפט.
- `memory`: הזיכרון שהיה לו לפני ההחלטה.
- `Compacted long-term memory`: סיכום זיכרון מקומפקט אם היה `prompt.memory.long_term_summary`.
- `Recent notes`: הזיכרונות האחרונים שנשארו אחרי compaction.
- `social_context`: צ'אט, סיכומי הודעות, וטריידים שהיו זמינים לו.
- `Compacted message summaries`: סיכומי הודעות אם היו `prompt.social_context.last_summaries` או `recent_summaries`.
- `Tool calls`: איזה כלים הפעיל, למה, מה הקלט, ומה הפלט.
- `Internal thinking`: הנימוק הפרטי שהמודל החזיר.
- `note_to_self`: מה נשמר לזיכרון הבא.
- `say_outloud`: מה נאמר לשחקנים.
- `Action`: הפעולה שנבחרה.
- `Engine Result`: האם הפעולה הצליחה ומה המנוע רשם.

חשוב: `ANALYSE_GAME` לא עושה קריאות LLM חדשות. הוא קורא את קבצי הסשן המוקלטים:

```text
<Player>\prompts\prompt_N.json
<Player>\responses\response_N.json
<Player>\responses\intermediate\response_N_iterM.json
tool_executions.json
chat_history.json
agent_memories.json
```

לגבי cache:

- מהלכי המשחק עצמם משוחזרים מה-responses המוקלטים, לא מ-cache של לוח.
- אם יש קול/TTS, מצב watch/analyse משתמש כברירת מחדל ב-`tts_cache` של הסשן שמנתחים:

```text
examples\ai_testing\my_games\<session>\tts_cache
```

- אם הקלטה קולית קיימת שם, היא תנוגן מה-cache.
- אם אין קובץ TTS קיים, ייתכן שהמערכת תכין/תייצר אודיו לפי הגדרות ה-TTS, אבל לא תשלח את המשחק ל-LLM מחדש.

## חיפוש תקלות בסשן

```powershell
Select-String -Path examples\ai_testing\my_games\session_20260515_235539\**\*.json,examples\ai_testing\my_games\session_20260515_235539\llm_communication.log `
  -Pattern "ACTION_FAILED|Invalid|failed|Error|Traceback|not allowed" `
  -CaseSensitive:$false
```

## כלל אצבע לדיבוג

1. מריצים משחק רגיל.
2. כשיש באג, עוצרים.
3. מוצאים את `Player:N` שבו הבאג קרה.
4. מתקנים קוד.
5. מריצים עם `--replay-stop-before Player:N`.
6. אם תקין, ממשיכים את הסשן החדש ומעדכנים backlog.

למידע מפורט יותר על replay, ראה גם `REPLAY_GUIDE.md`.
