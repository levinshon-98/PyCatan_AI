# פוסט בלוג 4: Status-Based Error Handling - כשהקוד מדבר במקום לצעוק

*תאריך: 6 בדצמבר 2025*

## פתיחה: הפתעה בקוד הקיים

כשהתחלתי לעבוד עם הספרייה המקורית של PyCatan, אחד הדברים הראשונים שהפתיעו אותי היה איך המערכת מטפלת בשגיאות. לא היו `try/except` blocks, לא היו exceptions שעפות באוויר, ובמקום זאת - כל פונקציה החזירה ערך מסוג `Statuses`.

```python
# דוגמה טיפוסית מהקוד
result = game.add_settlement(player=0, point=board.points[0][0])
if result == Statuses.ALL_GOOD:
    print("Settlement built successfully!")
elif result == Statuses.ERR_CARDS:
    print("Not enough cards!")
elif result == Statuses.ERR_BLOCKED:
    print("Location is blocked!")
```

בהתחלה חשבתי: "זה קצת מוזר, למה לא סתם לזרוק exception?" אבל ככל שעבדתי עם המערכת הזו, גיליתי שיש בה הגיון עמוק - ושיש גם מחיר.

הפוסט הזה הוא סיפור על גישה שונה לטיפול בשגיאות, ולמה לפעמים "לא לזרוק" זה יותר טוב מ"לזרוק".

## מה זה Status-Based Error Handling?

### הרעיון הבסיסי

במקום שפונקציה תזרק exception כשמשהו לא עובד, היא מחזירה קוד סטטוס שמתאר מה קרה.

```python
# גישה מסורתית עם Exceptions
def add_settlement(player, point):
    if not has_enough_cards(player):
        raise NotEnoughCardsError("Player needs Wood, Brick, Sheep, Wheat")
    if location_is_blocked(point):
        raise LocationBlockedError("Too close to another settlement")
    # ... build the settlement
    return settlement

# גישה של PyCatan עם Statuses
def add_settlement(player, point):
    if not has_enough_cards(player):
        return Statuses.ERR_CARDS
    if location_is_blocked(point):
        return Statuses.ERR_BLOCKED
    # ... build the settlement
    return Statuses.ALL_GOOD
```

### ה-Statuses Enum

PyCatan מגדירה enum פשוט עם כל סוגי הסטטוסים האפשריים:

```python
# pycatan/statuses.py
class Statuses:
    # Success
    ALL_GOOD = 2
    
    # Error codes
    ERR_CARDS = 3          # Not enough cards
    ERR_BLOCKED = 4        # Building is blocking
    ERR_BAD_POINT = 5      # Point not on board
    ERR_NOT_CON = 6        # Road points not connected
    ERR_ISOLATED = 7       # Building not connected to player's network
    ERR_HARBOR = 8         # Invalid harbor usage
    ERR_NOT_EXIST = 9      # Building doesn't exist
    ERR_BAD_OWNER = 10     # Wrong owner
    ERR_UPGRADE_CITY = 11  # Can't upgrade city
    ERR_DECK = 12          # Not enough cards in deck
    ERR_INPUT = 13         # Invalid input
    ERR_TEST = 14          # Testing error
```

**שימו לב:** הערכים מתחילים מ-2 ולא מ-0! למה? כי 0 ו-1 שווים ל-`False` ו-`True` בפייתון, והספרייה רצתה להימנע מבלבול.

## למה PyCatan בחרה בגישה הזו?

### סיבה 1: Game Logic = Decision Making, Not Crashing

משחקים הם מערכות שמקבלות החלטות. שחקן מנסה לבצע פעולה, והמשחק אומר "כן" או "לא" - ואם לא, אז למה.

```python
# במשחק אמיתי:
# "אני רוצה לבנות התנחלות כאן"
result = game.add_settlement(player=0, point=target_point)

if result == Statuses.ERR_CARDS:
    # "אין לך מספיק קלפים"
    show_message("You need: Wood, Brick, Sheep, Wheat")
    
elif result == Statuses.ERR_BLOCKED:
    # "המיקום הזה תפוס"
    show_message("Too close to another settlement")
    
elif result == Statuses.ALL_GOOD:
    # "בנוי!"
    show_message("Settlement built!")
```

