class ValuationService:
    # Змініть цей символ на "€" або "£", якщо у вас в Discogs налаштована інша валюта
    CURRENCY_SYMBOL = "€"

    # Multipliers based on condition (Base = VG+)
    CONDITIONS = {
        "Mint": 1.2,
        "NM": 1.1,
        "VG+": 1.0,
        "VG": 0.8,
        "G": 0.6
    }

    @staticmethod
    def calculate_smart_value(
        lowest_price: float | None, 
        median_price: float | None,
        highest_price: float | None,
        num_for_sale: int | None, 
        have_count: int | None, 
        want_count: int | None
    ):
        """
        Calculates the Smart Market Value range (VG+ to NM) based on available data.
        Uses median_price (VG+) as base if available, otherwise derives from lowest_price.
        """
        # Normalize inputs
        num_for_sale = num_for_sale or 0
        have_count = have_count or 0
        want_count = want_count or 0

        base_price = 0.0
        
        # Step 1: Determine Base Price
        if median_price and median_price > 0:
            base_price = median_price
        elif lowest_price and lowest_price > 0:
            # Fallback: treat lowest_price as roughly 0.8 of the VG+ price
            base_price = lowest_price / 0.8
        else:
            return None

        # Step 2: Market Skew Correction
        # If difference between lowest and median > 50% -> market skewed
        if lowest_price and median_price and median_price > 0:
            if (median_price - lowest_price) / median_price > 0.5:
                # Market is skewed (cheap copies available vs high median)
                # We adjust base price slightly downwards to be realistic
                base_price *= 0.9
        
        # If very few items for sale, the price might be unstable
        if num_for_sale < 3:
            # Conservative adjustment for low liquidity
            base_price *= 0.9

        # Step 3: Demand Adjustment
        demand_ratio = 0.0
        if have_count > 0:
            demand_ratio = want_count / have_count
            
            if demand_ratio > 0.25:
                # High demand
                base_price *= 1.10
            elif demand_ratio < 0.1:
                # Low demand
                base_price *= 0.95

        # Sanity check: Base price (VG+) should not exceed known Highest Price (Mint) significantly
        if highest_price and highest_price > 0 and base_price > highest_price:
            base_price = highest_price * 0.95

        # Step 4: Calculate Range (VG+ to NM)
        val_vg_plus = base_price * ValuationService.CONDITIONS["VG+"]
        val_nm = base_price * ValuationService.CONDITIONS["NM"]

        return {
            "min": round(val_vg_plus, 2),
            "max": round(val_nm, 2),
            "avg": round((val_vg_plus + val_nm) / 2, 2),
            "demand_ratio": round(demand_ratio, 2),
            "currency": ValuationService.CURRENCY_SYMBOL
        }