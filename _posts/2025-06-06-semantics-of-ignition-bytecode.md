---
layout: post
title: "Semantics of V8 Ignition Bytecode"
date: 2025-06-19 14:00:00 -0000
categories: verification jekyll
---

# 📘 V8 Ignition Bytecode Semantics

## Table of Contents
1. [Introduction](#introduction)
2. [Execution Model](#execution-model)
3. [Bytecode Format](#bytecode-format)
4. [Register Model](#register-model)
5. [Instruction Categories](#instruction-categories)
    - [Loading & Storing Values](#loading--storing-values)
    - [Control Flow](#control-flow)
    - [Function Calls](#function-calls)
    - [Arithmetic & Logic](#arithmetic--logic)
    - [Object & Property Access](#object--property-access)
    - [Environment & Scope](#environment--scope)
    - [Other Instructions](#other-instructions)
6. [Exception Handling](#exception-handling)
7. [Feedback Vectors](#feedback-vectors)
8. [Interpreter Dispatch Loop](#interpreter-dispatch-loop)
9. [Debugging & Tracing](#debugging--tracing)
10. [Semantics Reference Table](#semantics-reference-table)
11. [Resources & References](#resources--references)

---

## 1. Introduction
Brief overview of Ignition, its role in the V8 pipeline, and its use as a baseline interpreter for JavaScript execution.

## 2. Execution Model
Explanation of how Ignition executes bytecode:
- Stack vs register model
- Call frames
- Operand decoding

## 3. Bytecode Format
Details on the encoding of bytecode:
- Byte layout
- Operand types (e.g., Reg, Idx, Const)

## 4. Register Model
Overview of virtual registers:
- Accumulator
- Temporary registers
- Function frame slots

## 5. Instruction Categories

### 5.1 Loading & Storing Values
- `LdaConstant`, `StaNamedProperty`, `Mov`, etc.
- Semantics and use cases

### 5.2 Control Flow
- `Jump`, `JumpIfTrue`, `JumpIfToBooleanTrue`, `Return`, etc.

### 5.3 Function Calls
- `Call`, `CallUndefinedReceiver`, `Construct`, `CallRuntime`, etc.

### 5.4 Arithmetic & Logic
- `Add`, `Sub`, `BitwiseAnd`, etc.

### 5.5 Object & Property Access
- `GetNamedProperty`, `SetNamedProperty`, `DefineNamedOwnProperty`, etc.

### 5.6 Environment & Scope
- `PushContext`, `PopContext`, `LdaCurrentContext`, etc.

#### Contexts

In V8 there are different kinds of contexts:

- Global context: For `var` declarations in scripts, function declarations in scripts, and global properties.

- Script context: For `let` and `const` bindings declared at the top level of a module or script.
ES modules use a script context to hold their top-level bindings.
This context is separate from the global object.

- Function context: For function locals.

- Block context: For block-scoped let/const.

##### How contexts are arranged in V8

When JavaScript code runs, the scope chain (i.e., the chain of environments) is implemented as a linked list of contexts.

Each execution context is one object (array-like) that holds bindings. For example:

- Global context - top-level `var` bindings and function declarations.
- Script context — top-level let/const in a script or module.
- Function context — parameters and locals declared in a function.
- Block context — let/const declared inside a block.
- Catch context — the variable of a catch clause.

At any point during execution, the current context points to the innermost scope’s context.
Each context has a pointer to its next outer context.

Example:

```
let a = 10;
var b = 20;

function f() {
  let c = 30;
  console.log(a, b, c);
}
```

At the top level, `let a = 10` allocates *script context* slot for a, and `var b = 20` makes `b` become a property of the *global object* (i.e., the *global context*).

Before function `f` executes, only the *global* and *script* contexts are active.

When `f` is called, a function context is created to hold variable `c`.
The function context’s parent is the script context, and the chain looks like:

function context (holds `c`)
   ↓
script context (holds `a`)
   ↓
global context (holds `b`)

When Ignition generates bytecode for `console.log(a, b, c)`, the variable lookups work like this:

- `c`: `LdaContextSlot context_index=0 slot=...` (`0` = current context, i.e., function context)
- `a`: `LdaContextSlot context_index=1 slot=...` (`1` = parent context, i.e., script context)
- `b`: `LdaGlobal "b"` (global property lookup by name)

##### Global Context

There is a single global context in each execution.

Global Context Lookups are made by name (string). 

The global context is really a dictionary mapping names (strings) to values.

This means a variable like `var x = 42;` declared at *global* scope ends up as a property on the *global object*.

The Ignition bytecode uses instructions such as:

- `LdaGlobal [name]` — Load a global by name.

- `StaGlobal [name]` — Store a global by name.

These lookups go through a name resolution process (with potential checks like `HasProperty`, `prototype chain`, etc.).

This is slower than indexed lookups because it requires hash table lookups.

- Global variables are looked up by name.
- Local (closure) variables in contexts are looked up by index.

##### Script Context

*Modules* always get a script context: all top-level bindings (`import`, `export`, `let`, `const`, `class`) are lexical and live in the script context. *Ordinary* scripts may still allocate a script context if they declare top-level `let`/`const`.

This is because in classic scripts, while `var` and function declarations attach to the global object, `let` and `const` at the top level must not become properties of the *global object*, but remain lexical bindings.

So V8 creates a script context to hold those top-level lexical bindings.

This allows the engine to do:

- Fast indexed lookups for top-level `let`/`const` variables.

- Correct scoping semantics (e.g., `let x = 1`; doesn’t become `window.x`).

`StaCurrentScriptContextSlot` and `StaCurrentScriptContextSlot` are used respectively for storing to and loading from the script context.

##### Function Contexts

When a function needs to capture local variables in a closure (e.g., `let`, `const`, `var` in nested scopes), V8 creates a context object.

That context object is essentially an array (with fixed slots).

Each captured variable gets a context slot index assigned by the compiler.

The bytecode instructions use these indices:

- `LdaContextSlot [context_index] [slot_index]` — Load a value from a particular context in the chain.

- `StaContextSlot [context_index] [slot_index]` — Store a value.

`context_index` means “which context up the chain,” e.g.,

- `0`: current context

- `1`: parent context

- `2`: grandparent context

`slot_index` is the offset in that context array.

This lookup is a very fast indexed array access, and no name resolution needed.

Example:

```
let globalVar = 100;

function outer() {
  let outerVar = 200;
  return function inner() {
    console.log(globalVar);  // looked up by name
    console.log(outerVar);   // looked up by context index and slot
  };
}
```

- `globalVar` is a property of the *global object*, so `LdaGlobal` with the string `"globalVar"` is emitted.

- `outerVar` is stored in a context slot (e.g., slot `0` of the outer function’s context), and `inner` accesses it via `LdaContextSlot 1 0` (where `1` means the parent context).

#### `StaCurrentScriptContextSlot`

`StaCurrentScriptContextSlot [slot]`: pops the top value off the accumulator and stores a value into a slot of the *current* script context.

The instruction `StaCurrentScriptContextSlot` is typically used 

- in *module* code compiled by V8,
- when initializing `let`/`const` top-level variables in a *script*, and
- during assignments to such variables.

#### `LdaCurrentContextSlot`

Load a variable stored in the current context (the innermost scope) into the accumulator.
Operands: `slot_index`, the index of the variable in the current context.

`LdaCurrentContextSlot slot_index` is simply a special case of `LdaContextSlot 0 slot_index`, 
for brevity and slight performance improvement.

### 5.7 Closures

`CreateClosure` creates a new JavaScript function object corresponding to a particular function literal (`SharedFunctionInfo`).

One of the operands to `CreateClosure` is an index into the function literals table (i.e., which nested function you’re creating).

Another operand encodes whether the function should be shared or freshly allocated.

#### SharedFunctionInfo

When V8 compiles a JavaScript function, it produces a SharedFunctionInfo object, essentially the immutable metadata about the function:

- Its literal source text
- Its compiled code (or bytecode)
- Its parameter info
- Scope layout, etc.

This metadata is shared among all closures created from the same function literal.

#### Closure context

Crucially, the created closure captures the current execution context, defining its lexical scope.

If no new context has been created (i.e., no `PushContext` instruction has executed), the closure captures the current context, which is simply whatever context was active when the outer function started running.

If your function does not introduce any new local variables requiring a context (no `let`/`const`/`var` in a closure scope, no `with`, no `eval`, no `arguments` object, etc.), then the current context remains the outer context (for example, the function’s parent context or the global context).

So in that case, the `CreateClosure` instruction will assign the same context that was active at the start of the containing function.

That means any variables the closure references are looked up via that parent context chain.

When no new context has been created, the closure’s context is simply the current (outer) context at that point—often the parent function’s context or the global context if no intermediate contexts exist.

Example:

```
function outer() {
  return function inner() {
    return 42;
  };
}
```

When `outer` runs:

- No `PushContext` happens (since no new scope locals need a context).

- So the current context is the outer’s context (which, in this simple case, is the *global* context).

- The `CreateClosure` instruction creates `inner`, capturing the *global* context.

- That is why `inner` does not have its own special closure environment in this trivial example.

Contrast the example above with:

```
function outer() {
  let x = 10;
  return function inner() {
    return x;
  };
}
```

In this case:

- When `outer` runs, the `PushContext` instruction allocates a new block context to hold x.

- `CreateClosure` will capture that new context, so `inner` can access x.

### 5.8 Other Instructions
- `Nop`, `Debugger`, `StackCheck`, etc.

## 6. Exception Handling
- `Throw`, `ReThrow`, `TryCatch`, how stack unwinding works.

## 7. Feedback Vectors
Explanation of:
- Inline caches
- Dynamic feedback collection
- Effects on later optimizations

## 8. Interpreter Dispatch Loop
- How Ignition interprets instructions
- Bytecode handler dispatch strategy (e.g., computed gotos or switch)

## 9. Debugging & Tracing
- Breakpoints
- `DebugBreak`, tracing output
- Tools and logging

## 10. Semantics Reference Table
A comprehensive table of all bytecodes with:
- Mnemonic
- Operand types
- Description
- Side effects
- Static semantics (input/output)
- Control effects

## 11. Resources & References
- Links to V8 source code
- Design docs
- Blog posts and academic papers

