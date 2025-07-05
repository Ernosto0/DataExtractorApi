#!/usr/bin/env python3
"""
Test script for API marketplace provider security verification.
Run this script to test the security features.
"""

import requests
import json
import sys
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"
EXTRACT_ENDPOINT = f"{BASE_URL}/api/extract"

def test_request(headers=None, description=""):
    """Test a request with specific headers"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"{'='*60}")
    
    payload = {
        "text": "John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567",
        "fields": ["name", "address", "phone"]
    }
    
    try:
        response = requests.post(EXTRACT_ENDPOINT, json=payload, headers=headers or {})
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS")
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
        else:
            print("❌ FAILED")
            try:
                error_detail = response.json()
                print(f"Error: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Error: {response.text}")
                
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST FAILED: {e}")
        return False

def test_normal_request():
    """Test a normal request without any special headers"""
    return test_request(
        headers=None,
        description="Normal request (no special headers)"
    )

def test_zyla_request():
    """Test a request with Zyla headers"""
    current_time = datetime.now(timezone.utc).isoformat()
    
    return test_request(
        headers={
            "X-Zyla-Signature": "test-signature-12345",
            "X-Zyla-Timestamp": current_time,
            "User-Agent": "Zyla-API-Marketplace/1.0"
        },
        description="Zyla API Marketplace request"
    )

def test_rapidapi_request():
    """Test a request with RapidAPI headers"""
    return test_request(
        headers={
            "X-RapidAPI-Proxy-Secret": "1e7781f0-5911-11f0-a464-fb578da09ad0",
            "X-RapidAPI-User": "test-user-123",
            "X-RapidAPI-Host": "your-api.rapidapi.com"
        },
        description="RapidAPI request (with your actual secret)"
    )

def test_unauthorized_request():
    """Test a request that should be blocked"""
    return test_request(
        headers={
            "User-Agent": "UnauthorizedBot/1.0",
            "X-Suspicious-Header": "malicious-value"
        },
        description="Unauthorized request (should be blocked)"
    )

def check_server_status():
    """Check if the server is running"""
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ Server is running and accessible")
            return True
        else:
            print(f"❌ Server responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("❌ Server is not accessible")
        return False

def main():
    """Run all security tests"""
    print("🔒 API Marketplace Provider Security Test Suite")
    print("=" * 60)
    
    # Check if server is running
    if not check_server_status():
        print("\n❌ Cannot connect to server. Make sure your API is running on localhost:8000")
        sys.exit(1)
    
    # Run tests
    results = []
    
    # Test 1: Normal request
    results.append(("Normal Request", test_normal_request()))
    
    # Test 2: Zyla request
    results.append(("Zyla Request", test_zyla_request()))
    
    # Test 3: RapidAPI request
    results.append(("RapidAPI Request", test_rapidapi_request()))
    
    # Test 4: Unauthorized request
    results.append(("Unauthorized Request", test_unauthorized_request()))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:25} {status}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    # Interpretation
    print(f"\n{'='*60}")
    print("INTERPRETATION")
    print(f"{'='*60}")
    
    if results[0][1]:  # Normal request succeeded
        print("✅ Provider verification is DISABLED (development mode)")
        print("   - All requests are allowed")
        print("   - Good for development and testing")
        print("   - To enable security, set ENABLE_PROVIDER_VERIFICATION=true")
    else:
        print("🔒 Provider verification is ENABLED (production mode)")
        print("   - Only marketplace requests are allowed")
        print("   - Direct access is blocked")
        
        if results[1][1] or results[2][1]:  # Zyla or RapidAPI succeeded
            print("✅ Marketplace requests are working")
        else:
            print("❌ Marketplace requests are failing")
            print("   - Check your secret keys and IP ranges")
    
    print(f"\n{'='*60}")
    print("NEXT STEPS")
    print(f"{'='*60}")
    
    if results[0][1]:  # Verification disabled
        print("For production deployment:")
        print("1. Set ENABLE_PROVIDER_VERIFICATION=true in your .env file")
        print("2. Configure ZYLA_SECRET_KEY and RAPIDAPI_SECRET_KEY")
        print("3. Update IP ranges in security.py")
        print("4. Test with actual marketplace requests")
    else:
        print("Security is enabled. Make sure to:")
        print("1. Test with real marketplace requests")
        print("2. Monitor logs for verification failures")
        print("3. Keep IP ranges and secrets updated")

if __name__ == "__main__":
    main() 