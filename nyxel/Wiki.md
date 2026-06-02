## Welcome to the Nyxel wiki!

Nyxel : is a simple, easy, and straight-forward programming language.

Nyxel supports both Arabic and English when writing, its meant to be easy for everyone not just programmers

Here you will learn how to use it

# CLI

You can use Nyxel in the CLI with Nyxel command to run a script, check a file, or use the REPL.

| Command | Description |
|---|---|
| `nyx run <file.nx> [args…]` | Run a script. Any arguments after the filename show up as `args` in your script. |
| `nyx repl` | Fire up the interactive REPL. |
| `nyx check <file.nx>` | Just check the syntax — no code runs. |
| `nyx version` | Print out the installed version. |
| `nyx help` | Show help and usage info. |
| `nyx <file.nx>` | Shortcut for `nyx run`. |

## Examples

```bash
nyx run main.nx

nyx run process.nx input.csv --verbose

nyx check script.nx

nyx main.nx

```

## REPL

Launch REPL with `nyx repl`. You just type and get the result as simple as that.

## Some commands


| Command | Description |
|---|---|
| `help` | Shows a quick syntax guide. |
| `vars` | List your variables and functions. |
| `clear` | cleans the screen. |
| `exit/quit` | Leaves the REPL. |

Samples:

```text
>>> let x = 10
>>> x * 3
= 30

>>> say("hello")
hello

>>> fn double(n):
...     return n * 2
...

>>> double(7)
= 14
```

# Variables

Use `let` when creating a new variable. To change the value of an existing variable, If you set an undeclared name, Nyxel will automatically create a global variable.

```Nyxel

let name = "Alice"
let score = 42
let active = true
let data = none

score = score + 10
name = "Bob"
```

# Types & Values

| Type | Example | Note |
|---|---|---|
| `number` | `42`, `3.14`, `1e10` | Same data type for integers and floating-point numbers. |
| `text` | `"hello"`, `'world'` | Double or single quotations to enclose strings. |
| `bool` | `true`, `false` | Lowercase true or false keywords to define Boolean values. |
| `none` | `none` | Keyword used to denote. |
| `list` | `[1, 2, 3]`, `[]` | Items of different types enclosed within square brackets. |
| `dict` | `{"name": "Alice"}` | Key-value objects with dot access support. |

# Strings

```Nyxel
let msg = "Hello, World!"
let multi = "Line one\nLine two"

# Escape sequences:
# \n  New line
# \t  Tab
# \\  Backslash

let greeting = "Hello, " + name
```

# Lists

```Nyxel
let nums = [1, 2, 3, 4, 5]
let mixed = [1, "two", true]

say(nums[0])

nums[0] = 99

say(nums.length)  # 5

add 6 to nums
```

# Dicts

```Nyxel
let user = {"name": "Alice", "age": 30}

say(user.name)
say(user["name"])

user.age = 31

let copy = user.copy()
```

> Dicts are reference types. Assigning one dict to another will result in them referring to the same object. Use copy() to make a copy.

# Operators

## Math Operators

| Operator | Description |
|---|---|
| `+` | Add numbers or concatenate|
| `-` | Subtracts |
| `*` | Multiplies |
| `/` | Divide (returns float) |
| `//` | Floor division |
| `%` | Remainder (modulo) |
| `**` | raises to the power |

## Comparison Operators

| Operator | Description |
|---|---|
| `==` | Equal to |
| `!=` | Not equal to |
| `<` | Less than |
| `<=` | Less than or equal to |
| `>` | Greater than |
| `>=` | Greater than or equal to |

## Logic

| Operator | Description |
|---|---|
| `and` | Logical AND |
| `or` | Logical OR |
| `not` | Logical NOT |

## Membership Operators

| Operator | Description |
|---|---|
| `in` | Check if a value exists |
| `not in` | Check if a value does not exist |

# Conditionals

Nyxel supports both `when` / `otherwise`, or stick to `if` / `elif` / `else` if you come from Python.

## Using `when`