זה לא באג - זה חלק מחוקי המשחק. Exception מרמז על "משהו השתבש", אבל כאן שום דבר לא השתבש - המשחק פשוט אומר "לא, אתה לא יכול לעשות את זה".

### סיבה 2: AI Players Need to Know WHY

כשבונים AI player, הוא צריך ללמוד מהטעויות שלו:

```python
# AI מנסה אסטרטגיה
for possible_location in board.get_all_points():
    result = game.add_settlement(ai_player, possible_location)
    
    if result == Statuses.ERR_CARDS:
        # "אה, אין לי קלפים. אולי כדאי לסחור קודם?"
        ai_strategy.need_more_resources()
        
    elif result == Statuses.ERR_BLOCKED:
        # "המיקום הזה לא טוב. בוא ננסה אחר."
        continue
        
    elif result == Statuses.ERR_ISOLATED:
        # "אני לא מחובר לשם. צריך לבנות כביש קודם."
        ai_strategy.build_roads_first()
        
    elif result == Statuses.ALL_GOOD:
        # "מצוין! עבד!"
        break
```

עם exceptions, ה-AI היה צריך לתפוס כל exception בנפרד ולבדוק את הסוג שלו. עם statuses, זה פשוט if/elif chain נקי.

### סיבה 3: Performance במשחקים

Exceptions הן יקרות מבחינת ביצועים. זריקה ותפיסה של exception דורשת:
- בניית stack trace
- unwinding של ה-call stack
- טיפול ב-cleanup code

במשחק שעושה מאות בדיקות לגליטימיות של מהלכים (במיוחד עם AI), זה יכול להיות bottleneck.

```python
# AI בודק 100 מהלכים אפשריים לתור
for move in possible_moves:
    status = validate_move(move)
    if status == Statuses.ALL_GOOD:
        valid_moves.append(move)

# אין overhead של exceptions - פשוט השוואת מספרים
```

### סיבה 4: Predictable Control Flow

עם exceptions, flow control הוא פחות צפוי:

```python
# עם exceptions - איפה הקוד עשוי לקפוץ?
try:
    settlement = game.add_settlement(player, point)
    road = game.add_road(player, point, other_point)
    city = game.upgrade_to_city(player, settlement)
except NotEnoughCardsError:
    # זה יכול לבוא מכל אחת מהשלוש!
    handle_error()
```

```python
# עם statuses - ברור בדיוק מתי ואיפה
status = game.add_settlement(player, point)
if status != Statuses.ALL_GOOD:
    handle_settlement_error(status)
    return

status = game.add_road(player, point, other_point)
if status != Statuses.ALL_GOOD:
    handle_road_error(status)
    return

# Control flow ליניארי וברור
```

## איך זה נראה בפועל?

### דוגמה 1: בניית התנחלות

בואו נעקוב אחרי הקוד של `build_settlement`:

```python
# pycatan/player.py
def build_settlement(self, point, is_starting=False):
    # 1. בדיקה: האם המיקום חוקי?
    if not is_starting:
        # שלא בתור פתיחה - צריך להיות מחובר לכביש
        if not self.is_connected_to_point(point):
            return Statuses.ERR_ISOLATED  # ← החזרת סטטוס!
    
    # 2. בדיקה: יש מישהו קרוב מדי?
    for adjacent_point in point.connected_points:
        if adjacent_point.building != None:
            return Statuses.ERR_BLOCKED  # ← עוד סטטוס!
    
    # 3. בדיקה: יש קלפים?
    if not is_starting:
        cards_needed = [ResCard.Wood, ResCard.Brick, ResCard.Sheep, ResCard.Wheat]
        if not self.has_cards(cards_needed):
            return Statuses.ERR_CARDS  # ← ועוד!
        
        self.remove_cards(cards_needed)
    
    # 4. הכל טוב? בונים!
    building = Building(owner=self.num, type=Building.BUILDING_SETTLEMENT, point=point)
    point.building = building
    
    return Statuses.ALL_GOOD  # ← הצלחה!
```

