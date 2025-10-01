from imagekitio import ImageKit
import os
from dotenv import load_dotenv

# Load environment variables from .env file
# Load environment variables from .env file
load_dotenv()

# --- ImageKit Initialization ---
try:
    imagekit_public_key = os.environ.get("IMAGEKIT_PUBLIC_KEY")
    imagekit_private_key = os.environ.get("IMAGEKIT_PRIVATE_KEY")
    imagekit_url_endpoint = os.environ.get("IMAGEKIT_URL_ENDPOINT")
    if not all([imagekit_public_key, imagekit_private_key, imagekit_url_endpoint]):
        raise ValueError("One or more ImageKit credentials not found. Please check your .env file.")
    imagekit = ImageKit(
        public_key=imagekit_public_key,
        private_key=imagekit_private_key,
        url_endpoint=imagekit_url_endpoint
    )
    print("✅ Successfully connected to ImageKit!")
except Exception as e:
    print(f"❌ Error connecting to ImageKit: {e}")
    imagekit = None

def upload_file_to_imagekit(file_to_upload):
    """
    Uploads a file-like object to ImageKit.io and returns the public URL.
    This function is designed to be imported and used in other parts of the application.

    Args:
        file_to_upload: A file-like object with a 'filename' attribute (e.g., from request.files).

    Returns:
        The public URL of the uploaded file as a string.

    Raises:
        Exception: If the ImageKit client is not initialized.
        ValueError: If the file provided is invalid.
        Exception: If the upload process fails for any reason.
    """
    if not imagekit:
        raise Exception("ImageKit client is not initialized. Check server logs for connection errors.")

    try:
        # Make the function more robust: check for 'filename' (from Flask) or 'name' (from open()).
        original_filename = getattr(file_to_upload, 'filename', getattr(file_to_upload, 'name', None))
        if not file_to_upload or not original_filename:
            raise ValueError("Invalid file object provided for upload. It must have a 'filename' or 'name' attribute.")

        # Generate a unique filename to prevent overwrites in ImageKit
        import uuid
        _, extension = os.path.splitext(original_filename)
        unique_filename = f"listing_{uuid.uuid4()}{extension}"

        # Use the raw file stream directly, as recommended for robust uploads.
        # The `upload_file` method is specifically designed for this.
        upload_response = imagekit.upload_file(
            file=file_to_upload.stream, # Pass the binary stream, not the whole object
            file_name=unique_filename
        )

        # The response from upload_file is a dictionary-like object
        return upload_response.response_metadata.raw['url']
    except Exception as e:
        # Re-raise the exception to be handled by the calling route
        raise Exception(f"Failed to upload file to ImageKit: {str(e)}")

# --- Test Execution Block ---
if __name__ == "__main__":
    """
    This block runs only when the script is executed directly (e.g., `python helpers.py`).
    It's used here to test the upload_file_to_imagekit function in isolation.
    """
    print("\n--- Running Standalone Upload Test ---")
    test_image_path = "test_image.jpg"
    if os.path.exists(test_image_path):
        with open(test_image_path, "rb") as test_file:
            print(f"Attempting to upload '{test_image_path}'...")
            try:
                uploaded_url = upload_file_to_imagekit(test_file)
                print("✅ Success! File uploaded.")
                print(f"   Public URL: {uploaded_url}")
            except Exception as e:
                print(f"❌ Upload test failed: {e}")
    else:
        print(f"❌ Test file not found: '{test_image_path}'. Place it in the root directory to test.")