```Nyxel
let score = 85

when score >= 90:
    say("A")
otherwise when score >= 80:
    say("B")
otherwise when score >= 70:
    say("C")
otherwise:
    say("F")
```

## Using `if`

```Nyxel
if x > 0:
    say("positive")
elif x < 0:
    say("negative")
else:
    say("zero")
```

# Loops

## `for` Loops

Loop for lists, ranges, or other values.

```nyxel
let fruits = ["apple", "banana", "cherry"]

for fruit in fruits:
    say(fruit)
```

```nyxel
for i in range(5):
    say(i)
```

# `repeat` Loops

Use `repeat` to repeat executing a block of code for a certain period of time.

```nyxel
repeat 3:
    say("hello")
```

You can capture the current iteration index with `as`.

```nyxel
repeat 5 as i:
    say(i)
```

You can also repeat across a numbered range.

```nyxel
repeat i from 1 to 5:
    say(i)
```

# Functions

The functions can be either created by using fn or def statements. The functions can be used as values and will maintain access to the variables from their scope.

```nyxel
fn greet(name):
    return "Hello, " + name

say(greet("Alice"))   # Hello, Alice
```

## With default parameters:

```nyxel
fn greet(name, greeting = "Hello"):
    return greeting + ", " + name
```

## Closures:

```nyxel
fn make_counter():
    let count = 0
    fn increment():
        count += 1
        return count
    return increment

let counter = make_counter()
say(counter())   # 1
say(counter())   # 2
```

## Passing functions:

```nyxel
fn apply(f, x):
    return f(x)

fn double(n): return n * 2
say(apply(double, 5))   # 10
```

# Structs

Structs are basic templates for objects. Every single struct maintains its own unique data set.

```nyxel
struct Point:

x
y = 0

let a = Point(1, 2)
let b = Point(3)

# Mutate one instance; the other stays the same.

a.x = 99
say(b.x)   # 3
```

Filter a list of structs with where:

```nyxel
struct User:
    name
    age
    active = true

let users = [
    User("Alice", 30),
    User("Bob", 17),
]

let adults = users where item.age >= 18
say(adults.length)   # 1
```

# Error Handling

You may employ `try` / `catch` / `finally` when things can go wrong (better to be safe than sorry). The catch variable exposes `.kind` and `.message`.

```nyxel
try:
    let data = read("missing.txt")
catch e:
    say("Error:", e.kind, "—", e.message)
finally:
    say("Done (always runs)")
```

```nyxel
try:
    let result = 10 / 0
catch e:
    say(e.kind)      # MathError
    say(e.message)   # Division by zero
```

>Note: break, continue, and return always do what you expect even in try blocks :P.

# Modules

Use bring to pull in code from other .nx files. Nyxel looks in your current folder.

```nyxel

bring math_utils
say(math_utils.add(1, 2))

 # You can bring in with an alias:

bring math_utils as m
say(m.add(1, 2))

 # Or just import specific names:

bring add from math_utils

bring add, subtract from math_utils
```

> Note: Modules are executed only once per program run. Whenever you change a module and then run your program again, Nyxel will notice right away. Circular dependencies are detected and managed.

## Writing a module:

```nyxel
# math_utils.nx
fn add(a, b):
    return a + b

fn subtract(a, b):
    return a - b

let PI = 3.14159265
```

# Where Filter

Filter lists easily with where. Inside where, use item for the current value. With structs, you may not even need item but simply use field names.

```nyxel
let numbers = [1, 2, 3, 4, 5, 6]

# Filter even numbers
let evens = numbers where is_even(item)

# Filter by value
let big = numbers where item > 3
```

```nyxel
# Strings — You can use item.length simple

let words = ["hi", "hello", "hey", "greetings"]
let long_words = words where item.length > 4
```

```nyxel
# Objects — can use item.<field>
struct User: name / age

let users = [User("Alice", 30), User("Bob", 17)]

let adults  = users where item.age >= 18
 # OR
let adults2 = users where age >= 1 # Both work
```

