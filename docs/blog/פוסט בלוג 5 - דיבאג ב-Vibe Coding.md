# פוסט בלוג 5: דיבאג ב-Vibe Coding - כשהסוכן צריך לראות מה המחשב רואה

*תאריך: 8 בדצמבר 2025*

## פתיחה: הפואנטה לפני הכל

אני בונה סביבה שבה סוכנים מבוססי LLM יכולים לשחק קטאן, ובדרך גיליתי משהו חשוב על העתיד של vibe coding:

**כדי ש-vibe coding יהפוך באמת נגיש - לא רק למתכנתים או לאנשים סופר-טכניים - הסוכנים שאנחנו כותבים איתם חייבים לעשות קפיצת מדרגה משמעותית בכל מה שקשור לדיבאג.**

לא מדובר רק ביכולת לקרוא לוגים או לבדוק שגיאות קומפילציה. מדובר באיך הסוכן "מסתכל" על בעיות, ואיך הוא מציע לפתור אותן יחד עם המשתמש.

בואו נראה למה אני מתכוון דרך דוגמה אמיתית מהפרויקט.

---

## הבעיה: שלוש מערכות קואורדינטות שלא מדברות

### מה יש בלוח קטאן?

בלוח קטאן יש בגדול שתי ישויות בסיסיות:
- **19 משושים (tiles)** - שם יושבים המספרים והמשאבים
- **54 נקודות (vertices/points)** - הקודקודים שבהם אפשר לבנות התנחלויות

```
         🔵━━━🔵━━━🔵
        ╱ ⬡ ╲ ╱ ⬡ ╲ ╱ ⬡ ╲
       🔵━━━🔵━━━🔵━━━🔵
      ╱ ⬡ ╲ ╱ ⬡ ╲ ╱ ⬡ ╲ ╱ ⬡ ╲
     🔵━━━🔵━━━🔵━━━🔵━━━🔵
        ╲ ⬡ ╱ ╲ ⬡ ╱ ╲ ⬡ ╱ ╲ ⬡ ╱
         🔵━━━🔵━━━🔵━━━🔵
            ╲ ⬡ ╱ ╲ ⬡ ╱ ╲ ⬡ ╱
             🔵━━━🔵━━━🔵
             
       🔵 = נקודה (vertex) - מקום לבניית התנחלות
       ⬡ = משושה (tile) - מייצר משאבים
```

כל ישות מוחזקת במבנה נתונים עצמאי, כך שלכל אחת יש קואורדינטות ומזהה ייחודי:

```python
# כך מנוע המשחק רואה משושה
class Tile:
    def __init__(self, type, token_num, position, points):
        self.position = position  # [row, index] - למשל [0, 0]
        self.points = points      # רשימת הנקודות שמקיפות אותו
```

```python
# כך מנוע המשחק רואה נקודה
class Point:
    def __init__(self, tiles, position):
        self.position = position  # [row, index] - למשל [2, 5]
        self.tiles = tiles        # המשושים שהנקודה נוגעת בהם
```

### הסיבוך האמיתי: הויזואליזציה

הבעיה מתחילה כשרוצים **להציג את זה על המסך**.

יצרתי תצוגה ווב עם קלוד - שרת Flask מצד אחד, ו-JavaScript שמצייר את הלוח מצד שני:

```javascript
// board.js - ציור המשושים
hexToPixel(q, r) {
    // המרה ממערכת axial לפיקסלים
    const x = this.hexRadius * (3/2 * q);
    const y = this.hexRadius * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r);
    return {
        x: this.centerX + x,
        y: this.centerY + y
    };
}

getHexagonVertices(q, r) {
    const center = this.hexToPixel(q, r);
    const vertices = [];
    
    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i;  // כל 60 מעלות
        const x = center.x + this.hexRadius * Math.cos(angle);
        const y = center.y + this.hexRadius * Math.sin(angle);
        vertices.push({x: x, y: y});
    }
    
    return vertices;
}
```

עכשיו יש לי **שלוש מערכות קואורדינטות**:

| מערכת | שימוש | דוגמה |
|--------|-------|-------|
| **Game Logic** | מנוע המשחק ב-Python | `[row, index]` = `[2, 5]` |
| **Axial Coordinates** | ציור משושים ב-JS | `(q, r)` = `(-1, 2)` |
| **Pixel Coordinates** | מיקום על המסך | `(x, y)` = `(342, 267)` |

