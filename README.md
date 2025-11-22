# cmdl-interpreter
a small cmdl interpreter that i think is pretty cool

To use, make a file using the .cmdl extension in the same folder as the cmdl interpreter, open cmd in that folder, and do the command "python cmdl_interpreter.py yourfilename.cmdl" and your file will run inside the console.

---

## TEXT COMMAND

text "some text"
Writes text to the screen exactly as written.

text "hello ", x, " world"
Writes multiple pieces of text and variables in one line.

---

## CLEAR COMMAND

clear
Clears the entire screen.

---

## VARIABLES

set x = value
Creates or updates a variable.

Examples:
set x = 5
set name = "Dave"

---

## MATH COMMAND

math x = x + 2
math y = (x * 3) - 1
Performs arithmetic using + - * / and stores the result in the variable on the left.

---

## LOOPS

loop:
Runs the indented block under it forever.

loop(10):
Runs the indented block 10 times.

Examples:
loop:
text "hi"

loop(3):
text "three times"

If the value inside parentheses is a variable, it uses that variable’s value.

---

## IF / ELIF / ELSE

if condition:
commands...
elif condition:
commands...
else:
commands...

Conditions can use =, <, >, <=, >=, !=

Examples:
if x = 5:
text "x is five"
elif x > 5:
text "x is big"
else:
text "x is small"

---

## LABELS

labelname():
Defines a label.

Example:
start():

---

## GOTO

goto labelname()
Jumps to the label.

Example:
goto start()

---

## PAUSE COMMAND

pause()
Waits for the user to press Enter before continuing.

---

## UPDATE! INPUT FUNCTION ADDED

input varname:

Reads any text from the user and stores it in the variable.

input_number varname:

Reads user input, converts to a number (int or float), and stores it.

Includes:
Automatic string→number conversion
Re-prompts until valid number is entered for input_number
Works with all the existing syntax (labels, goto, loops, conditions, math, etc.)
No other features were changed.

# That's it for now, im going to try to make a 2d code thing or game engine next.