# Python Escape Hatch

You can code in Python at anytime with a simple block
python:
....
end
Nyxel vars will appear as Python vars

```nyxel
python:
    import hashlib
    h = hashlib.sha256(b"hello").hexdigest()
    print("SHA-256:", h)
end
```

Get a return value.

```nyxel
let result = python:
    return 2 ** 32
end
say(result)   # 4294967296
```

Access Nyxel variables:

```nyxel
let name = "World"
python:
    print(f"Hello, {name}!")
end
```

# Output

| Function | Description |
|---|---|
| `say(a, b, …)` | Print space-separated output. |
| `pretty(data)` | prints list and dict as pretty JSON. |

```nyxel
say("Score:", 42)         # Score: 42
say(true, false, none)    # true false none

let user = {"name": "Alice", "age": 30}
pretty(user)

# {
#   "name": "Alice",
#   "age": 30
# }
```

# File I/O

- `read(path)`              - Reads the whole file as plain text.  
- `write(path, text)`       - Writes text to an existing file.  
- `append(path, text)`      - Adds text to an existing file.  
- `read_lines(path)`        - Reads a file and returns a list of lines (without leading or trailing whitespace).  
- `lines_of(text)`          - Breaks up text into lines by new line character.
- `words_of(text)`          - Breaks up text into words.
- `save_json(path, data)`   - Converts a list or dict into JSON string and writes it to a file.
- `load_json(path)`         - Reads a JSON file and loads it as a Nyxel object or a list.
- `exists(path)`            - Checks if the file/directory at `path` exists.  

# HTTP

| Function | Description |
|---|---|
| `get(url)` | HTTP GET; JSON responses auto-parse to dicts with dot access. Otherwise, returns plain text. |
| `post(url, data)` | HTTP POST with JSON data. |

Example:

```nyxel
let res = get("https://api.example.com/users/1")
say(res.name, res.email)

let response = post(
    "https://api.example.com/users",
    {"name": "Alice", "age": 30}
)
say(response.id)

 # Handle HTTP errors:

try:
    let data = get("https://api.example.com/data")
catch e:
    say("NetworkError:", e.message)
```

# Maths

- `abs(n)`           - absolute value
- `round(n)`         - nearest integer
- `floor(n)`         - round down
- `ceil(n)`          - round up
- `sqrt(n)`          - square root
- `pow(base, exp)`   - power (or just use **)
- `log(n)`           - natural log
- `pi, e, inf`       - standard constants
- `rand_int(a, b)`   - random integer, a to b
- `random()`         - random float, 0.0 to 1.0
- `choice(list)`     - pick random item
- `shuffle(list)`    - create shuffled copy of a list

# Strings

In Nyxel, you can mess with text in two ways—either by using string functions directly (like upper(s)) or just by tacking on a dot and calling methods right on your text (like s.upper()). Here’s what you can do:

| Function | Dot Method | Description |
|---|---|---|
| `upper(s)` | `s.upper()` | Makes everything uppercase. |
| `lower(s)` | `s.lower()` | Makes it all lowercase. |
| `strip(s)` | `s.strip()` | Cleans up spaces at the beginning and end. |
| `split(s, sep?)` | `s.split(sep)` | Chops the string into pieces. |
| `join(sep, list)` | — | Stitches a list back together, using whatever separator you want. |
| `replace(s, a, b)` | `s.replace(a, b)` | Swaps one chunk of text for another. |
| `contains(s, sub)` | `s.contains(sub)` | Checks if your text includes something. |
| `starts_with(s, p)` | `s.starts_with(p)` | Checks how it starts. |
| `ends_with(s, p)` | `s.ends_with(p)` | Checks how it ends. |
| — | `s.length` | Gives you the number of characters. |

```nyxel
let s = "  Hello, World!  "
say(strip(s))              # → Hello, World! cleans up any unused spaces
say(s.upper())             # → HELLO, WORLD!  give you all caps just like you yelling it out
say(replace(s, "World", "Nyxel"))

let parts = split("a,b,c", ",")   # ["a", "b", "c"]
say(join("-", parts))             # a-b-c
```
# Lists & Data

