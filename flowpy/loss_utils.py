from __future__ import annotations
import math
import numpy as np

from typing import Callable

def sudden_contraction(inlet_area: float, outlet_area: float) -> float:
    """
    Coefficient 'a' for a sudden contraction with sharp edges.

    Source: Idelchik, Diagram 4.9 (Re > 3.5e4). Linear interpolation of the
    a vs (outlet_area / inlet_area) table.
    """
    if inlet_area <= 0 or outlet_area <= 0:
        raise ValueError("Areas must be positive.")
    r = max(0.0, min(1.0, outlet_area / inlet_area))  # clamp to [0, 1]

    # Idelchik 4.9 data: ratio -> a
    x = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0])
    y = np.array([1.00, 0.85, 0.68, 0.503, 0.300, 0.178, 0.00])

    return float(np.interp(r, x, y))


def free_discharge():
    return 1.0


def sudden_expansion(inlet_area, outlet_area):
    return (1 - inlet_area / outlet_area) ** 2


def f_annulus_turbulent(
    lambda_circ: float,
    D_outer: float,
    D_inner: float,
) -> float:
    """
    Turbulent Darcy friction factor for a *concentric annulus* (Idelchik, Diagram 2.7).

    This implementation follows the relationship that the **reciprocal** of the
    annulus friction factor is given by a near-unity correction applied to the
    reciprocal of the round-pipe value at the same Re and roughness:

        1 / lambda_ann = (0.02 * r + 0.98) * ( 1 / lambda_circ - 0.27 * r + 0.1 )

    where r = D_inner / D_outer (0 < r < 1).

    The function therefore computes the right-hand side and returns its reciprocal:

        lambda_ann = 1.0 / [ (0.02*r + 0.98) * ( 1/lambda_circ - 0.27*r + 0.1 ) ]

    Parameters
    ----------
    lambda_circ : float
        Darcy friction factor for a **circular pipe** at the **same Reynolds number
        and roughness** as the annulus. Re should be formed with the annulus hydraulic
        diameter (D_h = D_outer - D_inner) and the mean annulus velocity.
    D_outer : float
        Outer diameter of the annulus (m), D_outer > 0.
    D_inner : float
        Inner diameter of the annulus (m), 0 < D_inner < D_outer.

    Returns
    -------
    float
        lambda_ann, the turbulent Darcy friction factor for the concentric annulus.

    Notes
    -----
    - The printed form in some editions can be easy to misread; implemented here is the
      **reciprocal** form, which yields physically reasonable magnitudes (lambda_ann
      close to lambda_circ with modest corrections).
    - Assumes fully turbulent regime and a concentric annulus.
    - Ensure lambda_circ corresponds to the *same* Re and roughness as the annulus case.
    - Also see: https://www.hydraucalc.com/wp-content/uploads/2019/09/Straight-Pipe-Annular-Cross-Section-and-Smooth-Walls-IDELCHIK-Jun-2019.pdf

    Examples
    --------
    >>> f_annulus_turbulent(lambda_circ=0.017, D_outer=0.143, D_inner=0.102)
    0.0171  # approximately
    """
    if D_outer <= 0.0 or D_inner <= 0.0:
        raise ValueError("Diameters must be positive.")
    if not (D_inner < D_outer):
        raise ValueError("Require D_inner < D_outer for a concentric annulus.")
    if lambda_circ <= 0.0:
        raise ValueError("lambda_circ must be positive.")

    r = D_inner / D_outer  # diameter ratio (0 < r < 1)

    inv_lambda_ann = (0.02 * r + 0.98) * (1.0 / lambda_circ - 0.27 * r + 0.1)

    if inv_lambda_ann <= 0.0:
        raise ValueError(
            "Computed 1/lambda_ann <= 0; check inputs (Re, roughness, diameters)."
        )

    return 1.0 / inv_lambda_ann


def sharp_thick_inlet_facing_baffle(
    baffle_gap: float, hydraulic_diameter: float
) -> float:
    """
    Loss coefficient for a sharp, thick-edged inlet facing a baffle.

    Model
    -----
    For a flush, sharp-thick inlet the base term is:
        k_prime = 0.5
    With a facing baffle, add the proximity term sigma1(h/hydraulic_diameter):
        zeta = k_prime + sigma1

    The sigma1 value is linearly interpolated from a tabulated curve of
    h/hydraulic_diameter → sigma1 (Idelchik Diagram 3.8). For h/hydraulic_diameter ≥ 1 the correction is 0.

    Parameters
    ----------
    baffle_gap : float
        Gap between inlet mouth and facing baffle, h (m).
    hydraulic_diameter : float
        Hydraulic diameter of the inlet, hydraulic_diameter (m).

    Returns
    -------
    float
        Total entrance loss coefficient zeta.

    Raises
    ------
    ValueError
        If hydraulic_diameter ≤ 0.
    """
    if hydraulic_diameter <= 0.0:
        raise ValueError("hydraulic_diameter must be > 0.")

    k_prime: float = 0.5

    # Table for sigma1 vs h/hydraulic_diameter (Idelchik Diagram 3.8)
    h_hydraulic_diameter_vals = np.array(
        [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 1.00]
    )
    sigma_1_vals = np.array([1.60, 0.65, 0.37, 0.25, 0.15, 0.07, 0.04, 0.00])

    r = baffle_gap / hydraulic_diameter
    if r >= 1.0:
        sigma1 = 0.0
    else:
        sigma1 = float(np.interp(r, h_hydraulic_diameter_vals, sigma_1_vals))

    return k_prime + sigma1


