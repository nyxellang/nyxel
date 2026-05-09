# Nyxel Design Decisions
This file is a record of the major design decisions we made for the Nyxel,  specifically: value23. The rationale behind these decisions is also documented.

Alled us, and what alternatives were consciously rejected. Reading this before

In addition, the addition of a feature is compulsory.

 This lecture is aimed at accounting students, resulting in an emphasis on the financial aspects and the deduction of tax, rather than the practical impact for the business. Although the tax deduction aspect is the main focus it will be necessary to consider the implications of these taxes on the business, as advised by the tutor.

1. Path A:  scripting language (not performance language) (next: CC++) and Path B: performance language4 (next: JVM) can be integrated. 

Nyxel is on 2nd Path A.  This is a conscious, locked decision.

Path A expressive scripting languagel

-Topics: ergonomics, readability,  forgiving errors

- Runtime: tree-walk interpreter (Python coupled)

- Target: automation, glue code, learning, small utilities

Speed: “fast enough for scripting”

**B. Path** performance language (temp. reject).

- Would require: bytecode VM, JIT, static analysis, dropping Python

- Would be nice: fast iterations,  python interop, simple embedding

- Timeline:  may be possible in Stage3/4,  but not currently

**Consequence**: do not optimise the interpreter for speed. Do not add

Inst,  to optimize performance. Do not include a JIT. If a user hits

For a performance wall the answer is ` python:... end’,  not a faster Nyxel.

The bytecode design by nyxel/bytecode.py is a *specification* for a

Not a priority Stage 2. 

Crying is not a healthy coping mechanism.  Your body is not hungry but is crying because you are failing to feed your soul.  It often takes a good few days to break away from Y, you‘ll never regret having a positive outlook.

2. Object reference semantics

NyxObjects utilizes (though this is not documented anywhere): 2. All copies: have...

Donate pairs of mutations are to be share it both are visible.

5. After Having Taken the Test. For example, if you are really unsure if you are in A1 level, it is great to have actually tried to do the A1 test and have your results to compare with other levels.

Abc=a={x: 1}

Is the notation for an element of?, then and there exists an element of. 

B. X= 99

Http://vistavision.sourceforge.net/#ways (method 4) say(a.x) # -> 99

Here is an English text rewritten with more natural human language and without changing the meaning of the text.

**Why**:  familiar with Python and JS. Since they already know these... It’ would be strange and costly if there would be copying on every assignment.

Escape hatch:  a.copy() provides a shallow-copied independent object.

Future: when we get more serious on structs, we can add a` copy-on-write`

But for now: objects are (or have the effect of being) references. leaving the choice up to the programmer. No mode nor an immutable keyword andobjects are references. 

The farm has mixed house and yard lines and there are common zero lines adjacent to snags on many of the yards.  There are no small yard lines on the farm either.

## 3. `Param` Namedtuple that stores function parameters

The parameters parameters are saved as List[Param]whereparam is a.

 NamedTuple(name: str, default: Optional[Node]).

**Why**:  Used to specify params as List[str],  but in fact

Stored `List[Tuple[str, Node|None]]`. This led to silent breakage when the region and node objects were stored in.

Code assumed the primitive type. The namedtuple Param makes the structure

Self-documenting and spot mistakes immediately upon access.

**Rule**:  Do not bake out a raw (name, default) pair for params.  Instead always

Use `Param(name=,  default=)`.

A certain amount of variability is expected; if there are only slight differences; the measurements are consistent. However even if the differences between the sets of data is very small, the measurements could still be unsatisfactory; if the range is quite large then the number of significant figures should be increased.

4. `when / otherwise’ versus`if / elif /else’

Both work. They generate the same AST nodes.  The ‘when / otherwise’ is the

Nyxel-idiomatic style; if / else if / else maintained as an alias.

Why keep the alias: will break muscle memory ifhapus

i would add one more reason here, if we we add `if` then it will break muscle memory which we have previous, and we will have to learn all the commands again.

Enhance clarity. The alias is free and as making the language less

Unexpected to Python users.

Rule:  examples and documentation should use when /otherwise.

E.g.  Tests may have either.

‘s, therefore you, And thieves of your own lives. (1.3.319-422) This quoted non-existent speech from the Character of Wish, (1.3.395,) is concerning the choices thoughs ofmankindwhat to do with there lives. It insinuates that through our own choices we either make ourselves or break ourselves.

5. `fn` versus `def`

Both work. Same rule as above. `fn` is prefered in the new Nyxel code.

 H. D: So, the achievement of operating in a ‘neutral’ frame should not be feared as the undeniable pinnacle of classical cinema. All the same, the museum camera is not at all designed to tempt the filmmaker into ‘scheduling shots’.

6. REPL block detection heuristic in nature. 

The REPL finds block openers with a keyword + colon heuristic, not a

Full parser. See the comment in `nyxel/repl.py’ for details. And the

