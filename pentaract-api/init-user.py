"""
Initialize Pentaract user from environment variables
"""
import os
import time
import requests
import sys

def wait_for_api(max_attempts=30):
    """Wait for API to be ready"""
    print("⏳ Waiting for Pentaract API to be ready...")
    for i in range(max_attempts):
        try:
            response = requests.get("http://localhost:8547/api/health", timeout=2)
            if response.status_code == 200:
                print("✅ Pentaract API is ready!")
                return True
        except Exception:
            pass
        print(f"   Attempt {i+1}/{max_attempts}...")
        time.sleep(2)
    return False

def create_user():
    """Create user from environment variables"""
    email = os.getenv("PENTARACT_EMAIL")
    password = os.getenv("PENTARACT_PASSWORD")
    username = os.getenv("PENTARACT_USERNAME", "admin")
    
    if not email or not password:
        print("❌ PENTARACT_EMAIL and PENTARACT_PASSWORD must be set")
        return False
    
    print(f"👤 Creating Pentaract user: {email}")
    
    try:
        response = requests.post(
            "http://localhost:8547/api/auth/register",
            json={
                "email": email,
                "password": password,
                "username": username
            },
            timeout=5
        )
        
        if response.status_code == 201 or response.status_code == 200:
            print(f"✅ User created successfully: {email}")
            return True
        elif response.status_code == 400 and "already exists" in response.text.lower():
            print(f"ℹ️  User already exists: {email}")
            return True
        else:
            print(f"❌ Failed to create user: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Pentaract User Initialization")
    print("=" * 50)
    
    if not wait_for_api():
        print("❌ API not ready after 30 attempts")
        sys.exit(1)
    
    if not create_user():
        print("❌ Failed to create user")
        sys.exit(1)
    
    print("=" * 50)
    print("✅ Initialization complete!")

if __name__ == "__main__":
    main()
