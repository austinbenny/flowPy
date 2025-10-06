from typing import Callable

import yaml

from .flow_network_components import Inlet, Junction, Network, Outlet, Pipe
from .loss_utils import (
    beveled_contraction_alpha60,
    beveled_contraction_alpha140,
    discharge_from_straight_tube_to_baffle,
    f_annulus_turbulent,
    free_discharge,
    sharp_thick_inlet_facing_baffle,
    smooth_cone_diffuser_nar1,
    sudden_contraction,
    sudden_expansion,
)
from .geom_utils import (
    area_annulus,
    area_capsule_slot,
    area_circle,
    hydraulic_diameter_annulus,
    hydraulic_diameter_capsule_slot,
    hydraulic_diameter_circle,
)

GEOM_REGISTRY: dict[str, Callable[..., float]] = {
    "area_circle": area_circle,
    "area_annulus": area_annulus,
    "hydraulic_diameter_annulus": hydraulic_diameter_annulus,
    "hydraulic_diameter_circle": hydraulic_diameter_circle,
    "hydraulic_diameter_capsule_slot": hydraulic_diameter_capsule_slot,
    "area_capsule_slot": area_capsule_slot,
}

LOSS_REGISTRY: dict[str, Callable[..., float]] = {
    "f_annulus_turbulent": f_annulus_turbulent,
    "free_discharge": free_discharge,
    "sudden_expansion": sudden_expansion,
    "beveled_contraction_alpha60": beveled_contraction_alpha60,
    "beveled_contraction_alpha140": beveled_contraction_alpha140,
    "sharp_thick_inlet_facing_baffle": sharp_thick_inlet_facing_baffle,
    "discharge_from_straight_tube_to_baffle": discharge_from_straight_tube_to_baffle,
    "smooth_cone_diffuser_nar1": smooth_cone_diffuser_nar1,
    "sudden_contraction": sudden_contraction,
}


def resolve_refs(
    func_kwargs: dict, materialized: dict, spec_type: str = "geom"
) -> dict:
    """
    Resolve ${<spec_type>.<key>} strings in func_kwargs using
    materialized[spec_type][key]. Non-matching values are left unchanged.
    """
    if not func_kwargs:
        return {}

    prefix = "${" + spec_type + "."  # e.g., "${geom."
    out = {}

    for k, v in func_kwargs.items():
        if isinstance(v, str) and v.startswith(prefix) and v.endswith("}"):
            key = v[len(prefix) : -1]  # between prefix and trailing "}"
            try:
                out[k] = materialized[spec_type][key]
            except KeyError as e:
                raise KeyError(f"Unknown {spec_type} reference: {v}") from e
        else:
            out[k] = v

    return out


def build_network(inputs: yaml) -> Network:
    # Make list to store all nodes
    network_list = []
    inlet_plenum = None
    # Iterate through every other node
    for idx, sample_case in enumerate(inputs["network"]):
        if sample_case["type"] == "inlet":
            if idx != 0:
                raise IndexError(f"Inlet node should be first, currently {idx}")
            inlet_plenum = Inlet(
                name=sample_case["name"],
                outlet_pressure=sample_case["flow"]["pressure"],
                mass_flow_rate=sample_case["flow"]["mass_flow_rate"],
                density=sample_case["flow"]["density"],
                temperature=sample_case["flow"]["temperature"],
            )
            network_list.append(inlet_plenum)
        elif sample_case["type"] == "outlet":
            if idx != (len(inputs["network"]) - 1):
                raise IndexError(f"Outlet node should be last, currently {idx}")
            outlet_plenum = Outlet(
                sample_case["name"],
                network_list[-1],
            )
            network_list.append(outlet_plenum)
            break
        else:
            materialized = {"geom": {}, "loss": {}}

            for nest_type in materialized.keys():  # iteration order: "geom" then "loss"
                for key, spec in sample_case[nest_type].items():
                    # scalar passthrough (e.g., length: 1 or form: 14.7)
                    if isinstance(spec, (int, float)) or key == "flow_direction":
                        materialized[nest_type][key] = spec
                        continue

                    elif isinstance(spec, dict):
                        # callable form: {func: ..., params: {...}}
                        fn_name, func_kwargs = spec["func"], spec["params"]

                        # resolver for LOSS params
                        # allow string references to computed geom keys
                        # (e.g., inlet_area: "inlet_area")
                        if nest_type == "loss":
                            func_kwargs = resolve_refs(
                                func_kwargs, materialized, "geom"
                            )

                        registry = (
                            GEOM_REGISTRY if nest_type == "geom" else LOSS_REGISTRY
                        )
                        materialized[nest_type][key] = registry[fn_name](**func_kwargs)
                        continue

                    else:
                        raise TypeError(
                            f"[{sample_case['name']}]:"
                            f" Unsupported spec for {nest_type}.{key}: {spec!r}"
                        )

            ref_area = materialized["geom"][sample_case["ref_area"]["station"]]
            flow_splits = sample_case["ref_area"].get("flow_splits", 1)

            if sample_case["type"] == "pipe":
                network_obj = Pipe(
                    sample_case["name"],
                    length=materialized["geom"]["length"],
                    flow_direction=materialized["geom"]["flow_direction"],
                    hydraulic_diameter=materialized["geom"]["hydraulic_diameter"],
                    friction_factor=materialized["loss"]["friction"],
                    mass_flow_rate=inlet_plenum.mass_flow_rate,
                    density=inlet_plenum.density,
                    inlet_area=materialized["geom"]["inlet_area"],
                    outlet_area=materialized["geom"]["outlet_area"],
                    ref_area=ref_area,
                    upstream=network_list[-1],
                )
            else:
                network_obj = Junction(
                    name=sample_case["name"],
                    ref_area=ref_area,
                    mass_flow_rate=inlet_plenum.mass_flow_rate / flow_splits,
                    density=inlet_plenum.density,
                    form_loss=materialized["loss"]["form"],
                    upstream=network_list[-1],
                )

            network_list.append(network_obj)

    return Network(name=inputs["name"], network_list=network_list)


if __name__ == "__main__":
    pass