**והן צריכות להיות מסונכרנות!**

כשמשתמש לוחץ על נקודה במסך, אני צריך:
1. לתפוס את הפיקסלים `(342, 267)`
2. לתרגם למערכת axial 
3. לתרגם לקואורדינטות של המשחק `[2, 5]`
4. להעביר לפייתון לביצוע הפעולה

ואם יש טעות באחד השלבים? **הלוח נשבר.**

---

## כשום דבר לא עובד

ניסיתי הכל:

### ניסיון 1: לתת לקלוד לחשב
```
אני: "תחשב את התרגום בין מערכות הקואורדינטות"
קלוד: *כותב פונקציה מתמטית מורכבת*
תוצאה: הנקודות מוצגות, אבל לא במקום הנכון
```

### ניסיון 2: לפשט את המבנה
```
אני: "בוא ננסה גישה אחרת, נשתמש במזהים פשוטים 1-54"
קלוד: *בונה מערכת מיפוי*
תוצאה: המיפוי לא תואם את מה שעל המסך
```

### ניסיון 3: לבנות מחדש בנפרד
```
אני: "בוא נבנה רק את הלוח בפרויקט נפרד ונחבר חזרה"
קלוד: *בונה פרויקט קטן*
תוצאה: עובד בנפרד, נשבר בחיבור
```

### ניסיון 4: להחליף מודלים
```
קלוד -> Gemini -> GPT-4 -> חזרה לקלוד
תוצאה: כולם נתקעים באותו מקום
```

**התסמינים היו תמיד זהים:**
- או שהלוח עצמו נשבר ויזואלית
- או שהתוצאה לא הייתה הגיונית - על המסך רואים שתי נקודות צמודות, אבל מנוע המשחק טוען שהן רחוקות ולכן אי אפשר לבנות דרך

נשארתי עם זה קצת. שקלתי לכתוב את זה מחדש בעצמי, אבל זה סופר מורכב.

**ואז בא לי רעיון.**

---

## התובנה: "מה אם הסוכן יראה לי איך הוא רואה את המשחק?"

במקום לבקש מהסוכן לתקן את הבעיה, ביקשתי ממנו **לחשוף את מה שהוא "חושב"**.

### שלב 1: הדפסת הלוגיקה הפנימית

יצרנו סקריפט קטן שמדפיס בדיוק מה המשחק "רואה":

```python
# print_game_logic.py
from pycatan import Game

def print_game_expectations():
    game = Game()
    board = game.board
    
    print("GAME LOGIC EXPECTATIONS")
    print("="*60)
    print("Format: Hex [Row, Col] -> Connected Point Coordinates")
    print("-"*60)

    for r, row in enumerate(board.tiles):
        for i, tile in enumerate(row):
            point_coords = [list(p.position) for p in tile.points]
            point_coords.sort()
            print(f"Hex [{r}, {i}] connects to Points: {point_coords}")

if __name__ == "__main__":
    print_game_expectations()
```

הפלט נראה בערך ככה:

```
Hex [0, 0] connects to Points: [[0,0], [0,1], [1,0], [1,1], [1,2], [2,1]]
Hex [0, 1] connects to Points: [[0,1], [0,2], [1,2], [1,3], [1,4], [2,3]]
Hex [0, 2] connects to Points: [[0,2], [0,3], [1,4], [1,5], [1,6], [2,5]]
...
```

עכשיו אני רואה **מה המחשב חושב** - איזה משושה מחובר לאילו נקודות.

### שלב 2: כלי מיפוי אינטראקטיבי

ביקשתי מקלוד ליצור ממשק וובי פשוט לדיבאג:

```html
<!-- manual_mapping.html -->
<div class="mapping-controls">
    <div class="mode-switch">
        <label><input type="radio" name="mode" value="hex" checked> 
            Map Hexes (1-19)</label>
        <label><input type="radio" name="mode" value="point"> 
            Map Points (1-54)</label>
    </div>
    
    <div class="current-target">
        Click to assign ID: <span id="nextId">1</span>
        <div>
            Target Game Coords: 
            <span id="coordsHint">Row 0, Col 0</span>
        </div>
    </div>

    <button onclick="exportMapping()">Export Mapping</button>
    <textarea id="output" placeholder="Mapping will appear here..."></textarea>
</div>
```