def discharge_from_straight_tube_to_baffle(
    baffle_gap: float, hydraulic_diameter: float
) -> float:
    """
    Loss coefficient for a straight circular tube discharging onto a baffle.

    Source
    ------
    Idelchik, Diagram 11.7 — row for alpha = 0 degrees (straight tube).
    For this case the tabulated data exist only for h/D in [0.50, 1.00].

    Model
    -----
    zeta = f(h/D)   (no diffuser; alpha = 0 deg)

    Parameters
    ----------
    baffle_gap : float
        Gap h between tube exit plane and the facing baffle (m).
    hydraulic_diameter : float
        Tube diameter D (m). For a straight circular tube, hydraulic_diameter = D.

    Returns
    -------
    float
        Entrance/exit loss coefficient zeta for the tube-to-baffle discharge.

    Notes
    -----
    - For h/D below 0.50 the function returns the value at 0.50 (clamped).
    - For h/D above 1.00 the function returns the value at 1.00 (clamped).
    """
    if hydraulic_diameter <= 0.0:
        raise ValueError("hydraulic_diameter must be > 0.")

    r = baffle_gap / hydraulic_diameter

    # Idelchik Diagram 11.7, alpha = 0 deg (straight tube)
    h_over_D = np.array([0.50, 0.60, 0.70, 1.00])
    zeta = np.array([1.37, 1.20, 1.11, 1.00])

    # np.interp clips automatically outside the range to end values
    return float(np.interp(r, h_over_D, zeta))


def smooth_cone_diffuser_nar1(diverging_angle: float) -> float:
    """
    Interpolate zeta from the Re=1.0 row (Re ≈ 1e5) for n_ar1 = 2.

    The table combines both panels (alpha = 3..120 deg) from the image.
    Values are linearly interpolated and clipped to the table bounds.

    Parameters
    ----------
    diverging_angle : float
        Diffuser half-angle in degrees.

    Returns
    -------
    float
        Loss coefficient zeta for Re ≈ 1e5 and n_ar1 = 2.
    """
    # Alphas (deg) across both panels
    alpha = np.array([3, 4, 6, 8, 10, 12, 14, 16, 20, 30, 45, 60, 90, 120])

    # Row "1.0" from each panel ()
    zeta = np.array(
        [
            0.120,
            0.106,
            0.090,
            0.083,
            0.080,
            0.088,
            0.102,
            0.122,
            0.196,
            0.298,
            0.297,
            0.286,
            0.283,
            0.279,
        ]
    )

    return float(np.interp(diverging_angle, alpha, zeta))


def beveled_contraction_alpha60(
    bevel_length: float,
    hydraulic_diameter: float,
    inlet_area: float,
    outlet_area: float,
) -> float:
    """
    Total loss coefficient zeta for a beveled contraction at alpha = 60 deg.

    Uses Idelchik's form:
        zeta = zeta_pp(l/hydraulic_diameter) * (1 - outlet_area / inlet_area)^(3/4)

    zeta_pp(l/hydraulic_diameter) is taken from the 60 deg column of the beveled
    contraction table and linearly interpolated. Values outside the
    tabulated l/hydraulic_diameter range are clamped.

    Parameters
    ----------
    bevel_length : float
        Passage length
    hydraulic_diameter : float
        Hydraulic Diameter
    inlet_area : float
        Upstream area before the contraction.
    outlet_area : float
        Downstream (contracted) area.

    Returns
    -------
    float
        Loss coefficient zeta referenced to the downstream velocity.
    """
    if inlet_area <= 0.0 or outlet_area <= 0.0:
        raise ValueError("Areas must be positive.")
    r = outlet_area / inlet_area
    if not (0.0 < r <= 1.0):
        raise ValueError("outlet_area / inlet_area must be in (0, 1].")

    # 60 deg column: l/hydraulic_diameter → zeta_pp (a.k.a. zeta'')
    x = np.array([0.025, 0.050, 0.075, 0.10, 0.15, 0.60])
    y = np.array([0.40, 0.30, 0.23, 0.18, 0.15, 0.12])
    zeta_pp = float(np.interp(bevel_length / hydraulic_diameter, x, y))

    return zeta_pp * (1.0 - r) ** 0.75


def beveled_contraction_alpha140(
    bevel_length: float,
    hydraulic_diameter: float,
    inlet_area: float,
    outlet_area: float,
) -> float:
    """
    Total loss coefficient zeta for a beveled contraction at alpha = 140 deg.

    Uses Idelchik's form:
        zeta = zeta_pp(l/hydraulic_diameter) * (1 - outlet_area / inlet_area)^(3/4)

    zeta_pp(l/hydraulic_diameter) is taken from the 140 deg column of the beveled
    contraction table and linearly interpolated. Values outside the
    tabulated l/hydraulic_diameter range are clamped.

    Parameters
    ----------
    bevel_length : float
        Passage length
    hydraulic_diameter : float
        Hydraulic Diameter
    inlet_area : float
        Upstream area before the contraction.
    outlet_area : float
        Downstream (contracted) area.

    Returns
    -------
    float
        Loss coefficient zeta referenced to the downstream velocity.
    """
    if inlet_area <= 0.0 or outlet_area <= 0.0:
        raise ValueError("Areas must be positive.")
    r = outlet_area / inlet_area
    if not (0.0 < r <= 1.0):
        raise ValueError("outlet_area / inlet_area must be in (0, 1].")

    # 60 deg column: l/hydraulic_diameter → zeta_pp (a.k.a. zeta'')
    x = np.array([0.025, 0.050, 0.075, 0.10, 0.15, 0.60])
    y = np.array([0.45, 0.42, 0.40, 0.38, 0.37, 0.36])
    zeta_pp = float(np.interp(bevel_length / hydraulic_diameter, x, y))

    return zeta_pp * (1.0 - r) ** 0.75

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