import requests
import json

# URL của API
url = "http://localhost:8000/api/adjust-pose"

# Dữ liệu test
payload = {
    "input_rel_path": "/uploads/2025/09/30/origin/9ee92bc7-134b-5791-bfef-8afeb034fd46_20250430000646_074_LMGI_POSE_LABEL_PRIOR.rrd",
    "xyz": [0.1, 0.0, -0.05],  # Dịch chuyển 10cm theo X, 5cm xuống theo Z
    "rpy": [0, 0, 5]  # Quay 5 độ theo trục Z (yaw)
}

# Headers
headers = {
    "Content-Type": "application/json"
}

try:
    # Send request
    print("Sending request...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(url, json=payload, headers=headers)
    
    # Check result
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("SUCCESS!")
        print(f"Output URL: {result['output_url']}")
        print(f"Full Response: {json.dumps(result, indent=2)}")
    else:
        print("ERROR!")
        print(f"Error: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("ERROR: Cannot connect to server!")
    print("Make sure server is running on http://localhost:8000")
except Exception as e:
    print(f"ERROR: {e}")
