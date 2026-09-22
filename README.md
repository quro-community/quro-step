# quro-step

A small experimental scaffold for building long-horizon AI problem solving around **persisted semantic state**, rather than around an ever-growing conversation.

```text
from:  a chatbot that keeps continuity by growing its context
to:    short-lived, recoverable, composable execution units
       operating around PERSISTED SEMANTIC STATE
```

The experiment asks a narrow architectural question:

> Can continuity be carried by persisted semantic state while execution remains short-lived, independently recoverable, and composable?

The code is the proof of feasibility, not a production agent framework.

**Python ≥ 3.10. Standard library only.**

---

## Core idea

The kernel has three boundaries:

```text
SemanticPosition ──mount──▶ ExecutionState ──execute──▶ Artifact | Failure
                                      │
                                      ▼
                         ExecutionContinuity′ ◀──update──
```

```python
mount(position, continuity)
execute(state, unit)
update(continuity, artifact, provenance)
```

The important separation is:

> **Kernel executes. Control selects continuation.**

The kernel does not decide what should happen next.

That means there is deliberately no kernel-level:

```text
next
steer
retry
backtrack
replan
compact
fork
fold
```

Those are control-layer operations. They can be built on top of the substrate without expanding the kernel's execution model.

---

## Why the model is shaped this way

### 1. `ExecutionState` is derived, not persistent

The kernel reconstructs an `ExecutionState` from:

```text
SemanticPosition + ExecutionContinuity
```

The state contains only the information required to execute the current unit.

This avoids creating two competing sources of truth:

```text
persisted continuity
        +
persisted execution state
        = ambiguity
```

Instead:

```text
Continuity
     │
     └── mount ──▶ current ExecutionState
```

A state can disappear completely and be reconstructed later.

---

### 2. `SemanticPosition` is semantic, not physical

Execution identity is represented by semantic position rather than:

* filesystem paths
* conversation IDs
* prompt offsets
* model sessions
* storage locations

Repeated visits to the same logical unit therefore remain distinguishable:

```text
X#0 ≠ X#1
```

and independent branches remain distinct.

The purpose is recoverability of execution identity without depending on the machinery that happens to store or run it.

---

### 3. Continuity is the durable reconstruction source

`ExecutionContinuity` records the information needed to interpret a position later:

```text
plan
occurrences
recoverable positions
history
artifacts
```

The reference implementation is intentionally immutable.

That makes an important property structural:

```text
mount(...)
```

reads continuity; it does not mutate it.

A storage implementation can replace the in-memory representation later without changing what the kernel needs conceptually.

---

### 4. History is not semantic truth

History is append-only:

```text
H' = H ⧺ [record]
```

A conversation trace can therefore be preserved without turning the conversation itself into the mechanism that defines execution continuity.

This is important for the experiment because:

> **Conversation continuity and execution continuity are different things.**

The former may be useful evidence. It is not the source of truth for the latter.

---

### 5. `update` records; it does not decide

`update` deliberately performs the minimal semantic append/update operation.

It does **not** secretly become a:

* merge engine
* deduplicator
* conflict resolver
* branch manager
* summarizer
* fold engine

Those operations require higher-level policy.

Keeping them out of `update` is what allows the kernel to remain a substrate rather than becoming a workflow engine.

---

### 6. The kernel does not own control

The kernel only knows how to:

```text
mount
execute
update
```

For example:

```text
Control
  │
  ├── establishes P
  │
  ▼
mount(P, C)
  │
  ▼
execute(S, U)
  │
  ├── Artifact
  │      │
  │      ▼
  │   update(C, A, provenance)
  │      │
  │      ▼
  │   Continuity'
  │
  └── Failure
         │
         ▼
      Control decides
```

A failure does not automatically advance, retry, update continuity, or choose another position.

That decision belongs to the layer that owns the problem.

---

### 7. Domain payload is an extension point, not control authority

`ExecutionState` provides a domain payload so applications can attach information needed by their own execution logic.

The payload is intentionally separated from kernel-owned fields.

The important rule is not that a domain can never *write* something called `position` into its payload. It is that:

> the kernel never interprets domain payload as control instructions.

This keeps the substrate extensible without allowing application data to silently redefine kernel semantics.

---

### 8. Related concepts use distinct types

The project intentionally keeps conceptually similar extension slots separate:

```text
StateDomainPayload
ProvenanceDetail
ArtifactPayload
```

They may look structurally similar, but they represent different semantic roles.

This is a small design choice with a practical purpose: an application should not be able to accidentally substitute one kind of information for another merely because the underlying data happens to have the same shape.

---

### 9. The upper layers are consumers of the kernel

The repository contains higher-level modules such as:

```text
quro.continuity_ops
quro.context
```

They are built *above* the kernel.

The dependency direction is intentional:

```text
upper layers
     │
     ▼
  Kernel
```

not:

```text
Kernel
  │
  └──▶ upper-layer policy
```

This keeps the kernel reusable and prevents a convenient application abstraction from becoming an accidental part of the execution substrate.

---

## The minimal execution loop

Conceptually, the whole system reduces to:

```text
Position + Continuity
        │
      mount
        │
        ▼
 ExecutionState
        │
     execute
        │
        ├──────────────▶ Failure
        │
        ▼
     Artifact
        │
      update
        │
        ▼
   Continuity'
        │
        └──────▶ Control establishes the next Position
```

This is the central experiment.

Everything more elaborate is expected to be constructed above it.

---

## Source layout

```text
src/quro/
├── kernel/            # minimal execution substrate
│   ├── model/         # semantic model and value types
│   ├── mount/         # position resolution and mounting
│   ├── execution/     # execution and result handling
│   ├── continuity/   # continuity reading and updating
│   ├── persistence/  # persistence-oriented representations
│   ├── contract/     # kernel contracts / conformance helpers
│   └── kernel/       # public facade
│
├── continuity_ops/    # higher-level continuation operations
└── context/           # read-side context / artifact views
```

The important architectural boundary is simply:

```text
Kernel
  ▲
  │ consumed by
  │
Upper layers
```

---

## Minimal API

The intended kernel surface is small:

```python
from quro.kernel import Kernel, CallableExecutor

kernel = Kernel(executor=CallableExecutor(handlers))

mounted = kernel.mount(position, continuity)
result = kernel.execute(mounted.unwrap(), unit)
updated = kernel.update(continuity, result.unwrap(), provenance)
```

The exact data structures are in `src/`; the README intentionally does not duplicate them.

The important property is the shape of the interface:

```text
mount
execute
update
```

rather than the details of individual classes.

---

## What this project is — and is not

This repository is primarily an **architecture experiment**.

The code exists to demonstrate that the proposed separation can be implemented cleanly:

```text
semantic position
        +
persisted continuity
        +
short-lived execution
        +
explicit control outside the kernel
```

It is **not** intended to be:

* an autonomous agent runtime
* a planner
* a workflow engine
* a general recovery framework
* a replacement for application-level control logic

Those systems can use this substrate, but they are deliberately not part of the kernel's responsibility.

---

## Status

The project is exploratory.

The main result is not a large framework; it is the observation that a useful execution model can be reduced to a small set of explicit boundaries while leaving continuation strategy to higher layers.

The implementation should therefore be read as:

> **a concrete demonstration of an architectural idea, rather than an attempt to define the final form of an AI agent framework.**

---

## License

Proprietary — see `pyproject.toml`.