שימו לב לזרימה:
- כל בדיקה = החזרת סטטוס מיידי
- אין nesting עמוק
- ברור מאוד מה התנאים להצלחה

### דוגמה 2: שימוש בקוד היוצא

כשהשתמשתי במערכת הזו ב-`GameManager`, זה היה ממש פשוט:

```python
# pycatan/game_manager.py
def execute_build_settlement(self, action):
    """Execute a build settlement action."""
    coords = self.point_mapper.point_to_coordinate(action.point_id)
    point = self.game.board.points[coords[0]][coords[1]]
    
    # קריאה לפונקציה
    status = self.game.add_settlement(
        player=action.player,
        point=point,
        is_starting=self.in_setup_phase
    )
    
    # טיפול בכל סטטוס אפשרי
    if status == Statuses.ALL_GOOD:
        message = f"Settlement built at point {action.point_id}!"
        
    elif status == Statuses.ERR_CARDS:
        message = "Not enough resources! Need: Wood, Brick, Sheep, Wheat"
        
    elif status == Statuses.ERR_BLOCKED:
        message = "Can't build here - too close to another settlement"
        
    elif status == Statuses.ERR_ISOLATED:
        message = "Must build next to your roads or settlements"
        
    else:
        message = f"Cannot build settlement: {status}"
    
    # עדכון visualizations
    self.notify_action(action, status, message)
    
    return status
```

זה מאוד קריא וברור. כל מקרה מטופל במפורש.

### דוגמה 3: בדיקות (Testing)

אחד היתרונות הגדולים - בדיקות פשוטות מאוד:

```python
# tests/test_game.py
def test_adding_starting_settlements(self):
    g = Game()
    
    # בדיקה 1: התנחלות ראשונה צריכה להצליח
    res = g.add_settlement(0, g.board.points[0][0], True)
    assert res == Statuses.ALL_GOOD  # ← פשוט!
    
    # בדיקה 2: התנחלות קרובה מדי צריכה להיכשל
    res = g.add_settlement(1, g.board.points[0][1], True)
    assert res == Statuses.ERR_BLOCKED  # ← ברור למה!
    
    # בדיקה 3: התנחלות רחוקה מספיק צריכה להצליח
    res = g.add_settlement(2, g.board.points[0][2], True)
    assert res == Statuses.ALL_GOOD
```

אין צורך ב-`assertRaises` או בלוגיקה מסובכת של תפיסת exceptions. פשוט השוואת ערכים.

## היתרונות: מה עובד מעולה

### ✅ 1. קוד קריא וברור

```python
# כל ה-error paths ברורים
if not self.has_cards(needed_cards):
    return Statuses.ERR_CARDS

if location_is_blocked:
    return Statuses.ERR_BLOCKED

# ... more checks
return Statuses.ALL_GOOD
```

אתה רואה בדיוק מה הבדיקות ומה הסטטוס לכל מקרה.

### ✅ 2. Exhaustive Handling

אפשר בקלות לוודא שטיפלת בכל המקרים:

```python
# Python 3.10+ - match statement
match status:
    case Statuses.ALL_GOOD:
        handle_success()
    case Statuses.ERR_CARDS:
        handle_no_cards()
    case Statuses.ERR_BLOCKED:
        handle_blocked()
    case _:
        handle_unknown()  # כל מה ששכחנו
```

### ✅ 3. Testing פשוט

בדיקות הופכות לפשוטות ומדויקות:

```python
# בדיוק יודעים מה לצפות
assert result == Statuses.ERR_CARDS
assert result != Statuses.ALL_GOOD
```

### ✅ 4. אין הפתעות

הפונקציה לא תזרוק exception לא צפוי. אתה תמיד יודע שתקבל Statuses בחזרה.

```python
# תמיד אפשר לכתוב:
status = game.do_something()
if status == Statuses.ALL_GOOD:
    # continue
```

### ✅ 5. מושלם למשחקים ו-AI

כמו שראינו - AI יכול לנסות מהלכים ולקבל פידבק ברור:

```python
# AI learning loop
for move in all_possible_moves:
    status = try_move(move)
    learn_from_status(status)  # למד מהתוצאה
```

## החסרונות: מה פחות טוב

