"""
API Test Script
Tests the Distributed Translation System APIs
"""
import requests
import time
import json

BASE_URL = "http://localhost:5001"
FEEDBACK_URL = "http://localhost:5003"


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_login():
    """Test user authentication"""
    print_section("Testing Authentication")
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": "demo_user",
            "password": "demo_password"
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        token = response.json()["token"]
        print(f"\n✓ Authentication successful!")
        return token
    else:
        print(f"\n✗ Authentication failed!")
        return None


def test_translation(token):
    """Test translation request"""
    print_section("Testing Translation Request")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    translation_data = {
        "text": "Hello, how are you today?",
        "source_language": "en",
        "target_language": "de"
    }
    
    response = requests.post(
        f"{BASE_URL}/translate",
        headers=headers,
        json=translation_data
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code in [200, 202]:
        translation_id = response.json().get("translation_id")
        print(f"\n✓ Translation request submitted!")
        return translation_id
    else:
        print(f"\n✗ Translation request failed!")
        return None


def test_get_translation(token, translation_id):
    """Test getting translation status"""
    print_section("Testing Get Translation Status")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    max_attempts = 10
    for attempt in range(max_attempts):
        response = requests.get(
            f"{BASE_URL}/translation/{translation_id}",
            headers=headers
        )
        
        print(f"\nAttempt {attempt + 1}/{max_attempts}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "completed":
                print(f"\n✓ Translation completed!")
                print(f"Original: {data.get('original_text')}")
                print(f"Translated: {data.get('translated_text')}")
                return data
            elif data.get("status") == "failed":
                print(f"\n✗ Translation failed: {data.get('error_message')}")
                return None
        
        time.sleep(2)
    
    print(f"\n⚠ Translation still pending after {max_attempts} attempts")
    return None


def test_feedback_poll(token):
    """Test feedback polling"""
    print_section("Testing Feedback Polling")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{FEEDBACK_URL}/feedback/poll",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print(f"\n✓ Feedback polling successful!")
    else:
        print(f"\n✗ Feedback polling failed!")


def test_translation_history(token):
    """Test getting translation history"""
    print_section("Testing Translation History")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{BASE_URL}/translations/history?limit=5",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print(f"\n✓ Translation history retrieved!")
    else:
        print(f"\n✗ Failed to get translation history!")


def test_stats(token):
    """Test getting system statistics"""
    print_section("Testing System Statistics")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{BASE_URL}/stats",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print(f"\n✓ Statistics retrieved!")
    else:
        print(f"\n✗ Failed to get statistics!")


def test_observer_stats(token):
    """Test observer pattern statistics"""
    print_section("Testing Observer Pattern Statistics")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{FEEDBACK_URL}/observer/stats",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print(f"\n✓ Observer statistics retrieved!")
    else:
        print(f"\n✗ Failed to get observer statistics!")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  Distributed Translation System - API Tests")
    print("=" * 60)
    
    try:
        # Test 1: Login
        token = test_login()
        if not token:
            print("\n❌ Cannot proceed without authentication")
            return
        
        # Test 2: Submit translation
        translation_id = test_translation(token)
        if not translation_id:
            print("\n❌ Cannot proceed without translation ID")
            return
        
        # Test 3: Check translation status
        test_get_translation(token, translation_id)
        
        # Test 4: Feedback polling
        test_feedback_poll(token)
        
        # Test 5: Translation history
        test_translation_history(token)
        
        # Test 6: System statistics
        test_stats(token)
        
        # Test 7: Observer statistics
        test_observer_stats(token)
        
        print_section("All Tests Completed")
        print("✓ Testing complete!")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to services.")
        print("Make sure the services are running with: ./start.sh (or start.ps1 on Windows)")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    main()

