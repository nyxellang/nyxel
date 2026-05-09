# Nyxel

Nyxel is a simple, High-level programming language designed to be easy to read, and understand.
You just need to understand english and you'd be set.


## Requirements


Python 3.10 or higher, thats it


## Run a script

If one linux or MacOS:

sudo chmod +x nyx

./nyx run filename.nx


On windows

python nyx run filename.nx


## Try the REPL


python nyx repl


## Example
let users = get("https://jsonplaceholder.typicode.com/users")
let active = users where item.name.length <= 10
for each user in active:
say(user.name)


## example script


Open `projects/perfect.nx` — it shows a big part of what the language can do.