עכשיו הצד השני - מה **לא** עובד כל כך טוב עם הגישה הזו?

### ❌ 1. קל לשכוח לבדוק

זו הבעיה הכי גדולה. אין forcing function:

```python
# אפשר לשכוח לבדוק סטטוס!
game.add_settlement(player, point)  # ← מה אם נכשל?
game.add_road(player, point1, point2)  # ← ממשיכים בלי לבדוק

# עם exceptions - היית מאולץ לטפל
try:
    game.add_settlement(player, point)
except:
    # חייב לטפל!
```

פתרון שהשתמשתי בו:

```python
# תמיד שומרים ובודקים
status = game.add_settlement(player, point)
if status != Statuses.ALL_GOOD:
    self.handle_error(status)
    return  # עוצרים!

# רק אם הצלחנו - ממשיכים
status = game.add_road(player, point1, point2)
# ...
```

### ❌ 2. חוסר מידע מפורט

סטטוס הוא רק מספר. אין stack trace, אין הקשר:

```python
# מה קיבלנו?
status = Statuses.ERR_CARDS

# אבל... איזה קלפים חסרים? כמה? איפה?
# צריך לטפל בזה ידנית:
if status == Statuses.ERR_CARDS:
    needed = get_needed_cards()  # פונקציה נוספת
    missing = calculate_missing(player, needed)  # עוד לוגיקה
    show_error(f"Missing: {missing}")
```

עם exception:
```python
raise NotEnoughCardsError(
    f"Player {player} needs {needed} but has {player.cards}"
)
# כל המידע בתוך ה-exception
```

### ❌ 3. Verbosity - הרבה קוד חוזר

צריך if/elif blocks בכל מקום:

```python
# בכל פונקציה - אותו pattern
if status == Statuses.ALL_GOOD:
    # ...
elif status == Statuses.ERR_CARDS:
    # ...
elif status == Statuses.ERR_BLOCKED:
    # ...
elif status == Statuses.ERR_ISOLATED:
    # ...
# ... עוד 10 מקרים
```

אפשר לעטוף בפונקציה עזר:

```python
def handle_build_status(status, context):
    """Map status to user message."""
    messages = {
        Statuses.ALL_GOOD: "Success!",
        Statuses.ERR_CARDS: "Not enough resources",
        Statuses.ERR_BLOCKED: "Location blocked",
        # ...
    }
    return messages.get(status, "Unknown error")

# שימוש
message = handle_build_status(status, "settlement")
```

### ❌ 4. אין Propagation אוטומטי

עם exceptions, שגיאה "עולה" אוטומטית במעלה ה-call stack. עם statuses, צריך להעביר ידנית:

```python
# צריך להעביר את הסטטוס בכל שכבה
def high_level_action():
    status = mid_level_action()
    if status != Statuses.ALL_GOOD:
        return status  # ← העברה ידנית
    # ...
    return Statuses.ALL_GOOD

def mid_level_action():
    status = low_level_action()
    if status != Statuses.ALL_GOOD:
        return status  # ← שוב העברה
    # ...
    return Statuses.ALL_GOOD
```

עם exceptions - פשוט זורקים ולא תופסים, וזה עולה אוטומטית.

### ❌ 5. אי אפשר להחזיר גם ערך וגם סטטוס

לפעמים רוצים גם את התוצאה וגם את הסטטוס:

```python
# לא אלגנטי
def get_longest_road(player):
    # רוצים להחזיר גם את האורך וגם סטטוס
    # פתרון: tuple
    return (road_length, Statuses.ALL_GOOD)

# שימוש מסורבל
length, status = get_longest_road(player)
if status == Statuses.ALL_GOOD:
    print(f"Longest road: {length}")
```

פתרון שהשתמשתי - `ActionResult` class:

```python
@dataclass
class ActionResult:
    status: Statuses
    message: str
    data: Optional[Dict] = None

# שימוש
result = ActionResult(
    status=Statuses.ALL_GOOD,
    message="Settlement built!",
    data={"point_id": 15, "player": 0}
)
```

## איך עבדתי עם זה בפועל?

### אסטרטגיה 1: Wrapper Functions

