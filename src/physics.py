"""Afflux: turning a camera's blockage fraction into a water level.

THIS IS THE STEP THAT MAKES THE PROJECT MEAN SOMETHING. Without it the system
reports "the gate is 24% covered", which an operator already knows by looking.
With it it reports "the water will sit 38 cm higher, and the road floods at
61%" -- a consequence, early enough to act on.

SOURCES: docs/referensi_fisika.md. The equation is USBR's (Water Measurement
Manual ch.9 s.5, Cd = 0.61 = Cc*Cvf*Cva); the premise that floating debris
really does block a bottom-opening gate is Mohammed (2022), who MEASURED a 15%
rise in upstream depth from driftwood accumulation.

THE CHAIN, from rencana_penelitian.md 5.8-5.9:

    BF = blockage factor, the fraction of the opening lost to debris
    A  = A_bersih * (1 - BF)                     effective opening area
    Q  = Cd * b * a * sqrt(2 * g * h)            free-flow discharge through a gate
    h  = Q^2 / (Cd^2 * A^2 * 2g)                 invert it for the head needed

    =>  h is proportional to 1 / A^2

    h_tersumbat / h_bersih = 1 / (1 - BF)^2

The ratio form is the one that matters: it is DIMENSIONLESS. No discharge, no
gate width, no scale factor survives into it -- which is why an 80 cm aquarium
can validate the same law as a real barrage (docs/eksperimen_miniatur.md, E1).

TWO WARNINGS THAT ARE NOT DECORATION:

1. The square amplifies error. A camera reading 24% when the truth is 31% does
   not give a 7% error in afflux: 1/(0.76)^2 = 1.73 against 1/(0.69)^2 = 2.10,
   i.e. 18% low. Calibrate the camera (experiment E2) before trusting anything
   out of here.

2. It blows up as BF -> 1. A fully blocked gate has infinite head in this model,
   which is nonsense -- real water goes over the top, around the sides, or the
   structure fails. Anything above BF_MAX_TRUSTED is reported as "beyond the
   model", never as a number.

3. THIS IS AN UPPER BOUND, NOT A BEST ESTIMATE. Shrinking the area is what
   Australian Rainfall and Runoff calls the Reduced Area Method, and ARR says
   the RAM belongs to "bottom up" blockage (sedimentation) while blockage AT
   THE ENTRANCE -- which a floating debris raft is -- belongs to their Energy
   Loss Method, because the RAM "can exaggerate energy losses". Their worked
   example at 50% blockage: RAM 6.04 m of headwater against ELM 4.71 m, 28%
   high. The defence is that ARR's stated reason is inflated velocity along a
   culvert BARREL, and a gate is a thin orifice with no barrel -- so most of
   that failure mode does not reach us. It is still the conservative side, and
   the dashboard says so rather than hiding it. Ollett, Syme & Ryan (2017),
   J. Hydrology (NZ) 56(2):109-122; see docs/referensi_fisika.md section 3.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

G = 9.81

# Past this, 1/(1-BF)^2 stops describing anything physical: the flow stops being
# a gate discharge and becomes a weir over the top, and the curve runs to
# infinity while real water does not.
BF_MAX_TRUSTED = 0.85

DEFAULT_SITE_JSON = Path(__file__).resolve().parents[1] / "configs" / "site_geometry.json"


@dataclass(frozen=True)
class Gate:
    b_m: float
    a_m: float
    Cd: float
    h_bersih_m: float
    z_jalan_m: float

    @property
    def area_bersih_m2(self) -> float:
        return self.b_m * self.a_m


@dataclass(frozen=True)
class Site:
    gate: Gate
    bias: float
    skala: float
    calibrated: bool
    lat: float | None
    lon: float | None
    adm4: str | None


def load_site(path: Path | str = DEFAULT_SITE_JSON) -> Site:
    cfg: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    g = cfg["gate"]
    k = cfg.get("kalibrasi_kamera") or {}
    s = cfg.get("site") or {}
    return Site(
        gate=Gate(
            b_m=float(g["b_m"]),
            a_m=float(g["a_m"]),
            Cd=float(g["Cd"]),
            h_bersih_m=float(g["h_bersih_m"]),
            z_jalan_m=float(g["z_jalan_m"]),
        ),
        bias=float(k.get("bias", 0.0)),
        skala=float(k.get("skala", 1.0)),
        # Anything other than an explicit CALIBRATED counts as uncalibrated.
        # Defaulting the other way would let a missing field silently promote
        # guesses to measurements.
        calibrated=str(cfg.get("status", "")).upper() == "CALIBRATED",
        lat=s.get("lat"),
        lon=s.get("lon"),
        adm4=s.get("adm4"),
    )


def blockage_factor(accumulation_frac: float | None, site: Site) -> float | None:
    """Camera fraction -> BF, with the calibration from experiment E2 applied.

    None in, None out. A missing measurement must never become 0.0 here: 0.0
    means "the gate is clear", the most dangerous thing this module could
    invent.
    """
    if accumulation_frac is None or not math.isfinite(accumulation_frac):
        return None
    bf = site.skala * accumulation_frac + site.bias
    return min(1.0, max(0.0, bf))


def afflux_ratio(bf: float | None) -> float | None:
    """h_tersumbat / h_bersih = 1 / (1 - BF)^2. None beyond the trusted range."""
    if bf is None or bf >= BF_MAX_TRUSTED:
        return None
    return 1.0 / ((1.0 - bf) ** 2)


def afflux_m(bf: float | None, site: Site) -> float | None:
    """How much HIGHER the upstream water sits than with a clear gate."""
    ratio = afflux_ratio(bf)
    if ratio is None:
        return None
    return site.gate.h_bersih_m * (ratio - 1.0)


def head_m(bf: float | None, site: Site) -> float | None:
    """Absolute upstream head: h_bersih plus the afflux."""
    ratio = afflux_ratio(bf)
    if ratio is None:
        return None
    return site.gate.h_bersih_m * ratio


def discharge_m3s(head: float | None, site: Site, bf: float | None = None) -> float | None:
    """Q = Cd * b * a_efektif * sqrt(2 g h), free flow."""
    if head is None or head <= 0:
        return None
    area = site.gate.area_bersih_m2
    if bf is not None:
        area *= 1.0 - bf
    if area <= 0:
        return None
    return site.gate.Cd * area * math.sqrt(2.0 * G * head)


def critical_bf(site: Site) -> float | None:
    """The BF at which the upstream water reaches the road.

    Invert h_bersih / (1 - BF)^2 = z_jalan. This is the number worth predicting
    OUT LOUD before a demonstration: computing it from clear-water measurements
    alone, then showing the road flood at that value, is a far stronger claim
    than narrating a rising level.
    """
    h0, z = site.gate.h_bersih_m, site.gate.z_jalan_m
    if h0 <= 0 or z <= 0 or z <= h0:
        # The road is already at or below the clear-water level: nothing to
        # predict, and the site geometry needs re-measuring.
        return None
    return 1.0 - math.sqrt(h0 / z)


def margin_to_road_m(bf: float | None, site: Site) -> float | None:
    """Metres of level left before the road floods. Negative means already over."""
    h = head_m(bf, site)
    if h is None:
        return None
    return site.gate.z_jalan_m - h


def summary(accumulation_frac: float | None, site: Site) -> dict[str, Any]:
    """Everything the dashboard needs, in one dict. Missing stays None."""
    bf = blockage_factor(accumulation_frac, site)
    head = head_m(bf, site)
    return {
        "bf": bf,
        "beyond_model": bf is not None and bf >= BF_MAX_TRUSTED,
        "afflux_ratio": afflux_ratio(bf),
        "afflux_m": afflux_m(bf, site),
        "head_m": head,
        "head_bersih_m": site.gate.h_bersih_m,
        # Deliberately NOT the discharge at the afflux head: that is algebraically
        # identical to the clear-gate discharge (see demo()), so a dashboard
        # showing it would print the same number in both columns forever.
        #
        # This is capacity at an UNCHANGED water level -- what the gate can still
        # pass before the water starts piling up. That is the loss an operator
        # can act on.
        "discharge_bersih_m3s": discharge_m3s(site.gate.h_bersih_m, site, 0.0),
        "discharge_tersumbat_m3s": (
            None if bf is None else discharge_m3s(site.gate.h_bersih_m, site, bf)
        ),
        "critical_bf": critical_bf(site),
        "margin_to_road_m": margin_to_road_m(bf, site),
        "z_jalan_m": site.gate.z_jalan_m,
        "calibrated": site.calibrated,
    }


def demo() -> None:
    """Self-check: python -m physics"""
    gate = Gate(b_m=2.0, a_m=1.0, Cd=0.61, h_bersih_m=0.8, z_jalan_m=1.6)
    site = Site(gate=gate, bias=0.0, skala=1.0, calibrated=False, lat=None, lon=None, adm4=None)

    assert afflux_ratio(0.0) == 1.0, "a clear gate must not raise the level"
    assert abs(afflux_ratio(0.5) - 4.0) < 1e-9, "half blocked quadruples the head"
    assert afflux_ratio(0.9) is None, "beyond the trusted range must be None, not a number"
    assert blockage_factor(None, site) is None, "no measurement must never become 0.0"

    # Road at exactly twice the clear head: BF_kritis = 1 - sqrt(1/2) = 0.2929
    bfc = critical_bf(site)
    assert abs(bfc - (1 - math.sqrt(0.5))) < 1e-9
    assert abs(head_m(bfc, site) - gate.z_jalan_m) < 1e-9, "critical BF must reach the road"

    # DISCHARGE IS CONSERVED, and that is the point, not a bug.
    #
    #   Q = Cd * A0(1-BF) * sqrt(2g * h0/(1-BF)^2)
    #     = Cd * A0(1-BF) * sqrt(2g*h0) / (1-BF)
    #     = Cd * A0 * sqrt(2g*h0) = Q0
    #
    # The head rises by exactly the amount needed for the same river discharge
    # to still get through. That is what afflux IS. The damage is not lost flow;
    # it is the water piling up upstream to force that flow through a smaller
    # hole -- which is what floods the road.
    q0 = discharge_m3s(head_m(0.0, site), site, 0.0)
    q5 = discharge_m3s(head_m(0.5, site), site, 0.5)
    assert abs(q5 - q0) < 1e-9, "afflux is defined by holding discharge constant"

    # What DOES fall is the flow at an unchanged water level: same head, smaller
    # opening. That is the operator-facing loss of capacity.
    q_same_head = discharge_m3s(site.gate.h_bersih_m, site, 0.5)
    assert q_same_head < q0, "at unchanged level, a blocked gate passes less"

    s = summary(0.24, site)
    assert s["calibrated"] is False
    assert s["afflux_m"] is not None and s["afflux_m"] > 0

    print("physics ok")
    print(f"  BF 24%  -> head x{s['afflux_ratio']:.2f}, naik {s['afflux_m'] * 100:.0f} cm")
    print(f"  jalan tergenang di BF {bfc * 100:.0f}%")


if __name__ == "__main__":
    demo()
