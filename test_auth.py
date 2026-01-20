import requests

BASE_URL = 'https://graduation-project-production-be44.up.railway.app'

def test_login():
    url = f'{BASE_URL}/api/token/'
    data = {
        'username': 'teststudent',
        'email': 'test',
        'password': 'TestPassword123'
    }
    
    print(f"Attempting login to {url} with {data['email']}...")
    try:
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            tokens = response.json()
            print("Login successful!")
            
            # Verify refresh
            refresh_url = f'{BASE_URL}/api/token/refresh/'
            refresh_data = {'refresh': tokens.get('refresh')}
            print(f"Attempting token refresh...")
            refresh_response = requests.post(refresh_url, data=refresh_data)
            if refresh_response.status_code == 200:
                print("Token refresh successful!")
                print(f"New Access Token: {refresh_response.json().get('access')[:20]}...")
            else:
                 print(f"Token refresh failed: {refresh_response.status_code} - {refresh_response.text}")

            # Verify Logout (Blacklist)
            logout_url = f'{BASE_URL}/api/token/blacklist/'
            logout_data = {'refresh': tokens.get('refresh')}
            print(f"Attempting logout (blacklist refresh token)...")
            logout_response = requests.post(logout_url, data=logout_data)
            
            if logout_response.status_code == 200:
                 print("Logout successful (token blacklisted).")
                 
                 # Verify that refresh token is indeed invalid
                 print("Verifying refresh token is invalid...")
                 invalid_refresh_response = requests.post(refresh_url, data=refresh_data)
                 if invalid_refresh_response.status_code == 401:
                     print("Verification successful: Refresh token is invalid/blacklisted.")
                 else:
                     print(f"Verification failed: expected 401, got {invalid_refresh_response.status_code}")
            else:
                print(f"Logout failed: {logout_response.status_code} - {logout_response.text}")

        else:
            print(f"Login failed: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("Connection error. Make sure the server is running on localhost:8000")

if __name__ == '__main__':
    test_login()
