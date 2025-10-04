from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Dict, List, Protocol

import pandas as pd


class HasOutletPressure(Protocol):
    """Protocol for any upstream element exposing an outlet pressure."""

    outlet_pressure: float


@dataclass
class Inlet:
    name: str
    outlet_pressure: float
    mass_flow_rate: float
    density: float
    temperature: float


@dataclass
class Outlet:
    name: str
    last_node: Junction | Pipe


@dataclass
class Network:
    name: str
    network_list: List[Inlet | Outlet | Junction | Pipe]

    # Column catalog with SI units (order defines default display order)
    ALL_COLUMNS: ClassVar[Dict[str, str]] = {
        "name": None,
        "mass_flow_rate": "kg/s",
        "inlet_velocity": "m/s",
        "outlet_velocity": "m/s",
        "ref_velocity": "m/s",
        "inlet_area": "m^2",
        "outlet_area": "m^2",
        "ref_area": "m^2",
        "length": "m",
        "hydraulic_diameter": "m",
        "friction_factor": "-",  # Dimensionless but still a num
        "form_loss": "-",
        "dp_gravity": "kPa",
        "dp_accel": "kPa",
        "dp_loss": "kPa",
        "inlet_pressure": "kPa",
        "outlet_pressure": "kPa",
        "pressure_drop": "kPa",
        "cumulative_dp": "kPa",
    }

    TYPE_COLUMN: ClassVar[str] = "type"

    PIPE_COLS: ClassVar[List[str]] = [c for c in ALL_COLUMNS if c != "form_loss"]
    JUNCTION_COLS: ClassVar[List[str]] = [
        "name",
        "mass_flow_rate",
        "ref_velocity",
        "ref_area",
        "form_loss",
        "dp_loss",
        "inlet_pressure",
        "outlet_pressure",
        "pressure_drop",
    ]
    PLENUM_COLS: ClassVar[List[str]] = ["name"]

    def _column_order_with_type(self) -> List[str]:
        base = list(self.ALL_COLUMNS.keys())
        return base[:1] + [self.TYPE_COLUMN] + base[1:]

    def _cols_for_kind(self, comp_kind: str) -> List[str]:
        mapping = {
            "pipe": self.PIPE_COLS,
            "junction": self.JUNCTION_COLS,
            "inlet": self.PLENUM_COLS,
            "outlet": self.PLENUM_COLS,
        }
        return mapping.get(comp_kind, self.PLENUM_COLS)

    def create_summary_df(self) -> pd.DataFrame:
        df_cols = self._column_order_with_type()
        df = pd.DataFrame(columns=df_cols)

        for idx, comp in enumerate(self.network_list):
            comp_kind = type(comp).__name__.lower()
            cols = self._cols_for_kind(comp_kind)

            vals = [getattr(comp, c, None) for c in cols]

            target_cols = cols + [self.TYPE_COLUMN]
            target_vals = vals + [comp_kind]
            df.loc[idx, target_cols] = target_vals

        # cumulative pressure drop
        df["cumulative_dp"] = (
            df["pressure_drop"].astype("float64[pyarrow]").fillna(0).cumsum()
        )

        # Convert to float64[pyarrow] when possible
        for col, unit in self.ALL_COLUMNS.items():
            if unit:
                df[col] = df[col].astype("float64[pyarrow]")
            else:
                # Probably a string
                df[col] = df[col].astype("string[pyarrow]")

        return df

    def write_summary(self, csv_path: Path | str) -> None:
        df = self.create_summary_df()

        for col, unit in self.ALL_COLUMNS.items():
            if unit == "kPa":
                # Divide corresponding column by 1000
                df[col] = df[col] / 1000

        # Build headers with units where available
        def header_with_unit(col: str) -> str:
            unit = self.ALL_COLUMNS.get(col)
            # Add units for known, unit-bearing columns
            if unit:
                return f"{col} [{unit}]"
            return col

        headers = [header_with_unit(c) for c in df.columns]
        df.to_csv(csv_path, index=False, header=headers, float_format="%.3G")