| Function | Description |
|---|---|
| `append(list, value)` | Add an item to a list. |
| `len(x)` |  tells you how big is a list, text, or dict. |
| `range(n)` / `range(a, b)` | gives out a sequence of numbers. |
| `sorted(list)` |  gives you a sorted version. |
| `reversed(list)` | flips it backwards. |
| `unique(list)` | removes repeats, keeps order. |
| `flatten(list)` | smashes one level of nested lists flat. |
| `first_of(list)` / `last_of(list)` | grabs the start/end items. |
| `sum_of(list)` | do what you think they do. |
| `average_of(list)` | gives you the average of the list. |
| `max_of(list)` / `min_of(list)` | gives you the max and min in the list. |
| `count_of(list, val)` | counts how many times val pops up. |
| `numbers_of(text/list)` | pulls out just the numbers. |
| `group_by(list, field)` | groups things by any field. |

```nyxel
 # so lets say you have:

let scores = [85, 92, 78, 95, 88]

say(sum_of(scores))      # 438
say(average_of(scores))  # 87.6
say(max_of(scores))      # 95
say(sorted(scores))      # [78, 85, 88, 92, 95]

let raw = read("data.txt")
let values = numbers_of(raw)
say(average_of(values))
```

# Type Utilities

For checking or converting types, Nyxel keeps things painless and simple:

| Function | Description |
|---|---|
| `type(x)` |  returns the type of x: "number", "text", "list", "dict", "bool" or "none". |
| `str(x)` or `to_str(x)` |  turn it into a string. |
| `int(x)` / `to_int(x)` | turns it into an integer. |
| `float(x)` / `to_float(x)` |  turns it into a float. |
| `bool(x)` | turns it into bool true or false. |
| `is_number(x)`, `is_text(x)` | checks the type. |
| `is_even(n)`,`is_odd(n)` | checks the number n to see if it's even/odd. |
| `is_divisible_by(n, d)` | checks if n is a multiple of d. |
| `is_empty(x)` | checks whether it's empty, works with lists, text, etc.|
| `to_json(x)`,`from_json(s)` | go to and from the JSON |

# System Stuff


Do you want to execute shell commands or read environment variables? How about checking files? Here's how:

- `run(cmd)` – Runs a shell command and gives you the output as plain text.  
- `run_lines(cmd)` – Runs a shell command and gives you the output as a list of lines.  
- `env(key, default?)` – Reads an environment variable. If it's not set, you can give it a default.  
- `args` – Lists all command-line arguments passed to your script.  
- `exists(path)` – Checks if a file or directory exists.  
- `ls(path?)` – Lists what's in a directory. If you don't give it a path, it'll use the current one.  
- `mkdir(path)` – Creates a directory, along with any parent directories needed.  
- `cwd()` – Shows the current working directory.  
- `sleep(seconds)` – Pauses things for a while.  
- `exit(code?)` / `quit_app()` – Quits the program. You can set an exit code if you need to.

# Examples

## Shell commands

```nyxel
let output = run("ls -la")
say(output)

let files = run_lines("ls")
for f in files:
    say(f)
```

## Environment variables

```nyxel
let token = env("API_TOKEN")
let host  = env("HOST", "localhost")  # uses "localhost" if HOST isn't set
```

# Time & Date

| Function | Description |
|---|---|
| `time()` | Seconds since epoch as a float. Good for timing things. |
| `unix()` | Seconds since epoch rounded as an integer. |
| `date()` | A date/time object with fields and methods (see below). |
| `wait(n, unit?)` | Pause for `n` seconds (default), `"ms"`, or `"minutes"`. |

```nyxel
let t0 = time()
wait(2)
say(time() - t0)           # ≈ 2.0

wait(500, "ms")             # half a second
wait(1, "minutes")
```

## date() methods and fields

