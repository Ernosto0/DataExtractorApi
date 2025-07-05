"""
Security utilities for API marketplace provider verification.
This module handles verification of requests from trusted API marketplace platforms.
"""

import os
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Environment variables for security configuration
ENABLE_PROVIDER_VERIFICATION = os.getenv("ENABLE_PROVIDER_VERIFICATION", "false").lower() == "true"
ZYLA_SECRET_KEY = os.getenv("ZYLA_SECRET_KEY", "")
RAPIDAPI_SECRET_KEY = os.getenv("RAPIDAPI_SECRET_KEY", "1e7781f0-5911-11f0-a464-fb578da09ad0")

# Trusted IP ranges for API marketplaces
# Note: RapidAPI uses rapidapi.com gateway DNS, but specific IP ranges are not publicly documented
# For maximum security, you may need to contact RapidAPI support for their current IP ranges
ZYLA_IP_RANGES = [
    # Zyla API marketplace IP ranges
    "100.64.0.4",       # Your Railway internal IP
    "34.204.78.119",    # Zyla's external IP (from X-Forwarded-For)
    "34.204.78.0/24",   # Zyla's IP range (AWS us-east-1)
]

RAPIDAPI_IP_RANGES = [
    # RapidAPI uses rapidapi.com gateway - specific IP ranges not publicly documented
    # For production, contact RapidAPI support for current IP ranges
    # Common cloud provider ranges that RapidAPI might use:
    "52.0.0.0/8",      # AWS ranges (RapidAPI may use AWS infrastructure)
    "54.0.0.0/8",      # AWS ranges  
    "34.0.0.0/8",      # Google Cloud ranges
    "35.0.0.0/8",      # Google Cloud ranges
    "13.0.0.0/8",      # Azure ranges
    "20.0.0.0/8",      # Azure ranges
    "40.0.0.0/8",      # Azure ranges
    "104.16.0.0/13",   # Cloudflare ranges
    "104.24.0.0/14",   # Cloudflare ranges
    "172.64.0.0/13",   # Cloudflare ranges
    "131.0.72.0/22",   # Cloudflare ranges
]

class ProviderVerificationError(Exception):
    """Exception raised when provider verification fails"""
    pass

