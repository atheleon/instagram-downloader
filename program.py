import instaloader
import re
import os
import time
import random
from cryptography.fernet import Fernet

# Constants
MAX_DOWNLOADS_PER_DAY = 50  # Limit the number of downloads per day

download_count = 0
proxies = []  # To store proxies from the proxies.txt file

# Load proxies from the proxies.txt file
def load_proxies():
    global proxies
    try:
        with open('proxies.txt', 'r') as file:
            proxies = [line.strip() for line in file if line.strip()]
        if not proxies:
            print("No proxies found in proxies.txt. Please add proxies to continue.")
            return False
        print(f"Loaded {len(proxies)} proxies.")
        return True
    except FileNotFoundError:
        print("Error: proxies.txt file not found.")
        return False

# Function to encrypt and store credentials
def encrypt_and_store_credentials():
    # Generate a key for encryption
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)

    # Initialize cipher suite
    cipher_suite = Fernet(key)

    # Get username and password from user input
    username = input("Enter your Instagram username: ").strip()
    password = input("Enter your Instagram password: ").strip()

    # Encrypt the credentials
    encrypted_user = cipher_suite.encrypt(username.encode())
    encrypted_pass = cipher_suite.encrypt(password.encode())

    # Save encrypted credentials to a file
    with open("encrypted_credentials.txt", "wb") as file:
        file.write(encrypted_user + b"\n" + encrypted_pass)

    print("Credentials encrypted and saved successfully.")

# Load and decrypt credentials from an encrypted file
def load_credentials():
    try:
        # Load the encryption key
        with open("secret.key", "rb") as key_file:
            key = key_file.read()

        cipher_suite = Fernet(key)

        # Load and decrypt the credentials
        with open("encrypted_credentials.txt", "rb") as file:
            encrypted_user, encrypted_pass = file.read().splitlines()

        username = cipher_suite.decrypt(encrypted_user).decode()
        password = cipher_suite.decrypt(encrypted_pass).decode()

        return username, password

    except FileNotFoundError:
        print("Error: Credential files not found.")
        return None, None

# Set up a new proxy
def set_new_proxy(loader):
    global proxies
    if not proxies:
        print("No proxies available to use.")
        return False
    proxy = random.choice(proxies)
    try:
        loader.context._session.proxies = {
            'http': proxy,
            'https': proxy
        }
        print(f"Using proxy: {proxy}")
        return True
    except Exception as e:
        print(f"Error setting proxy: {e}")
        return False

# Login to Instagram and manage sessions
def login_to_instagram(loader):
    # Attempt to load an existing session
    try:
        loader.load_session_from_file("session")
        print("Session loaded successfully.")
        return True
    except FileNotFoundError:
        print("No session found, proceeding to login with credentials.")

    # Load credentials for login
    username, password = load_credentials()
    if not username or not password:
        print("Error: Unable to load credentials. Exiting.")
        return False

    try:
        loader.login(username, password)
        loader.save_session_to_file("session")
        print("Login successful. Session saved for future use.")
        return True
    except instaloader.exceptions.BadCredentialsException:
        print("Error: Invalid credentials. Login failed.")
    except instaloader.exceptions.ConnectionException:
        print("Error: Unable to connect to Instagram.")
    except Exception as e:
        print(f"An unexpected error occurred during login: {e}")

    return False

# Create directories for organizing downloads
def create_user_directory_structure(base_dir, username):
    user_directory = os.path.join(base_dir, username)
    subdirectories = ['profile_pictures', 'reels', 'stories', 'posts']
    
    try:
        os.makedirs(user_directory, exist_ok=True)
        for sub in subdirectories:
            os.makedirs(os.path.join(user_directory, sub), exist_ok=True)
        return user_directory
    except Exception as e:
        print(f"Error creating directories: {e}")
        return None

def handle_rate_limit(loader, account_username):
    print(f"Rate limit detected for account: {account_username}.")
    # Handle account-specific rate limits (e.g., switching accounts or pausing activity)
    # For now, just stop the script to avoid further issues
    print("Account is rate-limited. Please wait before trying again.")
    exit()  # Exit script to avoid further issues with the account

