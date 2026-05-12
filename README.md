<p align="center">
  <a href="https://github.com/nyxellang/nyxel/wiki">
    <img src="nyx.png" width="500">
  </a>
</p>

<div align="center">

<a href="https://github.com/nyxellang/nyxel/blob/main/LICENSE">
  <img src="https://img.shields.io/github/license/nyxellang/nyxel?style=flat-square">
</a>

<a href="https://www.python.org/">
  <img src="https://img.shields.io/badge/python-3.12-3776AB?style=flat-square&logo=python&logoColor=white">
</a>

<a href="https://github.com/nyxellang/nyxel/stargazers">
  <img src="https://img.shields.io/github/stars/nyxellang/nyxel?style=flat-square">
</a>

<a href="https://github.com/nyxellang/nyxel/wiki">
  <img src="https://img.shields.io/badge/wiki-documentation-2ea44f?style=flat-square&logo=github">
</a>

<a href="https://github.com/nyxellang/nyxel/commits/main">
  <img src="https://img.shields.io/github/last-commit/nyxellang/nyxel?style=flat-square">
</a>

</div>

# Nyxel

Nyxel is a simple, high-level programming language designed to be easy to read, and understand.
You just need to understand English or Arabic and you'd be set.

The philosophy of nyxel is that programming should be easy for everyone not just people who want to continue in tech
Programming shouldn't take days of studying it needs to be simple and easy.

## Requirements


Python 3.10 or higher, thats it.


## Run a script

If one linux or MacOS:

```bash
sudo chmod +x nyx

./nyx run filename.nx
```

On windows:
```
python nyx run filename.nx
```

## How to use

I highly suggest you to read the ![Wiki](https://github.com/nyxellang/nyxel/wiki))

You will learn a lot about Nyxel and how to use it

## Features 

 - Simple
 - Easy to read
 - Easy to debug
 - Bilingual
 - Correction if someone has an error
 
## Try the REPL

```
python nyx repl
```
or
```
./nyx repl
```

## Example
```nyxel
let users = get("https://jsonplaceholder.typicode.com/users")

let active = users where item.name.length <= 10

for each user in active:

say(user.name)
```

## Bilingual example

```nyxel
اجعل name = "Ahmed"

عندما name.length > 4:
  
قل("long name")
```

## example script


Open `projects/perfect.nx` — it shows a big part of what the language can do.


## Issues

The main one is that because its on Python it is quite slow but until now the speed doesn't matter that much because its still simple enough that the most demanding script won't take much time

## License

This project is under the MIT lincense