הרעיון פשוט:
1. רואה על המסך "Target: Row 0, Col 0"
2. מסתכל על ההדפסות - "זה הצומת השמאלי-עליון"
3. לוחץ על הצומת המתאים בלוח הויזואלי
4. הצומת הופך לירוק ומקבל מספר
5. עובר לצומת הבא

```javascript
// manual_mapping.js
handlePointClick(element) {
    const visualId = parseInt(element.getAttribute('data-vertex-id'));
    const vertex = this.vertices.find(v => v.id === visualId);

    // שמירת המיפוי
    this.mapping.points[this.currentId] = {
        x: vertex.x,
        y: vertex.y
    };

    // פידבק ויזואלי - הצומת הופך ירוק
    element.classList.add('mapped');
    
    // מעבר לצומת הבא
    this.currentId++;
    this.updateUI();
}
```

### שלב 3: התהליך בפועל

```
Target Game Coords: Row 0, Col 0
Click to assign ID: 1

[לוחץ על הצומת השמאלי העליון]

✓ Mapped Point 1 -> (x: 287, y: 178)

Target Game Coords: Row 0, Col 1  
Click to assign ID: 2

[לוחץ על הצומת הבא מימין]

✓ Mapped Point 2 -> (x: 332, y: 152)

...חוזר 52 פעמים נוספות...
```

### שלב 4: ייצוא המיפוי

אחרי שסיימתי את כל 54 הנקודות, לחצתי "Export":

```json
{
  "points": {
    "1": {"x": 287, "y": 178},
    "2": {"x": 332, "y": 152},
    "3": {"x": 377, "y": 178},
    ...
    "54": {"x": 512, "y": 422}
  }
}
```

**וזה עבד.**

זה לקח לי בערך חצי שעה. היה צריך רגע להבין מה זה כל משושה ואיזה נקודות מחוברות אליו, אבל ברגע שהדפוס ההגיוני התחיל להיווצר וראיתי את המיפוי **בעיניים** באופן ידני - זה פשוט רץ.

---

## הקוד שנוצר: PointMapper

המיפוי הידני הפך לקלאס `PointMapper` שמשמש את כל המערכת:

```python
# point_mapping.py
class PointMapper:
    """
    Manages mapping between point IDs and coordinates.
    
    Point IDs are simple numbers (1, 2, 3...) that users can easily reference.
    Coordinates are [row, index] pairs used internally by the game engine.
    """
    
    def __init__(self):
        self.point_to_coords: Dict[int, List[int]] = {}
        self.coords_to_point: Dict[str, int] = {}
        self._load_default_mapping()
    
    def _load_default_mapping(self):
        """Load the default Catan board point mapping."""
        # Standard Catan board layout - 54 intersection points
        default_mapping = [
            # Top row (7 points)
            [0, 0], [0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6],
            # Second row (9 points) 
            [1, 0], [1, 1], [1, 2], [1, 3], [1, 4], [1, 5], [1, 6], [1, 7], [1, 8],
            # ... ממשיך עד 54 נקודות
        ]
        
        for point_id, coords in enumerate(default_mapping, 1):
            self.point_to_coords[point_id] = coords
            self.coords_to_point[f"{coords[0]},{coords[1]}"] = point_id
    
    def point_to_coordinate(self, point_id: int) -> Optional[List[int]]:
        """Convert point ID to coordinates."""
        return self.point_to_coords.get(point_id)
    
    def coordinate_to_point(self, row: int, index: int) -> Optional[int]:
        """Convert coordinates to point ID."""
        return self.coords_to_point.get(f"{row},{index}")
```

עכשיו במקום:
```python
# לפני - צריך לדעת קואורדינטות פנימיות
game.add_settlement(player=0, point=board.points[2][5])
# מה זה [2][5]?? איפה זה על הלוח??
```

יש:
```python
# אחרי - מספר פשוט
point_id = 23  # הצומת שאני רואה על המסך
coords = mapper.point_to_coordinate(point_id)  # מחזיר [2, 5]
game.add_settlement(player=0, point=board.points[coords[0]][coords[1]])
```

---

