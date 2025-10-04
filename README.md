# README

This repository defines a 1D hydraulic network (pipes + junctions + boundary nodes) in a single YAML file and computes the pressure drop across each component.

## Top-Level Fields

- `name` — label for the network run
- `network` — **ordered list** of components (flow follows list order)


## Component Types & Schemas

Each entry in `network` is one of:

- `inlet` — sets upstream boundary conditions
- `outlet` — sets downstream boundary conditions
- `junction` — localized (form) losses, area changes, splits/merges, orifices, diffusers, etc.
- `pipe` — distributed friction over a length

### Common fields (all components)

```yaml
- name: <string>                 # for logs/plots
  type: inlet | outlet | junction | pipe
  desc: <string>                 # optional
```

### `inlet`

Specifies imposed flow state at the network entrance.

```yaml
type: inlet
flow:
  mass_flow_rate: <number>       # kg/s (required)
  density: <number>              # kg/m^3 (required)
  pressure: <number>             # Pa (required)
  temperature: <number>          # K (optional)
```

### `outlet`

Defines the network exit (optionally constrains mass flow).

```yaml
type: outlet
```

### `junction` (local/form losses)

```yaml
type: junction
geom:
  <geom_key>:
    func: <GEOM_REGISTRY name>   # e.g., area_circle, area_annulus
    params: { ... }              # kwargs for that function
  <geom_scalar_key>: <number>    # pass-through scalars (e.g., bevel_length)
ref_area:
  station: <geom_key>            # which area sets the reference velocity
  flow_splits: <int>             # number of identical parallel branches (default 1)
loss:
  form: <number> |               # direct K (ζ)
        { func: <LOSS_REGISTRY name>, params: { ... } }
```

### `pipe` (distributed/friction losses)

```yaml
type: pipe
geom:
  inlet_area:
    func: area_circle | area_annulus | ...
    params: { ... }
  outlet_area:
    func: area_circle | area_annulus | ...
    params: { ... }
  hydraulic_diameter:
    func: hydraulic_diameter_circle | hydraulic_diameter_annulus | ...
    params: { ... }
  length: <number>               # axial length (m)
  flow_direction: up | down      # optional; for your own reporting
ref_area:
  station: inlet_area | outlet_area
loss:
  friction: <number> |           # Darcy f
            { func: <LOSS_REGISTRY name>, params: { ... } }
```

## Parameter & Value Resolution

* **Scalars** under `geom` or `loss` are used **as-is**.
* **Callables** use the dict form `{ func: <name>, params: { ... } }` and resolve through:

  * `GEOM_REGISTRY` for `geom.*.func`
  * `LOSS_REGISTRY` for `loss.form` and `loss.friction`
* **Cross-references to computed geometry** inside `loss.params` are explicit, using **`${geom.<key>}`**.
  Example:

  ```yaml
  loss:
    form:
      func: beveled_contraction_alpha60
      params:
        inlet_area: ${geom.inlet_area}
        outlet_area: ${geom.outlet_area}
        hydraulic_diameter: ${geom.hydraulic_diameter}
        bevel_length: ${geom.bevel_length}
  ```
* **No nested callables** inside `loss.params`. If a value must be computed, put it in `geom` and reference it with `${geom.*}`.

## When to Use Pipes vs. Junctions

* Use **junctions** for localized geometry changes with a **form-loss** (K = \zeta).
* Use **pipes** for **distributed** viscous losses along a **length** with **Darcy (f)**.

## Minimal, Aligned Examples

### 1) Inlet boundary

```yaml
- name: inlet_plenum
  type: inlet
  flow:
    mass_flow_rate: 4000
    density: 8000
    pressure: 100_000
    temperature: 310
```

### 2) Junction with fixed K (reference = outlet area)

```yaml
- name: cfd_zone_0_inlet_loss
  type: junction
  geom:
    outlet_area:
      func: area_circle
      params: { D: 1 }
  ref_area:
    station: outlet_area
    flow_splits: 1
  loss:
    form: 14.7
```

### 3) Pipe with fixed friction factor

```yaml
- name: orifice_stack
  type: pipe
  geom:
    inlet_area:
      func: area_circle
      params: { D: 1 }
    outlet_area:
      func: area_circle
      params: { D: 1 }
    hydraulic_diameter:
      func: hydraulic_diameter_circle
      params: { D: 1 }
    length: 1
    flow_direction: up
  ref_area:
    station: inlet_area
  loss:
    friction: 0.017
```

### 4) Junction using computed geom via `${geom.*}`

```yaml
- name: trap_annulus_approach
  type: junction
  geom:
    inlet_area:
      func: area_circle
      params: { D: 1 }
    outlet_area:
      func: area_annulus
      params: { D_outer: 1, D_inner: 0.5 }
    hydraulic_diameter:
      func: hydraulic_diameter_annulus
      params: { D_outer: 1, D_inner: 0.5 }
    bevel_length: 1
  ref_area:
    station: outlet_area
    flow_splits: 1
  loss:
    form:
      func: beveled_contraction_alpha60
      params:
        inlet_area: ${geom.inlet_area}
        outlet_area: ${geom.outlet_area}
        hydraulic_diameter: ${geom.hydraulic_diameter}
        bevel_length: ${geom.bevel_length}
```

### 5) Pipe with annulus friction correlation

```yaml
- name: trap_annulus
  type: pipe
  geom:
    inlet_area:
      func: area_circle
      params: { D: 1 }
    outlet_area:
      func: area_annulus
      params: { D_outer: 1, D_inner: 0.5 }
    hydraulic_diameter:
      func: hydraulic_diameter_annulus
      params: { D_outer: 1, D_inner: 0.5 }
    length: 1
    flow_direction: up
  ref_area:
    station: outlet_area
  loss:
    friction:
      func: f_annulus_turbulent
      params:
        lambda_circ: 0.017
        D_outer: 1
        D_inner: 0.5
```

### 6) Free discharge to plenum (example)

```yaml
- name: discharge_outlet_plenum
  type: junction
  geom:
    inlet_area:
      func: area_circle
      params: { D: 1 }
  ref_area:
    station: inlet_area
    flow_splits: 1
  loss:
    form: 1
```

### 7) Outlet boundary

```yaml
- name: outlet_plenum
  type: outlet
  flow:
    mass_flow_rate: 4000
```

## Loader Behavior (per component)

1. **Materialize `geom`**

   * Numbers pass through.
   * Callables are evaluated via `GEOM_REGISTRY` with their `params`.

2. **Resolve `ref_area`**

   * `station` must point to a computed `geom` key.
   * `flow_splits` defaults to `1`.

3. **Materialize `loss`**

   * If numeric → used directly.
   * If callable → any `${geom.*}` in `params` is replaced with that computed value, then the function is called via `LOSS_REGISTRY`.

4. **Boundary nodes (`inlet`/`outlet`)**

   * `flow` is read and applied as solver boundary conditions. No `geom`/`loss` needed.

## Notes & Conventions

* Use **Darcy** friction factor (f) in pipes; use **form-loss** (K=\zeta) in junctions. Reference velocity is set by `ref_area.station`.
* If a junction is followed by a straight run, **do not** add an extra “exit K” unless there’s a geometric discontinuity (step, lip, plenum, etc.).
* Keep any geometry needed by a loss correlation under `geom` and reference with `${geom.*}` in the loss `params`.
