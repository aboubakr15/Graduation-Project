import requests

BASE_URL = 'https://graduation-project-production-be44.up.railway.app'

def test_login():
    url = f'{BASE_URL}/api/token/'
    data = {
        'email': 'test@test.com',
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
                new_tokens = refresh_response.json()
                print(f"New Access Token: {new_tokens.get('access')[:20]}...")
                
                # IMPORTANT: With rotate refresh tokens on, we get a new refresh token
                # We must use THIS new token for logout if blacklist after rotation is on
                refresh_token_to_logout = new_tokens.get('refresh') if 'refresh' in new_tokens else tokens.get('refresh')
            else:
                 print(f"Token refresh failed: {refresh_response.status_code} - {refresh_response.text}")
                 refresh_token_to_logout = tokens.get('refresh')

            # Verify Logout (Blacklist)
            logout_url = f'{BASE_URL}/api/token/blacklist/'
            logout_data = {'refresh': refresh_token_to_logout}
            print(f"Attempting logout (blacklist refresh token)...")
            logout_response = requests.post(logout_url, data=logout_data)
            
            if logout_response.status_code == 200:
                 print("Logout successful (token blacklisted).")
                 
                 # Verify that refresh token is indeed invalid
                 print("Verifying refresh token is invalid...")
                 # Try to refresh again with the blacklisted token
                 invalid_refresh_response = requests.post(refresh_url, data={'refresh': refresh_token_to_logout})
                 if invalid_refresh_response.status_code == 401:
                     print("Verification successful: Refresh token is invalid/blacklisted.")
                 else:
                     print(f"Verification failed: expected 401, got {invalid_refresh_response.status_code}")
                     print(f"Response: {invalid_refresh_response.text}")
            else:
                print(f"Logout failed: {logout_response.status_code} - {logout_response.text}")

        else:
            print(f"Login failed: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("Connection error. Make sure the server is running on localhost:8000")

if __name__ == '__main__':
    test_login()