@dataclass
class Junction:
    """
    Form-loss junction for total-pressure loss across a local element.

    Model
    -----
    Form loss:
        pressure_drop = form_loss * (1/2) * density * ref_velocity^2

    Reference velocity:
        ref_velocity = mass_flow_rate / (density * ref_area)

    Endpoints
    ---------
    inlet_pressure = upstream.outlet_pressure
    outlet_pressure = inlet_pressure - pressure_drop

    Conventions
    -----------
    upstream.outlet_pressure must be set before creation. K must match the
    chosen ref_velocity (convert K beforehand if needed).

    Parameters
    ----------
    name : str
        Identifier for the junction.
    ref_area : float
        Reference area (m^2).
    form_loss : float
        Form-loss coefficient (dimensionless).
    mass_flow_rate : float
        Mass flow rate (kg/s).
    density : float
        Fluid density (kg/m^3).
    upstream : HasOutletPressure
        Object with attribute outlet_pressure: float.

    Attributes (computed)
    ---------------------
    ref_velocity : float
        Bulk velocity based on ref_area (m/s).
    dp_loss : float
        Irrecoverable total-pressure loss (Pa).
    pressure_drop : float
        Total-pressure drop across the junction (Pa).
    inlet_pressure : float
        Inlet pressure (Pa).
    outlet_pressure : float
        Outlet pressure (Pa).
    """

    name: str
    ref_area: float
    form_loss: float
    mass_flow_rate: float
    density: float
    upstream: HasOutletPressure

    # Computed
    ref_velocity: float = field(init=False)
    dp_loss: float = field(init=False)
    pressure_drop: float = field(init=False)
    inlet_pressure: float = field(init=False)
    outlet_pressure: float = field(init=False)

    def __post_init__(self) -> None:
        self.compute()

    def compute(self) -> None:
        if getattr(self.upstream, "outlet_pressure", None) is None:
            raise ValueError(
                "upstream.outlet_pressure must be set before constructing Junction."
            )

        # Reference velocity and loss
        self.ref_velocity = self.mass_flow_rate / (self.density * self.ref_area)
        self.dp_loss = self.form_loss * 0.5 * self.density * self.ref_velocity**2
        self.pressure_drop = self.dp_loss

        # Endpoint pressures
        self.inlet_pressure = float(self.upstream.outlet_pressure)
        self.outlet_pressure = self.inlet_pressure - self.pressure_drop