## המחשבה הגדולה: מה זה אומר על עתיד ה-Vibe Coding

### המצב היום

אנחנו נמצאים בנקודה ש-vibe coding מרגיש לפעמים כמו לדבר עם הסוכן בטלפון:

- אם הסוכן במוד נחמד, יש סיכוי לדיבאג אמיתי
- אם אתם מספיק טכניים, אפשר לכוון אותו
- לפעמים יש לוגים ובדיקה שלב-שלב כחלק מהשיחה

**אבל אני מדבר על משהו מעבר לזה.**

### מה חסר?

סוכן טוב צריך להתחיל "לחשוב" ולהניח שהתוצר שלו הוא **כנראה לא אופטימלי**. במקום להמשיך לנסות לתקן את הקוד, הוא צריך:

1. **לזהות שהוא תקוע** - לא רק להמשיך לנסות וריאציות על אותו פתרון
2. **לחפש דרכים אחרות לאבחן** - דרך חוויית המשתמש, לא רק דרך הקוד
3. **להציע כלי עזר** - אולי אפילו לעצור את הפיתוח ולבנות כלי דיבאג

### הדוגמה מהפרויקט

במקרה שלי, הפתרון לא היה "לתקן את הקוד". הפתרון היה:

> **"בוא נבנה כלי שיעזור לי ולך לראות את אותו הדבר"**

הסוכן לא יכול היה לפתור את בעיית המיפוי לבד. אבל הוא **כן יכול** לבנות כלי שיעזור **לנו יחד** לפתור אותה:

```
┌─────────────────────────────────────────────────────────────┐
│  מצב נוכחי: סוכן מנסה לפתור לבד                            │
│                                                             │
│  User ──"תתקן את הבאג"──> Agent ──tries──> fails ──> tries  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  מצב רצוי: סוכן בונה גשר לשיתוף פעולה                      │
│                                                             │
│  User <──"בוא נראה יחד"──> Agent                           │
│    │                          │                             │
│    │    ┌────────────────┐    │                             │
│    └───>│  Debug Tool    │<───┘                             │
│         │  (visual)      │                                  │
│         └────────────────┘                                  │
│                │                                            │
│                v                                            │
│         Problem Solved                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### למה זה חשוב לנגישות?

כדי שבניית מוצרים תפסיק להיות משאב ששייך רק למי שטכני, הסוכנים צריכים ללמוד להציע עזרה בצורות שלא בהכרח באות מאיך שמתכנת רואה את הדברים:

| גישה של מתכנת | גישה של משתמש |
|---------------|---------------|
| "תבדוק את הלוגים" | "תראה לי מה אתה רואה" |
| "יש exception בשורה 47" | "למה הכפתור לא עובד?" |
| "הקואורדינטות לא נכונות" | "זה לא נראה כמו שצריך" |

סוכן שמבין את **שני** הצדדים יכול לגשר ביניהם.

---

## סיכום: כלי דיבאג כחלק מהפתרון

הלקח מהניסיון הזה:

> **לפעמים הפתרון לבעיה הוא לא לתקן את הקוד - אלא לבנות כלי שיעזור לנו להבין את הבעיה יחד.**

בפרויקט PyCatan, הכלי הזה היה `manual_mapping.html` - ממשק פשוט שהראה לי **מה המחשב רואה** ואפשר לי **להגיד לו מה נכון**.

זה לקח חצי שעה של עבודה ידנית, אבל:
- פתר בעיה שסוכנים לא הצליחו לפתור שבועות
- יצר artifact שימושי לפרויקט (קובץ המיפוי)
- לימד אותי משהו על איך לעבוד עם סוכנים

**ואולי הכי חשוב:** זה הראה לי שהעתיד של vibe coding הוא לא רק סוכנים שכותבים קוד טוב יותר - אלא סוכנים שיודעים **מתי לעצור ולבנות גשר** בין מה שהם רואים לבין מה שאנחנו רואים.

---

## קישורים

- [הקוד של Manual Mapping Tool](../pycatan/static/js/manual_mapping.js)
- [הקוד של PointMapper](../pycatan/point_mapping.py)
- [פוסט קודם על מערכת הקואורדינטות](פוסט%20בלוג%203%20-%20קואורדינטות%20וקסם%20שחור.md)