| Member | Description |
|---|---|
| `.year` | e.g. 2026 |
| `.month` | e.g. 5 |
| `.day` | e.g. 27 |
| `.hour` | e.g. 20 |
| `.weekday` | e.g. "Tuesday" |
| `.unix` | integer timestamp |
| `.format(fmt)` | strftime-like formatting |
| `str(d)` | e.g. "May 27, 2026  08:01 PM" |

```nyxel
let d = date()
say(d.year, d.month, d.day)       # 2026 5 27
say(d.weekday)                     # Tuesday
say(d.format("%d/%m/%Y"))          # 27/05/2026
say(str(d))                        # May 27, 2026  08:01 PM
```

# GUI

Requires: `pip install customtkinter`

For Arabic text: `pip install arabic-reshaper python-bidi`

Create windows with buttons, labels, inputs, and more using the `gui` module.

```nyxel
bring gui

let win = gui.window("My App", 800, 600)

fn on_click():
    lbl.text = "clicked!"

let lbl = win.add(gui.label("Hello"))
win.add(gui.btn("Click me").color("green").on_click(on_click))
win.run()
```

## Widget types

| Builder | Description |
|---|---|
| `gui.btn("text")` | A clickable button. |
| `gui.label("text")` | A text label. |
| `gui.dim_label("text")` | A dim/gray low-profile label. |
| `gui.input("placeholder")` | A text input field. |
| `gui.textbox(height)` | A multi-line text display (append-only). |
| `gui.checkbox("text")` | A checkable box. |
| `gui.switch("text")` | An on/off toggle switch. |
| `gui.slider(lo, hi)` | A draggable slider between lo and hi. |
| `gui.progressbar()` | An indeterminate progress bar. |
| `gui.dropdown("a", "b", ...)` | A dropdown menu. |
| `gui.radio("text", "group")` | A radio button within a group. |
| `gui.separator()` | A horizontal line. |

## Chaining methods

Every builder supports these chainable methods:

| Method | Description |
|---|---|
| `.color("green")` | Set the widget's accent color. |
| `.on_click(fn)` | Call `fn` when clicked (buttons, checkboxes, radios). |
| `.on_change(fn)` | Call `fn` when value changes (checkboxes, switches, sliders, dropdowns). |
| `.place(x, y)` | Position at pixel coordinates instead of default packing. |

```nyxel
win.add(gui.btn("Save").color("green").on_click(save_fn).place(20, 50))
```

## Window methods

| Method | Description |
|---|---|
| `win.add(builder)` | Add a widget to the window. Returns a live handle. |
| `win.on_key("escape", fn)` | Call `fn` when a key is pressed. |
| `win.run()` | Start the GUI event loop (blocks until closed). |
| `win.quit()` | Close the window and exit the app. |

## Widget handles

`win.add()` returns a handle you can use to read or update the widget later:

| Property / Method | Description |
|---|---|
| `.text` | Read or set the label text. |
| `.value` | Read or set the value (slider: float, input: string, checkbox/switch: bool). |
| `.checked` | Read the boolean state of a checkbox or switch. |
| `.append(text)` | Add text to a textbox (new line). |
| `.clear()` | Clear a textbox's contents. |

```nyxel
bring gui

let win = gui.window("Counter", 300, 200)
let count = 0

fn on_add():
    count = count + 1
    lbl.text = "Count: " + to_str(count)

let lbl = win.add(gui.label("Count: 0"))
win.add(gui.btn("Add").on_click(on_add))
win.add(gui.btn("Reset").color("red").on_click(fn ():
    count = 0
    lbl.text = "Count: 0"
end))
win.run()
```

# Key Listening

Requires: `pip install readchar`

Listen for key presses in the terminal (CLI mode, no GUI needed).

| Function | Description |
|---|---|
| `listen_key()` | Blocks until a key is pressed. Returns the key name. |
| `on_key(key)` | Blocks until the given key is pressed, returns `true`. |

```nyxel
# Wait for a single key press
let k = listen_key()
say("You pressed:", k)
```

