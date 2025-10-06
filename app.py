from flask import Flask, render_template, request, jsonify
import os
from supabase import create_client, Client
from functools import wraps
from gotrue.errors import AuthApiError
from dotenv import load_dotenv


load_dotenv() # Load environment variables from .env file

app = Flask(__name__)

# --- Supabase Integration ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Supabase URL and Key must be set in the .env file.")

supabase: Client = create_client(url, key)

# --- Uploadcare Integration ---
UPLOADCARE_PUBLIC_KEY = os.environ.get("UPLOADCARE_PUBLIC_KEY")

if not UPLOADCARE_PUBLIC_KEY:
    raise ValueError("UPLOADCARE_PUBLIC_KEY must be set in the .env file.")

# --------------------------

# --- Custom Decorators ---
def auth_required(f):
    """
    A decorator to protect routes with JWT authentication.
    It expects a 'Bearer <token>' in the 'Authorization' header,
    validates the token with Supabase, and passes the resulting user object to the decorated function.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authorization header is missing."}), 401
        
        parts = auth_header.split()

        if parts[0].lower() != 'bearer':
            return jsonify({"error": "Authorization header must start with 'Bearer'."}), 401
        elif len(parts) == 1:
            return jsonify({"error": "Token not found after 'Bearer' scheme."}), 401
        elif len(parts) > 2:
            return jsonify({"error": "Authorization header must be 'Bearer <token>'."}), 401

        jwt = parts[1]
        try:
            user_response = supabase.auth.get_user(jwt)
            user = user_response.user
            if not user:
                # This case is hit if the token is validly structured but not recognized by Supabase (e.g., expired, invalid signature)
                return jsonify({"error": "Invalid or expired token."}), 401
        except AuthApiError as e:
            return jsonify({"error": f"Authentication error: {e.message}"}), 401
        except Exception as e:
            # Log the unexpected error for server-side debugging
            app.logger.error(f"Unexpected error during token validation: {e}")
            return jsonify({"error": "An unexpected error occurred during authentication."}), 500

        # Pass the user object to the decorated function
        # as the first argument.
        return f(user, *args, **kwargs)
    return decorated_function
# -------------------------

# --- Template Context Processor ---
@app.context_processor
def inject_uploadcare_key():
    """Injects the Uploadcare public key into all templates."""
    return dict(uploadcare_public_key=UPLOADCARE_PUBLIC_KEY)

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
    return render_template('create_listing.html', uploadcare_public_key=UPLOADCARE_PUBLIC_KEY)

@app.route('/dashboard')
def dashboard_page():
    """Renders the user's dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/listings', methods=['POST'])
@auth_required
def create_listing(user): # The user object is now passed by the decorator
    """Creates a new listing in the database. This is a protected route."""
    try:
        # Get data from the form
        data = request.form
        image_url = data.get('image_url')

        if not all([data.get('name'), data.get('price'), data.get('category'), data.get('description'), data.get('stock')]):
            return jsonify({"error": "Missing required listing data."}), 400
        
        if not image_url:
            return jsonify({"error": "An image is required for the listing."}), 400
        
        # --- Improved Validation ---
        try:
            price = float(data.get('price'))
            stock = int(data.get('stock'))
            if price < 0 or stock < 0:
                return jsonify({"error": "Price and stock cannot be negative."}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Price and stock must be valid numbers."}), 400

        listing_data = {
            "name": data.get('name'),
            "price": price,
            "category": data.get('category'),
            "image_urls": [image_url], # Store the single URL in an array to match the DB schema
            "description": data.get('description'),
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

@app.route('/api/listings/<listing_id>', methods=['GET', 'PUT', 'DELETE'])
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
            data = request.form
            image_url = data.get('image_url')

            # --- Validation ---
            if not all([data.get('name'), data.get('price'), data.get('category'), data.get('description'), data.get('stock')]):
                return jsonify({"error": "Missing required listing data."}), 400
            
            if not image_url:
                return jsonify({"error": "A listing image is required."}), 400

            try:
                price = float(data.get('price'))
                stock = int(data.get('stock'))
                if price < 0 or stock < 0:
                    return jsonify({"error": "Price and stock cannot be negative."}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "Price and stock must be valid numbers."}), 400

            update_data = {
                "name": data.get('name'),
                "price": price,
                "category": data.get('category'),
                "description": data.get('description'),
                "stock": stock,
                "image_urls": [image_url] # Store as an array
            }

            response = supabase.table('listings').update(update_data).eq('id', listing_id).eq('user_id', user.id).execute()
            
            if not response.data:
                 return jsonify({"error": "Update failed. Listing not found or you do not have permission."}), 404
            return jsonify(response.data[0]), 200

        if request.method == 'DELETE':
            # Delete a listing. RLS policy will enforce ownership.
            print(f"Attempting to delete listing {listing_id} for user {user.id}...")
            response = supabase.table('listings').delete().eq('id', listing_id).eq('user_id', user.id).execute()
            
            # --- DEBUG LOGGING ---
            print(f"Supabase delete response: {response}")

            if not response.data:
                return jsonify({"error": "Delete failed. Listing not found or you do not have permission."}), 404
            return jsonify({"message": "Listing deleted successfully."}), 200

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)