יצרתי פונקציות עטיפה שממירות statuses להודעות:

```python
# pycatan/game_manager.py
def _status_to_message(self, status: Statuses, action_type: str) -> str:
    """Convert status code to human-readable message."""
    
    if status == Statuses.ALL_GOOD:
        return f"{action_type} completed successfully!"
    
    # Map של כל הסטטוסים
    error_messages = {
        Statuses.ERR_CARDS: "Not enough resource cards",
        Statuses.ERR_BLOCKED: "Location is blocked by another building",
        Statuses.ERR_ISOLATED: "Must connect to your existing roads/settlements",
        Statuses.ERR_NOT_CON: "Points are not adjacent",
        # ... all statuses
    }
    
    return error_messages.get(status, f"Error: {status}")
```

### אסטרטגיה 2: תמיד בודקים לפני המשך

כלל אצבע: **לעולם לא מתעלמים מ-status**

```python
# רע - מתעלמים
game.add_settlement(player, point)

# טוב - בודקים
status = game.add_settlement(player, point)
if status != Statuses.ALL_GOOD:
    return handle_error(status)

# או - בודקים והמשך
status = game.add_settlement(player, point)
if status == Statuses.ALL_GOOD:
    # רק אם הצלחנו - ממשיכים לשלב הבא
    next_step()
```

### אסטרטגיה 3: Logging מפורט

מכיוון שאין stack traces, הוספתי logging ידני:

```python
import logging

status = game.add_settlement(player, point)
if status != Statuses.ALL_GOOD:
    logging.error(
        f"Failed to build settlement: "
        f"player={player}, point={point.position}, "
        f"status={status}"
    )
    return status
```

### אסטרטגיה 4: Type Hints לבטיחות

Python 3.5+ - type hints עוזרים:

```python
from typing import Union
from pycatan.statuses import Statuses

def build_settlement(self, player: int, point: Point) -> Statuses:
    """Build a settlement. Returns status code."""
    # ...
    return Statuses.ALL_GOOD

# עכשיו ה-IDE יזכיר לך לבדוק את הסטטוס!
```

## השוואה: Exceptions vs Statuses

בואו נראה את אותו תרחיש בשתי גישות:

### תרחיש: בניית עיר

```python
# ===== גישה 1: Exceptions =====
class NotEnoughCardsError(Exception): pass
class NoSettlementError(Exception): pass
class WrongOwnerError(Exception): pass

def upgrade_to_city(player, point):
    # בדיקות
    if not point.building:
        raise NoSettlementError(f"No settlement at {point}")
    
    if point.building.owner != player:
        raise WrongOwnerError(f"Settlement belongs to player {point.building.owner}")
    
    if not has_cards(player, [Wheat, Wheat, Ore, Ore, Ore]):
        raise NotEnoughCardsError("Need 2 Wheat, 3 Ore")
    
    # בנייה
    remove_cards(player, [Wheat, Wheat, Ore, Ore, Ore])
    point.building.upgrade_to_city()

# שימוש
try:
    upgrade_to_city(player=0, point=target_point)
    print("City built!")
except NotEnoughCardsError as e:
    print(f"Not enough cards: {e}")
except NoSettlementError as e:
    print(f"No settlement: {e}")
except WrongOwnerError as e:
    print(f"Wrong owner: {e}")
```

```python
# ===== גישה 2: Statuses (PyCatan) =====
def upgrade_to_city(player, point):
    # בדיקות
    if not point.building:
        return Statuses.ERR_NOT_EXIST
    
    if point.building.owner != player:
        return Statuses.ERR_BAD_OWNER
    
    if not has_cards(player, [Wheat, Wheat, Ore, Ore, Ore]):
        return Statuses.ERR_CARDS
    
    # בנייה
    remove_cards(player, [Wheat, Wheat, Ore, Ore, Ore])
    point.building.upgrade_to_city()
    return Statuses.ALL_GOOD

# שימוש
status = upgrade_to_city(player=0, point=target_point)
if status == Statuses.ALL_GOOD:
    print("City built!")
elif status == Statuses.ERR_CARDS:
    print("Not enough cards: Need 2 Wheat, 3 Ore")
elif status == Statuses.ERR_NOT_EXIST:
    print("No settlement at this location")
elif status == Statuses.ERR_BAD_OWNER:
    print("This settlement belongs to another player")
```