def is_ip_in_range(ip: str, ip_ranges: list) -> bool:
    """
    Check if an IP address is within any of the specified ranges.
    """
    try:
        import ipaddress
        
        if not ip or ip == "unknown":
            return False
            
        ip_obj = ipaddress.ip_address(ip)
        
        for ip_range in ip_ranges:
            try:
                # Handle both single IPs and CIDR ranges
                if '/' in ip_range:
                    network = ipaddress.ip_network(ip_range, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    # Single IP address
                    if ip_obj == ipaddress.ip_address(ip_range):
                        return True
            except ValueError:
                logger.warning(f"Invalid IP range format: {ip_range}")
                continue
                
        return False
        
    except Exception as e:
        logger.error(f"Error checking IP range for {ip}: {e}")
        return False

def verify_zyla_request(request: Request) -> bool:
    """
    Verify that the request is coming from Zyla API marketplace.
    
    Zyla doesn't use API keys like RapidAPI. Instead, we verify based on:
    - IP address (requests come from Zyla's infrastructure)
    - User-Agent pattern (GuzzleHttp)
    - Request characteristics
    
    Args:
        request: FastAPI Request object
        
    Returns:
        bool: True if request is verified as coming from Zyla
    """
    try:
        user_agent = request.headers.get("User-Agent", "")
        
        # Get the real source IP address
        # Zyla requests come through proxies, so check forwarded headers
        forwarded_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP", "")
        client_ip = request.client.host if request.client else "unknown"
        
        # Use the most reliable IP source
        source_ip = forwarded_ip or real_ip or client_ip
        
        # Check if request has Zyla characteristics
        has_guzzle_agent = "GuzzleHttp" in user_agent
        has_zyla_ip = source_ip in ["34.204.78.119"] or is_ip_in_range(source_ip, ZYLA_IP_RANGES)
        
        # Look for any Zyla-specific headers (they might use x-zyla-api-key as a placeholder)
        has_zyla_header = any(header.lower().startswith('x-zyla') for header in request.headers.keys())
        
        # Verify based on multiple factors
        if has_zyla_ip and has_guzzle_agent:
            logger.info(f"Zyla request verified by IP and User-Agent - IP: {source_ip}, UA: {user_agent}")
            return True
        
        if has_zyla_ip and has_zyla_header:
            logger.info(f"Zyla request verified by IP and headers - IP: {source_ip}")
            return True
            
        if has_zyla_ip:
            logger.info(f"Zyla request verified by IP address - IP: {source_ip}")
            return True
            
        logger.warning(f"Zyla verification failed - IP: {source_ip}, UA: {user_agent}, Headers: {list(request.headers.keys())}")
        return False
        
    except Exception as e:
        logger.error(f"Error verifying Zyla request: {e}")
        return False

def verify_rapidapi_request(request: Request) -> bool:
    """
    Verify that the request is coming from RapidAPI marketplace.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        bool: True if request is verified as coming from RapidAPI
    """
    try:
        # Check for RapidAPI-specific headers
        rapidapi_proxy_secret = request.headers.get("X-RapidAPI-Proxy-Secret")
        rapidapi_user = request.headers.get("X-RapidAPI-User")
        
        if not rapidapi_proxy_secret:
            logger.warning("Missing RapidAPI verification headers")
            return False
            
        # Verify proxy secret if configured
        if RAPIDAPI_SECRET_KEY:
            if rapidapi_proxy_secret != RAPIDAPI_SECRET_KEY:
                logger.warning("RapidAPI proxy secret verification failed")
                return False
                
        # Check IP range
        client_ip = request.client.host if request.client else "unknown"
        if not is_ip_in_range(client_ip, RAPIDAPI_IP_RANGES):
            logger.warning(f"Request from non-RapidAPI IP: {client_ip}")
            return False
            
        logger.info(f"RapidAPI request verified successfully for user: {rapidapi_user}")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying RapidAPI request: {e}")
        return False

def verify_trusted_provider(request: Request) -> Dict[str, Any]:
    """
    Verify that the request is coming from a trusted API marketplace provider.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Dict containing verification result and provider info
        
    Raises:
        HTTPException: If verification is enabled and request is not from trusted provider
    """
    if not ENABLE_PROVIDER_VERIFICATION:
        return {
            "verified": True,
            "provider": "verification_disabled",
            "reason": "Provider verification is disabled"
        }
    
    # Check for Zyla
    if verify_zyla_request(request):
        return {
            "verified": True,
            "provider": "zyla",
            "reason": "Verified Zyla API marketplace request"
        }
    
    # Check for RapidAPI
    if verify_rapidapi_request(request):
        return {
            "verified": True,
            "provider": "rapidapi",
            "reason": "Verified RapidAPI marketplace request"
        }
    
    # Check if request is from local/direct access (for testing)
    client_ip = request.client.host if request.client else "unknown"
    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return {
            "verified": True,
            "provider": "local",
            "reason": "Local development request"
        }
    
    # If we get here, the request is not from a trusted provider
    verification_result = {
        "verified": False,
        "provider": "unknown",
        "reason": "Request not from trusted API marketplace provider",
        "client_ip": client_ip,
        "headers": dict(request.headers)
    }
    
    logger.warning(f"Untrusted request blocked: {verification_result}")
    
    raise HTTPException(
        status_code=403,
        detail={
            "message": "Access denied",
            "error": "Request must come from authorized API marketplace provider",
            "code": "UNAUTHORIZED_PROVIDER",
            "suggestion": "Use the API through Zyla or RapidAPI marketplace"
        }
    )

def get_provider_info(request: Request) -> Dict[str, Any]:
    """
    Get information about the API marketplace provider without enforcing verification.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Dict containing provider information
    """
    try:
        verification_result = verify_trusted_provider(request)
        return verification_result
    except HTTPException:
        # Return unknown provider info without raising exception
        return {
            "verified": False,
            "provider": "unknown",
            "reason": "Request not from trusted provider"
        }

# Middleware function to add provider verification to all API endpoints
async def provider_verification_middleware(request: Request, call_next):
    """
    Middleware to verify API marketplace providers for all API endpoints.
    """
    # Only apply to API endpoints
    if request.url.path.startswith("/api/"):
        try:
            provider_info = verify_trusted_provider(request)
            # Add provider info to request state for logging
            request.state.provider_info = provider_info
        except HTTPException as e:
            # Return the HTTP exception response
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=e.status_code,
                content=e.detail
            )
    
    # Continue with the request
    response = await call_next(request)
    return response 