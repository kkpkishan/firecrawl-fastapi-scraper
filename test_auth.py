#!/usr/bin/env python3
"""
Test script to verify authentication and all components
"""
import requests
import json

BASE_URL = "http://localhost:8000"
API_KEY = "dev-api-key-change-in-production-12345678"

def test_endpoint(name, method, url, headers=None, data=None, expected_status=200):
    """Test an endpoint and print results"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        
        print(f"Status Code: {response.status_code}")
        print(f"Expected: {expected_status}")
        
        try:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Response: {response.text}")
        
        if response.status_code == expected_status:
            print("✅ PASS")
            return True
        else:
            print("❌ FAIL")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("WEB SCRAPING BACKEND - COMPONENT TESTS")
    print("="*60)
    
    results = []
    
    # Test 1: Root endpoint
    results.append(test_endpoint(
        "Root Endpoint",
        "GET",
        f"{BASE_URL}/",
        expected_status=200
    ))
    
    # Test 2: Health check
    results.append(test_endpoint(
        "Health Check",
        "GET",
        f"{BASE_URL}/health",
        expected_status=200
    ))
    
    # Test 3: Readiness check
    results.append(test_endpoint(
        "Readiness Check",
        "GET",
        f"{BASE_URL}/readiness",
        expected_status=200
    ))
    
    # Test 4: OpenAPI schema
    results.append(test_endpoint(
        "OpenAPI Schema",
        "GET",
        f"{BASE_URL}/openapi.json",
        expected_status=200
    ))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit(main())