**מה ההבדל?**
- Exceptions: פחות קוד במקרה הטוב, אבל try/catch יכול להיות מסורבל
- Statuses: יותר קוד, אבל control flow ליניארי וצפוי

## לסיכום: מתי כדאי להשתמש בכל גישה?

### 🎯 השתמשו ב-Status Codes כאשר:

1. **משחקים וסימולציות** - שגיאות הן חלק מהלוגיקה
2. **AI ו-decision making** - צריך feedback ברור
3. **Performance critical** - הרבה בדיקות לשנייה
4. **Predictable errors** - אתם יודעים את כל המקרים מראש
5. **Multiple error types** - הרבה סוגי שגיאות שונים באותה פונקציה

### 🎯 השתמשו ב-Exceptions כאשר:

1. **אירועים חריגים** - דברים שלא אמורים לקרות
2. **Error propagation** - שגיאה צריכה לעלות רמות רבות
3. **Rich context** - צריך המון מידע על השגיאה
4. **Standard libraries** - אינטגרציה עם ספריות שזורקות exceptions
5. **ברור שמשהו השתבש** - לא decision, אלא באג

### 🎯 גישה היברידית (מה שעשיתי):

```python
# Status codes למשחק לוגיק
status = game.add_settlement(player, point)
if status != Statuses.ALL_GOOD:
    handle_game_error(status)

# Exceptions לבעיות אמיתיות
try:
    coords = point_mapper.point_to_coordinate(point_id)
    if coords is None:
        raise ValueError(f"Invalid point ID: {point_id}")
except Exception as e:
    logging.error(f"System error: {e}")
    raise
```

## המסקנה האישית שלי

אחרי עבודה עם Status-Based Error Handling במשך חודשים, אני חושב שזו **גישה מעולה למשחקים ולמערכות decision-making**. 

היתרונות:
- ✅ הקוד ברור וקריא
- ✅ Testing פשוט
- ✅ AI מקבל feedback טוב
- ✅ Performance טוב
- ✅ Control flow צפוי

החסרונות:
- ❌ קל לשכוח לבדוק
- ❌ Verbose - הרבה if/elif
- ❌ חסר context עשיר

**הלקח המרכזי:** כמו הרבה דברים בתכנות, זה לא "טוב" או "רע" - זה **מתאים** או **לא מתאים**. עבור PyCatan, זה היה מתאים מאוד.

ועכשיו, כשאני בונה את שכבת הסימולציה שלי, אני ממשיך להשתמש באותה גישה - כי היא עובדת. וכשאני צריך exceptions? אני לא מפחד להשתמש בהם גם. זה לא שחור או לבן - זה **כלי נוסף בארגז הכלים**.

---

## קוד לדוגמה: מעשי לחלוטין

```python
# דוגמה אמיתית מהפרויקט
from pycatan import Game, Statuses, ResCard

# יצירת משחק
game = Game(num_of_players=4)

# נסיון לבנות התנחלות בתור הראשון
point = game.board.points[0][0]
status = game.add_settlement(player=0, point=point, is_starting=True)

print(f"Status: {status}")  # Statuses.ALL_GOOD

# נסיון לבנות קרוב מדי
adjacent_point = game.board.points[0][1]
status = game.add_settlement(player=1, point=adjacent_point, is_starting=True)

print(f"Status: {status}")  # Statuses.ERR_BLOCKED

# טיפול בסטטוס
if status == Statuses.ALL_GOOD:
    print("✓ Settlement built successfully!")
elif status == Statuses.ERR_BLOCKED:
    print("✗ Cannot build - too close to another settlement")
elif status == Statuses.ERR_CARDS:
    print("✗ Not enough resources")
else:
    print(f"✗ Error: {status}")
```

---

*הפוסט הבא: "Actions Pattern - ממשק אחיד לכל הפעולות במשחק"*

*רוצים לראות את הקוד המלא? בקרו ב-[GitHub Repository](https://github.com/levinshon-98/PyCatan_AI)*
