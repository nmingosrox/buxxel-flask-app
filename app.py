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
    # --- Pagination Logic ---
    page = request.args.get('page', 1, type=int)
    per_page = 12 # Show 12 listings per page
    start_index = (page - 1) * per_page
    end_index = start_index + per_page - 1

    try:
        # Fetch a paginated set of data from the 'listings' table
        print("Attempting to fetch listings from Supabase...")
        # We also fetch a count to determine total pages
        response = supabase.table('listings').select("*", count='exact').order('id').range(start_index, end_index).execute()
        listings = response.data
        total_listings = response.count

        # Calculate pagination details
        has_next = end_index < total_listings - 1
        has_prev = page > 1
        
        print(f"✅ Successfully fetched {len(listings)} listings for page {page}.")
        return render_template('index.html', listings=listings, 
                               page=page, has_next=has_next, has_prev=has_prev)

    except Exception as e:
        print(f"❌ Failed to connect to Supabase or fetch listings: {e}")
        print("   Please check your .env file and Supabase table permissions.")
        # Render the page with an empty list so it doesn't crash
        return render_template('index.html', listings=[], page=1, has_next=False, has_prev=False)

@app.route('/new-listing')
def new_listing_page():
    """Renders the page for creating a new listing."""
    return render_template('create_listing.html', uploadcare_public_key=UPLOADCARE_PUBLIC_KEY)

@app.route('/dashboard')
def dashboard_page():
    """Renders the user's dashboard page."""
    return render_template('dashboard.html')

@app.route('/reset-password')
def reset_password_page():
    """Renders the page where users can set a new password."""
    return render_template('reset_password.html')

@app.route('/profile/<user_id>')
def profile_page(user_id):
    """Renders a public profile page for a given user, showing their active listings."""
    purveyor_username = "Unknown Purveyor"
    try:
        # Fetch the public username from the 'profiles' table
        profile_response = supabase.table('profiles').select("username").eq('id', user_id).single().execute()
        
        if profile_response.data and profile_response.data.get('username'):
            purveyor_username = profile_response.data['username']
        else:
            # Fallback to a generic name if no username is set
            purveyor_username = f"Purveyor #{user_id[:8]}"

        # Fetch all active (stock > 0) listings for this user
        listings_response = supabase.table('listings').select("*").eq('user_id', user_id).gt('stock', 0).order('created_at', desc=True).execute()
        
        listings = listings_response.data

        return render_template('profile.html', listings=listings, purveyor_username=purveyor_username)

    except Exception as e:
        app.logger.error(f"Error loading profile page for {user_id}: {e}")
        # Render a simple error state or redirect
        return render_template('profile.html', listings=[], purveyor_username="Error", error="Could not load profile.")


@app.route('/api/me/profile', methods=['GET', 'PUT'])
@auth_required
def handle_my_profile(user):
    """Handles fetching or updating the authenticated user's profile."""
    if request.method == 'GET':
        try:
            profile = supabase.table('profiles').select("username").eq('id', user.id).single().execute()
            return jsonify(profile.data or {}), 200
        except Exception as e:
            return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

    if request.method == 'PUT':
        data = request.get_json()
        username = data.get('username')
        if not username or len(username) < 3:
            return jsonify({"error": "Username must be at least 3 characters long."}), 400
        
        update_data = {"username": username, "updated_at": "now()"}
        response = supabase.table('profiles').update(update_data).eq('id', user.id).execute()
        return jsonify(response.data[0]), 200


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
            "pre_zero_stock": stock if stock > 0 else 1, # Initialize pre_zero_stock
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
    """Fetches paginated and searchable listings for the currently authenticated user."""
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('search', '', type=str)
    sort_by = request.args.get('sort_by', 'created_at', type=str)
    sort_order = request.args.get('sort_order', 'desc', type=str)
    per_page = 5 # A smaller number for the dashboard view
    start_index = (page - 1) * per_page
    end_index = start_index + per_page - 1

    try:
        # Whitelist sortable columns for security
        allowed_sort_columns = ['created_at', 'name', 'price', 'stock']
        if sort_by not in allowed_sort_columns:
            sort_by = 'created_at'
        
        is_desc = sort_order.lower() == 'desc'

        query = supabase.table('listings').select("*", count='exact').eq('user_id', user.id)

        if search_term:
            query = query.ilike('name', f'%{search_term}%')

        # Fetch total count and a slice of data, ordered by most recent first
        response = query.order(sort_by, desc=is_desc).range(start_index, end_index).execute()
        
        listings = response.data
        total_listings = response.count

        has_next = end_index < total_listings - 1

        return jsonify({
            "listings": listings,
            "pagination": {
                "page": page,
                "has_next": has_next,
                "total_listings": total_listings
            }
        }), 200
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/listings/<listing_id>/status', methods=['PUT'])
@auth_required
def handle_listing_status(user, listing_id):
    """Toggles the stock status of a listing for the authenticated user."""
    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ['in_stock', 'out_of_stock']:
        return jsonify({"error": "Invalid status provided."}), 400

    try:
        # First, get the current listing to check ownership and current stock
        listing_response = supabase.table('listings').select("stock, pre_zero_stock").eq('id', listing_id).eq('user_id', user.id).single().execute()
        
        if not listing_response.data:
            return jsonify({"error": "Listing not found or you do not have permission."}), 404

        current_listing = listing_response.data
        update_data = {}

        if new_status == 'out_of_stock':
            # Only update pre_zero_stock if current stock is not already 0
            if current_listing['stock'] > 0:
                update_data['pre_zero_stock'] = current_listing['stock']
            update_data['stock'] = 0
        
        elif new_status == 'in_stock':
            # Restore to previous stock level, or 1 if not available
            update_data['stock'] = current_listing.get('pre_zero_stock', 1) or 1

        response = supabase.table('listings').update(update_data).eq('id', listing_id).execute()

        if not response.data:
            return jsonify({"error": "Failed to update listing status."}), 500
        return jsonify(response.data[0]), 200

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