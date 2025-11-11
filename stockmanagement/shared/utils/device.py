"""Device detection utilities."""

from __future__ import annotations


def detect_device_type(user_agent: str | None) -> str | None:
    """
    Detect device type from user agent string.
    
    Args:
        user_agent: User agent string from HTTP request
        
    Returns:
        Device type: "mobile", "tablet", or "desktop", or None if cannot be determined
    """
    if not user_agent:
        return None
    
    user_agent_lower = user_agent.lower()
    
    # Mobile devices
    mobile_keywords = [
        "mobile",
        "android",
        "iphone",
        "ipod",
        "blackberry",
        "windows phone",
        "opera mini",
        "iemobile",
        "mobile safari",
    ]
    
    # Tablet devices
    tablet_keywords = [
        "tablet",
        "ipad",
        "playbook",
        "kindle",
        "silk",
        "nexus 7",
        "nexus 10",
        "galaxy tab",
        "surface",
    ]
    
    # Check for tablets first (more specific)
    for keyword in tablet_keywords:
        if keyword in user_agent_lower:
            return "tablet"
    
    # Check for mobile devices
    for keyword in mobile_keywords:
        if keyword in user_agent_lower:
            return "mobile"
    
    # Default to desktop if no mobile/tablet indicators found
    return "desktop"


def get_or_detect_device_type(
    provided_device_type: str | None, user_agent: str | None
) -> str | None:
    """
    Get device type from frontend or detect it automatically from user agent.
    
    Args:
        provided_device_type: Device type provided by frontend (optional)
        user_agent: User agent string from HTTP request
        
    Returns:
        Device type: "mobile", "tablet", or "desktop", or None if cannot be determined
    """
    # Use provided device type if available and not empty
    if provided_device_type and provided_device_type.strip():
        return provided_device_type.strip().lower()
    
    # Otherwise, detect from user agent
    return detect_device_type(user_agent)
