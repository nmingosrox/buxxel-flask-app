from flask import Flask, render_template, request, jsonify
import os
from supabase import create_client, Client
from imagekitio import ImageKit
from gotrue.errors import AuthApiError
# The UploadFileOptions class is not needed for this version of the library
from dotenv import load_dotenv
import uuid # Used for generating unique filenames

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)

# --- Supabase Integration ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Supabase URL and Key must be set in the .env file.")

supabase: Client = create_client(url, key)

# --- ImageKit Integration ---
ik_public_key = os.environ.get("IMAGEKIT_PUBLIC_KEY")
ik_private_key = os.environ.get("IMAGEKIT_PRIVATE_KEY")
ik_url_endpoint = os.environ.get("IMAGEKIT_URL_ENDPOINT")

if not all([ik_public_key, ik_private_key, ik_url_endpoint]):
    raise ValueError("IMAGEKIT_PUBLIC_KEY, IMAGEKIT_PRIVATE_KEY, and IMAGEKIT_URL_ENDPOINT must be set in the .env file.")

imagekit = ImageKit(
    public_key=ik_public_key,
    private_key=ik_private_key,
    url_endpoint=ik_url_endpoint
)

# --------------------------

# --- Custom Decorators ---
def auth_required(f):
    from functools import wraps
    """A decorator to protect routes with JWT authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header is missing or invalid."}), 401
        
        jwt = auth_header.split(' ')[1]
        try:
            user_response = supabase.auth.get_user(jwt)
            user = user_response.user
            if not user:
                return jsonify({"error": "Invalid or expired token."}), 401
        except AuthApiError as e:
            return jsonify({"error": f"Authentication error: {e.message}"}), 401
        except Exception:
            # Catch other potential exceptions during token validation
            return jsonify({"error": "Could not validate user token."}), 401

        # Pass the user object to the decorated function
        # This is stored in g (a request-specific global context) but passing as an arg is also common
        # For simplicity here, we'll pass it as the first argument.
        return f(user, *args, **kwargs)
    return decorated_function
# -------------------------

@app.route('/')
def home():
    """Renders the home page by fetching listings from Supabase."""
    try:
        # Fetch data from the 'listings' table, ordered by id
        print("Attempting to fetch listings from Supabase...")
        response = supabase.table('listings').select("*").order('id').execute()
        listings = response.data
        print(f"✅ Successfully fetched {len(listings)} listings.")
        return render_template('index.html', listings=listings)
    except Exception as e:
        print(f"❌ Failed to connect to Supabase or fetch listings: {e}")
        print("   Please check your .env file and Supabase table permissions.")
        # Render the page with an empty list so it doesn't crash
        return render_template('index.html', listings=[])

@app.route('/new-listing')
def new_listing_page():
    """Renders the page for creating a new listing."""
    return render_template('create_listing.html')

@app.route('/dashboard')
def dashboard_page():
    """Renders the user's dashboard page."""
    return render_template('dashboard.html')

@app.route('/edit-listing/<int:listing_id>')
def edit_listing_page(listing_id):
    """Renders the page for editing a specific listing."""
    return render_template('edit_listing.html', listing_id=listing_id)

def upload_file_to_imagekit(file_to_upload):
    """
    Helper function to upload a file to ImageKit.io.
    This is much simpler as it uses the backend's private API key.
    """
    try:
        if not file_to_upload or not file_to_upload.filename:
            raise ValueError("Invalid file provided for upload.")

        # Extract the original file extension (e.g., '.jpg', '.png')
        _, extension = os.path.splitext(file_to_upload.filename)
        # Generate a unique file name while preserving the extension
        unique_filename = f"listing_{uuid.uuid4()}{extension}"

        upload_response = imagekit.upload(
            file=file_to_upload, # Pass the file-like object directly
            file_name=unique_filename,
            # For imagekitio==4.2.0, options are passed as a dictionary.
            # 'use_unique_file_name' must be False to use our 'file_name'.
            # options={
                # "folder": "/buxxel_listings/",
                # "use_unique_file_name": False
            # }
        )
        return upload_response.url
    except Exception as e:
        raise Exception(f"Failed to upload file: {str(e)}")