@dataclass
class Pipe:
    """
    Pressure drop in a straight pipe section (steady, one-dimensional).

    Model
    -----
    Friction (Darcy-Weisbach):
        dp_loss = \
            friction_factor
            * (length / hydraulic_diameter)
            * (1/2)
            * density
            * ref_velocity^2

    Gravity (hydrostatic):
        dp_gravity = density * g * length * sgn
        where sgn = +1 for "up", -1 for "down", 0 for "side".

    Acceleration (kinetic energy):
        dp_accel = \
            (1/2)
            * density
            * (alpha2 * outlet_velocity^2 - alpha1 * inlet_velocity^2)

    Endpoints
    ---------
    pressure_drop  = dp_loss + dp_gravity + dp_accel
    inlet_pressure  = upstream.outlet_pressure
    outlet_pressure = inlet_pressure - pressure_drop

    Conventions
    -----------
    - upstream.outlet_pressure must be set before creation.
    - Set inlet_area == outlet_area for a constant-area pipe.
    - Choose ref_area to select the velocity used in the friction term.
    - flow_direction must be one of: "up", "down", "side".

    Parameters
    ----------
    name : str
        Identifier for the pipe element.
    length : float
        Pipe length used in friction and gravity terms (m).
    hydraulic_diameter : float
        Hydraulic diameter for friction (m).
    friction_factor : float
        Darcy friction factor (dimensionless).
    mass_flow_rate : float
        Mass flow rate (kg/s).
    density : float
        Fluid density (kg/m^3).
    inlet_area : float
        Inlet area for V1 (m^2).
    outlet_area : float
        Outlet area for V2 (m^2).
    ref_area : float
        Reference area for friction velocity (m^2).
    upstream : HasOutletPressure
        Object with attribute outlet_pressure: float.
    flow_direction : str
        "up" -> positive dp_gravity; "down" -> negative dp_gravity; "side" -> 0.
    alpha1 : float, optional
        Kinetic-energy correction at inlet. Default 1.0.
    alpha2 : float, optional
        Kinetic-energy correction at outlet. Default 1.0.

    Attributes (computed)
    ---------------------
    inlet_velocity : float
        V1 = mass_flow_rate / (density * inlet_area) (m/s).
    outlet_velocity : float
        V2 = mass_flow_rate / (density * outlet_area) (m/s).
    ref_velocity : float
        Velocity used in friction (m/s).
    dp_loss : float
        Frictional pressure drop (Pa).
    dp_gravity : float
        Hydrostatic pressure change (Pa).
    dp_accel : float
        Acceleration pressure change (Pa).
    pressure_drop : float
        Total pressure drop (Pa).
    inlet_pressure : float
        Inlet pressure (Pa).
    outlet_pressure : float
        Outlet pressure (Pa).
    """

    GRAVITY: ClassVar[float] = 9.80665  # m/s^2, class variable

    name: str
    length: float
    hydraulic_diameter: float
    friction_factor: float
    mass_flow_rate: float
    density: float
    inlet_area: float
    outlet_area: float
    upstream: "HasOutletPressure"  # forward ref
    ref_area: float
    flow_direction: str

    alpha1: float = 1.0
    alpha2: float = 1.0

    # Computed
    inlet_velocity: float = field(init=False)
    outlet_velocity: float = field(init=False)
    ref_velocity: float = field(init=False)
    dp_loss: float = field(init=False)
    dp_gravity: float = field(init=False)
    dp_accel: float = field(init=False)
    pressure_drop: float = field(init=False)
    inlet_pressure: float = field(init=False)
    outlet_pressure: float = field(init=False)

    def __post_init__(self) -> None:
        self.compute()

    def compute(self) -> None:
        if getattr(self.upstream, "outlet_pressure", None) is None:
            raise ValueError(
                f"For {self.upstream}, the outlet_pressure must be set"
                " before constructing Pipe."
            )

        # Section velocities
        self.inlet_velocity = self.mass_flow_rate / (self.density * self.inlet_area)
        self.outlet_velocity = self.mass_flow_rate / (self.density * self.outlet_area)

        # Friction (Darcy–Weisbach) using chosen reference velocity
        self.ref_velocity = self.mass_flow_rate / (self.density * self.ref_area)
        q_ref = 0.5 * self.density * (self.ref_velocity**2)
        self.dp_loss = (
            self.friction_factor * (self.length / self.hydraulic_diameter) * q_ref
        )

        # Hydrostatic term: set sign from flow_direction
        dir_key = self.flow_direction.strip().lower()
        if dir_key == "up":
            sign = +1.0
        elif dir_key == "down":
            sign = -1.0
        elif dir_key == "side":
            sign = 0.0
        else:
            raise ValueError(
                f"flow_direction must be 'up', 'down', or 'side' (got {self.flow_direction!r})"
            )
        self.dp_gravity = self.density * Pipe.GRAVITY * self.length * sign

        # Acceleration term
        self.dp_accel = (
            0.5
            * self.density
            * (
                self.alpha2 * self.outlet_velocity**2
                - self.alpha1 * self.inlet_velocity**2
            )
        )

        # Totals and endpoints
        self.pressure_drop = self.dp_loss + self.dp_gravity + self.dp_accel
        self.inlet_pressure = float(self.upstream.outlet_pressure)
        self.outlet_pressure = self.inlet_pressure - self.pressure_drop
