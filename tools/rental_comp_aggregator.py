"""
rental_comp_aggregator.py

Aggregates and analyzes rental comps from multiple sources
(e.g., Apartments.com parser output, manual input, other rental feeds).

Goals:
- Normalize rental comp structure
- Compute rent statistics by bedroom count
- Compute rent-per-sqft statistics
- Provide a recommended subject rent based on comps

Expected input formats:

1) Apartments.com parser output:
   {
       "success": True,
       "source": "apartments.com",
       "address_full": "...",
       "city": "...",
       "state": "...",
       "zip": "...",
       "unit_types": [
           {
               "beds": 0.0,
               "baths": 1.0,
               "sqft_min": 450,
               "sqft_max": 450,
               "rent_min": 1500,
               "rent_max": 1650
           },
           ...
       ],
       ...
   }

2) Manual comp format:
   {
       "beds": 2,
       "baths": 1,
       "sqft": 850,
       "rent": 2400,
       "source": "manual" or "craigslist" etc.
   }

This module standardizes these inputs into a list of comps like:

   {
       "beds": float or None,
       "baths": float or None,
       "sqft": int or None,
       "rent": float or None,
       "source": str or None
   }
"""

from typing import List, Dict, Optional
import statistics


class RentalCompAggregator:
    """
    Aggregates comps and calculates recommended market rent.

    Example usage:

        aggregator = RentalCompAggregator(
            subject_beds=2,
            subject_baths=1,
            subject_sqft=850
        )

        aggregator.add_comps_from_apartments(apartments_data)
        aggregator.add_manual_comp(beds=2, baths=1, sqft=800, rent=2350)

        summary = aggregator.summary()

        -> {
            "subject": {...},
            "overall_stats": {...},
            "by_bedroom": {...},
            "recommended_rent": {...}
        }
    """

    def __init__(
        self,
        subject_beds: Optional[float] = None,
        subject_baths: Optional[float] = None,
        subject_sqft: Optional[int] = None
    ):
        self.subject_beds = subject_beds
        self.subject_baths = subject_baths
        self.subject_sqft = subject_sqft
        self.comps: List[Dict] = []

    # ---------------------------------------------------------
    # Input normalization methods
    # ---------------------------------------------------------

    def add_comps_from_apartments(self, apartments_data: Dict, label: str = "apartments.com"):
        """
        Adds comps from Apartments.com parser output.
        """
        if not apartments_data or "unit_types" not in apartments_data:
            return

        for unit in apartments_data.get("unit_types", []):
            beds = unit.get("beds")
            baths = unit.get("baths")
            sqft_min = unit.get("sqft_min")
            sqft_max = unit.get("sqft_max")
            rent_min = unit.get("rent_min")
            rent_max = unit.get("rent_max")

            # Average sqft if range is provided
            sqft = None
            if sqft_min and sqft_max:
                sqft = int(round((sqft_min + sqft_max) / 2))
            elif sqft_min:
                sqft = sqft_min
            elif sqft_max:
                sqft = sqft_max

            # Average rent if range is provided
            rent = None
            if rent_min and rent_max:
                rent = round((rent_min + rent_max) / 2, 2)
            elif rent_min:
                rent = rent_min
            elif rent_max:
                rent = rent_max

            self.comps.append(
                {
                    "beds": beds,
                    "baths": baths,
                    "sqft": sqft,
                    "rent": rent,
                    "source": label
                }
            )

    def add_manual_comp(
        self,
        beds: Optional[float],
        baths: Optional[float],
        sqft: Optional[int],
        rent: Optional[float],
        source: str = "manual"
    ):
        """
        Adds a single manually-defined comp.
        """
        self.comps.append(
            {
                "beds": beds,
                "baths": baths,
                "sqft": sqft,
                "rent": rent,
                "source": source
            }
        )

    def add_many_manual_comps(self, comp_list: List[Dict]):
        """
        Adds multiple manual comps at once.

        Each comp dict should have keys:
            beds, baths, sqft, rent, source (source optional)
        """
        for c in comp_list:
            self.add_manual_comp(
                beds=c.get("beds"),
                baths=c.get("baths"),
                sqft=c.get("sqft"),
                rent=c.get("rent"),
                source=c.get("source", "manual")
            )

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    def _filter_valid_rent_comps(self) -> List[Dict]:
        """
        Returns comps that have at least a rent value.
        """
        return [c for c in self.comps if c.get("rent") is not None]

    def _rent_per_sqft_list(self) -> List[float]:
        rps_list = []
        for c in self.comps:
            rent = c.get("rent")
            sqft = c.get("sqft")
            if rent and sqft and sqft > 0:
                rps_list.append(rent / sqft)
        return rps_list

    # ---------------------------------------------------------
    # Statistical calculations
    # ---------------------------------------------------------

    def overall_stats(self) -> Dict:
        """
        Computes overall rent statistics across all comps.
        """
        valid_comps = self._filter_valid_rent_comps()
        rents = [c["rent"] for c in valid_comps if c["rent"] is not None]

        if not rents:
            return {
                "count": 0,
                "rent_min": None,
                "rent_max": None,
                "rent_avg": None,
                "rent_median": None,
                "rent_per_sqft_avg": None,
            }

        rent_min = min(rents)
        rent_max = max(rents)
        rent_avg = round(statistics.mean(rents), 2)
        rent_median = round(statistics.median(rents), 2)

        rps_list = self._rent_per_sqft_list()
        rps_avg = round(statistics.mean(rps_list), 4) if rps_list else None

        return {
            "count": len(rents),
            "rent_min": rent_min,
            "rent_max": rent_max,
            "rent_avg": rent_avg,
            "rent_median": rent_median,
            "rent_per_sqft_avg": rps_avg,
        }

    def stats_by_bedroom(self) -> Dict:
        """
        Computes rent stats grouped by bedroom count.
        """
        grouped: Dict[float, List[float]] = {}
        for c in self._filter_valid_rent_comps():
            beds = c.get("beds")
            rent = c.get("rent")
            if beds is None or rent is None:
                continue
            grouped.setdefault(beds, []).append(rent)

        result = {}
        for beds, rents in grouped.items():
            if not rents:
                continue
            result[beds] = {
                "count": len(rents),
                "rent_min": min(rents),
                "rent_max": max(rents),
                "rent_avg": round(statistics.mean(rents), 2),
                "rent_median": round(statistics.median(rents), 2),
            }

        return result

    # ---------------------------------------------------------
    # Recommended rent for subject
    # ---------------------------------------------------------

    def _recommended_rent_for_subject(self) -> Dict:
        """
        Uses:
        - bedroom-matched comps (exact match)
        - fallback to +/- 1 bedroom
        - optional rent-per-sqft logic if subject_sqft available
        """
        if self.subject_beds is None:
            # Without bed count, we fall back to overall stats
            overall = self.overall_stats()
            return {
                "method": "overall_only",
                "rent_estimate": overall.get("rent_avg"),
                "details": overall
            }

        # 1) Exact bed match
        exact_rents = [
            c["rent"]
            for c in self._filter_valid_rent_comps()
            if c.get("beds") == self.subject_beds and c.get("rent") is not None
        ]

        # 2) +/- 1 bed fallback
        close_rents = [
            c["rent"]
            for c in self._filter_valid_rent_comps()
            if c.get("beds") is not None
            and abs(c.get("beds") - self.subject_beds) <= 1
            and c.get("rent") is not None
        ]

        if exact_rents:
            base_estimate = round(statistics.mean(exact_rents), 2)
            method = "exact_bed_match"
        elif close_rents:
            base_estimate = round(statistics.mean(close_rents), 2)
            method = "plus_minus_one_bed"
        else:
            overall = self.overall_stats()
            return {
                "method": "fallback_overall",
                "rent_estimate": overall.get("rent_avg"),
                "details": overall
            }

        # If we have subject sqft and rent-per-sqft, refine
        if self.subject_sqft and self.subject_sqft > 0:
            rps_list = self._rent_per_sqft_list()
            if rps_list:
                avg_rps = statistics.mean(rps_list)
                sqft_based_estimate = round(avg_rps * self.subject_sqft, 2)

                # average of bedroom-based and sqft-based
                combined = round((base_estimate + sqft_based_estimate) / 2, 2)
                return {
                    "method": f"{method}_with_rent_per_sqft_adjustment",
                    "rent_estimate": combined,
                    "bed_based_estimate": base_estimate,
                    "sqft_based_estimate": sqft_based_estimate,
                }

        # No sqft refinement
        return {
            "method": method,
            "rent_estimate": base_estimate,
            "bed_based_estimate": base_estimate,
            "sqft_based_estimate": None,
        }

    # ---------------------------------------------------------
    # Public summary
    # ---------------------------------------------------------

    def summary(self) -> Dict:
        """
        High-level summary suitable for input to income models.
        """
        overall = self.overall_stats()
        by_bed = self.stats_by_bedroom()
        recommended = self._recommended_rent_for_subject()

        subject_info = {
            "beds": self.subject_beds,
            "baths": self.subject_baths,
            "sqft": self.subject_sqft,
        }

        return {
            "subject": subject_info,
            "overall_stats": overall,
            "by_bedroom": by_bed,
            "recommended_rent": recommended,
            "comp_count": len(self._filter_valid_rent_comps()),
        }
