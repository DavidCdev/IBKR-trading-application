from typing import Union, Tuple
from .logger import get_logger
logger = get_logger("TICK_SIZE_VALIDATOR")

class TickSizeValidator:
    """
    Validates and rounds option prices to conform to IBKR tick size requirements.

    IBKR tick size rules for options:
    - Options trading below $3.00: minimum tick size is $0.05
    - Options trading at $3.00 or higher: minimum tick size is $0.10
    """
    
    # Tick size thresholds and increments
    TICK_SIZE_BELOW_3 = 0.05
    TICK_SIZE_3_AND_ABOVE = 0.10
    PRICE_THRESHOLD = 3.00
    
    @classmethod
    def get_tick_size(cls, price: float) -> float:
        """
        Get the appropriate tick size for a given option price.
        
        Args:
            price: The option price in dollars
            
        Returns:
            The minimum tick size (0.05 or 0.10)
        """
        if price < cls.PRICE_THRESHOLD:
            return cls.TICK_SIZE_BELOW_3
        else:
            return cls.TICK_SIZE_3_AND_ABOVE
    
    @classmethod
    def round_to_valid_tick(cls, price: float) -> float:
        """
        Round a price to the nearest valid tick size.
        
        Args:
            price: The option price to round
            
        Returns:
            The rounded price that conforms to tick size requirements
        """
        try:
            if price <= 0:
                logger.warning(f"Invalid price {price}, cannot round to tick size")
                return price
            
            tick_size = cls.get_tick_size(price)
            
            # Round to nearest tick size
            if tick_size == cls.TICK_SIZE_BELOW_3:
                # For $0.05 ticks, multiply by 20, round, then divide by 20
                rounded_price = round(price * 20) / 20
            else:
                # For $0.10 ticks, multiply by 10, round, then divide by 10
                rounded_price = round(price * 10) / 10
            
            # Ensure we don't go below minimum price
            if rounded_price < 0.01:
                rounded_price = 0.01
            
            if rounded_price != price:
                logger.info(f"Rounded price from ${price:.4f} to ${rounded_price:.2f} (tick size: ${tick_size:.2f})")
            
            return rounded_price
            
        except Exception as e:
            logger.error(f"Error rounding price {price} to tick size: {e}")
            return price
    
    @classmethod
    def validate_price(cls, price: float) -> Tuple[bool, str]:
        """
        Validate if a price conforms to tick size requirements.
        
        Args:
            price: The option price to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if price <= 0:
                return False, f"Price {price} must be positive"
            
            tick_size = cls.get_tick_size(price)
            
            # Check if price is a multiple of the tick size
            if tick_size == cls.TICK_SIZE_BELOW_3:
                # Check if price is multiple of $0.05
                if abs(price * 20 - round(price * 20)) > 0.001:
                    return False, f"Price ${price:.4f} must be multiple of ${tick_size:.2f}"
            else:
                # Check if price is multiple of $0.10
                if abs(price * 10 - round(price * 10)) > 0.001:
                    return False, f"Price ${price:.4f} must be multiple of ${tick_size:.2f}"
            
            return True, "Price is valid"
            
        except Exception as e:
            logger.error(f"Error validating price {price}: {e}")
            return False, f"Validation error: {str(e)}"
    
    @classmethod
    def get_valid_price_range(cls, target_price: float, tolerance: float = 0.01) -> Tuple[float, float]:
        """
        Get a range of valid prices around a target price.
        
        Args:
            target_price: The target price
            tolerance: How far from target to look for valid prices
            
        Returns:
            Tuple of (min_valid_price, max_valid_price)
        """
        try:
            tick_size = cls.get_tick_size(target_price)
            
            # Find the nearest valid price below target
            min_price = target_price - tolerance
            min_valid_price = cls.round_to_valid_tick(min_price)
            
            # Find the nearest valid price above target
            max_price = target_price + tolerance
            max_valid_price = cls.round_to_valid_tick(max_price)
            
            # Ensure we don't go below minimum
            min_valid_price = max(0.01, min_valid_price)
            
            logger.debug(f"Valid price range for ${target_price:.4f}: ${min_valid_price:.2f} - ${max_valid_price:.2f}")
            return min_valid_price, max_valid_price
            
        except Exception as e:
            logger.error(f"Error getting valid price range for {target_price}: {e}")
            return target_price, target_price
    
    @classmethod
    def suggest_valid_price(cls, target_price: float, prefer_higher: bool = False) -> float:
        """
        Suggest a valid price close to the target price.
        
        Args:
            target_price: The target price
            prefer_higher: If True, prefer rounding up; if False, prefer rounding down
            
        Returns:
            A valid price close to the target
        """
        try:
            tick_size = cls.get_tick_size(target_price)
            
            if prefer_higher:
                # Round up to next valid tick
                if tick_size == cls.TICK_SIZE_BELOW_3:
                    suggested_price = (int(target_price * 20 + 0.5) + 1) / 20
                else:
                    suggested_price = (int(target_price * 10 + 0.5) + 1) / 10
            else:
                # Round down to previous valid tick
                if tick_size == cls.TICK_SIZE_BELOW_3:
                    suggested_price = int(target_price * 20) / 20
                else:
                    suggested_price = int(target_price * 10) / 10
            
            # Ensure minimum price
            suggested_price = max(0.01, suggested_price)
            
            logger.info(f"Suggested valid price for ${target_price:.4f}: ${suggested_price:.2f} (prefer_higher={prefer_higher})")
            return suggested_price
            
        except Exception as e:
            logger.error(f"Error suggesting valid price for {target_price}: {e}")
            return cls.round_to_valid_tick(target_price)


def validate_and_round_price(price: float, context: str = "") -> float:
    """
    Convenience function to validate and round a price to valid tick size.
    
    Args:
        price: The option price to validate and round
        context: Optional context for logging
        
    Returns:
        The rounded price that conforms to tick size requirements
    """
    try:
        validator = TickSizeValidator()
        
        # Validate the price first
        is_valid, message = validator.validate_price(price)
        
        if not is_valid:
            logger.warning(f"Price validation failed for {context}: {message}")
            # Round to valid tick size
            rounded_price = validator.round_to_valid_tick(price)
            logger.info(f"Rounded invalid price {price} to valid tick size: {rounded_price}")
            return rounded_price
        
        # Price is already valid, but ensure it's properly rounded
        rounded_price = validator.round_to_valid_tick(price)
        return rounded_price
        
    except Exception as e:
        logger.error(f"Error in validate_and_round_price for {price}: {e}")
        return price


def get_tick_size_info(price: float) -> dict:
    """
    Get detailed information about tick size requirements for a price.
    
    Args:
        price: The option price
        
    Returns:
        Dictionary with tick size information
    """
    try:
        validator = TickSizeValidator()
        tick_size = validator.get_tick_size(price)
        is_valid, message = validator.validate_price(price)
        
        info = {
            'price': price,
            'tick_size': tick_size,
            'is_valid': is_valid,
            'validation_message': message,
            'rounded_price': validator.round_to_valid_tick(price),
            'price_threshold': validator.PRICE_THRESHOLD,
            'below_threshold_tick': validator.TICK_SIZE_BELOW_3,
            'above_threshold_tick': validator.TICK_SIZE_3_AND_ABOVE
        }
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting tick size info for {price}: {e}")
        return {'error': str(e)}
