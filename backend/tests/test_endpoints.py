import sys
import requests
import json
from datetime import datetime
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

BASE_URL = "http://localhost:8000"

def test_company_endpoints():
    print("\n=== Testing Company Endpoints ===")
    
    # Create a company
    company_data = {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology"
    }
    
    print("\nCreating company...")
    response = requests.post(f"{BASE_URL}/api/v1/companies/", json=company_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json() if response.ok else response.text}")
    
    if response.status_code == 200:
        company_id = response.json()['id']
        
        # Get company by ID
        print("\nGetting company by ID...")
        response = requests.get(f"{BASE_URL}/api/v1/companies/{company_id}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json() if response.ok else response.text}")
        
        # Update company
        print("\nUpdating company...")
        update_data = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "sector": "Consumer Electronics"
        }
        response = requests.put(f"{BASE_URL}/api/v1/companies/{company_id}", json=update_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json() if response.ok else response.text}")

if __name__ == "__main__":
    # Test company endpoints
    test_company_endpoints()