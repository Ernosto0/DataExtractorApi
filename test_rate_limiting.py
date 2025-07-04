#!/usr/bin/env python3
"""
Test script for verifying rate limiting functionality.
Run this script to test both normal operation and rate limit enforcement.
"""

import requests
import time
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
EXTRACT_ENDPOINT = f"{BASE_URL}/api/extract"

def test_normal_request(use_api_key=False):
    """Test a normal extraction request"""
    print(f"\n{'='*50}")
    print(f"Testing normal request (API key: {use_api_key})")
    print(f"{'='*50}")
    
    payload = {
        "text": "John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567",
        "fields": ["name", "address", "phone"]
    }
    
    if use_api_key:
        payload["apikey"] = "test-api-key-123"
    
    try:
        response = requests.post(EXTRACT_ENDPOINT, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False

def test_rate_limiting(num_requests=15, delay=0.1):
    """Test rate limiting by sending multiple requests quickly"""
    print(f"\n{'='*50}")
    print(f"Testing rate limiting with {num_requests} requests")
    print(f"{'='*50}")
    
    payload = {
        "text": "Test message for rate limiting",
        "fields": ["test"]
    }
    
    success_count = 0
    rate_limited_count = 0
    
    for i in range(1, num_requests + 1):
        try:
            start_time = time.time()
            response = requests.post(EXTRACT_ENDPOINT, json=payload)
            end_time = time.time()
            
            status = response.status_code
            if status == 200:
                success_count += 1
                print(f"Request {i:2d}: ✅ SUCCESS (200) - {end_time - start_time:.2f}s")
            elif status == 429:
                rate_limited_count += 1
                print(f"Request {i:2d}: 🚫 RATE LIMITED (429)")
            else:
                print(f"Request {i:2d}: ❌ ERROR ({status}) - {response.text}")
                
            time.sleep(delay)
            
        except requests.exceptions.RequestException as e:
            print(f"Request {i:2d}: ❌ FAILED - {e}")
    
    print(f"\n📊 Results:")
    print(f"   Successful requests: {success_count}")
    print(f"   Rate limited requests: {rate_limited_count}")
    print(f"   Total requests: {num_requests}")
    
    if rate_limited_count > 0:
        print("✅ Rate limiting is working correctly!")
    else:
        print("⚠️  Rate limiting may not be working - no 429 responses received")

def check_server_status():
    """Check if the server is running"""
    print("Checking server status...")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("❌ Server is not reachable")
        print("   Make sure to start the server with: uvicorn main:app --reload")
        return False

def main():
    print(f"Rate Limiting Test Script")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {BASE_URL}")
    
    if not check_server_status():
        sys.exit(1)
    
    # Test normal operation
    print("\n1. Testing normal operation...")
    test_normal_request(use_api_key=False)
    
    # Wait a bit to reset rate limit
    print("\nWaiting 5 seconds before rate limit test...")
    time.sleep(5)
    
    # Test rate limiting
    print("\n2. Testing rate limiting...")
    test_rate_limiting(num_requests=15, delay=0.1)
    
    print(f"\n{'='*50}")
    print("Test completed!")
    print("If rate limiting is working, you should see some 429 responses.")
    print("If all requests succeed, rate limiting may not be active.")
    print(f"{'='*50}")

if __name__ == "__main__":
    main() 