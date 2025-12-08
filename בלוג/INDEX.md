# מעקב פוסטים / Blog Index

קובץ זה מרכז את הפוסטים שפורסמו ואת עיקרי התוכן שלהם.

## רשימת פוסטים

1. `פוסט בלוג 1 - מבוא לפרויקט.md`
   - נושא: רקע, מבנה וארכיטקטורה של PyCatan
   - נקודות עיקריות:
     - שימוש בלוגיקת המשחק הקיימת (`Game`) והוספת שכבת סימולציה
     - `GameManager` לניהול תורות וזרימת המשחק
     - מודל `User` מופשט עם `HumanUser` ו-`AIUser`
     - מודל `Actions` לאחידות בבקשת/ביצוע פעולות ותוצאות
     - Visualizations להצגת מצב המשחק בזמן אמת (Console/Web)
     - תכנון מודול תקשורת בין סוכני AI בעתיד
     - קטעי קוד לדוגמה ל-Actions, Users, GameManager
   - דיאגרמות: Mermaid המתארת את הקשרים בין הרכיבים
   - מצב: פורסם

2. `פוסט בלוג 2 - ניהול פרויקט עם Vibe Coding.md`
   - נושא: שיטות עבודה וניהול פרויקט עם GitHub Copilot
   - נקודות עיקריות:
     - Copilot Instructions כמערכת ניהול פרויקט (ARCHITECTURE.md, BUILD_PLAN.md)
     - מתודולוגיית 5-Step Vibe Coding: Define → Design → Develop → Test → Document
     - Living Documentation - מסמכים חיים שמתעדכנים לאורך הפרויקט
     - שיטות עבודה: Iterative Documentation, TDD עם AI, Checkpoint Pattern
     - יחס 70/30: AI כותב קוד, אנושי מחליט על ארכיטכטורה
     - לקחים: מה עבד (מהירות, איכות) ומה לא (over-engineering, context loss)
     - סטטיסטיקות: 1,200+ שורות קוד, 110+ בדיקות, 3 שלבים מושלמים
     - AI כמורה ולא כתחליף - חשיבות התקשורת והבנת הקוד
   - מצב: פורסם

3. `פוסט בלוג 3 - קואורדינטות וקסם שחור.md`
   - נושא: פתרון אתגר תרגום בין מערכת קואורדינטות פנימית לממשק משתמש
   - נקודות עיקריות:
     - הפער בין מערכת `[row, index]` הפנימית של PyCatan לאינטואיציה של המשתמש
     - שתי מערכות מקבילות: 54 צמתים ב-6 שורות, 19 משושים ב-5 שורות
     - התהליך: מחישוב מתמטי → קובץ סטטי → כלי מיפוי אינטראקטיבי
     - בניית Manual Mapping Tool עם ויזואליזציה ווב
     - תהליך מיפוי ידני: הדפסת לוגיקה + לחיצה על מסך = מיפוי מושלם
     - יצירת `PointMapper` class לתרגום דו-כיווני
     - המעבר מ-`board.points[2][5]` ל-`point_id=23` - ממשק אנושי
     - לקחים: פשטות > מורכבות, ויזואליזציה = מפתח, כלי פיתוח = חלק מהפרויקט
   - דוגמאות קוד: Point class, DefaultBoard, PointMapper, Manual Mapping Tool
   - מצב: פורסם

4. `פוסט בלוג 4 - Status Based Error Handling.md`
   - נושא: גישה אלטרנטיבית לטיפול בשגיאות - Status Codes במקום Exceptions
   - נקודות עיקריות:
     - מה זה Status-Based Error Handling ואיך זה שונה מ-Exceptions
     - `Statuses` enum עם 14 קודי סטטוס (ALL_GOOD, ERR_CARDS, ERR_BLOCKED, וכו')
     - למה PyCatan בחרה בגישה הזו: Game Logic = Decisions, AI feedback, Performance, Predictable Flow
     - דוגמאות מעשיות: build_settlement, build_road, upgrade_to_city
     - היתרונות: קוד קריא, testing פשוט, control flow ברור, מושלם ל-AI
     - החסרונות: קל לשכוח לבדוק, חסר context, verbosity, אין propagation אוטומטי
     - אסטרטגיות עבודה: wrapper functions, תמיד בודקים, logging, type hints
     - השוואה מפורטת: Exceptions vs Statuses - מתי להשתמש בכל אחת
     - גישה היברידית: statuses למשחק, exceptions לבאגים
   - דוגמאות קוד: Statuses enum, Player.build_settlement, GameManager.execute_build_settlement, Testing
   - מצב: פורסם

---

## Next Posts (Planned)
- חוקי תורות: Dice, Robber, discard, שלבי תור
- מערכת מסחר: הצעות, אישורים, counter-offers, בנק/נמלים
- AI Agents: תקשורת, קבלת החלטות, אסטרטגיות
- Web Visualization: חוויית משתמש, SSE, אינטראקטיביות