def download_instagram_content(url, account_username):
    global download_count

    # Initialize Instaloader with a custom user-agent
    loader = instaloader.Instaloader(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    # Set initial proxy
    if not set_new_proxy(loader):
        print("Failed to set initial proxy.")
        return

    # Always log in to avoid 401 Unauthorized errors
    if not login_to_instagram(loader):
        return

    base_directory = os.getcwd()  # Use the current working directory
    username = None
    original_directory = os.getcwd()  # Save the original directory

    attempt_count = 0
    max_attempts = len(proxies)  # Number of available proxies

    while attempt_count < max_attempts:
        try:
            # Introduce a random delay to mimic human-like behavior
            time.sleep(random.randint(60, 120))

            # Check URL type and determine the username
            if "instagram.com/p/" in url or "instagram.com/reel/" in url:
                shortcode = re.search(r'instagram\.com/(p|reel)/([A-Za-z0-9-_]+)', url)
                if shortcode:
                    post_shortcode = shortcode.group(2)
                    post = instaloader.Post.from_shortcode(loader.context, post_shortcode)
                    username = post.owner_username
                    user_directory = create_user_directory_structure(base_directory, username)
                    if user_directory:
                        target_directory = os.path.join(user_directory, 'posts')
                        loader.download_post(post, target=target_directory)
                        print(f"Downloaded post/reel to {target_directory}")
                        return  # Exit after a successful download

            elif "instagram.com/stories/" in url:
                username_match = re.search(r'instagram\.com/stories/([^/]+)/', url)
                if username_match:
                    username = username_match.group(1)
                    user_directory = create_user_directory_structure(base_directory, username)
                    if user_directory:
                        target_directory = os.path.join(user_directory, 'stories')
                        loader.download_stories([username], fast_update=True, filename_target=target_directory)
                        print(f"Downloaded stories for {username} to {target_directory}")
                        return  # Exit after a successful download

            elif "instagram.com/" in url:
                profile_name_match = re.search(r'instagram\.com/([^/?]+)', url)
                if profile_name_match:
                    username = profile_name_match.group(1)
                    user_directory = create_user_directory_structure(base_directory, username)
                    if user_directory:
                        target_directory = os.path.join(user_directory, 'profile_pictures')
                        os.chdir(target_directory)  # Change to the target directory
                        loader.download_profile(username, profile_pic_only=True)
                        os.chdir(original_directory)  # Change back to the original directory
                        print(f"Downloaded profile picture to {target_directory}")
                        return  # Exit after a successful download

            else:
                print("Error: Invalid Instagram URL. Unable to detect content type.")
                return

        except instaloader.exceptions.QueryReturnedBadRequestException as e:
            print("Error: Instagram returned a bad request.")
            if "feedback_required" in str(e):
                handle_rate_limit(loader, account_username)
            else:
                print("Unknown bad request error.")
                break

        except instaloader.exceptions.ConnectionException:
            print(f"Connection error with proxy. Attempting to switch proxies...")
            attempt_count += 1
            if not set_new_proxy(loader):
                print("Failed to switch to a new proxy.")
                break

        except instaloader.exceptions.InstaloaderException as e:
            if "feedback_required" in str(e):
                handle_rate_limit(loader, account_username)
            else:
                print(f"An error occurred while downloading: {e}")
                break

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break

    print("All proxies attempted and failed. Please check your network or account status.")


if __name__ == "__main__":
    # Load proxies from the proxies.txt file
    if not load_proxies():
        exit()

    # Check if encrypted credentials exist; if not, prompt for credentials and encrypt them
    if not os.path.exists("encrypted_credentials.txt"):
        print("No encrypted credentials found. Setting up credentials.")
        encrypt_and_store_credentials()

    # Load the username from the encrypted credentials
    account_username, _ = load_credentials()

    url_input = input("Enter the Instagram URL: ")
    download_instagram_content(url_input, account_username)