@app.route('/api/listings', methods=['POST'])
@auth_required
def create_listing(user): # The user object is now passed by the decorator
    """Creates a new listing in the database. This is a protected route."""
    try:
        # Get data from multipart form instead of JSON
        form_data = request.form
        files = request.files.getlist('images') # 'images' is the name of our file input

        if not all([form_data.get('name'), form_data.get('price'), form_data.get('category'), form_data.get('description'), form_data.get('stock')]):
            return jsonify({"error": "Missing required listing data."}), 400
        
        if not (1 <= len(files) <= 4):
            return jsonify({"error": "You must upload between 1 and 4 images."}), 400
        
        # --- Improved Validation ---
        try:
            price = float(form_data.get('price'))
            stock = int(form_data.get('stock'))
            if price < 0 or stock < 0:
                return jsonify({"error": "Price and stock cannot be negative."}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Price and stock must be valid numbers."}), 400

        # Upload images to Supabase Storage and get their URLs
        image_urls = [upload_file_to_imagekit(file) for file in files]

        listing_data = {
            "name": form_data.get('name'),
            "price": price,
            "category": form_data.get('category'),
            "image_urls": image_urls, # Corrected column name to match DB schema ('image_urls')
            "description": form_data.get('description'),
            "stock": stock,
            "user_id": user.id # Associate the listing with the logged-in user
        }
        
        response = supabase.table('listings').insert(listing_data).execute()

        return jsonify(response.data[0]), 201
    except Exception as e:
        # Log the full error for debugging
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/me/listings', methods=['GET'])
@auth_required
def get_user_listings(user):
    """Fetches all listings created by the currently authenticated user."""
    try:
        response = supabase.table('listings').select("*").eq('user_id', user.id).order('id').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/listings/<int:listing_id>', methods=['GET', 'PUT', 'DELETE'])
@auth_required
def handle_listing(user, listing_id):
    """Handles fetching, updating, or deleting a single listing for the authenticated user."""
    try:
        # The user must own the listing for any operation
        # We can check this once at the beginning for all methods

        if request.method == 'GET':
            # Fetch a single listing, ensuring the user owns it.
            response = supabase.table('listings').select("*").eq('id', listing_id).eq('user_id', user.id).single().execute()
            if not response.data:
                return jsonify({"error": "Listing not found or you do not have permission to view it."}), 404
            return jsonify(response.data), 200

        if request.method == 'PUT':
            # Update a listing. RLS policy will enforce ownership.
            # Handles multipart/form-data
            form_data = request.form
            files = request.files.getlist('new_images') # 'new_images' is the name of our new file input
            existing_images = request.form.getlist('existing_images') # URLs of images to keep

            # --- Validation ---
            if not all([form_data.get('name'), form_data.get('price'), form_data.get('category'), form_data.get('description'), form_data.get('stock')]):
                return jsonify({"error": "Missing required listing data."}), 400
            
            if not (1 <= (len(files) + len(existing_images)) <= 4):
                return jsonify({"error": "You must have between 1 and 4 total images."}), 400

            try:
                price = float(form_data.get('price'))
                stock = int(form_data.get('stock'))
                if price < 0 or stock < 0:
                    return jsonify({"error": "Price and stock cannot be negative."}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "Price and stock must be valid numbers."}), 400

            # Upload new images and combine with existing ones
            new_image_urls = [upload_file_to_imagekit(file) for file in files]
            all_image_urls = existing_images + new_image_urls

            update_data = {
                "name": form_data.get('name'),
                "price": price,
                "category": form_data.get('category'),
                "description": form_data.get('description'),
                "stock": stock,
                "image_urls": all_image_urls
            }

            response = supabase.table('listings').update(update_data).eq('id', listing_id).eq('user_id', user.id).execute()
            
            if not response.data:
                 return jsonify({"error": "Update failed. Listing not found or you do not have permission."}), 404
            return jsonify(response.data[0]), 200

        if request.method == 'DELETE':
            # Delete a listing. RLS policy will enforce ownership.
            response = supabase.table('listings').delete().eq('id', listing_id).eq('user_id', user.id).execute()
            if not response.data:
                return jsonify({"error": "Delete failed. Listing not found or you do not have permission."}), 404
            return jsonify({"message": "Listing deleted successfully."}), 200

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)