Major known limitation.

Why not parser-based: costly,  makes error display more complex,  too complicated?

This syntax applies to both currentandnew syntax: 

Upgrade trigger:  if nyxel has gained syntaxwhich where can appear at the end of

Set one line off with having to start a block (like inline dicts, lambdas, decorators),  and switch to

A light pre parse pass.

 All the study we conducted was to get a better understanding of the optimal way to use the 23-O-M. During the study year, we hit upon some answers but not enough. Using our paper, the 23.-O-M essays and the synthesis itself we want to try to give some answers about the best way to use this reagent.

7.  The class that beings error to runtime.py is called `NyxException`. 

NyxException:  a runtime value (a NyxObject with . Kind and . Message

Fields), not execution machinery. It belongs in `runtime.py` along with.

`NyxObject` is not in `interpreter.py` with the execution engine.

 Once a VM layer has been inserted, the VM will create NyxException objects as

At the runtime layer, just as the interpreter does now.

(This book summarises the research on organizational design over the past fifty years. It has a lot of applicable ideas for practitioners, such as how to improve group effectiveness and achieving flexibility and innovation in design.)

8. Module exports do not include built-in functions

Each file is added to the module, so if a file is loaded by bring, names are also only added M.  When a module is loaded through bring,  only names are added to the module (no M):

Are exported.  Predefined identifiers (`say`, `get’, `len’,...) are accessible

Inside the module during execution,  but NOT re-exported.

 But:  if imported modules were re-exported,  then the command include utils would flood the.

Here‘s caller‘s namespace including all of Nyxel‘s built-ins, making name clashing

Unexpectedly.

 The aim of this particular activity is to generate a discourse where the use of the second person singular is desirable for the reader while avoiding the use of the pronoun himself.

9. `where` uses reference preserving item wrapping, 10. `advance` has an unusual merging rule, 11. `advance` satisfies Equivariant and...(underline) in the arguments of definitions.

`people where age >= 18’ will produce a new list of people, but only including

Are the *comparable* NyxObjects as in the list originally (reference semantics). 

Mutate a filtered item is Mutate the original.

 Which obeys rule 2,  and is consistent with the behaviour of Python‘s filter

Does.

…there are a negligible number of J. M. Bowling types participating….

10.  Items that were intentionally removed:

Reason for removal:

|------------------|--------------|.13 Duration of Stage1;.14 Duration of Stage1‘s end;.15 Max duration of Phase1; |---|-------------|.24 Duration of Phase1.

| `\|>’ pipe | Too clever - decodes not reads |

| ’?.’ safe access | Too clever the adds symbol noise |

| `??` null coalesce | a bit too clever. Use `when` instead. |

| `-’>` arrow fn | Follows the pattern of a `fn` but not consistently

| `print` alias | Here is just one “print” function, it‘s called “say” |

| ‘import’ directive | ‘bring’ takes the Nyxel way |

Rule: do not overwrite these, even “just for backward compatibility.“34 34John Gruber (Daring Fireball) ( Sep 8 2003 ): The other thing I really hate is that Apple has been adding backslashes to filenames “just for compatibility” it claims.
