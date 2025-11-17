"""
sales_comp_model.py

Sales Comparison Model

This module takes:
- a subject property profile
- a set of comparable sales (manually input or scraped)

and produces:
- normalized comps with:
    - price_per_sqft
    - price_per_unit
    - similarity_score
- median PPSF / PPU
- an estimated value range for the subject:
    - low / base / high

This is a valuation tool designed to complement the income approach.
"""

from typing import List, Dict, Optional
from statistics import median


class SalesCompModel:
    """
    Parameters:
        subject: dict with at least:
            {
                "beds": float/int,
                "baths": float/int,
                "sqft": float,
                "num_units": int,
                "property_type": str
            }

        comps: list of dicts, each comp ideally includes:
            {
                "price": float,
                "sqft": float,
                "beds": float/int,
                "baths": float/int,
                "num_units": int,
                "distance_miles": float,
                "sale_date": "YYYY-MM-DD" (optional),
                "property_type": str (optional),
                "condition": str (optional),
                "source": str (optional)
            }

    Notes:
        - This model is intentionally simple and transparent.
        - You can later plug in MLS/Redfin/PropStream data to feed the comps.
    """

    def __init__(
        self,
        subject: Dict,
        comps: List[Dict],
        max_distance_miles: float = 2.0,
        min_sqft_ratio: float = 0.5,
        max_sqft_ratio: float = 1.5,
        target_comp_count: int = 6,
    ):
        self.subject = subject or {}
        self.comps = comps or []
        self.max_distance_miles = max_distance_miles
        self.min_sqft_ratio = min_sqft_ratio
        self.max_sqft_ratio = max_sqft_ratio
        self.target_comp_count = target_comp_count

        self._validated_subject = self._normalize_subject()

    # ---------------------------------------------------------
    # Subject normalization
    # ---------------------------------------------------------

    def _normalize_subject(self) -> Dict:
        beds = self.subject.get("beds")
        baths = self.subject.get("baths")
        sqft = self.subject.get("sqft")
        num_units = self.subject.get("num_units") or 1
        prop_type = (self.subject.get("property_type") or "").lower()

        return {
            "beds": float(beds) if beds is not None else None,
            "baths": float(baths) if baths is not None else None,
            "sqft": float(sqft) if sqft is not None else None,
            "num_units": int(num_units),
            "property_type": prop_type or "unknown",
        }

    # ---------------------------------------------------------
    # Comp filtering & normalization
    # ---------------------------------------------------------

    def _filter_comps(self) -> List[Dict]:
        """
        Basic filters:
        - distance <= max_distance_miles (if provided)
        - sqft within [min_sqft_ratio, max_sqft_ratio] of subject (if subject sqft present)
        """
        filtered = []
        subj_sqft = self._validated_subject.get("sqft")

        for comp in self.comps:
            price = comp.get("price")
            sqft = comp.get("sqft")
            dist = comp.get("distance_miles")

            if not price or not sqft:
                continue  # cannot use comps without price or sqft

            # Distance filter
            if dist is not None and dist > self.max_distance_miles:
                continue

            # Sqft filter
            if subj_sqft and sqft:
                ratio = sqft / subj_sqft
                if ratio < self.min_sqft_ratio or ratio > self.max_sqft_ratio:
                    continue

            filtered.append(comp)

        return filtered

    def _normalize_comp(self, comp: Dict) -> Dict:
        """
        Adds normalized fields:
        - price_per_sqft
        - price_per_unit
        - similarity_score (0–100; higher = more similar)
        """
        subj = self._validated_subject
        subj_beds = subj.get("beds")
        subj_baths = subj.get("baths")
        subj_sqft = subj.get("sqft")
        subj_units = subj.get("num_units")
        subj_type = subj.get("property_type")

        price = float(comp.get("price") or 0.0)
        sqft = float(comp.get("sqft") or 0.0)
        beds = comp.get("beds")
        baths = comp.get("baths")
        units = comp.get("num_units") or 1
        distance = comp.get("distance_miles") or 0.0
        prop_type = (comp.get("property_type") or "").lower()

        ppsf = price / sqft if sqft > 0 else None
        ppu = price / units if units > 0 else None

        # Similarity scoring (0–100)
        score = 100.0

        # Beds difference
        if subj_beds is not None and beds is not None:
            score -= abs(float(beds) - subj_beds) * 5.0

        # Baths difference
        if subj_baths is not None and baths is not None:
            score -= abs(float(baths) - subj_baths) * 4.0

        # Sqft ratio
        if subj_sqft and sqft:
            ratio = sqft / subj_sqft
            score -= abs(1.0 - ratio) * 30.0  # 30 points penalty per 100% variance

        # Units difference
        if subj_units and units:
            score -= abs(int(units) - subj_units) * 3.0

        # Property type mismatch
        if subj_type != "unknown" and prop_type and subj_type != prop_type:
            score -= 10.0

        # Distance penalty
        score -= min(distance, 5.0) * 2.0  # 2 points per mile up to 5 miles

        score = max(0.0, min(100.0, score))

        normalized = dict(comp)
        normalized.update(
            {
                "price_per_sqft": ppsf,
                "price_per_unit": ppu,
                "similarity_score": score,
            }
        )
        return normalized

    def _normalized_comps(self) -> List[Dict]:
        filtered = self._filter_comps()
        normalized = [self._normalize_comp(c) for c in filtered]
        # Sort by similarity_score descending
        normalized.sort(key=lambda c: c.get("similarity_score", 0.0), reverse=True)
        # Trim to target count
        return normalized[: self.target_comp_count]

    # ---------------------------------------------------------
    # Valuation statistics
    # ---------------------------------------------------------

    def _ppsf_stats(self, comps: List[Dict]) -> Dict:
        values = [c["price_per_sqft"] for c in comps if c.get("price_per_sqft")]
        if not values:
            return {"median_ppsf": None, "low_ppsf": None, "high_ppsf": None}

        values_sorted = sorted(values)
        med = median(values_sorted)
        low = values_sorted[max(0, int(len(values_sorted) * 0.20) - 1)]
        high = values_sorted[min(len(values_sorted) - 1, int(len(values_sorted) * 0.80))]
        return {
            "median_ppsf": med,
            "low_ppsf": low,
            "high_ppsf": high,
        }

    def _ppu_stats(self, comps: List[Dict]) -> Dict:
        values = [c["price_per_unit"] for c in comps if c.get("price_per_unit")]
        if not values:
            return {"median_ppu": None, "low_ppu": None, "high_ppu": None}

        values_sorted = sorted(values)
        med = median(values_sorted)
        low = values_sorted[max(0, int(len(values_sorted) * 0.20) - 1)]
        high = values_sorted[min(len(values_sorted) - 1, int(len(values_sorted) * 0.80))]
        return {
            "median_ppu": med,
            "low_ppu": low,
            "high_ppu": high,
        }

    def _subject_value_from_ppsf(self, ppsf: Optional[float]) -> Optional[float]:
        sqft = self._validated_subject.get("sqft")
        if ppsf is None or not sqft:
            return None
        return ppsf * sqft

    def _subject_value_from_ppu(self, ppu: Optional[float]) -> Optional[float]:
        units = self._validated_subject.get("num_units") or 1
        if ppu is None or units <= 0:
            return None
        return ppu * units

    # ---------------------------------------------------------
    # Public summary
    # ---------------------------------------------------------

    def summary(self) -> Dict:
        """
        Returns a dictionary with:
        - normalized_comps: list of comps with PPSF, PPU, similarity
        - stats: ppsf/ppu stats
        - value_estimates: low/base/high for the subject
        """
        comps_norm = self._normalized_comps()

        ppsf_stats = self._ppsf_stats(comps_norm)
        ppu_stats = self._ppu_stats(comps_norm)

        # Subject value estimates
        value_ppsf_med = self._subject_value_from_ppsf(ppsf_stats["median_ppsf"])
        value_ppu_med = self._subject_value_from_ppu(ppu_stats["median_ppu"])

        # Blend the two if both available; otherwise use whichever exists
        value_estimates: Dict[str, Optional[float]] = {
            "value_by_ppsf_median": value_ppsf_med,
            "value_by_ppu_median": value_ppu_med,
        }

        base_value_candidates = [v for v in [value_ppsf_med, value_ppu_med] if v]
        if base_value_candidates:
            base_value = sum(base_value_candidates) / len(base_value_candidates)
        else:
            base_value = None

        # Low/high bands (±7.5–10% around base, or based on low/high PPSF/PPU)
        low_values = [
            self._subject_value_from_ppsf(ppsf_stats["low_ppsf"]),
            self._subject_value_from_ppu(ppu_stats["low_ppu"]),
        ]
        high_values = [
            self._subject_value_from_ppsf(ppsf_stats["high_ppsf"]),
            self._subject_value_from_ppu(ppu_stats["high_ppu"]),
        ]
        low_candidates = [v for v in low_values if v]
        high_candidates = [v for v in high_values if v]

        value_estimates.update(
            {
                "base_value": base_value,
                "low_value": min(low_candidates) if low_candidates else None,
                "high_value": max(high_candidates) if high_candidates else None,
            }
        )

        return {
            "subject": self._validated_subject,
            "normalized_comps": comps_norm,
            "stats": {
                **ppsf_stats,
                **ppu_stats,
            },
            "value_estimates": value_estimates,
            "notes": "Sales comparison results are heuristic and should be benchmarked against professional appraisals.",
        }
