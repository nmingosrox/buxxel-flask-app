import pytest
from unittest.mock import patch, MagicMock, ANY
import os

# Set environment variables for testing before importing the app
os.environ['SUPABASE_URL'] = 'http://test.supabase.co'
os.environ['SUPABASE_KEY'] = 'test_key'
os.environ['UPLOADCARE_PUBLIC_KEY'] = 'test_uc_public'

# It's important to import the app *after* the environment variables are set
from app import app

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_supabase():
    """Fixture to mock the entire Supabase client."""
    with patch('app.supabase', autospec=True) as mock_sb:
        yield mock_sb

def test_home_success(client, mock_supabase):
    """Test the home page successfully fetches and displays listings."""
    # Arrange
    mock_data = [{'id': 1, 'name': 'Test Listing'}]
    mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value.data = mock_data

    # Act
    response = client.get('/')

    # Assert
    assert response.status_code == 200
    assert b'Test Listing' in response.data
    mock_supabase.table.assert_called_with('listings')
    mock_supabase.table().select.assert_called_with('*')

def test_home_supabase_error(client, mock_supabase):
    """Test the home page handles a Supabase connection error gracefully."""
    # Arrange
    mock_supabase.table.return_value.select.return_value.order.return_value.execute.side_effect = Exception("Connection failed")

    # Act
    response = client.get('/')

    # Assert
    assert response.status_code == 200
    assert b'Test Listing' not in response.data # The page should render but be empty

def test_simple_pages(client):
    """Test that simple template-rendering pages load correctly."""
    pages = ['/new-listing', '/dashboard']
    for page in pages:
        response = client.get(page)
        assert response.status_code == 200, f"Failed to load page: {page}"

class TestCreateListing:
    """Tests for the POST /api/listings endpoint."""

    @pytest.fixture
    def mock_user(self):
        """Mock user object returned from supabase.auth.get_user()."""
        user = MagicMock()
        user.id = 'user-uuid-123'
        user_response = MagicMock()
        user_response.user = user
        return user_response

    def test_create_listing_success(self, client, mock_supabase, mock_user):
        """Test successful creation of a new listing."""
        # Arrange
        mock_supabase.auth.get_user.return_value = mock_user
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{'id': 1, 'name': 'New Gadget'}]

        headers = {'Authorization': 'Bearer fake-jwt'}
        form_data = {
            'name': 'New Gadget',
            'price': '99.99',
            'category': 'Electronics',
            'description': 'A cool new gadget.',
            'stock': '10',
            'image_url': 'https://ucarecdn.com/some-uuid/image.jpg'
        }

        # Act
        response = client.post(
            '/api/listings',
            headers=headers,
            data=form_data
        )

        # Assert
        assert response.status_code == 201
        assert response.json['name'] == 'New Gadget'
        mock_supabase.auth.get_user.assert_called_with('fake-jwt')
        mock_supabase.table('listings').insert.assert_called_once()

    def test_create_listing_no_auth(self, client):
        """Test create listing fails without an authorization header."""
        response = client.post('/api/listings', data={})
        assert response.status_code == 401
        assert "Authorization header is missing" in response.json['error']

    def test_create_listing_invalid_token(self, client, mock_supabase):
        """Test create listing fails with an invalid or expired token."""
        # Arrange
        mock_supabase.auth.get_user.return_value.user = None
        headers = {'Authorization': 'Bearer invalid-jwt'}

        # Act
        response = client.post('/api/listings', headers=headers, data={})

        # Assert
        assert response.status_code == 401
        assert "Invalid or expired token" in response.json['error']

    def test_create_listing_missing_data(self, client, mock_supabase, mock_user):
        """Test create listing fails with missing form data."""
        mock_supabase.auth.get_user.return_value = mock_user
        headers = {'Authorization': 'Bearer fake-jwt'}
        response = client.post('/api/listings', headers=headers, data={'name': 'Incomplete'})
        assert response.status_code == 400
        assert "Missing required listing data" in response.json['error']