`listen_key()` returns these values:

| Key | Returns |
|---|---|
| Letters / numbers | The character itself (e.g. `"a"`, `"3"`) |
| Enter | `"enter"` |
| Space | `"space"` |
| Backspace | `"backspace"` |
| Tab | `"tab"` |
| Escape | `"escape"` |
| Arrow keys | `"up"`, `"down"`, `"left"`, `"right"` |
| Ctrl+A through Ctrl+Z | `"ctrl+a"` … `"ctrl+z"` |
| Ctrl+C | `"ctrl+c"` |

```nyxel
# Quit on Escape
while true:
    let k = listen_key()
    when k == "escape":
        say("Goodbye!")
        exit()

# Using on_key
say("Press Q to quit")
on_key("q")
say("Quitting...")
exit()
```

## Environment variables

```nyxel
let token = env("API_TOKEN")
let host  = env("HOST", "localhost")  # uses "localhost" if HOST isn’t set
```

# Dot Access

In Nyxel, you don’t have to jump through hoops for the basics. Just use a dot and get right to it:


- `"hello".length` gives you 5  
- `[1,2,3].length` is 3  
- `{"a":1}.length` is 1  
- `"".is_empty()` lands true (same goes for `[].is_empty()`)  
- `"hello".upper()` turns `"hello"` into `"HELLO"`  
- `"hello".contains("ell")` checks out as true  
- `[3,1,2].sorted()` flips to `[1,2,3]`  
- `[1,2,3].reversed()` ends up `[3,2,1]`  
- `[1,2,3].first()` is 1, `.last()` is 3  
- `[1,2,3].copy()` hands you a fresh new copy  

# Arabic Keywords

If you'd rather use Arabic because lets say you are learning Arabic and trying to improve or that you are Arab here are some keywords you need to know for Nyxel and you can use English and Arabic at the same time with no problems

> Note: خطأ has a double meaning in Arabic—“false” and “error.” In Nyxel, خطأ always means “false” as a keyword. So if you need to name an error variable in a catch block, go with something like اصطد ع: instead of اصطد خطأ:.


- `اجعل` = let  
- `عندما` = when  
- `وإلا` = otherwise  
- `لكل` = for  
- `في` = in  
- `بينما` = while  
- `كرر` = repeat  
- `إلى` = to  
- `توقف` = break  
- `تابع` = continue  
- `دالة` = fn  
- `أرجع` = return  
- `حاول` = try  
- `اصطد` = catch  
- `أخيرا` = finally  
- `استورد` = bring  
- `من` = from  
- `كـ` = as  
- `هيكل` = struct  
- `صحيح` = true  
- `خطأ` = false  
- `لاشيء` = none  
- `و` = and  
- `أو` = or  
- `ليس` = not  
- `حيث` = where
- `وقت` = time
- `تاريخ` = date
- `انتظر` = wait
- `استمع` = listen_key
- `عند_المفتاح` = on_key
- `إنهاء` / `أنهِ` = exit / quit_app  

## Example

```nyxel
اجعل الأرقام = [١٠, ٢٠, ٣٠]

لكل رقم في الأرقام:
    قل(رقم)
```

# Error Types


If you mess up and do something wrong, Nyxel doesn’t just shrug and leave you confused—it tells you what went wrong, what it tried to do, where it cracked, and often, how to fix it. You’ll see a handy pointer (^) showing the exact spot it tripped.


## Types of errors:
- SyntaxError is when typos, broken code, unfinished strings.
- NameError is when used a variable before making it.
- TypeError is when wrong data type.
- IndexError is when list item not there.
- KeyError is when missing dict key.
- AttributeError is when object’s field is missing.
- MathError is when stuff like dividing by zero or averaging an empty list (double check always).
- FileError is when file not found or bad JSON.
- NetworkError is when there's HTTP failed.
- ImportError is when theres trouble grabbing a module.
- PythonError is when anything Python throws from python blocks.

# The End

That's it, I hope you learnt something from this cya :P