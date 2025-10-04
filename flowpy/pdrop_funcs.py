from __future__ import annotations
import math


def area_circle(D: float) -> float:
    """Area of a circle with diameter D."""
    if D < 0:
        raise ValueError("D must be non-negative.")
    return math.pi * (D**2) / 4.0


def area_rectangle(L: float, w: float) -> float:
    """Area of a rectangle L x w."""
    if L < 0 or w < 0:
        raise ValueError("L and w must be non-negative.")
    return L * w


def area_capsule_slot(b: float, L: float) -> float:
    """
    Area of a 'capsule' slot: width b with two semicircular ends and
    straight length L between them.

    Formula: A = b*L + (π*b²)/4
             (two semicircles = one circle of diameter b)
    """
    if b < 0 or L < 0:
        raise ValueError("b and L must be non-negative.")
    return area_rectangle(L, b) + area_circle(b)


def area_annulus(D_outer: float, D_inner: float) -> float:
    """Area of a concentric annulus.

    Parameters
    ----------
    D_outer : float
        Outer diameter.
    D_inner : float
        Inner diameter.

    Returns
    -------
    float
        Annular area = \\pi/4 (D_outer**2 - D_inner**2).
    """
    return math.pi * (D_outer**2 - D_inner**2) / 4.0


def wetted_perimeter_circle(D: float) -> float:
    """Wetted perimeter of a full circular pipe (internal flow)."""
    return math.pi * D


def hydraulic_diameter_annulus(D_outer: float, D_inner: float) -> float:
    """Wetted perimeter of a concentric annulus (sum of inner+outer circumferences)."""
    return math.pi * (D_outer + D_inner)


def hydraulic_diameter_generic(A: float, P_w: float) -> float:
    """Hydraulic diameter from definition hydraulic_diameter = 4A / P_w.

    Parameters
    ----------
    A : float
        Flow area.
    P_w : float
        Wetted perimeter enclosing that area.

    Returns
    -------
    float
        Hydraulic diameter.
    """
    return 4.0 * A / P_w


def hydraulic_diameter_circle(D: float) -> float:
    """Hydraulic diameter of a circular pipe (equals the actual diameter)."""
    return D


def hydraulic_diameter_annulus_concentric(D_outer: float, D_inner: float) -> float:
    """Hydraulic diameter of a concentric annulus (Idel'chik): hydraulic_diameter = D_outer - D_inner."""
    return D_outer - D_inner


def hydraulic_diameter_rect_slot(a: float, b: float) -> float:
    """Hydraulic diameter of a rectangular slot (axb).

    Parameters
    ----------
    a : float
        Long dimension (slot length).
    b : float
        Short dimension (gap/height).

    Returns
    -------
    float
        hydraulic_diameter = 2ab / (a + b). For a ≫ b, hydraulic_diameter ≈ 2b.
    """
    return (2.0 * a * b) / (a + b)


def hydraulic_diameter_capsule_slot(b: float, L: float) -> float:
    """Hydraulic diameter of a 'capsule' slot (width b with two semicircular ends, straight length L).

    Parameters
    ----------
    b : float
        Slot width (distance between parallel sides).
    L : float
        Straight length between the semicircular ends.

    Returns
    -------
    float
        hydraulic_diameter computed from hydraulic_diameter = 4A / P_w with
        A = b L + (\\pi b**2)/4 and P_w = 2L + \\pi b.
    """
    A = b * L + math.pi * (b**2) / 4.0
    Pw = 2.0 * L + math.pi * b
    return 4.0 * A / Pw