class TestGetUserListings:
    """Tests for the GET /api/me/listings endpoint."""

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = 'user-uuid-123'
        user_response = MagicMock()
        user_response.user = user
        return user_response

    def test_get_user_listings_success(self, client, mock_supabase, mock_user):
        """Test successfully fetching listings for the authenticated user."""
        # Arrange
        mock_supabase.auth.get_user.return_value = mock_user
        mock_data = [{'id': 1, 'name': 'My Listing', 'user_id': 'user-uuid-123'}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = mock_data
        headers = {'Authorization': 'Bearer fake-jwt'}

        # Act
        response = client.get('/api/me/listings', headers=headers)

        # Assert
        assert response.status_code == 200
        assert len(response.json) == 1
        assert response.json[0]['name'] == 'My Listing'
        mock_supabase.table('listings').select('*').eq.assert_called_with('user_id', 'user-uuid-123')

    def test_get_user_listings_no_auth(self, client):
        """Test endpoint fails without an auth header."""
        response = client.get('/api/me/listings')
        assert response.status_code == 401

    def test_get_user_listings_invalid_token(self, client, mock_supabase):
        """Test endpoint fails with an invalid token."""
        mock_supabase.auth.get_user.return_value.user = None
        headers = {'Authorization': 'Bearer invalid-jwt'}
        response = client.get('/api/me/listings', headers=headers)
        assert response.status_code == 401

class TestHandleListing:
    """Tests for the /api/listings/<id> endpoint (GET, PUT, DELETE)."""

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = 'user-uuid-123'
        user_response = MagicMock()
        user_response.user = user
        return user_response

    @pytest.fixture
    def auth_headers(self):
        return {'Authorization': 'Bearer fake-jwt'}

    # --- GET ---
    def test_get_single_listing_success(self, client, mock_supabase, mock_user, auth_headers):
        """Test GET /api/listings/<id> success."""
        # Arrange
        mock_supabase.auth.get_user.return_value = mock_user
        mock_data = {'id': 1, 'name': 'My Listing', 'user_id': 'user-uuid-123'}
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_data

        # Act
        response = client.get('/api/listings/1', headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.json['name'] == 'My Listing'
        mock_supabase.table('listings').select('*').eq('id', 1).eq('user_id', 'user-uuid-123').single().execute.assert_called_once()

    def test_get_single_listing_not_found(self, client, mock_supabase, mock_user, auth_headers):
        """Test GET /api/listings/<id> when listing is not found or not owned."""
        mock_supabase.auth.get_user.return_value = mock_user
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = None

        response = client.get('/api/listings/99', headers=auth_headers)

        assert response.status_code == 404
        assert "Listing not found" in response.json['error']

    # --- PUT ---
    def test_update_listing_success(self, client, mock_supabase, mock_user, auth_headers):
        """Test PUT /api/listings/<id> success."""
        # Arrange
        mock_supabase.auth.get_user.return_value = mock_user
        update_payload = {
            'name': 'Updated Name',
            'price': '150.0',
            'category': 'Electronics',
            'description': 'Updated desc.',
            'stock': '5',
            'image_url': 'http://example.com/new_image.jpg'
        }
        mock_return_data = [{'id': 1, 'name': 'Updated Name', 'price': 150.0}]
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = mock_return_data

        # Act
        response = client.put(
            '/api/listings/1',
            headers=auth_headers,
            data=update_payload
        )

        # Assert
        assert response.status_code == 200
        assert response.json['name'] == 'Updated Name'
        # Check that the update call was made with the correct data structure
        update_call_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert update_call_args['name'] == 'Updated Name'
        assert update_call_args['price'] == 150.0

    def test_update_listing_not_found(self, client, mock_supabase, mock_user, auth_headers):
        """Test PUT /api/listings/<id> when listing is not found or not owned."""
        mock_supabase.auth.get_user.return_value = mock_user
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = None

        response = client.put(
            '/api/listings/99',
            headers=auth_headers,
            data={'name': 'new name', 'price': '1', 'stock': '1', 'category': 'c', 'description': 'd', 'image_url': 'url'}
        )

        assert response.status_code == 404
        assert "Update failed" in response.json['error']

    def test_update_listing_no_data(self, client, mock_supabase, mock_user, auth_headers):
        """Test PUT /api/listings/<id> with no update data."""
        mock_supabase.auth.get_user.return_value = mock_user

        response = client.put(
            '/api/listings/1', headers=auth_headers
        )

        assert response.status_code == 400
        assert "Missing required listing data" in response.json['error']

    # --- DELETE ---
    def test_delete_listing_success(self, client, mock_supabase, mock_user, auth_headers):
        """Test DELETE /api/listings/<id> success."""
        # Arrange
        mock_supabase.auth.get_user.return_value = mock_user
        # Successful delete in supabase-py returns a list with the deleted data
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{'id': 1}]

        # Act
        response = client.delete('/api/listings/1', headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert "Listing deleted successfully" in response.json['message']
        mock_supabase.table('listings').delete().eq('id', 1).eq('user_id', 'user-uuid-123').execute.assert_called_once()

    def test_delete_listing_not_found(self, client, mock_supabase, mock_user, auth_headers):
        """Test DELETE /api/listings/<id> when listing is not found or not owned."""
        mock_supabase.auth.get_user.return_value = mock_user
        # Failed delete in supabase-py returns an empty list
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        response = client.delete('/api/listings/99', headers=auth_headers)

        assert response.status_code == 404
        assert "Delete failed" in response.json['error']

    def test_handle_listing_invalid_token(self, client, mock_supabase, auth_headers):
        """Test all methods on /api/listings/<id> fail with an invalid token."""
        mock_supabase.auth.get_user.return_value.user = None

        get_response = client.get('/api/listings/1', headers=auth_headers)
        put_response = client.put('/api/listings/1', headers=auth_headers, data={'name': 'test'})
        delete_response = client.delete('/api/listings/1', headers=auth_headers)

        assert get_response.status_code == 401
        assert put_response.status_code == 401
        assert delete_response.status_code == 401
        assert "Invalid or expired token" in get_response.json['error']